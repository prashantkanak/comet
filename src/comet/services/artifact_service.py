"""Atomic artifact writes for structured cases, emails, and summaries."""

import json
from pathlib import Path
from uuid import uuid4

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


def _stage_bytes(path: Path, data: bytes) -> Path:
    """Write a private staging file beside its eventual destination."""
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    staged.write_bytes(data)
    return staged


def _unlink_if_present(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _publish_staged_files(staged: dict[Path, Path]) -> None:
    """Publish a set of staged files, restoring the prior set if commit fails.

    A filesystem cannot atomically rename files in three separate directories as
    one operation. This compensating transaction guarantees that a failed
    publish does not leave a mixture of newly published and prior artifacts.
    """
    backups: dict[Path, Path] = {}
    committed: set[Path] = set()
    published = False
    try:
        for final in staged:
            if final.exists():
                backup = final.with_name(f".{final.name}.{uuid4().hex}.bak")
                final.replace(backup)
                backups[final] = backup

        for final, stage in staged.items():
            stage.replace(final)
            committed.add(final)
        published = True
    except Exception:
        for final in committed:
            _unlink_if_present(final)
        for final, backup in backups.items():
            if backup.exists():
                backup.replace(final)
        raise
    finally:
        for stage in staged.values():
            _unlink_if_present(stage)
        if published:
            for backup in backups.values():
                _unlink_if_present(backup)


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
    """Publish JSON and Markdown artifacts as a recoverable set."""
    paths = artifact_paths(output_dir, document_id)
    payload = {
        "document_id": document_id,
        "source_file": source_file,
        "case": case.model_dump(mode="json"),
    }
    staged = {
        paths["structured"]: _stage_bytes(
            paths["structured"],
            (json.dumps(payload, indent=2, ensure_ascii=True) + "\n").encode("utf-8"),
        ),
        paths["email"]: _stage_bytes(paths["email"], email_markdown.encode("utf-8")),
        paths["summary"]: _stage_bytes(
            paths["summary"], summary_markdown.encode("utf-8")
        ),
    }
    _publish_staged_files(staged)
    return paths
