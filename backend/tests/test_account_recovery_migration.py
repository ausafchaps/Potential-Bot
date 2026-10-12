import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config
from app.core.config import settings
from app.models import AccountToken
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session


def test_recovery_migration_preserves_existing_accounts(tmp_path, monkeypatch):
    project = Path(__file__).resolve().parents[2]
    config = Config(str(project / "alembic.ini"))
    config.set_main_option("script_location", str(project / "backend" / "migrations"))
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setattr(settings, "database_url", url)
    command.upgrade(config, "20261009_0011")
    engine = create_engine(url)
    user_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO users (id,email,display_name,password_hash) "
                                "VALUES (:id,'saved@example.com','Saved','original-hash')"),
                           {"id": user_id.hex})
    command.upgrade(config, "head")
    command.check(config)
    with engine.connect() as connection:
        row = connection.execute(text(
            "SELECT password_hash,email_verified,credential_version FROM users"
        )).one()
        assert tuple(row) == ("original-hash", 0, 0)
    with Session(engine) as db:
        db.add(AccountToken(token_hash="a" * 64, user_id=user_id, purpose="reset",
                            email_hash="b" * 64, credential_version=0, expires_at=1000))
        db.commit()
    command.downgrade(config, "20261009_0011")
    assert "account_tokens" not in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT password_hash FROM users")) == "original-hash"
    command.upgrade(config, "head")
    command.check(config)
    engine.dispose()
