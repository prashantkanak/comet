"""Load text from supported document types."""

from pathlib import Path

import pymupdf
from docx import Document

from comet.exceptions import (
    DocumentReadError,
    EmptyDocumentError,
    UnsupportedDocumentError,
)
from comet.ingestion.discovery import SUPPORTED_EXTENSIONS
from comet.ingestion.text_normalizer import normalize_text


def load_document(path: Path) -> str:
    """Extract and normalize text from a TXT, PDF, or DOCX file.

    Raises:
        UnsupportedDocumentError: suffix is not a supported type.
        DocumentReadError: file is missing, corrupt, or unreadable.
        EmptyDocumentError: no usable text after extraction/normalization.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise UnsupportedDocumentError(
            f"Unsupported file type: {path.name}",
        )

    try:
        raw = _extract_raw(path, suffix)
    except (EmptyDocumentError, UnsupportedDocumentError):
        raise
    except Exception as exc:
        raise DocumentReadError(
            f"Could not read document: {path.name}",
        ) from exc

    text = normalize_text(raw)
    if not text:
        if suffix == ".pdf":
            raise EmptyDocumentError(
                f"No extractable text in PDF (empty or scanned): {path.name}",
                error_code="EMPTY_OR_SCANNED_PDF",
            )
        raise EmptyDocumentError(f"Document is empty: {path.name}")
    return text


def _extract_raw(path: Path, suffix: str) -> str:
    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".pdf":
        return _load_pdf(path)
    return _load_docx(path)


def _load_pdf(path: Path) -> str:
    document = pymupdf.open(path)
    try:
        pages = [page.get_text() for page in document]
    finally:
        document.close()
    return "\n".join(pages)


def _load_docx(path: Path) -> str:
    document = Document(path)
    return "\n".join(paragraph.text for paragraph in document.paragraphs)
