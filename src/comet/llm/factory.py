"""Construct an LLM provider from settings."""

from comet.config import Settings
from comet.exceptions import ConfigurationError
from comet.llm.base import LLMProvider
from comet.llm.gemini_provider import GeminiLLMProvider
from comet.llm.groq_provider import GroqLLMProvider
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
    if settings.llm_provider == "gemini":
        return GeminiLLMProvider(
            api_key=settings.gemini_api_key or "",
            model_name=settings.model_name,
        )
    if settings.llm_provider == "groq":
        return GroqLLMProvider(
            api_key=settings.groq_api_key or "",
            model_name=settings.model_name,
        )
    raise ConfigurationError(f"Unknown provider: {settings.llm_provider}")
