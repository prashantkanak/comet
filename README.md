# Comet AI

**COMET** — Complaint Orchestration & Management Engine for Triage.

Local, batch-oriented GenAI application for processing customer-complaint documents.

## Requirements

- Python 3.11+

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env        # optional; mock provider needs no API keys
```

## Usage

```bash
python -m comet.cli --help
```

Full batch processing is implemented incrementally; see `docs/technical-design.md` for delivery phases.

## Project layout

Application code lives under `src/comet/`. Tests live under `tests/`. Sample input documents are in `data/samples/`.

Generated artifacts (`output/`, `logs/`) are not tracked in Git.

## Development

```bash
pytest
```
