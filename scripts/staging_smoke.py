"""Bounded staging checks, without stored credentials or database access."""
from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
import time
import uuid
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

STAGING_URL = "https://studybot-staging.vercel.app"
NOTES = (
    b"Spaced repetition improves long-term memory by scheduling repeated reviews. "
    b"Active recall means retrieving information from memory without looking at notes. "
    b"Combining active recall and spaced repetition makes learning more effective. "
    b"A learner reviews a flashcard, recalls its answer, then schedules the next review."
)


class SmokeTestError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeTestError(message)


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward student credentials to a redirect destination.
        return None


class SmokeClient:
    def __init__(self, base_url: str, timeout_seconds: float = 60):
        parsed = urlsplit(base_url)
        self.local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        require(not parsed.username and not parsed.password and not parsed.query
                and not parsed.fragment and parsed.path in {"", "/"}, "Invalid base URL")
        require(base_url.rstrip("/") == STAGING_URL or
                (self.local and parsed.scheme == "http"),
                "Use the canonical staging URL or a local HTTP server")
        require(0 < timeout_seconds <= 90, "Request timeout must be between 0 and 90 seconds")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds
        self.opener = build_opener(NoRedirects())
        self.deadline: float | None = None

    def request(self, path: str, *, method: str = "GET", payload=None,
                token: str = "", expected: int = 200, body: bytes | None = None,
                content_type: str = "application/json"):
        require(path.startswith("/") and not path.startswith("//"), "Invalid request path")
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if payload is not None:
            body = json.dumps(payload).encode()
        if body is not None:
            headers["Content-Type"] = content_type
        timeout = self.timeout
        if self.deadline is not None:
            timeout = min(timeout, self.deadline - time.monotonic())
            require(timeout > 0, "Study-flow time budget exhausted")
        request = Request(self.base_url + path, method=method, data=body, headers=headers)
        try:
            response = self.opener.open(request, timeout=timeout)
        except HTTPError as exc:
            response = exc
        except (URLError, TimeoutError, OSError) as exc:
            raise SmokeTestError(f"{method} {path}: connection failed") from exc
        with response:
            require(response.code == expected,
                    f"{method} {path}: expected HTTP {expected}, received {response.code}")
            if expected >= 400 or expected == 204:
                return None
            try:
                return json.loads(response.read())
            except (ValueError, OSError) as exc:
                raise SmokeTestError(f"{method} {path}: invalid JSON response") from exc

    def upload(self, course_id: str, content: bytes, token: str, expected: int = 201):
        boundary = f"studybot-{uuid.uuid4().hex}"
        body = b"\r\n".join([
            f"--{boundary}".encode(),
            b'Content-Disposition: form-data; name="file"; filename="smoke-notes.txt"',
            b"Content-Type: text/plain", b"", content, f"--{boundary}--".encode(), b"",
        ])
        return self.request(f"/courses/{course_id}/documents/text", method="POST", token=token,
                            body=body, content_type=f"multipart/form-data; boundary={boundary}",
                            expected=expected)


def wait_for_revision(client: SmokeClient, revision: str | None, wait_seconds: float) -> None:
    require(revision is None or bool(re.fullmatch(r"[0-9a-f]{40}", revision)),
            "Expected revision must be a full lowercase Git SHA")
    require(0 <= wait_seconds <= 300, "Revision wait must be between 0 and 300 seconds")
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            health = client.request("/health")
            if health.get("status") == "ok" and (
                    revision is None or health.get("revision") == revision):
                return
        except SmokeTestError:
            pass
        require(time.monotonic() < deadline, "Staging did not serve the expected healthy revision")
        time.sleep(min(5, max(0, deadline - time.monotonic())))


@dataclass
class Student:
    email: str
    password: str
    token: str = ""
    user_id: str = ""

    def credentials(self):
        return {"email": self.email, "password": self.password}


def cleanup_students(client: SmokeClient, students: list[Student]) -> None:
    # Leave time for both students even if the main study flow used its deadline.
    client.deadline = time.monotonic() + 100
    client.timeout = min(client.timeout, 10)
    failed = []
    for student in reversed(students):
        try:
            if not student.token:
                session = client.request("/auth/login", method="POST",
                                         payload=student.credentials())
                student.token = session["access_token"]
            client.request("/auth/account", method="DELETE", token=student.token, expected=204,
                           payload={"password": student.password,
                                    "confirmation": "delete-my-account"})
            client.request("/auth/me", token=student.token, expected=401)
            client.request("/auth/login", method="POST", payload=student.credentials(),
                           expected=401)
        except (SmokeTestError, KeyError, TypeError):
            failed.append(student.email)
    require(not failed, "Temporary account cleanup failed: " + ", ".join(failed))


