import pytest
from app.core.config import Settings
from pydantic import ValidationError


def production_settings(**overrides) -> Settings:
    values = {
        "environment": "production",
        "database_url": "postgresql+psycopg://studybot:password@db/studybot",
        "cors_origins": "https://studybot.example.com",
        "llm_provider": "fake",
        "embedding_provider": "fake",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_settings_accept_explicit_safe_configuration() -> None:
    settings = production_settings()

    assert settings.environment == "production"


@pytest.mark.parametrize("field", [
    "auth_login_ip_limit", "auth_login_email_limit", "auth_login_window_seconds",
    "auth_signup_ip_limit", "auth_signup_window_seconds",
])
def test_auth_rate_limits_cannot_be_disabled_with_zero(field):
    with pytest.raises(ValidationError):
        production_settings(**{field: 0})


def test_only_server_configuration_enables_vercel_header_trust(monkeypatch):
    monkeypatch.delenv("AUTH_CLIENT_IP_SOURCE", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    assert Settings(_env_file=None).auth_client_ip_source == "direct"
    monkeypatch.setenv("VERCEL", "1")
    assert Settings(_env_file=None).auth_client_ip_source == "vercel"
    direct = Settings(_env_file=None, auth_client_ip_source="direct")
    assert direct.auth_client_ip_source == "direct"
    with pytest.raises(ValidationError):
        Settings(_env_file=None, auth_client_ip_source="forwarded")


def test_production_settings_reject_sqlite() -> None:
    with pytest.raises(ValidationError, match="PostgreSQL database"):
        production_settings(database_url="sqlite:///./studybot.db")


@pytest.mark.parametrize(
    "cors_origins",
    ["", "*", "http://studybot.example.com", "http://localhost:5173", "https://127.0.0.1"],
)
def test_production_settings_reject_unsafe_cors(cors_origins: str) -> None:
    with pytest.raises(ValidationError, match="HTTPS CORS"):
        production_settings(cors_origins=cors_origins)


@pytest.mark.parametrize(
    "overrides",
    [
        {"llm_provider": "unknown"},
        {"embedding_provider": "unknown"},
    ],
)
def test_production_settings_reject_unknown_providers(
    overrides: dict[str, str],
) -> None:
    with pytest.raises(ValidationError, match="Unsupported production"):
        production_settings(**overrides)


@pytest.mark.parametrize(
    ("overrides", "expected_message"),
    [
        (
            {"llm_provider": "groq", "groq_api_key": None, "llm_api_key": None},
            "Groq provider requires an API key",
        ),
        (
            {
                "embedding_provider": "openai",
                "embedding_api_key": None,
                "openai_api_key": None,
            },
            "OpenAI embedding provider requires an API key",
        ),
    ],
)
def test_production_settings_require_real_provider_credentials(
    overrides: dict[str, str | None],
    expected_message: str,
) -> None:
    with pytest.raises(ValidationError, match=expected_message):
        production_settings(**overrides)
