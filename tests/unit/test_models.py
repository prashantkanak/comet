"""Domain model unit tests."""

import pytest
from pydantic import ValidationError

from comet.models import CaseStatus, ComplaintCase, ComplaintCategory, ProcessingStatus


def _valid(**overrides):
    payload = {
        "issue_description": "Charged twice for one month.",
        "is_complaint": True,
        "escalation_required": False,
        "supporting_document_available": False,
    }
    payload.update(overrides)
    return payload


def test_valid_case_defaults():
    case = ComplaintCase.model_validate(_valid())
    assert case.customer_name is None
    assert case.email is None
    assert case.complaint_category is ComplaintCategory.UNKNOWN
    assert case.overall_case_status is CaseStatus.UNKNOWN
    assert case.resolution_provided is None


def test_nullable_fields_stay_null():
    case = ComplaintCase.model_validate(
        _valid(customer_name=None, email=None, phone_number=None, resolution_provided=None)
    )
    dumped = case.model_dump()
    assert dumped["email"] is None
    assert dumped["phone_number"] is None


def test_invalid_enum_rejected():
    with pytest.raises(ValidationError):
        ComplaintCase.model_validate(_valid(complaint_category="not-a-category"))


def test_invalid_email_rejected():
    with pytest.raises(ValidationError):
        ComplaintCase.model_validate(_valid(email="not-an-email"))


def test_required_issue_missing():
    payload = _valid()
    del payload["issue_description"]
    with pytest.raises(ValidationError):
        ComplaintCase.model_validate(payload)


def test_processing_status_values():
    assert ProcessingStatus.SUCCESS.value == "success"
    assert ProcessingStatus.FAILED.value == "failed"
    assert ProcessingStatus.SKIPPED.value == "skipped"
