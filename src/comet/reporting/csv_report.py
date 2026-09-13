"""UTF-8 CSV report of every discovered document."""

import csv
from io import StringIO
from pathlib import Path

from comet.models import DocumentResult
from comet.services.artifact_service import write_text_atomic

CSV_COLUMNS = [
    "document_id",
    "source_file",
    "status",
    "customer_name",
    "complaint_category",
    "is_complaint",
    "escalation_required",
    "overall_case_status",
    "email_generated",
    "summary_generated",
    "error_code",
    "processed_at",
]


def _bool_cell(value: bool | None) -> str:
    if value is None:
        return ""
    return "true" if value else "false"


def _row(result: DocumentResult) -> dict[str, str]:
    case = result.case
    processed = result.completed_at or result.started_at
    return {
        "document_id": result.document_id,
        "source_file": result.source_file,
        "status": result.status.value,
        "customer_name": (case.customer_name or "") if case else "",
        "complaint_category": case.complaint_category.value if case else "",
        "is_complaint": _bool_cell(case.is_complaint if case else None),
        "escalation_required": _bool_cell(
            case.escalation_required if case else None
        ),
        "overall_case_status": case.overall_case_status.value if case else "",
        "email_generated": _bool_cell(result.customer_email_path is not None),
        "summary_generated": _bool_cell(result.case_summary_path is not None),
        "error_code": result.error_code or "",
        "processed_at": processed.isoformat(),
    }


def write_final_report(path: Path, results: list[DocumentResult]) -> Path:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for result in results:
        writer.writerow(_row(result))
    write_text_atomic(path, buffer.getvalue())
    return path
