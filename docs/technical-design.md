# Comet AI — Technical Design Document

**Status:** implementation blueprint  
**Version:** 1.0  
**Primary language:** Python 3.11+

## 1. Purpose

Comet AI (COMET — Complaint Orchestration & Management Engine for Triage) is a local, batch-oriented GenAI application for processing customer-complaint documents. It reads documents from a local input directory, extracts their text, converts each document into validated structured case data, generates two distinct AI outputs, and creates a management report.

The project is designed to demonstrate Python, modular architecture, LLM integration, prompt engineering, Pydantic structured output, dependency-aware parallel work, error handling, logging, batch processing, and automated tests—without requiring a database, vector store, Docker, or paid infrastructure other than an optional LLM API.

## 2. Scope

### In scope

- Batch discovery and processing of `.txt`, `.pdf`, and `.docx` files.
- Per-document text extraction and file-level failure isolation.
- Pydantic-validated complaint/case extraction from an LLM.
- A professional customer email generated only from validated case data.
- A concise internal case summary generated only from validated case data.
- Concurrent generation of the email and internal summary after extraction succeeds.
- JSON, text/Markdown, CSV, logs, and a run manifest as local artifacts.
- Configurable OpenAI and Gemini adapters, with a mock provider for offline development and tests.
- CLI-first operation; a Streamlit UI is optional and deferred.

### Explicitly out of scope for the first release

- Sending emails, changing CRM records, or any other external side effect.
- OCR for scanned/image-only PDFs.
- Authentication, multi-user access, databases, RAG, vector stores, queues, Docker, or cloud deployment.
- Legal decisions or autonomous handling of complaints.

## 3. Success criteria

The minimum release is complete when one CLI command can process a mixed batch of valid and invalid documents and:

1. produces one structured JSON record, customer email, and case summary for every successfully extracted case;
2. produces `final_report.csv` with both successful and failed document rows;
3. continues processing after an unsupported, corrupt, empty, or LLM-failed document;
4. validates extraction against Pydantic rather than storing raw LLM output;
5. runs downstream email and summary tasks in parallel only after validated extraction;
6. passes unit and workflow tests without a real API key.

## 4. Architecture

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
                                      │               │
                                      └──────┬────────┘
                                             ▼
                                    artifact writer + report builder
                                             │
         ┌───────────────────┬───────────────┼──────────────────────┐
         ▼                   ▼               ▼                      ▼
