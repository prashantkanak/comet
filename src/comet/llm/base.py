"""Provider interface used by extraction, email, and summary services."""

from typing import Protocol

from comet.models import ComplaintCase


class LLMProvider(Protocol):
    def extract_case(
        self, document_text: str, *, repair: bool = False
    ) -> ComplaintCase: ...

    def generate_customer_email(self, case: ComplaintCase) -> str: ...

    def generate_case_summary(self, case: ComplaintCase) -> str: ...
