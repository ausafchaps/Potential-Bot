import httpx

from app.services.embeddings.base import (
    EmbeddingProviderConfigurationError,
    EmbeddingProviderError,
)

DEFAULT_MODEL_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
}


class OpenAIEmbeddingProvider:
    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str,
        timeout_seconds: float,
        dimensions: int | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise EmbeddingProviderConfigurationError(
                "OpenAI embedding provider requires EMBEDDING_API_KEY or OPENAI_API_KEY"
            )
        if not model.strip():
            raise EmbeddingProviderConfigurationError(
                "OpenAI embedding provider requires EMBEDDING_MODEL"
            )
        if dimensions is not None and dimensions <= 0:
            raise EmbeddingProviderConfigurationError(
                "OpenAI embedding dimensions must be greater than zero"
            )

        self.api_key = api_key
        self.model = model.strip()
        self._dimensions = dimensions
        self.http_client = http_client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
        )

    @property
    def model_name(self) -> str:
        if self._dimensions is None:
            return self.model
        return f"{self.model}:dimensions={self._dimensions}"

    @property
    def dimensions(self) -> int:
        if self._dimensions is not None:
            return self._dimensions
        return DEFAULT_MODEL_DIMENSIONS.get(self.model, 0)

    def embed_text(self, text: str) -> list[float]:
        payload: dict[str, object] = {
            "model": self.model,
            "input": text,
            "encoding_format": "float",
        }
        if self._dimensions is not None:
            payload["dimensions"] = self._dimensions

        try:
            response = self.http_client.post(
                "/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            response_payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise EmbeddingProviderError(
                f"OpenAI embedding provider returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise EmbeddingProviderError("OpenAI embedding provider request failed") from exc
        except ValueError as exc:
            raise EmbeddingProviderError("OpenAI embedding provider returned invalid JSON") from exc

        try:
            embedding = response_payload["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise EmbeddingProviderError(
                "OpenAI embedding provider response did not include an embedding"
            ) from exc

        if not isinstance(embedding, list) or not embedding:
            raise EmbeddingProviderError("OpenAI embedding provider returned an empty embedding")

        try:
            return [float(value) for value in embedding]
        except (TypeError, ValueError) as exc:
            raise EmbeddingProviderError(
                "OpenAI embedding provider returned a non-numeric embedding"
            ) from exc
