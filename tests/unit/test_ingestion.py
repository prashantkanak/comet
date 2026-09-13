"""Ingestion unit tests for discovery, loaders, and failure isolation."""

from pathlib import Path

import pymupdf
import pytest
from docx import Document

from comet.exceptions import (
    DocumentReadError,
    EmptyDocumentError,
    UnsupportedDocumentError,
)
from comet.ingestion import (
    discover_documents,
    ingest_directory,
    load_document,
    normalize_text,
)


def _write_pdf(path: Path, text: str) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def _write_docx(path: Path, paragraphs: list[str]) -> None:
    doc = Document()
    for paragraph in paragraphs:
        doc.add_paragraph(paragraph)
    doc.save(path)


def test_normalize_text_collapses_whitespace():
    raw = "Hello   world\r\n\r\n\r\n\x00Next"
    assert normalize_text(raw) == "Hello world\n\nNext"


def test_discover_documents_sorts_and_splits(tmp_path):
    (tmp_path / "b.TXT").write_text("two")
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "c.docx").write_bytes(b"pk")
    (tmp_path / "notes.csv").write_text("id,name")
    (tmp_path / ".hidden.txt").write_text("ignore")

    eligible, unsupported = discover_documents(tmp_path)
    names = [p.name for p in eligible]
    assert names == ["a.pdf", "b.TXT", "c.docx"]
    assert [p.name for p in unsupported] == ["notes.csv"]


def test_load_txt(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("  billed twice  \n\n")
    assert load_document(path) == "billed twice"


def test_load_pdf_and_docx(tmp_path):
    pdf = tmp_path / "quality.pdf"
    _write_pdf(pdf, "The blender lid cracked after one use.")
    docx = tmp_path / "service.docx"
    _write_docx(docx, ["Hold time was 45 minutes.", "No callback."])

    assert "blender lid" in load_document(pdf)
    text = load_document(docx)
    assert "Hold time was 45 minutes." in text
    assert "No callback." in text


def test_unsupported_suffix(tmp_path):
    path = tmp_path / "photo.png"
    path.write_bytes(b"\x89PNG")
    with pytest.raises(UnsupportedDocumentError) as exc:
        load_document(path)
    assert exc.value.error_code == "UNSUPPORTED_FILE_TYPE"


def test_empty_txt(tmp_path):
    path = tmp_path / "blank.txt"
    path.write_text("   \n\n")
    with pytest.raises(EmptyDocumentError) as exc:
        load_document(path)
    assert exc.value.error_code == "EMPTY_DOCUMENT"


def test_empty_or_scanned_pdf(tmp_path):
    path = tmp_path / "scan.pdf"
    _write_pdf(path, "")
    with pytest.raises(EmptyDocumentError) as exc:
        load_document(path)
    assert exc.value.error_code == "EMPTY_OR_SCANNED_PDF"


def test_corrupt_pdf(tmp_path):
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"not a pdf")
    with pytest.raises(DocumentReadError) as exc:
        load_document(path)
    assert exc.value.error_code == "DOCUMENT_READ_ERROR"


def test_ingest_directory_continues_after_failures(tmp_path):
    _write_pdf(tmp_path / "ok.pdf", "Package arrived crushed.")
    (tmp_path / "good.txt").write_text("Wrong amount charged.")
    (tmp_path / "empty.txt").write_text("   ")
    (tmp_path / "broken.pdf").write_bytes(b"not a pdf")
    (tmp_path / "notes.csv").write_text("a,b")

    results = ingest_directory(tmp_path)
    by_name = {Path(item.source_file).name: item for item in results}

    assert by_name["ok.pdf"].status == "extracted"
    assert by_name["good.txt"].status == "extracted"
    assert by_name["empty.txt"].status == "failed"
    assert by_name["empty.txt"].error_code == "EMPTY_DOCUMENT"
    assert by_name["broken.pdf"].status == "failed"
    assert by_name["broken.pdf"].error_code == "DOCUMENT_READ_ERROR"
    assert by_name["notes.csv"].status == "skipped"
    assert by_name["notes.csv"].error_code == "UNSUPPORTED_FILE_TYPE"
    assert len(results) == 5
