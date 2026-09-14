"""Tests for the Vercel FastAPI entrypoint without hitting the network."""

from dataclasses import replace

from fastapi.testclient import TestClient

from comet.llm import MockLLMProvider
from comet.web import app


def test_home_shows_upload_form():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "COMET" in response.text
    assert "Complaint Orchestration &amp; Management Engine for Triage" in response.text
    assert "Upload complaint" in response.text
    assert 'name="files"' in response.text
    assert "multiple" in response.text


def test_process_rejects_unsupported_type():
    response = TestClient(app).post(
        "/",
        files=[("files", ("notes.csv", b"a,b\n1,2\n", "text/csv"))],
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.text


def test_process_runs_workflow_for_txt(tmp_path, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr("comet.web.default_tmp_root", lambda: tmp_path / "uploads")
    monkeypatch.setattr("comet.web.default_output_dir", lambda: tmp_path / "out")
    monkeypatch.setattr("comet.ui.pipeline.create_provider", lambda _settings: MockLLMProvider())

    response = TestClient(app).post(
        "/",
        files=[("files", ("case.txt", b"I was charged twice on my invoice.", "text/plain"))],
    )
    assert response.status_code == 200, response.text
    assert "Case review" in response.text
    assert "Documents processed" in response.text
    assert "case.txt" in response.text
    assert "Customer email" in response.text
    assert "history.replaceState" in response.text
    assert response.headers.get("cache-control") == "no-store"


def test_process_shows_token_usage(tmp_path, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr("comet.web.default_tmp_root", lambda: tmp_path / "uploads")
    monkeypatch.setattr("comet.web.default_output_dir", lambda: tmp_path / "out")
    monkeypatch.setattr("comet.ui.pipeline.create_provider", lambda _settings: MockLLMProvider())
    from comet.ui.pipeline import run_batch as original_run_batch

    def _run_with_usage(settings):
        return replace(
            original_run_batch(settings),
            token_usage={
                "calls": 3,
                "prompt_tokens": 40,
                "completion_tokens": 80,
                "total_tokens": 120,
            },
        )

    monkeypatch.setattr("comet.web.run_batch", _run_with_usage)
    response = TestClient(app).post(
        "/",
        files=[("files", ("case.txt", b"I was charged twice on my invoice.", "text/plain"))],
    )
    assert response.status_code == 200, response.text
    assert "Prompt tokens" in response.text
    assert "120" in response.text


def test_home_refresh_is_empty_form():
    client = TestClient(app)
    home = client.get("/")
    assert home.status_code == 200
    assert "Case review" not in home.text
    assert "history.replaceState" in home.text


def test_sample_download_serves_txt():
    response = TestClient(app).get("/samples/billing_complaint.txt")
    assert response.status_code == 200
    assert "Jane Doe" in response.text
