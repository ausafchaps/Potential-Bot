from app.services.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderConfigurationError,
)
from app.services.embeddings.fake import FakeEmbeddingProvider


def get_embedding_provider(provider_name: str = "fake") -> EmbeddingProvider:
    normalized_provider = provider_name.strip().lower()
    if normalized_provider == "fake":
        return FakeEmbeddingProvider()

    raise EmbeddingProviderConfigurationError(
        f"Unsupported embedding provider '{provider_name}'"
    )

