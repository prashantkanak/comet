"""Run ingestion across a directory, isolating per-file failures."""

import logging
from dataclasses import dataclass
from pathlib import Path

from comet.exceptions import IngestionError
from comet.ingestion.discovery import discover_documents
from comet.ingestion.loaders import load_document

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestResult:
    source_file: str
    status: str
    error_code: str | None = None
    char_count: int | None = None
    text: str | None = None


def ingest_directory(input_dir: Path) -> list[IngestResult]:
    """Extract text from every discovered file without stopping the batch."""
    eligible, unsupported = discover_documents(input_dir)
    results: list[IngestResult] = []

    for path in unsupported:
        logger.warning("Skipping unsupported file: %s", path.name)
        results.append(
            IngestResult(
                source_file=str(path),
                status="skipped",
                error_code="UNSUPPORTED_FILE_TYPE",
            )
        )

    for path in eligible:
        try:
            text = load_document(path)
        except IngestionError as exc:
            logger.error("Ingestion failed for %s: %s", path.name, exc.error_code)
            results.append(
                IngestResult(
                    source_file=str(path),
                    status="failed",
                    error_code=exc.error_code,
                )
            )
            continue
        except Exception:
            logger.exception("Unexpected ingestion error for %s", path.name)
            results.append(
                IngestResult(
                    source_file=str(path),
                    status="failed",
                    error_code="DOCUMENT_READ_ERROR",
                )
            )
            continue

        logger.info("Extracted text from %s (%s chars)", path.name, len(text))
        results.append(
            IngestResult(
                source_file=str(path),
                status="extracted",
                char_count=len(text),
                text=text,
            )
        )

    results.sort(key=lambda item: item.source_file)
    return results
