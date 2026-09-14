"""Upload + batch helpers for the FastAPI API (and CLI-adjacent UI tests)."""

import csv
import logging
import os
from pathlib import Path
from uuid import uuid4

from comet.config import Settings
from comet.exceptions import ConfigurationError
from comet.ingestion.discovery import SUPPORTED_EXTENSIONS
from comet.llm import create_provider
from comet.logging_config import setup_logging
from comet.workflow import BatchProcessor
from comet.workflow.batch import BatchRunSummary

logger = logging.getLogger(__name__)
UPLOAD_TYPES = sorted(ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS)
PRODUCT_NAME = "COMET"
PRODUCT_FULL_FORM = (
    "Complaint Orchestration & Management Engine for Triage"
)
_SAMPLES = Path(__file__).resolve().parents[3] / "data" / "samples"
SAMPLE_DOCUMENTS = (
    ("TXT sample", "Billing complaint", _SAMPLES / "billing_complaint.txt", "text/plain"),
    ("PDF sample", "Product-quality incident", _SAMPLES / "product_quality.pdf", "application/pdf"),
    (
        "DOCX sample",
        "Service-delay complaint",
        _SAMPLES / "service_issue.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
)


def default_tmp_root() -> Path:
    """Local runs use ./tmp; Vercel functions can only write under /tmp."""
    if os.environ.get("VERCEL"):
        return Path("/tmp/comet-uploads")
    return Path("tmp")


def default_output_dir() -> Path:
    if os.environ.get("VERCEL"):
        return Path("/tmp/comet-output")
    return Path("output")


TMP_ROOT = default_tmp_root()


def validate_upload_filename(filename: str) -> str:
    """Accept only a basename with a supported complaint-document suffix."""
    name = Path(filename).name
    suffix = Path(name).suffix.lower()
    if not name or name in {".", ".."} or not Path(name).stem:
        raise ConfigurationError("Choose a file with a name.")
    if suffix not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ConfigurationError(
            f"Unsupported file type '{suffix or name}'. Use {allowed}."
        )
    return name


def stage_upload(filename: str, data: bytes, tmp_root: Path | None = None) -> Path:
    """Write one uploaded file into a unique tmp folder and return that path."""
    run_dir = stage_uploads([(filename, data)], tmp_root)
    return next(run_dir.iterdir())


def stage_uploads(
    files: list[tuple[str, bytes]], tmp_root: Path | None = None
) -> Path:
    """Write many uploads into one tmp folder and return that folder."""
    if not files:
        raise ConfigurationError("Choose at least one .txt, .pdf, or .docx file.")
    run_dir = Path(tmp_root or default_tmp_root()) / uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=True)
    used: set[str] = set()
    for filename, data in files:
        name = validate_upload_filename(filename)
        dest_name = name
        index = 1
        while dest_name.lower() in used:
            dest_name = f"{Path(name).stem}_{index}{Path(name).suffix}"
            index += 1
        used.add(dest_name.lower())
        (run_dir / dest_name).write_bytes(data)
    return run_dir


def build_settings(
    input_dir: str,
    output_dir: str,
    overwrite: bool,
) -> Settings:
    """Build UI settings from the deployment-owned environment defaults.

    Provider, model, credentials, and retry settings stay in `.env`; they are
    intentionally not user-facing controls.
    """
    return Settings(
        input_dir=Path(input_dir).expanduser(),
        output_dir=Path(output_dir).expanduser(),
        overwrite=overwrite,
    )


def run_batch(settings: Settings) -> BatchRunSummary:
    """Run the unchanged application workflow for a UI submission."""
    settings.validate_provider_credentials()
    if not settings.input_dir.is_dir():
        raise ConfigurationError(f"Input directory does not exist: {settings.input_dir}")
    log_dir = Path("/tmp/comet-logs") if os.environ.get("VERCEL") else Path("logs")
    setup_logging(settings.log_level, log_dir=log_dir)
    provider = create_provider(settings)
    model_name = settings.model_name or getattr(provider, "model_name", None)
    credential_set = {
        "openai": bool(settings.openai_api_key),
        "gemini": bool(settings.gemini_api_key),
        "groq": bool(settings.groq_api_key),
    }.get(settings.llm_provider, False)
    logger.info(
        "request_llm provider=%s model=%s credential_set=%s",
        settings.llm_provider,
        model_name or "",
        credential_set,
    )
    return BatchProcessor(
        settings.input_dir,
        settings.output_dir,
        provider,
        overwrite=settings.overwrite,
        max_attempts=settings.max_llm_attempts,
        llm_provider=settings.llm_provider,
        model_name=model_name,
    ).run()


def report_rows(report_path: Path) -> list[dict[str, str]]:
    """Read the existing workflow CSV for the dashboard table."""
    with Path(report_path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def display_report_rows(report_path: Path) -> list[dict[str, str]]:
    """CSV rows for the UI: source_file is the basename only."""
    rows = []
    for row in report_rows(report_path):
        displayed = dict(row)
        source = displayed.get("source_file", "")
        displayed["source_file"] = Path(source).name if source else ""
        rows.append(displayed)
    return rows


def read_text(path: str | None) -> str | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.is_file():
        return None
    return file_path.read_text(encoding="utf-8")


def summary_to_api(summary: BatchRunSummary) -> dict:
    """JSON payload for the Streamlit client; artifact bodies, not server paths."""
    documents = []
    for result in summary.results:
        case = result.case.model_dump(mode="json") if result.case is not None else None
        documents.append(
            {
                "source_file": Path(result.source_file).name,
                "document_id": result.document_id,
                "status": result.status.value,
                "error_code": result.error_code,
                "error_message": result.error_message,
                "case": case,
                "customer_email": read_text(result.customer_email_path) or "",
                "case_summary": read_text(result.case_summary_path) or "",
                "structured_data": read_text(result.structured_data_path) or "{}",
            }
        )
    return {
        "counts": summary.counts,
        "token_usage": summary.token_usage,
        "report_rows": display_report_rows(summary.report_path),
        "report_csv": summary.report_path.read_text(encoding="utf-8"),
        "documents": documents,
    }
