"""Groq adapter tests using a stub client (no network)."""

import json

from comet.config import Settings
from comet.llm.factory import create_provider
from comet.llm.groq_provider import GroqLLMProvider
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


class _Message:
    def __init__(self, content: str | None) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str | None) -> None:
        self.message = _Message(content)


class _Usage:
    def __init__(self, prompt: int, completion: int, total: int) -> None:
        self.prompt_tokens = prompt
        self.completion_tokens = completion
        self.total_tokens = total


class _Response:
    def __init__(self, content: str | None, usage: _Usage | None = None) -> None:
        self.choices = [_Choice(content)]
        self.usage = usage or _Usage(11, 22, 33)


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


def test_groq_extracts_json_without_reasoning():
    client = _StubClient([json.dumps(VALID_PAYLOAD)])
    provider = GroqLLMProvider(api_key="gsk-test", client=client)

    case = provider.extract_case("Charged twice.")

    assert isinstance(case, ComplaintCase)
    kwargs = client.completions.calls[0]
    assert kwargs["model"] == "qwen/qwen3.8-27b"
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["reasoning_effort"] == "none"
    assert provider.token_usage.as_dict() == {
        "calls": 1,
        "prompt_tokens": 11,
        "completion_tokens": 22,
        "total_tokens": 33,
    }


def test_factory_groq_honors_model_override():
    settings = Settings(
        llm_provider="groq",
        groq_api_key="gsk-test",
        model_name="llama-3.1-8b-instant",
    )
    provider = create_provider(settings)
    assert isinstance(provider, GroqLLMProvider)
    assert provider.model_name == "llama-3.1-8b-instant"
