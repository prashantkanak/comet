"""Normalize extracted document text before downstream use."""

import re

_MULTI_SPACE = re.compile(r"[ \t]+")
_MULTI_BLANK = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    """Strip control junk, unify newlines, and collapse extra whitespace."""
    cleaned = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [_MULTI_SPACE.sub(" ", line).strip() for line in cleaned.split("\n")]
    return _MULTI_BLANK.sub("\n\n", "\n".join(lines)).strip()
