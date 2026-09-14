"""BatchProcessor, run manifest, and 10+ mixed-file counts."""

import csv
import json
from pathlib import Path

import pymupdf
from docx import Document

from comet.config import Settings
from comet.llm import MockLLMProvider
from comet.models import ProcessingStatus
from comet.reporting import CSV_COLUMNS
from comet.workflow import BatchProcessor


def _write_pdf(path: Path, text: str) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def _write_docx(path: Path, text: str) -> None:
    document = Document()
    document.add_paragraph(text)
    document.save(path)


def _mixed_batch(root: Path) -> None:
    """Create 12 mixed files: 7 valid, 3 failed, 2 skipped."""
    _write_pdf(root / "quality.pdf", "The blender lid cracked after one use.")
    _write_docx(root / "hold.docx", "Hold time was 45 minutes. No callback.")
    (root / "billing.txt").write_text("I was charged twice on my invoice.")
    (root / "delivery.txt").write_text(
        "The package never arrived. Tracking says delivered."
    )
    (root / "access.txt").write_text(
        "I am locked out of my account and cannot login."
    )
    (root / "service.txt").write_text(
        "Please call me back about my open service ticket."
    )
    (root / "other.txt").write_text(
        "The website is slow when I try to view my bill."
    )
    (root / "empty.txt").write_text("   ")
    (root / "blank.txt").write_text("\n\n")
    (root / "broken.pdf").write_bytes(b"not a pdf")
    (root / "notes.csv").write_text("id,name\n")
    (root / "photo.png").write_bytes(b"\x89PNG")


def test_batch_of_twelve_mixed_files_has_accurate_counts(tmp_path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    _mixed_batch(input_dir)

    summary = BatchProcessor(
        input_dir,
        output_dir,
        MockLLMProvider(),
        overwrite=True,
        llm_provider="mock",
        model_name="mock",
    ).run()

    assert summary.counts["discovered"] == 12
    assert summary.counts["successful"] == 7
    assert summary.counts["failed"] == 3
    assert summary.counts["skipped"] == 2
    assert summary.counts["discovered"] == (
        summary.counts["successful"]
        + summary.counts["failed"]
        + summary.counts["skipped"]
    )

    rows = list(csv.DictReader(summary.report_path.open(encoding="utf-8")))
    assert list(rows[0].keys()) == CSV_COLUMNS
    assert len(rows) == 12
    by_status: dict[str, int] = {}
    for row in rows:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
    assert by_status["success"] == 7
    assert by_status["failed"] == 3
    assert by_status["skipped"] == 2

    manifest = json.loads(summary.manifest_path.read_text())
    assert manifest["counts"] == summary.counts
    dumped = json.dumps(manifest)
    assert "openai_api_key" not in dumped.lower()
    assert "sk-" not in dumped
    assert manifest["config"]["llm_provider"] == "mock"
    assert len(manifest["results"]) == 12
    names = {Path(item.source_file).name: item for item in summary.results}
    assert names["empty.txt"].status is ProcessingStatus.FAILED
    assert names["notes.csv"].status is ProcessingStatus.SKIPPED
    assert names["billing.txt"].status is ProcessingStatus.SUCCESS


def test_public_config_omits_secrets():
    settings = Settings(llm_provider="openai", openai_api_key="sk-secret")
    dumped = settings.public_config()
    assert "openai_api_key" not in dumped
    assert "sk-secret" not in str(dumped)
