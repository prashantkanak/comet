"""Discover eligible complaint documents in an input directory."""

from pathlib import Path

SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx"}


def discover_documents(input_dir: Path) -> tuple[list[Path], list[Path]]:
    """Return sorted eligible files and unsupported files under input_dir.

    Hidden files (names starting with '.') are ignored. Directories are walked
    recursively so a mixed `data/` tree is one scan.
    """
    root = Path(input_dir)
    eligible: list[Path] = []
    unsupported: list[Path] = []

    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if path.name.startswith("."):
            continue
        if path.suffix.lower() in SUPPORTED_EXTENSIONS:
            eligible.append(path)
        else:
            unsupported.append(path)

    return eligible, unsupported
