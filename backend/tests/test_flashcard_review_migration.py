import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config
from app.core.config import settings
from app.models import Course, Flashcard, FlashcardProgress, FlashcardSet, User
from sqlalchemy import create_engine, delete, event, inspect
from sqlalchemy.orm import Session


def test_review_migration_preserves_cards_and_cascades_progress(tmp_path, monkeypatch):
    project = Path(__file__).resolve().parents[2]
    config = Config(str(project / "alembic.ini"))
    config.set_main_option("script_location", str(project / "backend" / "migrations"))
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setattr(settings, "database_url", url)
    command.upgrade(config, "20261005_0010")
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    card_id, user_id = uuid.uuid4(), uuid.uuid4()
    with Session(engine) as db:
        user = User(id=user_id, email="migration-review@example.com", display_name="Student")
        course = Course(owner=user, title="Saved notes")
        card_set = FlashcardSet(course=course, topic="topic", difficulty="easy",
                               status="generated", provider="fake")
        db.add(Flashcard(id=card_id, flashcard_set=card_set, position=1,
                        front="Question", back="Answer"))
        db.commit()
    command.upgrade(config, "head")
    command.check(config)
    with Session(engine) as db:
        assert db.get(Flashcard, card_id).back == "Answer"
        db.add(FlashcardProgress(flashcard_id=card_id, user_id=user_id, review_count=1,
                                interval_minutes=10, last_rating="again",
                                last_reviewed_at=1000, due_at=1600))
        db.commit()
    command.downgrade(config, "20261005_0010")
    assert "flashcard_progress" not in inspect(engine).get_table_names()
    with Session(engine) as db:
        assert db.get(Flashcard, card_id).front == "Question"
    command.upgrade(config, "head")
    command.check(config)
    with Session(engine) as db:
        db.add(FlashcardProgress(flashcard_id=card_id, user_id=user_id, review_count=1,
                                interval_minutes=10, last_rating="again",
                                last_reviewed_at=1000, due_at=1600))
        db.commit()
        db.execute(delete(Flashcard).where(Flashcard.id == card_id))
        db.commit()
        assert db.get(FlashcardProgress, (card_id, user_id)) is None
    engine.dispose()
