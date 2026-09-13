"""Document discovery, loading, and text normalization."""

from comet.ingestion.discovery import SUPPORTED_EXTENSIONS, discover_documents
from comet.ingestion.loaders import load_document
from comet.ingestion.runner import IngestResult, ingest_directory
from comet.ingestion.text_normalizer import normalize_text

__all__ = [
    "SUPPORTED_EXTENSIONS",
    "IngestResult",
    "discover_documents",
    "ingest_directory",
    "load_document",
    "normalize_text",
]
