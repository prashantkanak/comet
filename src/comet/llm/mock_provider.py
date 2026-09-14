"""Deterministic offline provider for development and tests."""

import re

from comet.ingestion.scope import is_out_of_scope
from comet.llm.drafts import case_summary_from_case, customer_email_from_case
from comet.models import CaseStatus, ComplaintCase, ComplaintCategory

_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_PHONE = re.compile(r"\+\d[\d\- ]{8,}\d")
_CUSTOMER = re.compile(
    r"(?:customer|from)\s*:\s*([A-Za-z][A-Za-z .'-]{1,80})",
    re.I,
)
_CATEGORY_HINTS = (
    (ComplaintCategory.BILLING, ("invoice", "charg", "refund", "billing", "subscription")),
    (ComplaintCategory.DELIVERY, ("deliver", "package", "shipping", "tracking")),
    (ComplaintCategory.PRODUCT_QUALITY, ("crack", "defect", "quality", "broken", "mug")),
    (ComplaintCategory.SERVICE, ("hold", "callback", "service", "ticket")),
    (ComplaintCategory.ACCOUNT_ACCESS, ("login", "password", "account access", "locked out")),
)


class MockLLMProvider:
    """Return validated case data derived only from supplied text/fields."""

    model_name = "mock"

    def extract_case(self, document_text: str, *, repair: bool = False) -> ComplaintCase:
        del repair
        lower = document_text.lower()
        category = ComplaintCategory.UNKNOWN
        for candidate, hints in _CATEGORY_HINTS:
            if any(hint in lower for hint in hints):
                category = candidate
                break

        email_match = _EMAIL.search(document_text)
        phone_match = _PHONE.search(document_text)
        name_match = _CUSTOMER.search(document_text)

        payload = {
            "customer_name": name_match.group(1).strip() if name_match else None,
            "email": email_match.group(0) if email_match else None,
            "phone_number": phone_match.group(0) if phone_match else None,
            "complaint_category": category,
            "issue_description": document_text[:1000],
            "resolution_provided": None,
            "is_complaint": not is_out_of_scope(document_text),
            "escalation_required": any(
                token in lower for token in ("urgent", "second", "never received")
            ),
            "supporting_document_available": any(
                token in lower for token in ("attach", "photo", "enclosed")
            ),
            "overall_case_status": CaseStatus.OPEN,
        }
        return ComplaintCase.model_validate(payload)

    def generate_customer_email(self, case: ComplaintCase) -> str:
        return customer_email_from_case(case)

    def generate_case_summary(self, case: ComplaintCase) -> str:
        return case_summary_from_case(case)
