import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config
from app.core.config import settings
from app.models import AuthRateLimit, Course, User
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session


def test_auth_migration_preserves_legacy_accounts_and_courses(tmp_path, monkeypatch):
    project = Path(__file__).resolve().parents[2]
    config = Config(str(project / "alembic.ini"))
    config.set_main_option("script_location", str(project / "backend" / "migrations"))
    database_url = f"sqlite:///{tmp_path / 'legacy.db'}"
    monkeypatch.setattr(settings, "database_url", database_url)
    command.upgrade(config, "20260611_0007")
    engine = create_engine(database_url)
    user_id, course_id = uuid.uuid4(), uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO users (id, email, display_name) VALUES (:id, :email, :name)"),
            {"id": user_id.hex, "email": "legacy@example.com", "name": "Legacy Student"},
        )
        connection.execute(
            text("INSERT INTO courses (id, owner_id, title) VALUES (:id, :owner_id, :title)"),
            {"id": course_id.hex, "owner_id": user_id.hex, "title": "Existing course"},
        )

    command.upgrade(config, "head")
    command.check(config)
    with Session(engine) as db:
        user = db.get(User, user_id)
        assert user.email == "legacy@example.com"
        assert user.password_hash is None
        assert user.is_admin is False
        assert db.get(Course, course_id).owner_id == user_id
        db.add(AuthRateLimit(bucket_key="a" * 64, attempts=1, expires_at=123))
        db.commit()

    command.downgrade(config, "20261002_0008")
    assert "auth_rate_limits" not in inspect(engine).get_table_names()
    assert "auth_sessions" in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    command.check(config)

    command.downgrade(config, "20260611_0007")
    assert "auth_sessions" not in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM users")) == 1
        assert connection.scalar(text("SELECT COUNT(*) FROM courses")) == 1
    command.upgrade(config, "head")
    command.check(config)
    engine.dispose()
