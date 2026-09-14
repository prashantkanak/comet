"""Opt-in smoke test against a real OpenAI key. Never run in default CI."""

import os
from pathlib import Path

import pytest

from comet.llm.openai_provider import OpenAILLMProvider
from comet.models import ComplaintCase, ProcessingStatus
from comet.workflow import BatchProcessor

pytestmark = pytest.mark.live


@pytest.mark.skipif(os.getenv("COMET_LIVE_LLM") != "1", reason="set COMET_LIVE_LLM=1")
def test_openai_extracts_sanitized_sample(tmp_path):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY is not set")

    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    (input_dir / "sample.txt").write_text(
        "Customer: Alex Rivera\n"
        "The package for order ORD-1001 never arrived and tracking shows delivered.\n"
    )

    summary = BatchProcessor(
        input_dir,
        output_dir,
        OpenAILLMProvider(api_key=api_key),
        overwrite=True,
        llm_provider="openai",
        model_name="gpt-4o-mini",
    ).run()

    assert summary.counts["discovered"] == 1
    assert summary.counts["successful"] == 1
    result = summary.results[0]
    assert result.status is ProcessingStatus.SUCCESS
    assert isinstance(result.case, ComplaintCase)
    assert result.case.issue_description
    assert Path(result.structured_data_path).is_file()
    assert Path(result.customer_email_path).is_file()
    assert Path(result.case_summary_path).is_file()
    summary_md = Path(result.case_summary_path).read_text()
    assert "## Overview" in summary_md
    assert "## Next action" in summary_md
