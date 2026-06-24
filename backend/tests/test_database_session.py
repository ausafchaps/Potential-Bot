from app.core.config import Settings
from app.db.session import build_engine_options, normalize_database_url


def test_normalize_database_url_selects_psycopg_for_managed_postgres_url() -> None:
    url = normalize_database_url("postgresql://studybot:password@db.example.com/studybot")

    assert url.drivername == "postgresql+psycopg"


def test_normalize_database_url_accepts_legacy_managed_postgres_scheme() -> None:
    url = normalize_database_url("postgres://studybot:password@db.example.com/studybot")

    assert url.drivername == "postgresql+psycopg"


def test_normalize_database_url_preserves_explicit_psycopg_driver() -> None:
    url = normalize_database_url(
        "postgresql+psycopg://studybot:password@db.example.com/studybot"
    )

    assert url.drivername == "postgresql+psycopg"


def test_sqlite_engine_options_enable_thread_sharing() -> None:
    settings = Settings(_env_file=None, environment="test")
    url = normalize_database_url("sqlite:///./test.db")

    options = build_engine_options(settings, url)

    assert options == {
        "pool_pre_ping": True,
        "connect_args": {"check_same_thread": False},
    }


def test_postgres_engine_options_use_bounded_pool_settings() -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        database_pool_size=7,
        database_max_overflow=3,
        database_pool_timeout_seconds=12.5,
        database_pool_recycle_seconds=900,
    )
    url = normalize_database_url("postgresql://studybot:password@db.example.com/studybot")

    options = build_engine_options(settings, url)

    assert options == {
        "pool_pre_ping": True,
        "pool_size": 7,
        "max_overflow": 3,
        "pool_timeout": 12.5,
        "pool_recycle": 900,
    }
