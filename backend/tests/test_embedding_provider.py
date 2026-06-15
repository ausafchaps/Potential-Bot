import json

import httpx
import pytest
from app.core.config import Settings
from app.services.embeddings.base import (
    EmbeddingProviderConfigurationError,
    EmbeddingProviderError,
)
from app.services.embeddings.factory import get_embedding_provider
from app.services.embeddings.fake import FakeEmbeddingProvider
from app.services.embeddings.openai import OpenAIEmbeddingProvider


def test_embedding_factory_returns_fake_provider_by_default() -> None:
    provider = get_embedding_provider(settings=Settings())

    assert isinstance(provider, FakeEmbeddingProvider)
    assert provider.provider_name == "fake"


def test_embedding_factory_builds_openai_provider_with_api_key() -> None:
    provider = get_embedding_provider(
        settings=Settings(
            embedding_provider="openai",
            embedding_api_key="test-key",
            embedding_model="text-embedding-3-small",
        )
    )

    assert isinstance(provider, OpenAIEmbeddingProvider)
    assert provider.provider_name == "openai"
    assert provider.model == "text-embedding-3-small"
    assert provider.model_name == "text-embedding-3-small"
    assert provider.dimensions == 1536


def test_embedding_factory_uses_openai_api_key_fallback() -> None:
    provider = get_embedding_provider(
        settings=Settings(
            embedding_provider="openai",
            openai_api_key="fallback-key",
            embedding_model="text-embedding-3-small",
        )
    )

    assert isinstance(provider, OpenAIEmbeddingProvider)
    assert provider.api_key == "fallback-key"


def test_embedding_factory_rejects_unknown_provider() -> None:
    with pytest.raises(EmbeddingProviderConfigurationError, match="Unsupported"):
        get_embedding_provider(settings=Settings(embedding_provider="unknown"))


def test_openai_embedding_provider_requires_api_key() -> None:
    with pytest.raises(EmbeddingProviderConfigurationError, match="requires EMBEDDING_API_KEY"):
        OpenAIEmbeddingProvider(
            api_key=None,
            model="text-embedding-3-small",
            base_url="https://api.openai.com/v1",
            timeout_seconds=30,
        )


def test_openai_embedding_provider_uses_dimension_specific_model_name() -> None:
    provider = OpenAIEmbeddingProvider(
        api_key="test-key",
        model="text-embedding-3-small",
        base_url="https://api.openai.com/v1",
        timeout_seconds=30,
        dimensions=512,
    )

    assert provider.model_name == "text-embedding-3-small:dimensions=512"
    assert provider.dimensions == 512


def test_openai_embedding_provider_sends_request_and_parses_vector() -> None:
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(
            200,
            json={"data": [{"embedding": [0.1, "0.2", -0.3]}]},
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.openai.com/v1",
    )
    provider = OpenAIEmbeddingProvider(
        api_key="test-key",
        model="text-embedding-3-small",
        base_url="https://api.openai.com/v1",
        timeout_seconds=30,
        dimensions=512,
        http_client=client,
    )

    vector = provider.embed_text("Binary search halves arrays.")

    assert vector == [0.1, 0.2, -0.3]
    assert len(captured_requests) == 1
    request = captured_requests[0]
    assert request.url.path == "/v1/embeddings"
    assert request.headers["Authorization"] == "Bearer test-key"
    payload = json.loads(request.content)
    assert payload == {
        "model": "text-embedding-3-small",
        "input": "Binary search halves arrays.",
        "encoding_format": "float",
        "dimensions": 512,
    }


def test_openai_embedding_provider_raises_provider_error_for_http_failures() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(429, json={})),
        base_url="https://api.openai.com/v1",
    )
    provider = OpenAIEmbeddingProvider(
        api_key="test-key",
        model="text-embedding-3-small",
        base_url="https://api.openai.com/v1",
        timeout_seconds=30,
        http_client=client,
    )

    with pytest.raises(EmbeddingProviderError, match="HTTP 429"):
        provider.embed_text("Binary search")


def test_openai_embedding_provider_raises_provider_error_for_missing_embedding() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"data": []})),
        base_url="https://api.openai.com/v1",
    )
    provider = OpenAIEmbeddingProvider(
        api_key="test-key",
        model="text-embedding-3-small",
        base_url="https://api.openai.com/v1",
        timeout_seconds=30,
        http_client=client,
    )

    with pytest.raises(EmbeddingProviderError, match="did not include an embedding"):
        provider.embed_text("Binary search")
