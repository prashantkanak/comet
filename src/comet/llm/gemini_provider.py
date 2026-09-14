"""Gemini adapter for structured case extraction and draft generation."""

import json
import logging

from comet.exceptions import LLMProviderError, StructuredOutputValidationError
from comet.llm.prompts import (
    EMAIL_SYSTEM,
    EXTRACTION_SYSTEM,
    SUMMARY_SYSTEM,
    email_user_message,
    extraction_user_message,
    summary_user_message,
)
from comet.models import ComplaintCase

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


class GeminiLLMProvider:
    """Call Google GenAI and validate structured extraction as ComplaintCase."""

    def __init__(
        self,
        api_key: str,
        model_name: str | None = None,
        *,
        client: object | None = None,
    ) -> None:
        if client is None:
            try:
                from google import genai
            except ImportError as exc:
                raise LLMProviderError(
                    "Gemini support requires the google-genai package"
                ) from exc
            client = genai.Client(api_key=api_key)
        self._client = client
        self.model_name = model_name or DEFAULT_GEMINI_MODEL

    def extract_case(self, document_text: str, *, repair: bool = False) -> ComplaintCase:
        content = self._complete(
            EXTRACTION_SYSTEM,
            extraction_user_message(document_text, repair=repair),
            json_object=True,
        )
        return _parse_case_json(content)

    def generate_customer_email(self, case: ComplaintCase) -> str:
        return self._complete(EMAIL_SYSTEM, email_user_message(case))

    def generate_case_summary(self, case: ComplaintCase) -> str:
        return self._complete(SUMMARY_SYSTEM, summary_user_message(case))

    def _complete(self, system: str, user: str, *, json_object: bool = False) -> str:
        # The Google GenAI SDK accepts this config mapping and supports passing
        # a Pydantic model as response_schema for structured output.
        config: dict[str, object] = {
            "system_instruction": system,
            "temperature": 0,
        }
        if json_object:
            config["response_mime_type"] = "application/json"
            config["response_schema"] = ComplaintCase
        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=user,
                config=config,
            )
        except Exception as exc:
            _reraise_provider_error(exc)
            raise
        return _response_text(response)


def _response_text(response: object) -> str:
    content = getattr(response, "text", None)
    if not content or not str(content).strip():
        raise StructuredOutputValidationError("Gemini returned empty content")
    return str(content)


def _parse_case_json(content: str) -> ComplaintCase:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise StructuredOutputValidationError("Gemini returned invalid JSON") from exc
    try:
        return ComplaintCase.model_validate(payload)
    except Exception as exc:
        raise StructuredOutputValidationError(
            "Gemini JSON failed ComplaintCase validation"
        ) from exc


def _reraise_provider_error(exc: Exception) -> None:
    status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    transient = status_code in {408, 409, 429, 500, 502, 503, 504}
    logger.warning(
        "gemini_provider_error type=%s transient=%s",
        type(exc).__name__,
        transient,
    )
    raise LLMProviderError("Gemini provider request failed", transient=transient) from exc
