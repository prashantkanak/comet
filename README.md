# Comet AI

**COMET** — Complaint Orchestration & Management Engine for Triage.

Local, batch-oriented GenAI app: read complaint documents from disk, extract a **Pydantic-validated** case, draft a customer email and an internal summary, then write JSON, Markdown, CSV, and a run manifest. Nothing is sent; all output is for human review.

## Requirements

- Python 3.11+
- Optional: `OPENAI_API_KEY` only if you use `--provider openai`

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env        # mock mode needs no API keys
```

## Run (mock — no API key)

```bash
python -m comet.cli --input data/samples --output output --provider mock --overwrite
```

You should see a completion line like `discovered=… successful=… failed=… skipped=…`, plus `report=` and `manifest=`. Mixed samples include valid `.txt` / `.pdf` / `.docx` files plus empty, corrupt, and unsupported files so one document failure never stops the batch.

```bash
pytest
```

## Architecture

```text
input directory
  │  PDF / DOCX / TXT
  ▼
Document discovery ──► load + extract text ──► normalize + validate text
                                                    │
                                                    ▼
                                        LLM structured extraction
                                             │ Pydantic validation
                                             ▼
                                         ComplaintCase
                                      ┌──────┴────────┐
                                      ▼               ▼
                           Customer email LLM    Internal summary LLM
                                      │               │  (concurrent)
                                      └──────┬────────┘
                                             ▼
                         artifacts + final_report.csv + run_manifest.json
```

Per document: load → extract → `[email || summary]` on a two-worker pool → atomic write. Documents in a batch run sequentially.

| Decision | Why |
|---|---|
| CLI before UI | Core path is testable without a dashboard |
| Pydantic at the LLM boundary | Model JSON never becomes a case until it validates |
| Provider interface + mock | Offline tests; swap OpenAI without changing workflow |
| One prompt per task | Extraction, email, and summary stay decoupled |
| Local files + CSV | No database, queue, or cloud required |
| Drafts only | Generated email is never sent |

Design details: `docs/technical-design.md`.

## CLI

```bash
python -m comet.cli --input data/samples --output output --provider mock --overwrite
```

| Argument | Default | Purpose |
|---|---|---|
| `--input` | `data` | Directory to scan (recursive) |
| `--output` | `output` | Artifact root |
| `--provider` | `mock` | `mock`, `openai`, `gemini`, or `groq` |
| `--max-attempts` | `2` | Extraction attempts (one repair/retry) |
| `--log-level` | `INFO` | Console/file verbosity |
| `--overwrite` | off | Replace existing artifacts for the same document id |

Exit code `0` even if some documents fail. Non-zero only for setup problems (missing input dir, bad config, unwritable output).

## Outputs

| Path | Content |
|---|---|
| `output/structured_data/{id}.json` | Validated `ComplaintCase` plus source metadata |
| `output/customer_emails/{id}.md` | Draft email (`# Subject:` …) |
| `output/case_summaries/{id}.md` | Overview, issue, action, status, next action |
| `output/final_report.csv` | One row per discovered file |
| `output/run_manifest.json` | Timestamps, config without secrets, counts |
| `logs/application.log` | Rotating log — file names and error codes, not complaint bodies |

`document_id` is `{sanitized_stem}_{8-char hash of relative path}`.

### Sample CSV (mock)

```text
document_id,source_file,status,customer_name,complaint_category,is_complaint,escalation_required,overall_case_status,email_generated,summary_generated,error_code,processed_at
billing_complaint_506b2f49,data/samples/billing_complaint.txt,success,Jane Doe,billing,true,false,open,true,true,,2026-09-14T00:00:00+00:00
empty_78907f14,data/samples/empty.txt,failed,,,,,,false,false,EMPTY_DOCUMENT,2026-09-14T00:00:00+00:00
notes_0ef99c8b,data/samples/notes.csv,skipped,,,,,,false,false,UNSUPPORTED_FILE_TYPE,2026-09-14T00:00:00+00:00
```

Booleans are `true`/`false`; missing values are blank.

### Sample email excerpt (mock)

```markdown
# Subject: We received your billing case

Dear Jane Doe,

Thank you for contacting us. We have recorded the following issue from your message:

Customer Complaint — Fictional Sample
...
This is a draft for human review. It does not confirm dates, refunds, policies, or other commitments.
```

## OpenAI (optional)

Set `OPENAI_API_KEY` in `.env` (never commit `.env`). Default model is `gpt-4o-mini`.

```bash
python -m comet.cli --input data/samples --output output --provider openai --overwrite
```

Opt-in live test (costs real tokens; uses one fictional paragraph in a temp dir):

```bash
export OPENAI_API_KEY=...
COMET_LIVE_LLM=1 pytest tests/integration/test_live_openai.py
```

## Gemini (optional)

Set `GEMINI_API_KEY` in `.env`, optionally set `MODEL_NAME`, then run:

```bash
python -m comet.cli --input data/samples --output output --provider gemini --overwrite
```

Gemini structured extraction uses the official Google GenAI SDK's JSON response schema, followed by the same Pydantic validation and bounded retry path as OpenAI.

## Groq (optional)

Set `GROQ_API_KEY` in `.env`. Default model is `qwen/qwen3.8-27b`.

```bash
python -m comet.cli --input data/samples --output output --provider groq --overwrite
```

Groq uses the OpenAI-compatible Chat Completions API (`https://api.groq.com/openai/v1`).

## Layout

```text
src/comet/           application package
  cli.py             entry point
  ingestion/         discovery, loaders, normalization
  llm/               prompts, mock, OpenAI / Gemini / Groq adapters, factory
  models/            ComplaintCase, DocumentResult, enums
  services/          extraction, email, summary, artifacts
  workflow/          DocumentProcessor, BatchProcessor
  reporting/         CSV + run manifest
tests/               unit tests; live tests under tests/integration/
data/samples/        fictional mixed fixtures
docs/technical-design.md
```

`.env`, `output/`, and `logs/` are gitignored.

## Tests

Default `pytest` uses the mock provider and temp directories only. It does not need an API key.

## Optional dashboard (Phase 9)

The Streamlit dashboard is a thin UI over the same `BatchProcessor` used by the CLI; it does not duplicate ingestion or LLM logic. Upload one `.txt`, `.pdf`, or `.docx` file; the dashboard validates the type, stages it under `tmp/`, processes only that file, then shows the extracted case, draft email, internal summary, and CSV download.

```bash
streamlit run src/comet/ui/app.py
```

Use mock mode for a local demonstration. For OpenAI or Gemini, keep the relevant API key in `.env`; the dashboard deliberately has no API-key field.

## Vercel

[Vercel’s Python runtime](https://vercel.com/docs/functions/runtimes/python) hosts **FastAPI/WSGI**, not Streamlit. This repo’s deployable app is `app.py` (`comet.web:app`): same upload → `tmp` → `BatchProcessor` flow, with HTML results. Streamlit remains for local use.

```bash
pip install -e ".[dev]"
# local check
python -c "from app import app; print(app.title)"
```

Redeploy after pushing `app.py`, `vercel.json`, and FastAPI deps. Set `OPENAI_API_KEY` / `GEMINI_API_KEY` / `GROQ_API_KEY` in the Vercel project if you use those providers. Mock mode needs no keys. Function timeout is 60s (`vercel.json`).
