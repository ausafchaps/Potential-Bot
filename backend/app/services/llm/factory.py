from app.core.config import Settings, get_settings
from app.services.llm.base import LLMProvider, LLMProviderConfigurationError
from app.services.llm.fake import FakeLLMProvider
from app.services.llm.groq import GroqLLMProvider


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    resolved_settings = settings or get_settings()
    provider_name = resolved_settings.llm_provider.strip().lower()

    if provider_name == "fake":
        return FakeLLMProvider()
    if provider_name == "groq":
        return GroqLLMProvider(
            api_key=resolved_settings.llm_api_key or resolved_settings.groq_api_key,
            model=resolved_settings.llm_model,
            base_url=resolved_settings.llm_base_url,
            timeout_seconds=resolved_settings.llm_timeout_seconds,
        )

    raise LLMProviderConfigurationError(
        f"Unsupported LLM provider '{resolved_settings.llm_provider}'"
    )
