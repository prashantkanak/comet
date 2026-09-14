"""DocumentProcessor: extraction before downstream, concurrent email/summary."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from comet.models import ComplaintCase, ProcessingStatus
from comet.services.artifact_service import ensure_output_dirs
from comet.workflow import DocumentProcessor


def _case() -> ComplaintCase:
    return ComplaintCase.model_validate(
        {
            "issue_description": "Charged twice for one month.",
            "is_complaint": True,
            "escalation_required": False,
            "supporting_document_available": False,
            "complaint_category": "billing",
            "overall_case_status": "open",
        }
    )


class _ConcurrentProvider:
    def __init__(self) -> None:
        self.order: list[str] = []
        self.lock = threading.Lock()
        self.email_started = threading.Event()
        self.summary_started = threading.Event()
        self.extract_done = threading.Event()
        self.marks: dict[str, float] = {}

    def _mark(self, name: str) -> None:
        with self.lock:
            self.order.append(name)
            self.marks[name] = time.monotonic()

    def extract_case(self, document_text: str, *, repair: bool = False) -> ComplaintCase:
        del document_text, repair
        self._mark("extract")
        self.extract_done.set()
        return _case()

    def generate_customer_email(self, case: ComplaintCase) -> str:
        del case
        assert self.extract_done.is_set()
        self._mark("email_start")
        self.email_started.set()
        assert self.summary_started.wait(timeout=2)
        time.sleep(0.05)
        self._mark("email_end")
        return "# Subject: ok\n\nDear Customer,\n"

    def generate_case_summary(self, case: ComplaintCase) -> str:
        del case
        assert self.extract_done.is_set()
        self._mark("summary_start")
        self.summary_started.set()
        assert self.email_started.wait(timeout=2)
        time.sleep(0.05)
        self._mark("summary_end")
        return (
            "# Case summary\n\n## Overview\nok\n\n## Issue\nok\n\n"
            "## Action\nok\n\n## Status\nok\n\n## Next action\nok\n"
        )


def test_extraction_completes_before_overlapping_email_and_summary(tmp_path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    (input_dir / "ok.txt").write_text("Charged twice on my invoice.")
    ensure_output_dirs(output_dir)
    provider = _ConcurrentProvider()
    executor = ThreadPoolExecutor(max_workers=2)
    try:
        processor = DocumentProcessor(
            input_dir,
            output_dir,
            provider,
            overwrite=True,
            executor=executor,
        )
        result = processor.process(input_dir / "ok.txt")
    finally:
        executor.shutdown(wait=True)

    assert result.status is ProcessingStatus.SUCCESS
    assert provider.order[0] == "extract"
    assert provider.order.index("extract") < provider.order.index("email_start")
    assert provider.order.index("extract") < provider.order.index("summary_start")
    assert provider.marks["email_start"] < provider.marks["summary_end"]
    assert provider.marks["summary_start"] < provider.marks["email_end"]
    assert result.customer_email_path
    assert result.case_summary_path
    assert result.structured_data_path
