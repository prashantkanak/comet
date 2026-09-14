"""OpenAI adapter tests using a stub client (no network)."""

import json

import pytest

from comet.exceptions import ConfigurationError, LLMProviderError, StructuredOutputValidationError
from comet.config import Settings
from comet.llm.factory import create_provider
from comet.llm.gemini_provider import GeminiLLMProvider
from comet.llm.mock_provider import MockLLMProvider
from comet.llm.openai_provider import OpenAILLMProvider
from comet.llm.prompts import EXTRACTION_REPAIR
from comet.models import ComplaintCase
from comet.services.extraction_service import extract_case

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


class _Message:
    def __init__(self, content: str | None) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str | None) -> None:
        self.message = _Message(content)


class _Response:
    def __init__(self, content: str | None) -> None:
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = list(outputs)
        self.calls: list[dict] = []

    def create(self, **kwargs: object) -> _Response:
        self.calls.append(kwargs)
        item = self.outputs.pop(0)
        if isinstance(item, Exception):
            raise item
        return _Response(item)  # type: ignore[arg-type]


class _StubClient:
    def __init__(self, outputs: list[object]) -> None:
        self.completions = _Completions(outputs)
        self.chat = type("Chat", (), {"completions": self.completions})()


def test_factory_returns_mock_by_default():
    provider = create_provider(Settings(llm_provider="mock"))
    assert isinstance(provider, MockLLMProvider)


def test_factory_openai_requires_implemented_adapter():
    settings = Settings(llm_provider="openai", openai_api_key="sk-test")
    provider = create_provider(settings)
    assert isinstance(provider, OpenAILLMProvider)
    assert provider.model_name == "gpt-4o-mini"


def test_factory_returns_gemini_provider():
    settings = Settings(llm_provider="gemini", gemini_api_key="fake")
    provider = create_provider(settings)
    assert isinstance(provider, GeminiLLMProvider)
    assert provider.model_name == "gemini-2.5-flash"


def test_openai_parses_valid_json():
    client = _StubClient([json.dumps(VALID_PAYLOAD)])
    provider = OpenAILLMProvider(api_key="sk-test", client=client)
    case = provider.extract_case("Charged twice.")
    assert isinstance(case, ComplaintCase)
    assert case.complaint_category.value == "billing"
    assert case.email is None


def test_openai_malformed_json_then_repair_succeeds():
    client = _StubClient(["not-json", json.dumps(VALID_PAYLOAD)])
    provider = OpenAILLMProvider(api_key="sk-test", client=client)
    case = extract_case(provider, "Charged twice.", max_attempts=2, sleep=lambda _s: None)
    assert case.issue_description == "Charged twice for one month."
    assert len(client.completions.calls) == 2
    second_user = client.completions.calls[1]["messages"][1]["content"]
    assert EXTRACTION_REPAIR in second_user


def test_openai_malformed_output_fails_after_retry_limit():
    client = _StubClient(["not-json", '{"issue_description": 1}'])
    provider = OpenAILLMProvider(api_key="sk-test", client=client)
    with pytest.raises(StructuredOutputValidationError):
        extract_case(provider, "Charged twice.", max_attempts=2, sleep=lambda _s: None)
    assert len(client.completions.calls) == 2


def test_openai_transport_error_is_provider_error():
    client = _StubClient([ConnectionError("network down")])
    provider = OpenAILLMProvider(api_key="sk-test", client=client)
    with pytest.raises(LLMProviderError) as exc:
        provider.extract_case("Charged twice.")
    assert exc.value.error_code == "LLM_PROVIDER_ERROR"
    assert "network down" not in str(exc.value)
