import json

import httpx
import pytest
from app.core.config import Settings
from app.services.llm.base import (
    LLMProviderConfigurationError,
    LLMProviderError,
    LLMRequest,
)
from app.services.llm.factory import get_llm_provider
from app.services.llm.fake import FakeLLMProvider
from app.services.llm.groq import GroqLLMProvider


def test_llm_factory_returns_fake_provider_by_default() -> None:
    provider = get_llm_provider(Settings())

    assert isinstance(provider, FakeLLMProvider)
    assert provider.provider_name == "fake"


def test_llm_factory_builds_groq_provider_with_api_key() -> None:
    provider = get_llm_provider(
        Settings(llm_provider="groq", groq_api_key="test-key", llm_model="llama-test")
    )

    assert isinstance(provider, GroqLLMProvider)
    assert provider.provider_name == "groq"
    assert provider.model == "llama-test"


def test_llm_factory_rejects_unknown_provider() -> None:
    with pytest.raises(LLMProviderConfigurationError, match="Unsupported LLM provider"):
        get_llm_provider(Settings(llm_provider="unknown"))


def test_groq_provider_requires_api_key() -> None:
    with pytest.raises(LLMProviderConfigurationError, match="requires LLM_API_KEY"):
        GroqLLMProvider(
            api_key=None,
            model="llama-test",
            base_url="https://api.groq.com/openai/v1",
            timeout_seconds=30,
        )


def test_groq_provider_sends_grounded_prompt_and_parses_answer() -> None:
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": " Binary search halves arrays. [1] "}}]},
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.groq.com/openai/v1",
    )
    provider = GroqLLMProvider(
        api_key="test-key",
        model="llama-test",
        base_url="https://api.groq.com/openai/v1",
        timeout_seconds=30,
        http_client=client,
    )

    response = provider.generate_answer(
        LLMRequest(
            question="What is binary search?",
            prompt="Study material:\n[1] Binary search halves arrays.",
            context_chunks=[],
        )
    )

    assert response.text == "Binary search halves arrays. [1]"
    assert len(captured_requests) == 1
    request = captured_requests[0]
    assert request.url.path == "/openai/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-key"
    payload = json.loads(request.content)
    assert payload["model"] == "llama-test"
    assert payload["messages"][1]["content"] == "Study material:\n[1] Binary search halves arrays."


def test_groq_provider_raises_provider_error_for_http_failures() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(429, json={})),
        base_url="https://api.groq.com/openai/v1",
    )
    provider = GroqLLMProvider(
        api_key="test-key",
        model="llama-test",
        base_url="https://api.groq.com/openai/v1",
        timeout_seconds=30,
        http_client=client,
    )

    with pytest.raises(LLMProviderError, match="HTTP 429"):
        provider.generate_answer(
            LLMRequest(question="What is binary search?", prompt="Prompt", context_chunks=[])
        )


def test_groq_provider_raises_provider_error_for_missing_answer_text() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"choices": []})),
        base_url="https://api.groq.com/openai/v1",
    )
    provider = GroqLLMProvider(
        api_key="test-key",
        model="llama-test",
        base_url="https://api.groq.com/openai/v1",
        timeout_seconds=30,
        http_client=client,
    )

    with pytest.raises(LLMProviderError, match="did not include answer text"):
        provider.generate_answer(
            LLMRequest(question="What is binary search?", prompt="Prompt", context_chunks=[])
        )
