"""Shared pytest fixtures."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLES_DIR = Path(__file__).parent.parent / "data" / "samples"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def samples_dir() -> Path:
    return SAMPLES_DIR
