"""Atomic artifact writes for structured cases, emails, and summaries."""

import json
from pathlib import Path

from comet.models import ComplaintCase

STRUCTURED_DIR = "structured_data"
EMAIL_DIR = "customer_emails"
SUMMARY_DIR = "case_summaries"


def ensure_output_dirs(output_dir: Path) -> None:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    for name in (STRUCTURED_DIR, EMAIL_DIR, SUMMARY_DIR):
        (root / name).mkdir(parents=True, exist_ok=True)


def write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def write_text_atomic(path: Path, text: str) -> None:
    write_bytes_atomic(path, text.encode("utf-8"))


def artifact_paths(output_dir: Path, document_id: str) -> dict[str, Path]:
    root = Path(output_dir)
    return {
        "structured": root / STRUCTURED_DIR / f"{document_id}.json",
        "email": root / EMAIL_DIR / f"{document_id}.md",
        "summary": root / SUMMARY_DIR / f"{document_id}.md",
    }


def artifacts_exist(output_dir: Path, document_id: str) -> bool:
    return any(path.exists() for path in artifact_paths(output_dir, document_id).values())


def write_success_artifacts(
    output_dir: Path,
    document_id: str,
    source_file: str,
    case: ComplaintCase,
    email_markdown: str,
    summary_markdown: str,
) -> dict[str, Path]:
    """Write JSON + both Markdown drafts together. Callers must treat this as all-or-nothing."""
    paths = artifact_paths(output_dir, document_id)
    payload = {
        "document_id": document_id,
        "source_file": source_file,
        "case": case.model_dump(mode="json"),
    }
    write_text_atomic(
        paths["structured"],
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
    )
    write_text_atomic(paths["email"], email_markdown)
    write_text_atomic(paths["summary"], summary_markdown)
    return paths
