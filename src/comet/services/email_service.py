"""Customer email draft from a validated ComplaintCase only."""

import logging

from comet.exceptions import EmailGenerationError, LLMError
from comet.llm.base import LLMProvider
from comet.models import ComplaintCase

logger = logging.getLogger(__name__)


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
    return draft
