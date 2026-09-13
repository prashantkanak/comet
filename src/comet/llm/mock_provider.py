"""Deterministic offline provider for development and tests."""

import re

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

    def extract_case(self, document_text: str) -> ComplaintCase:
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
            "is_complaint": True,
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
        name = case.customer_name or "Customer"
        return (
            f"# Subject: We received your {case.complaint_category.value} case\n\n"
            f"Dear {name},\n\n"
            "Thank you for contacting us. We have recorded the following issue "
            "from your message:\n\n"
            f"{case.issue_description}\n\n"
            f"Current status: {case.overall_case_status.value}\n"
            f"Escalation flagged: {'yes' if case.escalation_required else 'no'}\n\n"
            "This is a draft for human review. It does not confirm dates, refunds, "
            "policies, or other commitments.\n\n"
            "Regards,\nCustomer Support\n"
        )

    def generate_case_summary(self, case: ComplaintCase) -> str:
        action = case.resolution_provided or "Unknown / not provided in the case record"
        next_action = (
            "Escalate for human review"
            if case.escalation_required
            else "Review draft and assign an owner"
        )
        name = case.customer_name or "Unknown"
        return (
            "# Case summary\n\n"
            "## Overview\n"
            f"{name} / {case.complaint_category.value} / "
            f"complaint={str(case.is_complaint).lower()}\n\n"
            "## Issue\n"
            f"{case.issue_description}\n\n"
            "## Action\n"
            f"{action}\n\n"
            "## Status\n"
            f"{case.overall_case_status.value}\n\n"
            "## Next action\n"
            f"{next_action}\n"
        )
