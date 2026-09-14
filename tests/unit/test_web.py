"""Tests for the Vercel FastAPI entrypoint without hitting the network."""

from fastapi.testclient import TestClient

from comet.llm import MockLLMProvider
from comet.web import app


def test_home_shows_upload_form():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "Complaint document" in response.text
    assert 'accept=".docx,.pdf,.txt"' in response.text


def test_process_rejects_unsupported_type():
    response = TestClient(app).post(
        "/",
        files={"file": ("notes.csv", b"a,b\n1,2\n", "text/csv")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.text


def test_process_runs_workflow_for_txt(tmp_path, monkeypatch):
    monkeypatch.setattr("comet.web.default_tmp_root", lambda: tmp_path / "uploads")
    monkeypatch.setattr("comet.web.default_output_dir", lambda: tmp_path / "out")
    monkeypatch.setattr("comet.ui.pipeline.create_provider", lambda _settings: MockLLMProvider())

    response = TestClient(app).post(
        "/",
        files={"file": ("case.txt", b"I was charged twice on my invoice.", "text/plain")},
    )
    assert response.status_code == 200
    assert "Results" in response.text
    assert "case.txt" in response.text
    assert "Customer email" in response.text