def check_usage(client: SmokeClient, token: str, before=None, consumed: int = 0,
                allow_fake_ai: bool = False):
    usage = client.request("/auth/ai-usage", token=token)
    require(usage["enabled"] or allow_fake_ai, "Staging must use a real AI provider")
    for window in ("minute", "day"):
        value = usage[window]
        require(value["limit"] > 0 and 0 <= value["used"] <= value["limit"]
                and value["remaining"] == value["limit"] - value["used"],
                "AI allowance is inconsistent")
        if before is not None:
            # Either adjacent bucket can own a generation crossing a UTC boundary.
            if value["resets_at"] == before[window]["resets_at"]:
                expected = before[window]["used"] + (consumed if usage["enabled"] else 0)
                require(value["used"] == expected, "AI usage accounting changed unexpectedly")
            else:
                require(value["used"] <= consumed, "AI allowance did not reset")
    return usage


def check_citations(citations, document_id: str) -> None:
    require(bool(citations) and all(c["document_id"] == document_id and c["chunk_id"]
                                   and c["text"] in NOTES.decode() for c in citations),
            "Generated work must cite the uploaded notes")


def learning_flow(client: SmokeClient, student: Student, other: Student, allow_fake_ai: bool):
    token = student.token
    course = client.request(f"/users/{student.user_id}/courses", method="POST", token=token,
                            expected=201, payload={"title": "Deployment smoke check"})
    course_id = course["id"]
    root = f"/courses/{course_id}"
    for path in (root, root + "/documents", root + "/dashboard", root + "/questions",
                 root + "/quizzes", root + "/flashcard-sets", root + "/flashcard-review"):
        client.request(path, token=other.token, expected=404)
    client.request(root, expected=401)
    storage = client.request("/auth/storage-usage", token=token)
    require(storage["documents"]["used"] == storage["text_bytes"]["used"] == 0,
            "New account has unexpected storage")
    usage = check_usage(client, token, allow_fake_ai=allow_fake_ai)
    document = client.upload(course_id, NOTES, token)
    document_id = document["id"]
    require(document["status"] == "completed" and document["chunk_count"] == 1,
            "Notes ingestion failed")
    client.request(f"/documents/{document_id}", token=other.token, expected=404)
    chunks = client.request(f"/documents/{document_id}/chunks", token=token)
    require(len(chunks) == 1, "Uploaded notes were not persisted")
    storage = client.request("/auth/storage-usage", token=token)
    require(storage["documents"]["used"] == 1
            and storage["text_bytes"]["used"] == len(NOTES), "Storage accounting failed")
    require(0 < storage["max_file_bytes"] <= 3_000_000, "Unexpected staging upload limit")
    client.upload(course_id, b"x" * (storage["max_file_bytes"] + 1), token, expected=413)
    client.request(root + "/questions", method="POST", token=token, expected=422,
                   payload={"question": "x" * 1001})
    usage = check_usage(client, token, usage, allow_fake_ai=allow_fake_ai)

    answer = client.request(root + "/questions", method="POST", token=token,
                            payload={"question": "How do spaced repetition and active recall "
                                     "help long-term memory?", "limit": 5})
    require(answer["status"] == "answered" and bool(answer["answer"]), "Answer generation failed")
    check_citations(answer["citations"], document_id)
    usage = check_usage(client, token, usage, 1, allow_fake_ai)
    quiz = client.request(root + "/quizzes", method="POST", token=token, expected=201,
                          payload={"topic": "spaced repetition and active recall",
                                   "question_count": 3, "difficulty": "easy", "limit": 5})
    require(quiz["status"] == "generated" and len(quiz["questions"]) == 3,
            "Quiz generation failed")
    for question in quiz["questions"]:
        check_citations(question["citations"], document_id)
    usage = check_usage(client, token, usage, 1, allow_fake_ai)
    cards = client.request(root + "/flashcard-sets", method="POST", token=token, expected=201,
                           payload={"topic": "spaced repetition and active recall", "card_count": 3,
                                    "difficulty": "easy", "limit": 5})
    require(cards["status"] == "generated" and len(cards["cards"]) == 3,
            "Flashcard generation failed")
    for card in cards["cards"]:
        check_citations(card["citations"], document_id)
    usage = check_usage(client, token, usage, 1, allow_fake_ai)

    # Wrong answers exercise weak-topic analytics as well as grading.
    attempt = client.request(f"/quizzes/{quiz['id']}/attempts", method="POST", token=token,
                             expected=201, payload={"answers": [
                                 {"question_id": q["id"], "selected_option_id": next(
                                     o["id"] for o in q["options"] if not o["is_correct"])}
                                 for q in quiz["questions"]]})
    require(attempt["score_percent"] == 0 and attempt["question_count"] == 3,
            "Quiz grading failed")
    queue = client.request(root + "/flashcard-review", token=token)
    require(queue["due_count"] == 3, "New flashcards should be due")
    card = queue["cards"][0]
    review = client.request(f"/flashcards/{card['id']}/reviews", method="POST", token=token,
                            payload={"rating": "good", "version": card["version"]})
    require(review["version"] == card["version"] + 1, "Review was not saved")
    queue = client.request(root + "/flashcard-review", token=token)
    require(queue["due_count"] == 2 and queue["reviewed_count"] == 1,
            "Review scheduling failed")
    dashboard = client.request(root + "/dashboard", token=token)
    require(dashboard["document_count"] == 1 and dashboard["saved_count"] == 3
            and dashboard["quiz_attempt_count"] == 1 and dashboard["review"]["due_count"] == 2
            and dashboard["recent_scores"][0]["score_percent"] == 0
            and bool(dashboard["weak_topics"])
            and {w["kind"] for w in dashboard["saved_work"]} == {"answer", "quiz", "flashcards"},
            "Dashboard did not reflect the study flow")
    for path in (f"/quizzes/{quiz['id']}", f"/flashcard-sets/{cards['id']}",
                 f"/answers/{answer['answer_id']}"):
        client.request(path, token=token)
        client.request(path, token=other.token, expected=404)
    history = client.request(root + "/questions", token=token)
    require(len(history) == 1, "Answer history was not persisted")
    client.request(f"/documents/{document_id}", method="DELETE", token=token, expected=204)
    storage = client.request("/auth/storage-usage", token=token)
    require(storage["documents"]["used"] == storage["text_bytes"]["used"] == 0,
            "Document deletion did not release storage")
    saved = client.request(f"/answers/{answer['answer_id']}", token=token)
    require(saved["answer"] == answer["answer"] and bool(saved["citations"])
            and all(c["text"] in NOTES.decode() for c in saved["citations"]),
            "Deleting notes damaged saved answer citations")
    check_usage(client, token, usage, allow_fake_ai=allow_fake_ai)


