"""OpenAI adapter for structured case extraction."""

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

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


class OpenAILLMProvider:
    """Call OpenAI chat completions and validate the JSON as ComplaintCase."""

    def __init__(
        self,
        api_key: str,
        model_name: str | None = None,
        *,
        client: object | None = None,
    ) -> None:
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
        self._client = client
        self.model_name = model_name or DEFAULT_OPENAI_MODEL

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

    def _complete(
        self,
        system: str,
        user: str,
        *,
        json_object: bool = False,
    ) -> str:
        kwargs: dict[str, object] = {
            "model": self.model_name,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_object:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            _reraise_provider_error(exc)
            raise
        return _message_content(response)


def _message_content(response: object) -> str:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, TypeError) as exc:
        raise StructuredOutputValidationError(
            "Provider response was missing message content"
        ) from exc
    if not content or not str(content).strip():
        raise StructuredOutputValidationError("Provider returned empty content")
    return str(content)


def _parse_case_json(content: str) -> ComplaintCase:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise StructuredOutputValidationError("Provider returned invalid JSON") from exc
    try:
        return ComplaintCase.model_validate(payload)
    except Exception as exc:
        raise StructuredOutputValidationError(
            "Provider JSON failed ComplaintCase validation"
        ) from exc


def _reraise_provider_error(exc: Exception) -> None:
    transient = False
    try:
        from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

        transient = isinstance(
            exc, (APIConnectionError, APITimeoutError, RateLimitError)
        )
        if isinstance(exc, APIStatusError) and getattr(exc, "status_code", None) in {
            408,
            409,
            429,
            500,
            502,
            503,
            504,
        }:
            transient = True
    except ImportError:
        pass
    logger.warning(
        "openai_provider_error type=%s transient=%s",
        type(exc).__name__,
        transient,
    )
    raise LLMProviderError(
        "LLM provider request failed",
        transient=transient,
    ) from exc
