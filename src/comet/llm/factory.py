"""Construct an LLM provider from settings."""

from comet.config import Settings
from comet.exceptions import ConfigurationError
from comet.llm.base import LLMProvider
from comet.llm.mock_provider import MockLLMProvider
from comet.llm.openai_provider import OpenAILLMProvider


def create_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "mock":
        return MockLLMProvider()
    if settings.llm_provider == "openai":
        return OpenAILLMProvider(
            api_key=settings.openai_api_key or "",
            model_name=settings.model_name,
        )
    raise ConfigurationError(
        f"Provider '{settings.llm_provider}' is not implemented yet. Use mock or openai."
    )
