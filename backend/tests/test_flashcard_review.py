import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from app.main import app
from app.models import AIUsageBucket, Course, FlashcardProgress
from app.schemas.flashcard_review import FlashcardReviewCreate, ReviewRating
from app.services import flashcard_review as reviews
from app.services.flashcard_review import ReviewConflict, next_interval, review_flashcard
from auth_helpers import TEST_PASSWORD
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from test_flashcard_generation_api import build_client, create_course, upload_text


@pytest.fixture
def cards(monkeypatch):
    monkeypatch.setattr(reviews.time, "time", lambda: 172800)
    client = build_client()
    course = create_course(client)
    upload_text(client, course, b"Binary search halves sorted arrays to find values.")
    result = client.post(f"/courses/{course}/flashcard-sets",
                         json={"topic": "binary search", "card_count": 3}).json()
    try:
        yield client, course, result["cards"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(("rating", "minutes"), [
    ("again", 10), ("hard", 1440), ("good", 4320), ("easy", 10080),
])
def test_ratings_persist_and_leave_due_queue(cards, rating, minutes):
    client, course, generated = cards
    before = client.get(f"/courses/{course}/flashcard-review")
    assert before.headers["cache-control"] == "no-store"
    assert before.json()["due_count"] == 3
    assert before.json()["reviewed_count"] == 0
    assert len(before.json()["cards"][0]["citations"]) == 1
    card_id = generated[0]["id"]
    response = client.post(f"/flashcards/{card_id}/reviews",
                           json={"rating": rating, "version": 0})
    assert response.status_code == 200
    assert response.json()["interval_minutes"] == minutes
    assert response.json()["version"] == 1
    after = client.get(f"/courses/{course}/flashcard-review").json()
    assert after["due_count"] == 2 and after["reviewed_count"] == 1
    assert card_id not in [card["id"] for card in after["cards"]]
    with client.testing_session_local() as db:
        progress = db.scalar(select(FlashcardProgress))
        assert progress.due_at == 172800 + minutes * 60
        assert progress.last_rating == rating
        assert db.scalar(select(AIUsageBucket)) is None


def test_due_boundary_repeat_schedule_and_again_reset(cards, monkeypatch):
    client, course, generated = cards
    card_id = generated[0]["id"]
    endpoint = f"/flashcards/{card_id}/reviews"
    assert client.post(endpoint, json={"rating": "good", "version": 0}).status_code == 200
    assert client.post(endpoint, json={"rating": "good", "version": 1}).status_code == 409
    monkeypatch.setattr(reviews.time, "time", lambda: 172800 + 4320 * 60 - 1)
    assert card_id not in [c["id"] for c in client.get(
        f"/courses/{course}/flashcard-review").json()["cards"]]
    monkeypatch.setattr(reviews.time, "time", lambda: 172800 + 4320 * 60)
    queue = client.get(f"/courses/{course}/flashcard-review").json()
    due = next(c for c in queue["cards"] if c["id"] == card_id)
    assert due["version"] == 1
    result = client.post(endpoint, json={"rating": "good", "version": 1})
    assert result.json()["interval_minutes"] == 8640
    monkeypatch.setattr(reviews.time, "time", lambda: 172800 + (4320 + 8640) * 60)
    result = client.post(endpoint, json={"rating": "again", "version": 2})
    assert result.json()["interval_minutes"] == 10
    assert next_interval(ReviewRating.easy, 525600) == 525600


def test_duplicate_invalid_and_unknown_reviews_do_not_change_progress(cards):
    client, _, generated = cards
    endpoint = f"/flashcards/{generated[0]['id']}/reviews"
    for body in [{"rating": "bad", "version": 0}, {"rating": "good", "version": -1},
                 {"rating": "good"}]:
        assert client.post(endpoint, json=body).status_code == 422
    assert client.post(endpoint, json={"rating": "easy", "version": 4}).status_code == 409
    assert client.post(f"/flashcards/{uuid.uuid4()}/reviews",
                       json={"rating": "good", "version": 0}).status_code == 404
    assert client.post(endpoint, json={"rating": "good", "version": 0}).status_code == 200
    assert client.post(endpoint, json={"rating": "easy", "version": 0}).status_code == 409
    with client.testing_session_local() as db:
        progress = db.scalar(select(FlashcardProgress))
        assert progress.review_count == 1 and progress.last_rating == "good"


def test_review_ownership_course_isolation_and_session_persistence(cards):
    client, course, generated = cards
    endpoint = f"/flashcards/{generated[0]['id']}/reviews"
    owner_headers = dict(client.headers)
    assert client.post(endpoint, json={"rating": "hard", "version": 0}).status_code == 200
    other = client.post("/auth/register", json={"email": "other-review@example.com",
        "display_name": "Other", "password": "Other-review-password!"}).json()
    client.headers["Authorization"] = f"Bearer {other['access_token']}"
    assert client.get(f"/courses/{course}/flashcard-review").status_code == 404
    assert client.post(endpoint, json={"rating": "good", "version": 1}).status_code == 404
    empty = client.post(f"/users/{other['user']['id']}/courses",
                        json={"title": "Empty"}).json()["id"]
    queue = client.get(f"/courses/{empty}/flashcard-review").json()
    assert queue["total_count"] == 0 and queue["due_count"] == 0
    client.headers.clear()
    assert client.get(f"/courses/{course}/flashcard-review").status_code == 401
    assert client.post(endpoint, json={"rating": "good", "version": 1}).status_code == 401
    client.headers.update(owner_headers)
    limited = client.get(f"/courses/{course}/flashcard-review?limit=1").json()
    assert limited["reviewed_count"] == 1 and len(limited["cards"]) == 1
    assert client.get(f"/courses/{course}/flashcard-review?limit=0").status_code == 422
    assert client.get(f"/courses/{course}/flashcard-review?limit=51").status_code == 422
    client.post("/auth/logout")
    login = client.post("/auth/login", json={"email": "student@example.com",
                        "password": TEST_PASSWORD})
    assert login.status_code == 200
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    assert client.get(f"/courses/{course}/flashcard-review").json()["reviewed_count"] == 1


def test_concurrent_first_rating_commits_once(cards, tmp_path):
    client, _, generated = cards
    # Copy the disposable fixture into a file DB so each worker has a connection.
    source = client.testing_session_local.kw["bind"]
    destination = create_engine(f"sqlite:///{tmp_path / 'reviews.db'}")
    with source.connect() as src, destination.connect() as dst:
        src.connection.driver_connection.backup(dst.connection.driver_connection)
    with Session(destination) as db:
        owner = db.scalar(select(Course.owner_id))
    card_id = uuid.UUID(generated[0]["id"])

    def rate(_):
        with Session(destination) as db:
            try:
                review_flashcard(db, card_id, owner,
                                 FlashcardReviewCreate(rating="good", version=0))
                return True
            except ReviewConflict:
                return False

    with ThreadPoolExecutor(max_workers=8) as workers:
        assert sum(workers.map(rate, range(12))) == 1
    with Session(destination) as db:
        assert db.scalar(select(FlashcardProgress.review_count)) == 1
    destination.dispose()


def test_failed_commit_rolls_back_and_hides_database_details(cards, monkeypatch):
    client, course, generated = cards

    def unavailable(_):
        raise SQLAlchemyError("private database details")

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", unavailable)
        result = client.post(f"/flashcards/{generated[0]['id']}/reviews",
                             json={"rating": "good", "version": 0})
    assert result.status_code == 503
    assert "private database details" not in result.text
    assert client.get(f"/courses/{course}/flashcard-review").json()["due_count"] == 3
    with client.testing_session_local() as db:
        assert db.scalar(select(FlashcardProgress)) is None
