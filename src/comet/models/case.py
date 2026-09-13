"""Validated complaint/case record produced by structured extraction."""

from pydantic import BaseModel, EmailStr

from comet.models.enums import CaseStatus, ComplaintCategory


class ComplaintCase(BaseModel):
    customer_name: str | None = None
    email: EmailStr | None = None
    phone_number: str | None = None
    complaint_category: ComplaintCategory = ComplaintCategory.UNKNOWN
    issue_description: str
    resolution_provided: str | None = None
    is_complaint: bool
    escalation_required: bool
    supporting_document_available: bool
    overall_case_status: CaseStatus = CaseStatus.UNKNOWN