def run_smoke_test(base_url: str, timeout_seconds: float = 60, *,
                   expected_revision: str | None = None, wait_seconds: float = 0,
                   allow_fake_ai: bool = False, client: SmokeClient | None = None) -> dict:
    client = client or SmokeClient(base_url, timeout_seconds)
    require(not allow_fake_ai or client.local, "Fake AI is only allowed on local servers")
    wait_for_revision(client, expected_revision, wait_seconds)
    require(client.request("/ready").get("status") == "ready", "Database is not ready")
    capabilities = client.request("/auth/capabilities")
    require(capabilities.get("account_email_enabled") is False
            and capabilities.get("verification_required") is False,
            "Disposable-account checks require account email and verification to remain disabled")
    students: list[Student] = []
    client.deadline = time.monotonic() + 360
    run_id = uuid.uuid4().hex
    print(f"Staging smoke run: {run_id}", flush=True)
    error: Exception | None = None
    try:
        for index in range(2):
            student = Student(f"staging-smoke-{run_id}-{index}@example.com",
                              secrets.token_urlsafe(32))
            students.append(student)
            session = client.request("/auth/register", method="POST", expected=201,
                                     payload={**student.credentials(),
                                              "display_name": "Smoke student"})
            student.token = session["access_token"]
            student.user_id = session["user"]["id"]
            client.request("/auth/logout", method="POST", token=student.token, expected=204)
            revoked_token = student.token
            student.token = ""
            client.request("/auth/me", token=revoked_token, expected=401)
            session = client.request("/auth/login", method="POST", payload=student.credentials())
            student.token = session["access_token"]
            require(client.request("/auth/me", token=student.token)["id"] == student.user_id,
                    "Password login returned the wrong student")
        learning_flow(client, students[0], students[1], allow_fake_ai)
        wait_for_revision(client, expected_revision, 0)
    except Exception as exc:
        error = exc
    finally:
        try:
            cleanup_students(client, students)
        except SmokeTestError as cleanup_error:
            reason = str(error) if isinstance(error, SmokeTestError) else "Study flow failed"
            if error is None:
                reason = "Study flow passed"
            raise SmokeTestError(f"{reason}; {cleanup_error}") from None
    if error:
        if isinstance(error, SmokeTestError):
            raise error
        raise SmokeTestError(
            "Unexpected study-flow response; temporary accounts were removed") from None
    return {"run_id": run_id, "study_flow": "passed", "accounts_removed": len(students),
            "generation_requests": 3, "revision": expected_revision}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=STAGING_URL)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--expected-revision")
    parser.add_argument("--wait-seconds", type=float, default=0)
    parser.add_argument("--allow-fake-ai", action="store_true", help="Local development only")
    args = parser.parse_args()
    try:
        result = run_smoke_test(args.base_url, args.timeout,
                                expected_revision=args.expected_revision,
                                wait_seconds=args.wait_seconds, allow_fake_ai=args.allow_fake_ai)
    except SmokeTestError as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        return 1
    print("SMOKE PASSED")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
