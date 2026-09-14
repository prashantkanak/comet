"""Gemini adapter tests using a stub client (no network)."""

import json

import pytest

from comet.exceptions import LLMProviderError, StructuredOutputValidationError
from comet.llm.gemini_provider import GeminiLLMProvider
from comet.llm.prompts import EMAIL_SYSTEM, EXTRACTION_SYSTEM
from comet.models import ComplaintCase

VALID_PAYLOAD = {
    "customer_name": None,
    "email": None,
    "phone_number": None,
    "complaint_category": "billing",
    "issue_description": "Charged twice for one month.",
    "resolution_provided": None,
    "is_complaint": True,
    "escalation_required": False,
    "supporting_document_available": False,
    "overall_case_status": "open",
}


class _Response:
    def __init__(self, text: str | None) -> None:
        self.text = text


class _Models:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = list(outputs)
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> _Response:
        self.calls.append(kwargs)
        item = self.outputs.pop(0)
        if isinstance(item, Exception):
            raise item
        return _Response(item if isinstance(item, str) else None)


class _StubClient:
    def __init__(self, outputs: list[object]) -> None:
        self.models = _Models(outputs)


def test_gemini_extracts_pydantic_case_with_json_schema():
    client = _StubClient([json.dumps(VALID_PAYLOAD)])
    provider = GeminiLLMProvider(api_key="fake", client=client)

    case = provider.extract_case("Charged twice.")

    assert isinstance(case, ComplaintCase)
    assert case.complaint_category.value == "billing"
    kwargs = client.models.calls[0]
    assert kwargs["model"] == "gemini-2.5-flash"
    assert kwargs["config"] == {
        "system_instruction": EXTRACTION_SYSTEM,
        "temperature": 0,
        "response_mime_type": "application/json",
        "response_schema": ComplaintCase.model_json_schema(),
    }
    assert "<<<DOCUMENT>>>" in str(kwargs["contents"])


def test_gemini_email_uses_case_json_and_not_structured_response_mode():
    client = _StubClient(["# Subject: Billing case\n\nDear Customer,\n"])
    provider = GeminiLLMProvider(api_key="fake", client=client)
    case = ComplaintCase.model_validate(VALID_PAYLOAD)

    provider.generate_customer_email(case)

    kwargs = client.models.calls[0]
    assert kwargs["config"] == {"system_instruction": EMAIL_SYSTEM, "temperature": 0}
    assert "<<<CASE_JSON>>>" in str(kwargs["contents"])
    assert "<<<DOCUMENT>>>" not in str(kwargs["contents"])


def test_gemini_malformed_json_is_validation_error():
    provider = GeminiLLMProvider(api_key="fake", client=_StubClient(["not-json"]))
    with pytest.raises(StructuredOutputValidationError):
        provider.extract_case("Charged twice.")


def test_gemini_transport_error_is_provider_error():
    provider = GeminiLLMProvider(
        api_key="fake", client=_StubClient([ConnectionError("network down")])
    )
    with pytest.raises(LLMProviderError) as exc:
        provider.extract_case("Charged twice.")
    assert exc.value.error_code == "LLM_PROVIDER_ERROR"
    assert "network down" not in str(exc.value)


def test_gemini_forbidden_explains_key_or_model_access():
    class _Forbidden(Exception):
        status_code = 403

    provider = GeminiLLMProvider(
        api_key="fake", client=_StubClient([_Forbidden("blocked")])
    )
    with pytest.raises(LLMProviderError) as exc:
        provider.extract_case("Charged twice.")
    assert "403 Forbidden" in str(exc.value)
    assert "blocked" not in str(exc.value)
