"""Construct an LLM provider from settings."""

from comet.config import Settings
from comet.exceptions import ConfigurationError
from comet.llm.base import LLMProvider
from comet.llm.mock_provider import MockLLMProvider


def create_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "mock":
        return MockLLMProvider()
    raise ConfigurationError(
        f"Provider '{settings.llm_provider}' is not implemented yet. Use --provider mock."
    )
