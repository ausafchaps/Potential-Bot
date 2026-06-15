from app.core.config import Settings, get_settings
from app.services.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderConfigurationError,
)
from app.services.embeddings.fake import FakeEmbeddingProvider
from app.services.embeddings.openai import OpenAIEmbeddingProvider


def get_embedding_provider(
    provider_name: str | None = None,
    settings: Settings | None = None,
) -> EmbeddingProvider:
    resolved_settings = settings or get_settings()
    resolved_provider_name = provider_name or resolved_settings.embedding_provider
    normalized_provider = resolved_provider_name.strip().lower()

    if normalized_provider == "fake":
        return FakeEmbeddingProvider()
    if normalized_provider == "openai":
        return OpenAIEmbeddingProvider(
            api_key=(
                resolved_settings.embedding_api_key
                or resolved_settings.openai_api_key
            ),
            model=resolved_settings.embedding_model,
            base_url=resolved_settings.embedding_base_url,
            timeout_seconds=resolved_settings.embedding_timeout_seconds,
            dimensions=resolved_settings.embedding_dimensions,
        )

    raise EmbeddingProviderConfigurationError(
        f"Unsupported embedding provider '{resolved_provider_name}'"
    )
