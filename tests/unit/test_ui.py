"""Tests for the thin Streamlit presentation layer without starting a server."""

from pathlib import Path

import pytest

from comet.exceptions import ConfigurationError
from comet.llm import MockLLMProvider
from comet.ui.pipeline import (
    build_settings,
    report_rows,
    run_batch,
    stage_upload,
    validate_upload_filename,
)


def test_build_settings_does_not_accept_or_persist_api_keys(tmp_path):
    settings = build_settings(
        str(tmp_path / "in"),
        str(tmp_path / "out"),
        "mock",
        "",
        2,
        True,
    )
    assert settings.llm_provider == "mock"
    assert settings.input_dir == tmp_path / "in"
    assert settings.output_dir == tmp_path / "out"
    assert settings.model_name is None
    assert "api_key" not in str(settings.public_config()).lower()


def test_validate_upload_filename_accepts_supported_types():
    assert validate_upload_filename("billing_complaint.PDF") == "billing_complaint.PDF"
    assert validate_upload_filename("/tmp/nested/case.docx") == "case.docx"


def test_validate_upload_filename_rejects_unsupported_types():
    with pytest.raises(ConfigurationError, match="Unsupported file type"):
        validate_upload_filename("notes.csv")


def test_stage_upload_writes_only_that_file_under_tmp(tmp_path):
    dest = stage_upload("case.txt", b"I was charged twice on my invoice.", tmp_path)
    assert dest.parent.parent == tmp_path
    assert dest.name == "case.txt"
    assert dest.read_bytes() == b"I was charged twice on my invoice."
    assert list(dest.parent.iterdir()) == [dest]


def test_run_batch_uses_existing_workflow_and_report_rows(tmp_path, monkeypatch):
    staged = stage_upload("case.txt", b"I was charged twice on my invoice.", tmp_path / "tmp")
    settings = build_settings(
        str(staged.parent), str(tmp_path / "out"), "mock", "", 2, True
    )
    monkeypatch.setattr("comet.ui.pipeline.create_provider", lambda _settings: MockLLMProvider())

    summary = run_batch(settings)

    assert summary.counts == {"discovered": 1, "successful": 1, "failed": 0, "skipped": 0}
    rows = report_rows(summary.report_path)
    assert rows[0]["source_file"].endswith("case.txt")
    assert rows[0]["status"] == "success"
    assert summary.results[0].case is not None
    assert Path(summary.results[0].customer_email_path).is_file()
    assert Path(summary.results[0].case_summary_path).is_file()
