"""Mock Markdown drafts from a validated case only."""

from comet.models import ComplaintCase


def customer_email_from_case(case: ComplaintCase) -> str:
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


def case_summary_from_case(case: ComplaintCase) -> str:
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
