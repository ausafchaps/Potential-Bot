import httpx

from app.services.llm.base import (
    LLMProviderConfigurationError,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
)


class GroqLLMProvider:
    provider_name = "groq"

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str,
        timeout_seconds: float,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise LLMProviderConfigurationError(
                "Groq provider requires LLM_API_KEY or GROQ_API_KEY"
            )
        if not model.strip():
            raise LLMProviderConfigurationError("Groq provider requires LLM_MODEL")

        self.api_key = api_key
        self.model = model
        self.http_client = http_client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
        )

    def generate_answer(self, request: LLMRequest) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are StudyBot, an auditable study assistant. Answer only from "
                        "the provided study material and include citation markers such as [1]."
                    ),
                },
                {"role": "user", "content": request.prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 600,
        }

        try:
            response = self.http_client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            response_payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"Groq provider returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError("Groq provider request failed") from exc
        except ValueError as exc:
            raise LLMProviderError("Groq provider returned invalid JSON") from exc

        try:
            text = response_payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("Groq provider response did not include answer text") from exc

        normalized_text = str(text).strip()
        if not normalized_text:
            raise LLMProviderError("Groq provider returned empty answer text")

        return LLMResponse(text=normalized_text)

