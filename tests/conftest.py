"""Shared pytest fixtures."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLES_DIR = Path(__file__).parent.parent / "data" / "samples"


@pytest.fixture(autouse=True)
def isolate_llm_env(request, monkeypatch):
    """Unit tests must not inherit .env provider/model (e.g. groq)."""
    if request.node.get_closest_marker("live"):
        return
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("MODEL_NAME", "")


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def samples_dir() -> Path:
    return SAMPLES_DIR
