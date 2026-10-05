from pathlib import Path

from alembic import command
from alembic.config import Config
from app.core.config import settings
from app.models import AIUsageBucket
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session


def test_ai_usage_migration_upgrade_downgrade_and_drift(tmp_path, monkeypatch):
    project = Path(__file__).resolve().parents[2]
    config = Config(str(project / "alembic.ini"))
    config.set_main_option("script_location", str(project / "backend" / "migrations"))
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setattr(settings, "database_url", url)
    command.upgrade(config, "20261005_0009")
    engine = create_engine(url)
    assert "ai_usage_buckets" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    command.check(config)
    with Session(engine) as db:
        db.add(AIUsageBucket(bucket_key="a" * 64, attempts=1, expires_at=1000))
        db.commit()
    command.downgrade(config, "20261005_0009")
    assert "ai_usage_buckets" not in inspect(engine).get_table_names()
    assert "auth_rate_limits" in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    command.check(config)
    engine.dispose()
