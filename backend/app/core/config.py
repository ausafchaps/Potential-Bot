from functools import lru_cache
from os import getenv
from typing import Literal, Self
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "StudyBot"
    environment: str = "local"
    auth_session_hours: int = Field(default=24, ge=1, le=168)
    email_provider: Literal["disabled", "smtp"] = "disabled"
    email_from: str = ""
    smtp_host: str = ""
    smtp_port: Literal[465, 587] = 465
    smtp_username: str = ""
    smtp_password: str = Field(default="", repr=False)
    smtp_timeout_seconds: float = Field(default=5, gt=0, le=10)
    public_app_url: str = "http://127.0.0.1:8000"
    auth_require_email_verification: bool = False
    auth_reset_minutes: int = Field(default=15, ge=5, le=60)
    auth_verify_hours: int = Field(default=24, ge=1, le=72)
    auth_email_ip_limit: int = Field(default=10, ge=1, le=1000)
    auth_email_address_limit: int = Field(default=3, ge=1, le=100)
    auth_email_project_daily_limit: int = Field(default=100, ge=1, le=10000)
    auth_login_ip_limit: int = Field(default=30, ge=1, le=10000)
    auth_login_email_limit: int = Field(default=10, ge=1, le=10000)
    auth_login_window_seconds: int = Field(default=900, ge=1, le=86400)
    auth_signup_ip_limit: int = Field(default=10, ge=1, le=10000)
    auth_signup_window_seconds: int = Field(default=3600, ge=1, le=86400)
    auth_client_ip_source: Literal["direct", "vercel"] = Field(
        default_factory=lambda: "vercel" if getenv("VERCEL") == "1" else "direct"
    )
    database_url: str = "sqlite:///./studybot.db"
    database_pool_size: int = Field(default=5, ge=1)
    database_max_overflow: int = Field(default=10, ge=0)
    database_pool_timeout_seconds: float = Field(default=30.0, gt=0)
    database_pool_recycle_seconds: int = Field(default=1800, ge=0)
    llm_provider: str = "fake"
    llm_model: str = "openai/gpt-oss-20b"
    llm_api_key: str | None = None
    groq_api_key: str | None = None
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_timeout_seconds: float = 30.0
    ai_user_daily_limit: int = Field(default=20, ge=1, le=100000)
    ai_user_minute_limit: int = Field(default=3, ge=1, le=10000)
    ai_project_daily_limit: int = Field(default=100, ge=1, le=1000000)
    ai_project_minute_limit: int = Field(default=10, ge=1, le=10000)
    embedding_provider: str = "fake"
    embedding_model: str = "text-embedding-3-small"
    embedding_api_key: str | None = None
    openai_api_key: str | None = None
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_timeout_seconds: float = 30.0
    embedding_dimensions: int | None = None
    cors_origins: str = (
        "http://127.0.0.1:5173,"
        "http://localhost:5173,"
        "http://127.0.0.1:5500,"
        "http://localhost:5500"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_settings(self) -> Self:
        parsed_app = urlparse(self.public_app_url)
        if (parsed_app.scheme not in {"http", "https"} or not parsed_app.hostname
                or parsed_app.username or parsed_app.password
                or parsed_app.query or parsed_app.fragment
                or parsed_app.path not in {"", "/"}):
            raise ValueError("PUBLIC_APP_URL must be an origin without credentials or path")
        if self.email_provider == "smtp":
            if not all([self.smtp_host, self.smtp_username, self.smtp_password, self.email_from]):
                raise ValueError("SMTP requires a host, username, password, and EMAIL_FROM")
            if "@" not in self.email_from or any(c in self.email_from for c in "\r\n"):
                raise ValueError("EMAIL_FROM must be one email address")
        if self.auth_require_email_verification and self.email_provider == "disabled":
            raise ValueError("Required email verification needs an email provider")
        if self.environment.strip().lower() != "production":
            return self

        if not self.database_url.lower().startswith(
            ("postgres://", "postgresql://", "postgresql+psycopg://")
        ):
            raise ValueError("Production requires a PostgreSQL database")

        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        parsed_origins = [urlparse(origin) for origin in origins]
        if not origins or "*" in origins or any(
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            for parsed in parsed_origins
        ):
            raise ValueError("Production requires explicit HTTPS CORS origins")

        if self.email_provider != "disabled" and (
            parsed_app.scheme != "https" or parsed_app.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError("Production account links require a public HTTPS PUBLIC_APP_URL")

        llm_provider = self.llm_provider.strip().lower()
        if llm_provider not in {"fake", "groq"}:
            raise ValueError(f"Unsupported production LLM provider '{self.llm_provider}'")

        if llm_provider == "groq" and not (self.llm_api_key or self.groq_api_key):
            raise ValueError("The Groq provider requires an API key in production")

        embedding_provider = self.embedding_provider.strip().lower()
        if embedding_provider not in {"fake", "openai"}:
            raise ValueError(
                f"Unsupported production embedding provider '{self.embedding_provider}'"
            )

        if embedding_provider == "openai" and not (
            self.embedding_api_key or self.openai_api_key
        ):
            raise ValueError("The OpenAI embedding provider requires an API key in production")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
