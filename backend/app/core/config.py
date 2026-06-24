from functools import lru_cache
from typing import Self
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "StudyBot"
    environment: str = "local"
    database_url: str = "sqlite:///./studybot.db"
    database_pool_size: int = Field(default=5, ge=1)
    database_max_overflow: int = Field(default=10, ge=0)
    database_pool_timeout_seconds: float = Field(default=30.0, gt=0)
    database_pool_recycle_seconds: int = Field(default=1800, ge=0)
    llm_provider: str = "fake"
    llm_model: str = "llama-3.1-8b-instant"
    llm_api_key: str | None = None
    groq_api_key: str | None = None
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_timeout_seconds: float = 30.0
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
