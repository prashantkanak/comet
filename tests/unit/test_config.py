"""Configuration tests."""

import pytest

from comet.config import Settings
from comet.exceptions import ConfigurationError


def test_mock_provider_needs_no_key():
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
