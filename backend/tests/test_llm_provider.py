import json

import httpx
import pytest
from app.core.config import Settings
from app.services.llm.base import (
    LLMProviderConfigurationError,
    LLMProviderError,
    LLMProviderRateLimited,
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
    assert payload["max_completion_tokens"] == 4096
    assert "reasoning_effort" not in payload
    assert "response_format" not in payload
    assert payload["messages"][1]["content"] == "Study material:\n[1] Binary search halves arrays."


def test_groq_provider_raises_provider_error_for_http_failures() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(500, json={})),
        base_url="https://api.groq.com/openai/v1",
    )
    provider = GroqLLMProvider(
        api_key="test-key",
        model="llama-test",
        base_url="https://api.groq.com/openai/v1",
        timeout_seconds=30,
        http_client=client,
    )

    with pytest.raises(LLMProviderError, match="HTTP 500"):
        provider.generate_answer(
            LLMRequest(question="What is binary search?", prompt="Prompt", context_chunks=[])
        )


@pytest.mark.parametrize("header,expected", [("120", 120), ("invalid", 60), ("-1", 1)])
def test_groq_provider_preserves_safe_retry_delay(header, expected):
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(
            429, headers={"Retry-After": header}, json={"error": "private provider detail"},
        )), base_url="https://api.groq.com/openai/v1",
    )
    provider = GroqLLMProvider(
        api_key="test-key", model="openai/gpt-oss-20b",
        base_url="https://api.groq.com/openai/v1", timeout_seconds=30, http_client=client,
    )
    with pytest.raises(LLMProviderRateLimited) as exc:
        provider.generate_answer(
            LLMRequest(question="Question", prompt="Prompt", context_chunks=[])
        )
    assert exc.value.retry_after == expected
    assert "private" not in str(exc.value)


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


@pytest.mark.parametrize("model", ["openai/gpt-oss-20b", "openai/gpt-oss-120b"])
def test_groq_reasoning_models_return_only_final_content(model: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["reasoning_effort"] == "low"
        assert payload["include_reasoning"] is False
        assert payload["max_completion_tokens"] == 4096
        assert payload["response_format"] == {"type": "json_object"}
        return httpx.Response(200, json={"choices": [{
            "message": {"content": "Final answer. [1]", "reasoning": "Private reasoning"},
            "finish_reason": "stop",
        }]})

    provider = GroqLLMProvider(
        api_key="test-key", model=model, base_url="https://api.groq.com/openai/v1",
        timeout_seconds=30,
        http_client=httpx.Client(transport=httpx.MockTransport(handler),
                                 base_url="https://api.groq.com/openai/v1"),
    )
    assert provider.generate_answer(LLMRequest(
        question="Question", prompt="Prompt", context_chunks=[], json_output=True,
    )).text == "Final answer. [1]"


@pytest.mark.parametrize("content,finish_reason,error", [
    ("Partial answer", "length", "completion token limit"),
    (None, "stop", "did not include answer text"),
    ("   ", "stop", "empty answer text"),
])
def test_groq_rejects_incomplete_or_empty_content(content, finish_reason, error) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"choices": [{
            "message": {"content": content}, "finish_reason": finish_reason,
        }]})),
        base_url="https://api.groq.com/openai/v1",
    )
    provider = GroqLLMProvider(
        api_key="test-key", model="openai/gpt-oss-20b",
        base_url="https://api.groq.com/openai/v1", timeout_seconds=30, http_client=client,
    )
    with pytest.raises(LLMProviderError, match=error):
        provider.generate_answer(
            LLMRequest(question="Question", prompt="Prompt", context_chunks=[])
        )
