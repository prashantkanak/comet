"""Run manifest for a batch: config-safe summary and result counts."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from comet.models import DocumentResult, ProcessingStatus
from comet.services.artifact_service import write_text_atomic


def count_results(results: list[DocumentResult]) -> dict[str, int]:
    successful = failed = skipped = 0
    for item in results:
        if item.status is ProcessingStatus.SUCCESS:
            successful += 1
        elif item.status is ProcessingStatus.SKIPPED:
            skipped += 1
        else:
            failed += 1
    return {
        "discovered": len(results),
        "successful": successful,
        "failed": failed,
        "skipped": skipped,
    }


def write_run_manifest(
    path: Path,
    *,
    started_at: datetime,
    completed_at: datetime,
    config: dict[str, Any],
    results: list[DocumentResult],
    report_path: Path,
    token_usage: dict[str, int] | None = None,
) -> Path:
    payload = {
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "config": config,
        "counts": count_results(results),
        "token_usage": token_usage,
        "report_path": str(report_path),
        "results": [
            {
                "document_id": item.document_id,
                "source_file": Path(item.source_file).name,
                "status": item.status.value,
                "error_code": item.error_code,
            }
            for item in results
        ],
    }
    write_text_atomic(path, json.dumps(payload, indent=2) + "\n")
    return path
