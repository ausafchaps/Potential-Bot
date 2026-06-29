from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class SmokeResult:
    user_id: str
    course_id: str
    document_id: str
    answer_id: str
    citation_count: int


class SmokeTestError(RuntimeError):
    pass


def request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 30,
) -> dict[str, Any]:
    body = None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = Request(
        urljoin(base_url, path),
        data=body,
        headers=request_headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw_body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SmokeTestError(f"{method} {path} failed with {exc.code}: {detail}") from exc
    except URLError as exc:
        raise SmokeTestError(f"{method} {path} failed: {exc.reason}") from exc

    if not raw_body:
        return {}
    return json.loads(raw_body)


def upload_text_document(base_url: str, course_id: str, timeout_seconds: float) -> dict[str, Any]:
    boundary = f"----studybot-smoke-{uuid.uuid4().hex}"
    content = (
        b"Spaced repetition schedules reviews just before memory fades. "
        b"Grounded study assistants should cite source notes, preserve course context, "
        b"and turn weak topics into focused quizzes and flashcards."
    )
    body = b"\r\n".join(
        [
            f"--{boundary}".encode("ascii"),
            (
                b'Content-Disposition: form-data; name="file"; '
                b'filename="staging-smoke-notes.txt"'
            ),
            b"Content-Type: text/plain",
            b"",
            content,
            f"--{boundary}--".encode("ascii"),
            b"",
        ]
    )
    request = Request(
        urljoin(base_url, f"/courses/{course_id}/documents/text"),
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SmokeTestError(f"POST document upload failed with {exc.code}: {detail}") from exc
    except URLError as exc:
        raise SmokeTestError(f"POST document upload failed: {exc.reason}") from exc


def run_smoke_test(base_url: str, timeout_seconds: float) -> SmokeResult:
    health = request_json(base_url, "/health", timeout_seconds=timeout_seconds)
    if health.get("status") != "ok":
        raise SmokeTestError(f"/health returned unexpected payload: {health}")

    readiness = request_json(base_url, "/ready", timeout_seconds=timeout_seconds)
    if readiness.get("status") != "ready":
        raise SmokeTestError(f"/ready returned unexpected payload: {readiness}")

    unique_id = uuid.uuid4().hex
    user = request_json(
        base_url,
        "/users",
        method="POST",
        payload={
            "email": f"staging-smoke-{unique_id}@example.com",
            "display_name": "Staging Smoke Student",
        },
        timeout_seconds=timeout_seconds,
    )
    user_id = user["id"]

    course = request_json(
        base_url,
        f"/users/{user_id}/courses",
        method="POST",
        payload={
            "title": "Staging Smoke Course",
            "description": "Created by the StudyBot staging smoke test.",
        },
        timeout_seconds=timeout_seconds,
    )
    course_id = course["id"]

    document = upload_text_document(base_url, course_id, timeout_seconds)
    if document.get("status") != "completed" or document.get("chunk_count", 0) < 1:
        raise SmokeTestError(f"Document ingestion returned unexpected payload: {document}")

    answer = request_json(
        base_url,
        f"/courses/{course_id}/questions",
        method="POST",
        payload={"question": "What does spaced repetition help with?", "limit": 5},
        timeout_seconds=timeout_seconds,
    )
    if answer.get("status") != "answered":
        raise SmokeTestError(f"Question returned unexpected payload: {answer}")
    if len(answer.get("citations", [])) < 1:
        raise SmokeTestError(f"Question returned no citations: {answer}")

    persisted_course = request_json(
        base_url,
        f"/courses/{course_id}",
        timeout_seconds=timeout_seconds,
    )
    if persisted_course.get("id") != course_id:
        raise SmokeTestError(f"Course persistence check failed: {persisted_course}")

    return SmokeResult(
        user_id=user_id,
        course_id=course_id,
        document_id=document["id"],
        answer_id=answer["answer_id"],
        citation_count=len(answer["citations"]),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run StudyBot staging API smoke checks.")
    parser.add_argument(
        "--base-url",
        required=True,
        help="Deployed StudyBot API base URL, for example https://studybot-api-staging.onrender.com",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Request timeout in seconds.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/") + "/"

    try:
        result = run_smoke_test(base_url, args.timeout)
    except SmokeTestError as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        return 1

    print("SMOKE PASSED")
    print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
