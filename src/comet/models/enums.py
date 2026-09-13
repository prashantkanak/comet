"""Enumerations for cases and processing outcomes."""

from enum import Enum


class ComplaintCategory(str, Enum):
    BILLING = "billing"
    DELIVERY = "delivery"
    PRODUCT_QUALITY = "product_quality"
    SERVICE = "service"
    ACCOUNT_ACCESS = "account_access"
    OTHER = "other"
    UNKNOWN = "unknown"


class CaseStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class ProcessingStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
