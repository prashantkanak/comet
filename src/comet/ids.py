"""Deterministic document identifiers."""

import hashlib
import re
from pathlib import Path

_NON_ALNUM = re.compile(r"[^a-zA-Z0-9]+")


def build_document_id(path: Path, input_root: Path) -> str:
    """Sanitize the file stem and append a short hash of the relative path."""
    resolved = Path(path).resolve()
    root = Path(input_root).resolve()
    try:
        relative = resolved.relative_to(root).as_posix()
    except ValueError:
        relative = resolved.name

    stem = _NON_ALNUM.sub("_", Path(path).stem).strip("_").lower() or "document"
    stem = stem[:40]
    digest = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:8]
    return f"{stem}_{digest}"
