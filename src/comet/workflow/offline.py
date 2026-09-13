"""Sequential mock-mode pipeline: ingest, extract, write artifacts and CSV."""

from datetime import datetime, timezone
from pathlib import Path

from comet.ids import build_document_id
from comet.ingestion import ingest_directory
from comet.llm.base import LLMProvider
from comet.models import DocumentResult, ProcessingStatus
from comet.reporting import write_final_report
from comet.services.artifact_service import (
    artifacts_exist,
    ensure_output_dirs,
    write_success_artifacts,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def run_offline_pipeline(
    input_dir: Path,
    output_dir: Path,
    provider: LLMProvider,
    overwrite: bool = False,
) -> tuple[list[DocumentResult], Path]:
    """Process a mixed directory with a mock (or any) provider, no parallelism."""
    ensure_output_dirs(output_dir)
    results: list[DocumentResult] = []

    for item in ingest_directory(input_dir):
        source = Path(item.source_file)
        doc_id = build_document_id(source, input_dir)
        started = utcnow()

        if item.status == "skipped":
            results.append(
                DocumentResult(
                    source_file=item.source_file,
                    document_id=doc_id,
                    status=ProcessingStatus.SKIPPED,
                    error_code=item.error_code,
                    error_message=item.error_code,
                    started_at=started,
                    completed_at=utcnow(),
                )
            )
            continue

        if item.status != "extracted" or not item.text:
            results.append(
                DocumentResult(
                    source_file=item.source_file,
                    document_id=doc_id,
                    status=ProcessingStatus.FAILED,
                    error_code=item.error_code,
                    error_message=item.error_code,
                    started_at=started,
                    completed_at=utcnow(),
                )
            )
            continue

        if artifacts_exist(output_dir, doc_id) and not overwrite:
            results.append(
                DocumentResult(
                    source_file=item.source_file,
                    document_id=doc_id,
                    status=ProcessingStatus.FAILED,
                    error_code="ARTIFACTS_EXIST",
                    error_message="Matching artifacts already exist; pass --overwrite",
                    started_at=started,
                    completed_at=utcnow(),
                )
            )
            continue

        try:
            case = provider.extract_case(item.text)
            email_md = provider.generate_customer_email(case)
            summary_md = provider.generate_case_summary(case)
            paths = write_success_artifacts(
                output_dir,
                doc_id,
                item.source_file,
                case,
                email_md,
                summary_md,
            )
        except Exception as exc:
            results.append(
                DocumentResult(
                    source_file=item.source_file,
                    document_id=doc_id,
                    status=ProcessingStatus.FAILED,
                    error_code="OFFLINE_PIPELINE_ERROR",
                    error_message=type(exc).__name__,
                    started_at=started,
                    completed_at=utcnow(),
                )
            )
            continue

        results.append(
            DocumentResult(
                source_file=item.source_file,
                document_id=doc_id,
                status=ProcessingStatus.SUCCESS,
                case=case,
                customer_email_path=str(paths["email"]),
                case_summary_path=str(paths["summary"]),
                structured_data_path=str(paths["structured"]),
                started_at=started,
                completed_at=utcnow(),
            )
        )

    report_path = write_final_report(output_dir / "final_report.csv", results)
    return results, report_path
