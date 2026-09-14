"""Single-document workflow: extract, then email and summary concurrently."""

import logging
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

from comet.exceptions import (
    EmailGenerationError,
    IngestionError,
    LLMProviderError,
    StructuredOutputValidationError,
    SummaryGenerationError,
)
from comet.ids import build_document_id
from comet.ingestion.discovery import SUPPORTED_EXTENSIONS
from comet.ingestion.loaders import load_document
from comet.llm.base import LLMProvider
from comet.models import ComplaintCase, DocumentResult, ProcessingStatus
from comet.services.artifact_service import artifacts_exist, write_success_artifacts
from comet.services.email_service import generate_customer_email
from comet.services.extraction_service import extract_case
from comet.services.summary_service import generate_case_summary

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _log_complete(result: DocumentResult) -> None:
    duration_ms = 0.0
    if result.completed_at is not None:
        duration_ms = (result.completed_at - result.started_at).total_seconds() * 1000
    logger.info(
        "document_process_complete document_id=%s status=%s error_code=%s duration_ms=%.0f",
        result.document_id,
        result.status.value,
        result.error_code or "",
        duration_ms,
    )


class DocumentProcessor:
    """Owns one document: load → extract → [email || summary] → atomic write."""

    def __init__(
        self,
        input_root: Path,
        output_dir: Path,
        provider: LLMProvider,
        *,
        overwrite: bool = False,
        max_attempts: int = 2,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        self.input_root = Path(input_root)
        self.output_dir = Path(output_dir)
        self.provider = provider
        self.overwrite = overwrite
        self.max_attempts = max_attempts
        self._owns_executor = executor is None
        self._executor = executor or ThreadPoolExecutor(max_workers=2)

    def close(self) -> None:
        if self._owns_executor:
            self._executor.shutdown(wait=True)

    def __enter__(self) -> "DocumentProcessor":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def process(self, path: Path) -> DocumentResult:
        path = Path(path)
        started = _utcnow()
        doc_id = build_document_id(path, self.input_root)
        source = str(path)
        logger.info("document_process_start document_id=%s file=%s", doc_id, path.name)

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return self._finish(
                source,
                doc_id,
                started,
                status=ProcessingStatus.SKIPPED,
                error_code="UNSUPPORTED_FILE_TYPE",
            )

        if artifacts_exist(self.output_dir, doc_id) and not self.overwrite:
            return self._finish(
                source,
                doc_id,
                started,
                error_code="ARTIFACTS_EXIST",
                error_message="Matching artifacts already exist; pass --overwrite",
            )

        try:
            text = load_document(path)
        except IngestionError as exc:
            return self._finish(
                source, doc_id, started, error_code=exc.error_code
            )

        try:
            case = extract_case(
                self.provider, text, max_attempts=self.max_attempts
            )
            email_md, summary_md = self._generate_downstream(case)
            paths = write_success_artifacts(
                self.output_dir,
                doc_id,
                source,
                case,
                email_md,
                summary_md,
            )
        except EmailGenerationError as exc:
            return self._finish(source, doc_id, started, error_code=exc.error_code)
        except SummaryGenerationError as exc:
            return self._finish(source, doc_id, started, error_code=exc.error_code)
        except StructuredOutputValidationError as exc:
            return self._finish(source, doc_id, started, error_code=exc.error_code)
        except LLMProviderError as exc:
            return self._finish(source, doc_id, started, error_code=exc.error_code)
        except Exception as exc:
            return self._finish(
                source,
                doc_id,
                started,
                error_code="DOCUMENT_PROCESS_ERROR",
                error_message=type(exc).__name__,
            )

        result = DocumentResult(
            source_file=source,
            document_id=doc_id,
            status=ProcessingStatus.SUCCESS,
            case=case,
            customer_email_path=str(paths["email"]),
            case_summary_path=str(paths["summary"]),
            structured_data_path=str(paths["structured"]),
            started_at=started,
            completed_at=_utcnow(),
        )
        _log_complete(result)
        return result


    def _generate_downstream(self, case: ComplaintCase) -> tuple[str, str]:
        email_future = self._executor.submit(
            generate_customer_email, self.provider, case
        )
        summary_future = self._executor.submit(
            generate_case_summary, self.provider, case
        )
        wait([email_future, summary_future], return_when=ALL_COMPLETED)

        email_error: Exception | None = None
        summary_error: Exception | None = None
        email_md = ""
        summary_md = ""
        try:
            email_md = email_future.result()
        except Exception as exc:
            email_error = exc
        try:
            summary_md = summary_future.result()
        except Exception as exc:
            summary_error = exc
        if email_error or summary_error:
            raise email_error or summary_error
        return email_md, summary_md

    def _finish(
        self,
        source: str,
        doc_id: str,
        started: datetime,
        *,
        status: ProcessingStatus = ProcessingStatus.FAILED,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> DocumentResult:
        result = DocumentResult(
            source_file=source,
            document_id=doc_id,
            status=status,
            error_code=error_code,
            error_message=error_message or error_code,
            started_at=started,
            completed_at=_utcnow(),
        )
        _log_complete(result)
        return result
