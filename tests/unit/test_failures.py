"""Failure-path tests: unreadable files, setup errors, PII-free logs."""

import logging
import os
from pathlib import Path

import pytest

from comet.cli import main
from comet.exceptions import DocumentReadError, LLMProviderError
from comet.ingestion.loaders import load_document
from comet.llm import MockLLMProvider
from comet.models import ComplaintCase, ProcessingStatus
from comet.workflow import BatchProcessor


def test_unreadable_file_is_document_read_error(tmp_path):
    path = tmp_path / "secret.txt"
    path.write_text("hidden complaint about a refund")
    path.chmod(0)
    try:
        if os.access(path, os.R_OK):
            pytest.skip("process can still read chmod 0 files")
        with pytest.raises(DocumentReadError) as exc:
            load_document(path)
        assert exc.value.error_code == "DOCUMENT_READ_ERROR"
    finally:
        path.chmod(0o644)


def test_cli_stops_when_output_path_is_not_a_directory(tmp_path):
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    (input_dir / "ok.txt").write_text("Late delivery of order 12.")
    output_file = tmp_path / "not-a-dir"
    output_file.write_text("blocker")
    assert main(["--input", str(input_dir), "--output", str(output_file)]) == 1


def test_batch_logs_omit_customer_text_and_email(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    (input_dir / "ok.txt").write_text(
        "From: Jane Doe <jane.doe@example.com>\nI was charged twice on my invoice."
    )
    BatchProcessor(
        input_dir, output_dir, MockLLMProvider(), overwrite=True
    ).run()
    text = caplog.text
    assert "jane.doe@example.com" not in text
    assert "charged twice" not in text.lower()
    assert "document_process_complete" in text
    assert "batch_complete" in text


def test_batch_maps_exhausted_transient_llm_error(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "comet.services.extraction_service.time.sleep", lambda _seconds: None
    )
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    (input_dir / "ok.txt").write_text("I was charged twice on my invoice.")
    (input_dir / "notes.csv").write_text("a,b")

    class AlwaysTransient:
        def extract_case(self, document_text, *, repair=False):
            del document_text, repair
            raise LLMProviderError("rate limited", transient=True)

        def generate_customer_email(self, case: ComplaintCase) -> str:
            raise AssertionError("email must not run after extraction failure")

        def generate_case_summary(self, case: ComplaintCase) -> str:
            raise AssertionError("summary must not run after extraction failure")

    summary = BatchProcessor(
        input_dir, output_dir, AlwaysTransient(), overwrite=True, max_attempts=2
    ).run()
    names = {Path(item.source_file).name: item for item in summary.results}
    assert names["ok.txt"].status is ProcessingStatus.FAILED
    assert names["ok.txt"].error_code == "LLM_PROVIDER_ERROR"
    assert names["ok.txt"].error_message == "rate limited"
    assert names["notes.csv"].status is ProcessingStatus.SKIPPED
    assert summary.counts["discovered"] == 2
