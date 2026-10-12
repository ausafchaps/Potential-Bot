import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config
from app.core.config import settings
from sqlalchemy import create_engine, inspect, text


def test_storage_migration_backfills_unicode_and_preserves_notes(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "backend/migrations"))
    url = f"sqlite:///{tmp_path / 'storage.db'}"
    monkeypatch.setattr(settings, "database_url", url)
    command.upgrade(config, "20261012_0012")
    engine = create_engine(url)
    user, course, document = [uuid.uuid4().hex for _ in range(3)]
    note = "é書 note"
    with engine.begin() as db:
        db.execute(text("INSERT INTO users(id,email,display_name) "
                        "VALUES(:id,'old@example.com','Old')"),
                   {"id": user})
        db.execute(text("INSERT INTO courses(id,owner_id,title) VALUES(:id,:owner,'Old')"),
                   {"id": course, "owner": user})
        db.execute(text("INSERT INTO documents(id,course_id,filename,content_type,status) "
                        "VALUES(:id,:course,'old.txt','text/plain','completed')"),
                   {"id": document, "course": course})
        for index in range(2):
            db.execute(text("INSERT INTO document_chunks(id,document_id,chunk_index,text) "
                            "VALUES(:id,:doc,:idx,:note)"),
                       {"id": uuid.uuid4().hex, "doc": document, "idx": index, "note": note})
    command.upgrade(config, "head")
    command.check(config)
    with engine.connect() as db:
        assert db.scalar(text("SELECT storage_bytes FROM documents")) == len(note.encode()) * 2
        assert db.scalar(text("SELECT count(*) FROM storage_lock")) == 1
    command.downgrade(config, "20261012_0012")
    assert "storage_bytes" not in {c["name"] for c in inspect(engine).get_columns("documents")}
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM document_chunks")) == 2
    command.upgrade(config, "head")
    command.check(config)
    engine.dispose()
