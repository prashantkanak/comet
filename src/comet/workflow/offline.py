"""Compatibility wrapper around BatchProcessor."""

from pathlib import Path

from comet.llm.base import LLMProvider
from comet.models import DocumentResult
from comet.workflow.batch import BatchProcessor


def run_offline_pipeline(
    input_dir: Path,
    output_dir: Path,
    provider: LLMProvider,
    overwrite: bool = False,
    max_attempts: int = 2,
) -> tuple[list[DocumentResult], Path]:
    """Discover files, process each document, and write CSV + run manifest."""
    summary = BatchProcessor(
        input_dir,
        output_dir,
        provider,
        overwrite=overwrite,
        max_attempts=max_attempts,
        max_document_workers=4,
        llm_provider="mock",
        model_name=getattr(provider, "model_name", None),
    ).run()
    return summary.results, summary.report_path
