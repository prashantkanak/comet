"""Application configuration via environment variables and CLI overrides."""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from comet.exceptions import ConfigurationError

LLMProviderName = Literal["mock", "openai", "gemini"]


class Settings(BaseSettings):
    """Runtime settings loaded from .env and optional CLI overrides."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: LLMProviderName = Field(default="mock", alias="LLM_PROVIDER")
    model_name: str | None = Field(default=None, alias="MODEL_NAME")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    max_llm_attempts: int = Field(default=2, ge=1, alias="MAX_LLM_ATTEMPTS")
    input_dir: Path = Field(default=Path("data"), alias="INPUT_DIR")
    output_dir: Path = Field(default=Path("output"), alias="OUTPUT_DIR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    overwrite: bool = Field(default=False)

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.upper()

    def validate_provider_credentials(self) -> None:
        """Fail fast when a real provider is selected without its API key."""
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ConfigurationError(
                "OPENAI_API_KEY is required when LLM_PROVIDER is 'openai'."
            )
        if self.llm_provider == "gemini" and not self.gemini_api_key:
            raise ConfigurationError(
                "GEMINI_API_KEY is required when LLM_PROVIDER is 'gemini'."
            )
