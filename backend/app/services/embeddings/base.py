from typing import Protocol


class EmbeddingProviderConfigurationError(ValueError):
    pass


class EmbeddingProviderError(RuntimeError):
    pass


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    dimensions: int

    def embed_text(self, text: str) -> list[float]:
        pass