structured_data/*.json  customer_emails/*  case_summaries/*  final_report.csv
```

### Execution model

Processing **within a document** is dependency-aware:

```text
load → extract → validate text → structured extraction → [email || summary] → save
```

The bracketed tasks are independent and run using `ThreadPoolExecutor(max_workers=2)`. Batch documents are processed sequentially initially to keep API usage, logs, and failure diagnosis simple. A later configuration option may process documents concurrently, but only after the per-document workflow is fully tested.

## 5. Repository layout

```text
comet-ai/
├── data/                         # local input; ignored except sample fixtures
├── output/                       # generated, ignored by Git
├── logs/                         # generated, ignored by Git
├── docs/
│   └── technical-design.md
├── src/
│   └── comet/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── logging_config.py
│       ├── exceptions.py
│       ├── models/
│       │   ├── case.py
│       │   ├── results.py
│       │   └── enums.py
│       ├── ingestion/
│       │   ├── discovery.py
│       │   ├── loaders.py
│       │   └── text_normalizer.py
│       ├── llm/
│       │   ├── base.py
│       │   ├── factory.py
│       │   ├── openai_provider.py
│       │   ├── gemini_provider.py
│       │   ├── mock_provider.py
│       │   └── prompts.py
│       ├── services/
│       │   ├── extraction_service.py
│       │   ├── email_service.py
│       │   ├── summary_service.py
│       │   └── artifact_service.py
│       ├── workflow/
│       │   ├── processor.py
│       │   └── batch.py
│       └── reporting/
│           └── csv_report.py
├── tests/
│   ├── fixtures/
│   ├── unit/
│   └── integration/
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
└── run.py                         # thin compatibility entry point (optional)
```

Use a `src/` layout so application imports are explicit and tests cannot accidentally import files from the repository root.

## 6. Domain model and contracts

### 6.1 Structured extraction schema

Pydantic is the boundary between untrusted model output and application data. Optional fields must become `null`, not invented values. Enumerations keep reporting values consistent.

```python
class ComplaintCategory(str, Enum):
    BILLING = "billing"
    DELIVERY = "delivery"
    PRODUCT_QUALITY = "product_quality"
    SERVICE = "service"
    ACCOUNT_ACCESS = "account_access"
    OTHER = "other"
    UNKNOWN = "unknown"

class CaseStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CLOSED = "closed"
    UNKNOWN = "unknown"

class ComplaintCase(BaseModel):
    customer_name: str | None = None
    email: EmailStr | None = None
    phone_number: str | None = None
    complaint_category: ComplaintCategory = ComplaintCategory.UNKNOWN
    issue_description: str
    resolution_provided: str | None = None
    is_complaint: bool
    escalation_required: bool
    supporting_document_available: bool
    overall_case_status: CaseStatus = CaseStatus.UNKNOWN
```

`issue_description` and `is_complaint` are required because the workflow cannot responsibly create a case with neither an issue nor a classification. The extraction prompt must instruct the model to use `unknown` for uncertain enum values and `null` for missing optional facts.

### 6.2 Runtime result model

```python
class ProcessingStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"

class DocumentResult(BaseModel):
    source_file: str
    document_id: str
    status: ProcessingStatus
    case: ComplaintCase | None = None
    customer_email_path: str | None = None
    case_summary_path: str | None = None
    structured_data_path: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
```

`DocumentResult` is the canonical object consumed by artifact writing and CSV reporting. A failed result never has partial success artifacts advertised as complete.

### 6.3 Artifact formats

| Artifact | Location | Format | Required content |
|---|---|---|---|
| Structured case | `output/structured_data/{id}.json` | JSON | `ComplaintCase` plus source metadata |
| Customer message | `output/customer_emails/{id}.md` | Markdown | subject and professionally worded body |
| Internal summary | `output/case_summaries/{id}.md` | Markdown | overview, issue, action, status, next action |
| Consolidated report | `output/final_report.csv` | UTF-8 CSV | one row per discovered document |
| Run manifest | `output/run_manifest.json` | JSON | timestamp, configuration-safe summary, result counts |

`document_id` is generated deterministically from a sanitized file stem plus a short hash of its relative path; this prevents collisions such as `complaint.pdf` and `complaint.docx`.

## 7. Component design

### 7.1 Configuration

`Settings` uses `pydantic-settings` and reads `.env` plus command-line overrides.

| Setting | Example | Notes |
|---|---|---|
| `LLM_PROVIDER` | `mock`, `openai`, `gemini`, `groq` | `mock` is safe default for development |
| `MODEL_NAME` | provider-specific | explicit and reproducible |
| `OPENAI_API_KEY` / `GEMINI_API_KEY` / `GROQ_API_KEY` | unset in Git | exactly one required for real provider |
| `MAX_LLM_ATTEMPTS` | `2` | one validation/transport retry maximum |
| `INPUT_DIR` | `data` | CLI normally supplies this |
| `OUTPUT_DIR` | `output` | artifacts only |
| `LOG_LEVEL` | `INFO` | no document text or secrets in normal logs |

The application fails fast with a clear configuration error if a real provider is selected without its required key. `.env` must be ignored; `.env.example` contains names only.

### 7.2 Ingestion

`discover_documents(input_dir)` returns sorted eligible files and a list of unsupported files. Supported extensions are case-insensitive: `.txt`, `.pdf`, `.docx`.

`load_document(path)` dispatches by suffix:

- TXT: `Path.read_text(encoding="utf-8", errors="replace")`
- PDF: PyMuPDF (`fitz`) page text extraction
- DOCX: `python-docx` paragraphs joined with newlines

The loader raises typed errors: `UnsupportedDocumentError`, `DocumentReadError`, and `EmptyDocumentError`. The batch orchestrator catches them per file and records a `FAILED` or `SKIPPED` result.

Initial PDF support is text-based only. If PyMuPDF returns whitespace, report `EMPTY_OR_SCANNED_PDF`; OCR can be a later enhancement.

### 7.3 LLM provider abstraction

Services depend on a small provider interface instead of a LangChain class directly:

```python
class LLMProvider(Protocol):
    def extract_case(self, document_text: str) -> ComplaintCase: ...
    def generate_customer_email(self, case: ComplaintCase) -> str: ...
    def generate_case_summary(self, case: ComplaintCase) -> str: ...
```

The OpenAI and Gemini implementations may use their official SDKs or LangChain adapters internally, but callers only know this interface. `MockLLMProvider` returns deterministic fixture data and makes CI free of API calls.

### 7.4 Prompt design and safety constraints

All prompts live in `llm/prompts.py`, are versioned as constants, and have one job.

| Task | Inputs | Output | Non-negotiable instruction |
|---|---|---|---|
| Extraction | source text | `ComplaintCase` schema | Extract explicit facts only; missing is `null`, never guess. |
| Email | validated `ComplaintCase` JSON | Markdown email | Do not invent dates, money, policies, commitments, or contact details. |
| Summary | validated `ComplaintCase` JSON | Markdown summary | Use only supplied case fields; label unknown/missing action clearly. |

Document text is untrusted input. Prompts must delimit it clearly and state that instructions inside the document are data, not instructions for the system. Generated output is never sent automatically; it remains a draft artifact for human review.

### 7.5 Extraction and retry policy

1. Call the provider’s structured-output extraction method.
2. Validate through `ComplaintCase.model_validate(...)` (or the provider’s Pydantic structured-output feature).
3. On schema validation error or transient provider error, log only the failure category and retry once with a repair instruction.
4. If retry fails, return `FAILED` with `STRUCTURED_OUTPUT_VALIDATION_ERROR` or `LLM_PROVIDER_ERROR`.
5. Do not retry unsupported/corrupt/empty source files.

Retries are bounded and use exponential backoff only for transient provider errors. Raw model payloads are excluded from logs by default to avoid accidental disclosure of customer information.

### 7.6 Workflow orchestration

`DocumentProcessor.process(path) -> DocumentResult` owns a single-document run:

1. Build `document_id` and start timing.
2. Extract and normalize text.
3. Create validated `ComplaintCase`.
4. Submit `generate_customer_email(case)` and `generate_case_summary(case)` to a two-worker executor.
5. Wait for both; if either fails, the document is failed and no success result is published.
6. Atomically write all successful artifacts.
7. Return a complete `DocumentResult`.

Use atomic artifact writes (`temporary file` then `replace`) so interrupted runs do not leave a misleading final file. Keep the executor scoped to a processor run or batch; always shut it down cleanly.

`BatchProcessor.run()` discovers inputs, processes each item in sorted order, catches every expected and unexpected per-document exception, writes the final report after all items, and returns an exit summary. It should exit non-zero only for a setup-level failure (missing input directory, invalid configuration, unwritable output), not simply because one document failed.

### 7.7 Reporting

`final_report.csv` has stable columns:

```text
document_id,source_file,status,customer_name,complaint_category,is_complaint,
escalation_required,overall_case_status,email_generated,summary_generated,
error_code,processed_at
```

Boolean fields use `true`/`false`; missing values are blank; `status` always uses the processing enum. The report must include unsupported documents, so a manager sees the complete batch outcome.

## 8. CLI design

Preferred command:

```bash
python -m comet.cli --input data --output output --provider mock
```

Arguments:

| Argument | Default | Purpose |
|---|---|---|
| `--input PATH` | `data` | directory to scan |
| `--output PATH` | `output` | output directory |
| `--provider` | environment/default | `mock`, `openai`, `gemini`, or `groq` |
| `--max-attempts INT` | `2` | max LLM extraction attempts |
| `--log-level LEVEL` | `INFO` | console/file verbosity |
| `--overwrite` | false | permit replacement of existing matching artifacts |

The completion summary prints discovered, successful, failed, and skipped counts plus the report path. It must never print API keys or full source document content.

## 9. Error handling and observability

| Failure | Handling | Result |
|---|---|---|
| Unsupported suffix | warning; continue | `SKIPPED`, `UNSUPPORTED_FILE_TYPE` |
| Corrupt/unreadable file | error; continue | `FAILED`, `DOCUMENT_READ_ERROR` |
| Empty or scanned text-only PDF | error; continue | `FAILED`, `EMPTY_DOCUMENT` / `EMPTY_OR_SCANNED_PDF` |
| LLM timeout/rate limit | bounded retry | `FAILED` if exhausted |
| Invalid structured output | one repair retry | `FAILED` if still invalid |
| Email/summary generation failure | fail that document; continue batch | `FAILED`, task-specific code |
| Output write failure | stop run only if output root unavailable; otherwise per document | clear setup/file error |

Use Python `logging` with a console handler and rotating `logs/application.log`. Each record should carry `document_id` where available. Log event names, file names, durations, provider/model name, and error types—not raw customer text, email addresses, or API responses.

## 10. Testing strategy

Tests must use temporary directories and `MockLLMProvider` unless explicitly marked as manual integration tests.

| Test layer | Key cases |
|---|---|
| Loader unit tests | TXT, DOCX, text PDF, unsupported suffix, unreadable file, empty content |
| Model unit tests | valid case, nullable fields, invalid enum, invalid email, required issue missing |
| Prompt/service tests | services receive only validated case data; mock responses are persisted correctly |
| Workflow tests | downstream tasks run after extraction; one document failure does not halt batch; CSV has every discovered item |
| Artifact tests | deterministic IDs, atomic writes, expected JSON/Markdown/CSV format |
| Manual smoke test | real provider against sanitized sample data, explicitly opt-in |

Coverage should focus on business behavior and failure paths rather than chasing a percentage. The core `BatchProcessor` and `DocumentProcessor` paths should have strong branch coverage.

## 11. Delivery phases

Each phase ends in a runnable milestone and a commit-sized scope.

### Phase 0 — Foundation and repository hygiene

Create the `src` package, `pyproject.toml`, `.gitignore`, `.env.example`, logging setup, basic CLI shell, sample inputs, and test configuration.

**Done when:** `python -m comet.cli --help` works; `pytest` runs; no secrets/output/logs are tracked.

### Phase 1 — Document ingestion

Implement discovery, TXT/PDF/DOCX loaders, typed errors, text normalization, and ingestion unit tests.

**Done when:** a mixed `data/` directory reports text extraction for valid files and continues past unsupported, corrupt, or empty files.

### Phase 2 — Domain models and offline pipeline

Implement `ComplaintCase`, enums, `DocumentResult`, output directory management, deterministic IDs, and `MockLLMProvider`.

**Done when:** a mock result validates and can be written as JSON, Markdown, and CSV without any API key.

### Phase 3 — Structured LLM extraction

Implement provider factory, one real provider adapter first (OpenAI *or* Gemini), extraction prompt, Pydantic parsing, retry, and error codes. Keep the mock path working.

**Done when:** a supported document produces a Pydantic-validated case; malformed provider output fails safely after the retry limit.

### Phase 4 — Customer email generation

Implement the email prompt and service using only `ComplaintCase` input.

**Done when:** each successful mock/real extraction produces a professional draft without fields not present in the case data.

### Phase 5 — Internal summary generation

Implement the internal-summary prompt and service, separate from customer email logic.

**Done when:** each successful extraction produces the five required summary sections: overview, issue, action, status, next action.

### Phase 6 — Orchestrated per-document workflow

Build `DocumentProcessor`; run email and summary generation concurrently; atomically write artifacts after both succeed.

**Done when:** tests prove extraction happens before both downstream tasks, and the independent tasks overlap/concurrently execute under a controlled fake provider.

### Phase 7 — Batch reporting and operational polish

Build `BatchProcessor`, consolidated CSV, run manifest, completion summary, structured logging, and robust per-file continuation.

**Done when:** a batch of 10+ mixed fixture files produces a complete report with accurate success/failure/skipped counts.

### Phase 8 — Hardening and quality

Add failure-path tests, README with architecture/setup/sample output, clean lint/type checks if configured, and a sanitized manual real-provider smoke test.

**Done when:** a new evaluator can clone the project, run mock mode locally, understand all design decisions, and inspect generated sample output.

### Phase 9 — Optional Streamlit UI

Implemented after CLI stabilization as `src/comet/ui/app.py`. It is a thin UI that invokes the same workflow API and does not duplicate business logic.

**Done when:** the UI accepts one supported upload into `tmp/`, starts a run on that file, shows the extracted case plus draft artifacts, and offers the CSV download.

## 12. Dependency plan

Initial required dependencies:

```text
pydantic>=2
pydantic-settings
python-dotenv
PyMuPDF
python-docx
pytest
```

Add exactly one provider SDK in Phase 3, then the other only if portability is implemented and tested. Add LangChain/LangGraph only if they make the workflow more readable than the explicit `DocumentProcessor`; the core requirement is clear orchestration, not a framework logo. `concurrent.futures` is sufficient for the initial parallel branch and needs no added dependency.

## 13. Key decisions and rationale

| Decision | Rationale |
|---|---|
| CLI before UI | keeps the core demonstrable, testable, and low-risk |
| Pydantic at LLM boundary | prevents arbitrary LLM text from becoming application data |
| Provider interface + mock | supports local no-cost testing and avoids vendor lock-in |
| One task per prompt | maps directly to the required multi-step workflow and reduces coupling |
| Per-document parallelism only | shows concurrency without uncontrolled API burst/rate-limit complexity |
| Local files + CSV | directly meets the assignment without unnecessary infrastructure |
| No automatic email sending | protects users and keeps generated output reviewable |
| Privacy-aware logging | customer complaints may contain personal data |

## 14. Risks and mitigations

| Risk | Mitigation |
|---|---|
| LLM hallucinates facts | strict prompts, nullable schema fields, structured validation, human-review drafts |
| Provider output malformed | bounded retry, error code, no raw response saved as final case |
| API costs/rate limits | mock default, sequential batch initially, explicit model/config, bounded retries |
| Scanned PDFs return no text | detect and report; scope OCR as a future feature |
| Sensitive data in sample data/logs | use fictional fixtures and avoid source text/raw payload logging |
| Partial output from interrupted run | atomic writes and run manifest |

## 15. Future improvements (not required for submission)

- OCR fallback for scanned PDFs.
- Human review/approval queue and editable generated drafts.
- Configurable taxonomy and business rules for escalation.
- Optional per-document batch concurrency with rate limiting.
- Streamlit dashboard.
- Redacted audit exports and retention controls.
- CRM/email integration only with explicit approval and security design.

## 16. First implementation order

Start with **Phase 0**, then complete Phases 1 and 2 in mock mode. Do not begin real LLM integration until document ingestion, models, artifacts, and tests are already working. This keeps every later phase small, testable, and easy to demonstrate.
