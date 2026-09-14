"""Tests for the thin Streamlit presentation layer without starting a server."""

from pathlib import Path

import pytest

from comet.exceptions import ConfigurationError
from comet.llm import MockLLMProvider
from comet.ui.app import SAMPLE_DOCUMENTS
from comet.ui.pipeline import (
    build_settings,
    display_report_rows,
    report_rows,
    run_batch,
    stage_upload,
    stage_uploads,
    validate_upload_filename,
)


def test_build_settings_does_not_accept_or_persist_api_keys(tmp_path):
    settings = build_settings(
        str(tmp_path / "in"),
        str(tmp_path / "out"),
        True,
    )
    assert settings.llm_provider == "mock"
    assert settings.input_dir == tmp_path / "in"
    assert settings.output_dir == tmp_path / "out"
    assert settings.model_name is None
    assert "api_key" not in str(settings.public_config()).lower()


def test_sample_documents_cover_each_supported_extension():
    suffixes = {path.suffix.lower() for _label, _title, path, _mime in SAMPLE_DOCUMENTS}
    assert suffixes == {".txt", ".pdf", ".docx"}
    for _label, _title, path, _mime in SAMPLE_DOCUMENTS:
        assert path.is_file(), path


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


def test_stage_uploads_keeps_multiple_files_in_one_folder(tmp_path):
    run_dir = stage_uploads(
        [
            ("case.txt", b"I was charged twice on my invoice."),
            ("notes.docx", b"PK"),
        ],
        tmp_path,
    )
    names = sorted(path.name for path in run_dir.iterdir())
    assert names == ["case.txt", "notes.docx"]


def test_display_report_rows_uses_basename_for_source_file(tmp_path, monkeypatch, capsys):
    staged = stage_upload("case.txt", b"I was charged twice on my invoice.", tmp_path / "tmp")
    settings = build_settings(str(staged.parent), str(tmp_path / "out"), True)
    monkeypatch.setattr("comet.ui.pipeline.create_provider", lambda _settings: MockLLMProvider())
    summary = run_batch(settings)
    logs = capsys.readouterr().err
    assert "request_llm provider=mock" in logs
    assert "credential_set=False" in logs
    displayed = display_report_rows(summary.report_path)
    assert displayed[0]["source_file"] == "case.txt"
    assert "/" not in displayed[0]["source_file"]
    assert "\\" not in displayed[0]["source_file"]
    assert report_rows(summary.report_path)[0]["source_file"].endswith("case.txt")
    staged = stage_upload("case.txt", b"I was charged twice on my invoice.", tmp_path / "tmp")
    settings = build_settings(
        str(staged.parent), str(tmp_path / "out"), True
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
