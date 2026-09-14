"""Bounded extraction with one repair/transport retry."""

import logging
import time
from collections.abc import Callable

from comet.exceptions import LLMError, LLMProviderError, StructuredOutputValidationError
from comet.llm.base import LLMProvider
from comet.models import ComplaintCase

logger = logging.getLogger(__name__)


def extract_case(
    provider: LLMProvider,
    document_text: str,
    *,
    max_attempts: int = 2,
    sleep: Callable[[float], None] = time.sleep,
) -> ComplaintCase:
    """Validate structured extraction; retry once on validation or transient errors."""
    attempts = max(1, max_attempts)
    last_error: LLMError | None = None

    for attempt in range(1, attempts + 1):
        repair = attempt > 1
        logger.info(
            "extraction_attempt attempt=%s/%s repair=%s",
            attempt,
            attempts,
            repair,
        )
        try:
            case = provider.extract_case(document_text, repair=repair)
            return ComplaintCase.model_validate(case.model_dump())
        except StructuredOutputValidationError as exc:
            last_error = exc
            logger.warning(
                "extraction_failed category=%s attempt=%s",
                exc.error_code,
                attempt,
            )
        except LLMProviderError as exc:
            last_error = exc
            logger.warning(
                "extraction_failed category=%s attempt=%s transient=%s",
                exc.error_code,
                attempt,
                exc.transient,
            )
            if not exc.transient:
                raise
            if attempt < attempts:
                sleep(2 ** (attempt - 1))
        except Exception as exc:
            wrapped = LLMProviderError(
                "Unexpected provider failure",
                transient=False,
            )
            wrapped.__cause__ = exc
            raise wrapped from exc

    assert last_error is not None
    raise last_error
