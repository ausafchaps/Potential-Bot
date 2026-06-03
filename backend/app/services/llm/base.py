from dataclasses import dataclass
from typing import Protocol

from app.services.retrieval import RankedChunk


@dataclass(frozen=True)
class LLMRequest:
    question: str
    prompt: str
    context_chunks: list[RankedChunk]


@dataclass(frozen=True)
class LLMResponse:
    text: str


class LLMProviderConfigurationError(ValueError):
    pass


class LLMProviderError(RuntimeError):
    pass


class LLMProvider(Protocol):
    provider_name: str

    def generate_answer(self, request: LLMRequest) -> LLMResponse:
        pass
