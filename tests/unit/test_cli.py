"""CLI shell tests."""

import subprocess
import sys
from pathlib import Path

import pytest

from comet.cli import build_parser, main, settings_from_args


def test_build_parser_help():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--help"])


def test_settings_from_args_defaults():
    parser = build_parser()
    args = parser.parse_args([])
    settings = settings_from_args(args)
    assert settings.input_dir == Path("data")
    assert settings.output_dir == Path("output")
    assert settings.llm_provider == "mock"
    assert settings.max_llm_attempts == 2


def test_settings_from_args_overrides():
    parser = build_parser()
    args = parser.parse_args(
        ["--input", "custom_in", "--output", "custom_out", "--provider", "mock"]
    )
    settings = settings_from_args(args)
    assert settings.input_dir == Path("custom_in")
    assert settings.output_dir == Path("custom_out")
    assert settings.llm_provider == "mock"


def test_main_missing_input_dir(tmp_path):
    missing = tmp_path / "nope"
    assert main(["--input", str(missing)]) == 1


def test_main_success_with_samples_dir(samples_dir, tmp_path):
    assert main(["--input", str(samples_dir), "--output", str(tmp_path / "out")]) == 0


def test_cli_module_help():
    result = subprocess.run(
        [sys.executable, "-m", "comet.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Comet AI" in result.stdout
    assert "--input" in result.stdout
    assert "--provider" in result.stdout


def test_openai_without_key_fails():
    assert main(["--provider", "openai"]) == 1


def test_cli_ingestion_continues_on_mixed_batch(tmp_path, capsys):
    (tmp_path / "ok.txt").write_text("Late delivery of order 12.")
    (tmp_path / "empty.txt").write_text(" ")
    (tmp_path / "notes.csv").write_text("a,b")
    out = tmp_path / "out"
    assert main(["--input", str(tmp_path), "--output", str(out)]) == 0
    stdout = capsys.readouterr().out
    assert "successful=" in stdout
    assert "failed=" in stdout
    assert "skipped=" in stdout
    assert "EMPTY_DOCUMENT" in stdout
    assert "UNSUPPORTED_FILE_TYPE" in stdout
    assert "Late delivery" not in stdout
    assert (out / "final_report.csv").is_file()
    assert list((out / "structured_data").glob("*.json"))
