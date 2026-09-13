"""Runtime processing result consumed by artifact writing and CSV reporting."""

from datetime import datetime

from pydantic import BaseModel

from comet.models.case import ComplaintCase
from comet.models.enums import ProcessingStatus


class DocumentResult(BaseModel):
    source_file: str
    document_id: str
    status: ProcessingStatus
    case: ComplaintCase | None = None
    customer_email_path: str | None = None
    case_summary_path: str | None = None
    structured_data_path: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
