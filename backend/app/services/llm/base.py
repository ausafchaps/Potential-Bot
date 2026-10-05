from dataclasses import dataclass
from typing import Protocol

from app.services.retrieval import RankedChunk


@dataclass(frozen=True)
class LLMRequest:
    question: str
    prompt: str
    context_chunks: list[RankedChunk]
    json_output: bool = False


@dataclass(frozen=True)
class LLMResponse:
    text: str


class LLMProviderConfigurationError(ValueError):
    pass


class LLMProviderError(RuntimeError):
    pass


class LLMProviderRateLimited(LLMProviderError):
    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__("AI provider usage limit reached")


class LLMProvider(Protocol):
    provider_name: str

    def generate_answer(self, request: LLMRequest) -> LLMResponse:
        pass
