"""Batch orchestration: sequential documents, CSV, run manifest, continuation."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from comet.ids import build_document_id
from comet.ingestion.discovery import discover_documents
from comet.llm.base import LLMProvider
from comet.models import DocumentResult, ProcessingStatus
from comet.reporting import count_results, write_final_report, write_run_manifest
from comet.services.artifact_service import ensure_output_dirs
from comet.workflow.processor import DocumentProcessor

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BatchRunSummary:
    results: list[DocumentResult]
    report_path: Path
    manifest_path: Path
    started_at: datetime
    completed_at: datetime
    counts: dict[str, int]


class BatchProcessor:
    """Discover inputs, process each file, write report + manifest."""

    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        provider: LLMProvider,
        *,
        overwrite: bool = False,
        max_attempts: int = 2,
        llm_provider: str = "mock",
        model_name: str | None = None,
    ) -> None:
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.provider = provider
        self.overwrite = overwrite
        self.max_attempts = max_attempts
        self.llm_provider = llm_provider
        self.model_name = model_name or getattr(provider, "model_name", None)

    def run(self) -> BatchRunSummary:
        started_at = datetime.now(timezone.utc)
        logger.info(
            "batch_start provider=%s model=%s input=%s output=%s overwrite=%s",
            self.llm_provider,
            self.model_name or "",
            self.input_dir,
            self.output_dir,
            self.overwrite,
        )
        ensure_output_dirs(self.output_dir)
        eligible, unsupported = discover_documents(self.input_dir)
        paths = sorted(eligible + unsupported, key=lambda path: str(path))
        logger.info(
            "batch_discovered total=%s eligible=%s unsupported=%s",
            len(paths),
            len(eligible),
            len(unsupported),
        )

        results: list[DocumentResult] = []
        with DocumentProcessor(
            self.input_dir,
            self.output_dir,
            self.provider,
            overwrite=self.overwrite,
            max_attempts=self.max_attempts,
        ) as processor:
            for path in paths:
                try:
                    results.append(processor.process(path))
                except Exception:
                    doc_id = build_document_id(path, self.input_dir)
                    logger.exception(
                        "batch_item_unexpected document_id=%s file=%s",
                        doc_id,
                        path.name,
                    )
                    now = datetime.now(timezone.utc)
                    results.append(
                        DocumentResult(
                            source_file=str(path),
                            document_id=doc_id,
                            status=ProcessingStatus.FAILED,
                            error_code="DOCUMENT_PROCESS_ERROR",
                            error_message="DOCUMENT_PROCESS_ERROR",
                            started_at=now,
                            completed_at=now,
                        )
                    )

        report_path = write_final_report(self.output_dir / "final_report.csv", results)
        completed_at = datetime.now(timezone.utc)
        config = {
            "llm_provider": self.llm_provider,
            "model_name": self.model_name,
            "max_llm_attempts": self.max_attempts,
            "input_dir": str(self.input_dir),
            "output_dir": str(self.output_dir),
            "overwrite": self.overwrite,
        }
        manifest_path = write_run_manifest(
            self.output_dir / "run_manifest.json",
            started_at=started_at,
            completed_at=completed_at,
            config=config,
            results=results,
            report_path=report_path,
        )
        counts = count_results(results)
        logger.info(
            "batch_complete discovered=%s successful=%s failed=%s skipped=%s report=%s",
            counts["discovered"],
            counts["successful"],
            counts["failed"],
            counts["skipped"],
            report_path,
        )
        return BatchRunSummary(
            results=results,
            report_path=report_path,
            manifest_path=manifest_path,
            started_at=started_at,
            completed_at=completed_at,
            counts=counts,
        )
