"""Reject prompt-injection and off-task documents before complaint processing."""

import re

NOT_A_COMPLAINT_CODE = "NOT_A_COMPLAINT"
NOT_A_COMPLAINT_MESSAGE = (
    "Rejected: this file is not a customer complaint. "
    "COMET only extracts complaint cases and does not follow instructions "
    "in uploaded documents."
)

_INJECTION = (
    r"ignore (all )?(previous|prior|above) (instructions|prompts)",
    r"disregard (the )?(system|previous) (prompt|instructions)",
    r"you are now",
    r"reveal your (system |hidden )?prompt",
    r"jailbreak",
    r"system prompt",
)
_OFF_TASK = (
    r"write (me )?(a |some )?(python |javascript |java |rust )?code",
    r"implement (a |an )",
    r"solve this (leetcode|algorithm|puzzle)",
    r"act as (a )?(linux |hacker|shell)",
)
_COMPLAINT = (
    "complaint",
    "refund",
    "invoice",
    "charged",
    "delivery",
    "order",
    "package",
    "billing",
    "account",
    "ticket",
    "customer",
    "broken",
    "defective",
    "warranty",
    "subscription",
    "never arrived",
    "late delivery",
)


def is_out_of_scope(text: str) -> bool:
    """True when the text is a jailbreak or unrelated task, not a complaint."""
    lower = text.lower()
    has_complaint = any(hint in lower for hint in _COMPLAINT)
    if has_complaint:
        return False
    injection = any(re.search(pattern, lower) for pattern in _INJECTION)
    off_task = any(re.search(pattern, lower) for pattern in _OFF_TASK)
    return injection or off_task
