"""Internal case summary from a validated ComplaintCase only."""

import logging

from comet.exceptions import LLMError, SummaryGenerationError
from comet.llm.base import LLMProvider
from comet.models import ComplaintCase

logger = logging.getLogger(__name__)

REQUIRED_SUMMARY_SECTIONS = (
    "## Overview",
    "## Issue",
    "## Action",
    "## Status",
    "## Next action",
)


def has_required_summary_sections(text: str) -> bool:
    lower = text.lower()
    return all(section.lower() in lower for section in REQUIRED_SUMMARY_SECTIONS)


def generate_case_summary(provider: LLMProvider, case: ComplaintCase) -> str:
    """Ask the provider for an internal summary using only the validated case."""
    logger.info("summary_generation_start")
    try:
        draft = provider.generate_case_summary(case)
    except SummaryGenerationError:
        raise
    except LLMError as exc:
        raise SummaryGenerationError("Case summary generation failed") from exc
    except Exception as exc:
        raise SummaryGenerationError("Case summary generation failed") from exc

    if not draft or not draft.strip():
        raise SummaryGenerationError("Case summary generation returned empty text")
    if not has_required_summary_sections(draft):
        raise SummaryGenerationError(
            "Case summary is missing one of: overview, issue, action, status, next action"
        )
    return draft
