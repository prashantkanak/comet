"""Tests for the Vercel FastAPI JSON API without hitting the network."""

from dataclasses import replace

from fastapi.testclient import TestClient

from comet.llm import MockLLMProvider
from comet.web import app


def test_home_describes_the_api():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "COMET"
    assert body["process"] == "/api/process"
    assert response.headers.get("cache-control") == "no-store"


def test_process_rejects_unsupported_type():
    response = TestClient(app).post(
        "/api/process",
        files=[("files", ("notes.csv", b"a,b\n1,2\n", "text/csv"))],
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_process_runs_workflow_for_txt(tmp_path, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setattr("comet.web.default_tmp_root", lambda: tmp_path / "uploads")
    monkeypatch.setattr("comet.web.default_output_dir", lambda: tmp_path / "out")
    monkeypatch.setattr("comet.ui.pipeline.create_provider", lambda _settings: MockLLMProvider())

    response = TestClient(app).post(
        "/api/process",
        files=[("files", ("case.txt", b"I was charged twice on my invoice.", "text/plain"))],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["counts"]["discovered"] == 1
    assert body["documents"][0]["source_file"] == "case.txt"
    assert "Dear" in body["documents"][0]["customer_email"]
    assert "document_id" in body["report_rows"][0]
    assert "document_id" in body["report_csv"]
    assert "/" not in body["documents"][0]["source_file"]


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
        "/api/process",
        files=[("files", ("case.txt", b"I was charged twice on my invoice.", "text/plain"))],
    )
    assert response.status_code == 200, response.text
    assert response.json()["token_usage"]["total_tokens"] == 120


def test_home_has_no_run_payload():
    body = TestClient(app).get("/").json()
    assert "documents" not in body
    assert "report_csv" not in body


def test_sample_download_serves_txt():
    response = TestClient(app).get("/samples/billing_complaint.txt")
    assert response.status_code == 200
    assert "Jane Doe" in response.text


def test_sample_index_lists_supported_files():
    response = TestClient(app).get("/api/samples")
    assert response.status_code == 200
    names = {item["filename"] for item in response.json()["samples"]}
    assert names == {"billing_complaint.txt", "product_quality.pdf", "service_issue.docx"}
