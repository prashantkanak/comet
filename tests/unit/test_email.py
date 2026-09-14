"""Customer email service tests — case JSON only, no invented fields."""

import pytest

from comet.exceptions import EmailGenerationError
from comet.llm import MockLLMProvider, OpenAILLMProvider
from comet.llm.prompts import EMAIL_SYSTEM, email_user_message
from comet.models import ComplaintCase
from comet.services.email_service import generate_customer_email
from comet.workflow import run_offline_pipeline


def _case(**overrides) -> ComplaintCase:
    payload = {
        "issue_description": "Charged twice for one month.",
        "is_complaint": True,
        "escalation_required": False,
        "supporting_document_available": False,
        "complaint_category": "billing",
        "overall_case_status": "open",
    }
    payload.update(overrides)
    return ComplaintCase.model_validate(payload)


def test_email_prompt_forbids_invention_and_uses_case_json_only():
    assert "Do not invent" in EMAIL_SYSTEM
    case = _case(customer_name=None, email=None, phone_number=None)
    user = email_user_message(case)
    assert "<<<CASE_JSON>>>" in user
    assert "Charged twice for one month." in user
    assert "<<<DOCUMENT>>>" not in user
    assert '"customer_name": null' in user
    assert '"email": null' in user


def test_mock_email_uses_only_present_case_fields():
    case = _case(customer_name=None, email=None, phone_number=None)
    draft = generate_customer_email(MockLLMProvider(), case)
    assert draft.startswith("# Subject:")
    assert "Dear Customer" in draft
    assert "Charged twice for one month." in draft
    assert "@" not in draft
    assert "555" not in draft
    assert "Jane" not in draft
    assert "$" not in draft or "does not confirm" in draft.lower()


def test_mock_email_includes_known_customer_name():
    case = _case(customer_name="Alex Rivera")
    draft = generate_customer_email(MockLLMProvider(), case)
    assert "Dear Alex Rivera" in draft


def test_email_service_rejects_empty_draft():
    class EmptyEmail:
        def extract_case(self, document_text, *, repair=False):
            raise AssertionError("email service must not extract")

        def generate_customer_email(self, case):
            del case
            return "   "

        def generate_case_summary(self, case):
            del case
            return "summary"

    with pytest.raises(EmailGenerationError) as exc:
        generate_customer_email(EmptyEmail(), _case())
    assert exc.value.error_code == "EMAIL_GENERATION_ERROR"


def test_openai_email_sends_case_json_not_source_document():
    class _Message:
        def __init__(self, content):
            self.content = content

    class _Choice:
        def __init__(self, content):
            self.message = _Message(content)

    class _Response:
        def __init__(self, content):
            self.choices = [_Choice(content)]

    class _Completions:
        def __init__(self, outputs):
            self.outputs = list(outputs)
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return _Response(self.outputs.pop(0))

    class _StubClient:
        def __init__(self, outputs):
            self.completions = _Completions(outputs)
            self.chat = type("Chat", (), {"completions": self.completions})()

    draft_text = (
        "# Subject: We received your billing case\n\n"
        "Dear Customer,\n\nWe recorded: Charged twice for one month.\n"
    )
    client = _StubClient([draft_text])
    provider = OpenAILLMProvider(api_key="sk-test", client=client)
    result = generate_customer_email(provider, _case())
    assert result.startswith("# Subject:")
    kwargs = client.completions.calls[0]
    assert kwargs["messages"][0]["content"] == EMAIL_SYSTEM
    user = kwargs["messages"][1]["content"]
    assert "<<<CASE_JSON>>>" in user
    assert "Charged twice" in user
    assert kwargs.get("response_format") is None


def test_pipeline_email_failure_writes_no_success_artifacts(tmp_path):
    class ExtractOkEmailFails:
        def extract_case(self, document_text, *, repair=False):
            del document_text, repair
            return _case()

        def generate_customer_email(self, case):
            del case
            raise EmailGenerationError("boom")

        def generate_case_summary(self, case):
            del case
            return (
                "# Case summary\n\n## Overview\nok\n\n## Issue\nok\n\n"
                "## Action\nok\n\n## Status\nok\n\n## Next action\nok\n"
            )

    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    (input_dir / "ok.txt").write_text("Charged twice on my invoice.")
    results, _report = run_offline_pipeline(
        input_dir, output_dir, ExtractOkEmailFails(), overwrite=True
    )
    assert results[0].error_code == "EMAIL_GENERATION_ERROR"
    assert results[0].customer_email_path is None
    assert list((output_dir / "customer_emails").glob("*.md")) == []
    assert list((output_dir / "structured_data").glob("*.json")) == []
