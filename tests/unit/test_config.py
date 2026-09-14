"""Configuration tests."""

import pytest

from comet.config import Settings
from comet.exceptions import ConfigurationError


def test_empty_llm_provider_env_defaults_to_mock(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "")
    settings = Settings()
    assert settings.llm_provider == "mock"
    settings.validate_provider_credentials()
    settings = Settings(llm_provider="mock")
    settings.validate_provider_credentials()


def test_openai_requires_key():
    settings = Settings(llm_provider="openai", openai_api_key=None)
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        settings.validate_provider_credentials()


def test_gemini_requires_key():
    settings = Settings(llm_provider="gemini", gemini_api_key=None)
    with pytest.raises(ConfigurationError, match="GEMINI_API_KEY"):
        settings.validate_provider_credentials()


def test_groq_requires_key():
    settings = Settings(llm_provider="groq", groq_api_key=None)
    with pytest.raises(ConfigurationError, match="GROQ_API_KEY"):
        settings.validate_provider_credentials()
