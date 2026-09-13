"""Command-line interface for Comet AI."""

import argparse
import logging
import sys
from pathlib import Path

from comet import __version__
from comet.config import Settings
from comet.exceptions import ConfigurationError
from comet.llm import create_provider
from comet.logging_config import setup_logging
from comet.models import ProcessingStatus
from comet.workflow import run_offline_pipeline

logger = logging.getLogger(__name__)

COMET_TAGLINE = (
    "Complaint Orchestration & Management Engine for Triage"
)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="comet",
        description=f"Comet AI — {COMET_TAGLINE}.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data"),
        help="Directory to scan for input documents (default: data)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output"),
        help="Directory for generated artifacts (default: output)",
    )
    parser.add_argument(
        "--provider",
        choices=["mock", "openai", "gemini"],
        default=None,
        help="LLM provider (default: mock or LLM_PROVIDER env var)",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=None,
        help="Maximum LLM extraction attempts (default: 2)",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Logging verbosity (default: INFO)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing matching output artifacts",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"comet-ai {__version__}",
    )
    return parser


def settings_from_args(args: argparse.Namespace) -> Settings:
    """Merge CLI arguments into Settings."""
    overrides: dict[str, object] = {
        "input_dir": args.input,
        "output_dir": args.output,
        "overwrite": args.overwrite,
    }
    if args.provider is not None:
        overrides["llm_provider"] = args.provider
    if args.max_attempts is not None:
        overrides["max_llm_attempts"] = args.max_attempts
    if args.log_level is not None:
        overrides["log_level"] = args.log_level

    return Settings(**overrides)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        settings = settings_from_args(args)
        settings.validate_provider_credentials()
        provider = create_provider(settings)
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    setup_logging(settings.log_level)
    logger.info(
        "Comet AI v%s starting (provider=%s, input=%s, output=%s)",
        __version__,
        settings.llm_provider,
        settings.input_dir,
        settings.output_dir,
    )

    if not settings.input_dir.is_dir():
        logger.error("Input directory does not exist: %s", settings.input_dir)
        return 1

    try:
        results, report_path = run_offline_pipeline(
            settings.input_dir,
            settings.output_dir,
            provider,
            overwrite=settings.overwrite,
        )
    except OSError as exc:
        logger.error("Output directory is not writable: %s", exc)
        return 1

    successful = failed = skipped = 0
    for item in results:
        if item.status == ProcessingStatus.SUCCESS:
            successful += 1
            print(f"success  {item.document_id}  {item.source_file}")
        elif item.status == ProcessingStatus.SKIPPED:
            skipped += 1
            print(f"skipped  {item.document_id}  {item.source_file}  {item.error_code}")
        else:
            failed += 1
            print(f"failed   {item.document_id}  {item.source_file}  {item.error_code}")

    print(
        f"discovered={len(results)} successful={successful} "
        f"failed={failed} skipped={skipped}"
    )
    print(f"report={report_path}")
    logger.info(
        "Run complete discovered=%s successful=%s failed=%s skipped=%s report=%s",
        len(results),
        successful,
        failed,
        skipped,
        report_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
