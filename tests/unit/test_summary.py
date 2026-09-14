"""Internal summary service tests — five required sections, case JSON only."""

import pytest

from comet.exceptions import SummaryGenerationError
from comet.llm import MockLLMProvider, OpenAILLMProvider
from comet.llm.prompts import SUMMARY_SYSTEM, summary_user_message
from comet.models import ComplaintCase
from comet.services.summary_service import (
    REQUIRED_SUMMARY_SECTIONS,
    generate_case_summary,
)
from comet.workflow import run_offline_pipeline


def _case(**overrides) -> ComplaintCase:
    payload = {
        "issue_description": "Charged twice for one month.",
        "is_complaint": True,
        "escalation_required": False,
        "supporting_document_available": False,
        "complaint_category": "billing",
        "overall_case_status": "open",
        "resolution_provided": None,
    }
    payload.update(overrides)
    return ComplaintCase.model_validate(payload)


def test_summary_prompt_requires_five_sections_and_case_json_only():
    for heading in REQUIRED_SUMMARY_SECTIONS:
        assert heading in SUMMARY_SYSTEM
    assert "unknown" in SUMMARY_SYSTEM.lower()
    user = summary_user_message(_case(customer_name=None, resolution_provided=None))
    assert "<<<CASE_JSON>>>" in user
    assert "<<<DOCUMENT>>>" not in user
    assert '"resolution_provided": null' in user


def test_mock_summary_has_required_sections_and_labels_missing_action():
    draft = generate_case_summary(MockLLMProvider(), _case(customer_name=None))
    for heading in REQUIRED_SUMMARY_SECTIONS:
        assert heading in draft
    assert "Charged twice for one month." in draft
    assert "Unknown / not provided" in draft
    assert "@" not in draft


def test_mock_summary_escalation_next_action():
    draft = generate_case_summary(
        MockLLMProvider(), _case(escalation_required=True)
    )
    assert "Escalate" in draft


def test_summary_service_rejects_missing_section():
    class Incomplete:
        def extract_case(self, document_text, *, repair=False):
            raise AssertionError("summary service must not extract")

        def generate_customer_email(self, case):
            del case
            return "email"

        def generate_case_summary(self, case):
            del case
            return "# Case summary\n\n## Overview\nOnly this.\n"

    with pytest.raises(SummaryGenerationError) as exc:
        generate_case_summary(Incomplete(), _case())
    assert exc.value.error_code == "SUMMARY_GENERATION_ERROR"


def test_openai_summary_sends_case_json_not_source_document():
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
        "# Case summary\n\n"
        "## Overview\nUnknown / billing\n\n"
        "## Issue\nCharged twice for one month.\n\n"
        "## Action\nUnknown / not provided in the case record\n\n"
        "## Status\nopen\n\n"
        "## Next action\nReview draft and assign an owner\n"
    )
    client = _StubClient([draft_text])
    provider = OpenAILLMProvider(api_key="sk-test", client=client)
    result = generate_case_summary(provider, _case())
    assert "## Next action" in result
    kwargs = client.completions.calls[0]
    assert kwargs["messages"][0]["content"] == SUMMARY_SYSTEM
    user = kwargs["messages"][1]["content"]
    assert "<<<CASE_JSON>>>" in user
    assert kwargs.get("response_format") is None


def test_pipeline_summary_failure_writes_no_success_artifacts(tmp_path):
    class ExtractAndEmailOkSummaryFails:
        def extract_case(self, document_text, *, repair=False):
            del document_text, repair
            return _case()

        def generate_customer_email(self, case):
            del case
            return "# Subject: ok\n\nDear Customer,\n"

        def generate_case_summary(self, case):
            del case
            return "not a real summary"

    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    (input_dir / "ok.txt").write_text("Charged twice on my invoice.")
    results, _report = run_offline_pipeline(
        input_dir, output_dir, ExtractAndEmailOkSummaryFails(), overwrite=True
    )
    assert results[0].error_code == "SUMMARY_GENERATION_ERROR"
    assert results[0].case_summary_path is None
    assert list((output_dir / "case_summaries").glob("*.md")) == []
    assert list((output_dir / "structured_data").glob("*.json")) == []
    assert list((output_dir / "customer_emails").glob("*.md")) == []
