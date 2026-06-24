from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, settings


def normalize_database_url(database_url: str) -> URL:
    url = make_url(database_url)
    if url.drivername in {"postgres", "postgresql"}:
        return url.set(drivername="postgresql+psycopg")
    return url


def build_engine_options(config: Settings, database_url: URL) -> dict[str, Any]:
    options: dict[str, Any] = {"pool_pre_ping": True}
    if database_url.get_backend_name() == "sqlite":
        options["connect_args"] = {"check_same_thread": False}
        return options

    options.update(
        pool_size=config.database_pool_size,
        max_overflow=config.database_max_overflow,
        pool_timeout=config.database_pool_timeout_seconds,
        pool_recycle=config.database_pool_recycle_seconds,
    )
    return options


def create_database_engine(config: Settings = settings) -> Engine:
    database_url = normalize_database_url(config.database_url)
    return create_engine(database_url, **build_engine_options(config, database_url))


engine = create_database_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
