"""Customer email draft from a validated ComplaintCase only."""

import logging

from comet.exceptions import EmailGenerationError, LLMError
from comet.llm.base import LLMProvider
from comet.models import ComplaintCase

logger = logging.getLogger(__name__)


def is_valid_email_draft(draft: str) -> bool:
    """Return whether a generated draft has the required subject and body."""
    normalized = draft.strip()
    if not normalized.startswith("# Subject:"):
        return False
    lines = normalized.splitlines()
    subject = lines[0].removeprefix("# Subject:").strip()
    body = "\n".join(lines[1:]).strip()
    return bool(subject and body)


def generate_customer_email(provider: LLMProvider, case: ComplaintCase) -> str:
    """Ask the provider for a draft email using only the validated case."""
    logger.info("email_generation_start")
    try:
        draft = provider.generate_customer_email(case)
    except EmailGenerationError:
        raise
    except LLMError as exc:
        raise EmailGenerationError("Customer email generation failed") from exc
    except Exception as exc:
        raise EmailGenerationError("Customer email generation failed") from exc

    if not draft or not draft.strip():
        raise EmailGenerationError("Customer email generation returned empty text")
    if not is_valid_email_draft(draft):
        raise EmailGenerationError(
            "Customer email must include a '# Subject:' heading and a non-empty body"
        )
    return draft
