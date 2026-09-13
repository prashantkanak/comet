"""Deterministic IDs, mock provider, and artifact/CSV writes."""

import json
from pathlib import Path

from comet.ids import build_document_id
from comet.llm import MockLLMProvider
from comet.models import ComplaintCategory, ProcessingStatus
from comet.reporting import CSV_COLUMNS
from comet.services.artifact_service import write_text_atomic
from comet.workflow import run_offline_pipeline


def test_document_id_is_stable_and_avoids_stem_collisions(tmp_path):
    root = tmp_path
    pdf = tmp_path / "complaint.pdf"
    docx = tmp_path / "complaint.docx"
    pdf.write_text("a")
    docx.write_text("b")
    first = build_document_id(pdf, root)
    assert build_document_id(pdf, root) == first
    assert build_document_id(docx, root) != first
    assert first.startswith("complaint_")


def test_mock_provider_validates_and_does_not_invent_contact():
    provider = MockLLMProvider()
    case = provider.extract_case("The package never arrived and tracking says delivered.")
    assert case.complaint_category is ComplaintCategory.DELIVERY
    assert case.email is None
    assert case.phone_number is None
    email = provider.generate_customer_email(case)
    summary = provider.generate_case_summary(case)
    assert "package never arrived" in email
    assert "## Overview" in summary
    assert "## Issue" in summary
    assert "## Action" in summary
    assert "## Status" in summary
    assert "## Next action" in summary
    assert "refund" not in email.lower() or "does not confirm" in email.lower()


def test_atomic_write_replaces_target(tmp_path):
    path = tmp_path / "note.txt"
    write_text_atomic(path, "one")
    write_text_atomic(path, "two")
    assert path.read_text() == "two"
    assert not list(tmp_path.glob("*.tmp"))


def test_offline_pipeline_writes_json_markdown_csv(tmp_path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    (input_dir / "ok.txt").write_text(
        "Customer: Jane Doe\nFrom: Jane Doe <jane.doe@example.com>\n"
        "I was charged twice on my invoice.\n"
    )
    (input_dir / "empty.txt").write_text("   ")
    (input_dir / "notes.csv").write_text("a,b")

    results, report = run_offline_pipeline(
        input_dir, output_dir, MockLLMProvider(), overwrite=True
    )
    by_name = {Path(item.source_file).name: item for item in results}

    success = by_name["ok.txt"]
    assert success.status is ProcessingStatus.SUCCESS
    assert success.case is not None
    assert success.case.email == "jane.doe@example.com"
    structured = Path(success.structured_data_path)
    payload = json.loads(structured.read_text())
    assert payload["document_id"] == success.document_id
    assert payload["case"]["issue_description"]
    assert Path(success.customer_email_path).read_text().startswith("# Subject:")
    assert "## Next action" in Path(success.case_summary_path).read_text()

    assert by_name["empty.txt"].status is ProcessingStatus.FAILED
    assert by_name["empty.txt"].structured_data_path is None
    assert by_name["notes.csv"].status is ProcessingStatus.SKIPPED

    text = report.read_text(encoding="utf-8")
    header = text.splitlines()[0]
    assert header.split(",") == CSV_COLUMNS
    assert "success" in text
    assert "failed" in text
    assert "skipped" in text
    assert len(text.splitlines()) == 1 + len(results)


def test_overwrite_false_blocks_existing_artifacts(tmp_path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    (input_dir / "ok.txt").write_text("Delivery is late.")
    run_offline_pipeline(input_dir, output_dir, MockLLMProvider(), overwrite=True)
    again, _ = run_offline_pipeline(
        input_dir, output_dir, MockLLMProvider(), overwrite=False
    )
    assert again[0].status is ProcessingStatus.FAILED
    assert again[0].error_code == "ARTIFACTS_EXIST"
