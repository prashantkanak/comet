"""FastAPI entrypoint for Vercel. Streamlit is local-only; Vercel needs ASGI."""

from html import escape
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse

from comet import __version__
from comet.exceptions import ConfigurationError
from comet.ui.pipeline import (
    UPLOAD_TYPES,
    build_settings,
    default_output_dir,
    default_tmp_root,
    read_text,
    report_rows,
    run_batch,
    stage_upload,
)
from comet.workflow.batch import BatchRunSummary

app = FastAPI(title="Comet AI")

def _page(*, error: str | None = None, summary: BatchRunSummary | None = None) -> str:
    results = ""
    if error:
        results = f'<p class="error">{escape(error)}</p>'
    elif summary is not None:
        counts = summary.counts
        blocks = [
            "<section class='results'><h2>Results</h2>",
            "<div class='metrics'>",
            f"<div><span>Documents</span><strong>{counts['discovered']}</strong></div>",
            f"<div><span>Successful</span><strong>{counts['successful']}</strong></div>",
            f"<div><span>Failed</span><strong>{counts['failed']}</strong></div>",
            f"<div><span>Skipped</span><strong>{counts['skipped']}</strong></div>",
            "</div>",
        ]
        for result in summary.results:
            name = escape(Path(result.source_file).name)
            blocks.append(
                f"<article><h3>{name}</h3>"
                f"<p class='muted'>document_id {escape(result.document_id)} · "
                f"status {escape(result.status.value)}</p>"
            )
            if result.error_code:
                blocks.append(
                    f"<p class='error'>{escape(result.error_code)}: "
                    f"{escape(result.error_message or result.error_code)}</p></article>"
                )
                continue
            case = result.case
            if case is not None:
                blocks.append(
                    "<dl>"
                    f"<dt>Category</dt><dd>{escape(case.complaint_category.value)}</dd>"
                    f"<dt>Status</dt><dd>{escape(case.overall_case_status.value)}</dd>"
                    f"<dt>Customer</dt><dd>{escape(case.customer_name or '—')}</dd>"
                    f"<dt>Issue</dt><dd>{escape(case.issue_description)}</dd>"
                    "</dl>"
                )
            email_md = read_text(result.customer_email_path) or ""
            summary_md = read_text(result.case_summary_path) or ""
            structured = read_text(result.structured_data_path) or "{}"
            blocks.append(
                "<h4>Customer email</h4>"
                f"<pre>{escape(email_md)}</pre>"
                "<h4>Internal summary</h4>"
                f"<pre>{escape(summary_md)}</pre>"
                "<h4>Structured JSON</h4>"
                f"<pre>{escape(structured)}</pre></article>"
            )
        rows = report_rows(summary.report_path)
        if rows:
            headers = "".join(f"<th>{escape(key)}</th>" for key in rows[0])
            body = "".join(
                "<tr>" + "".join(f"<td>{escape(value)}</td>" for value in row.values()) + "</tr>"
                for row in rows
            )
            blocks.append(f"<table><thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table>")
        blocks.append("</section>")
        results = "".join(blocks)

    accept = ",".join(f".{ext}" for ext in UPLOAD_TYPES)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Comet AI</title>
  <style>
    :root {{ color-scheme: light; font-family: ui-sans-serif, system-ui, sans-serif; }}
    body {{ max-width: 920px; margin: 2rem auto; padding: 0 1.25rem 3rem; color: #0f172a; }}
    .banner {{ background: #eff6ff; border: 1px solid #bfdbfe; padding: 0.9rem 1rem; border-radius: 10px; }}
    form {{ display: grid; gap: 0.85rem; margin: 1.5rem 0; }}
    label {{ font-weight: 600; font-size: 0.9rem; }}
    input, select {{ padding: 0.55rem 0.7rem; border: 1px solid #cbd5e1; border-radius: 8px; }}
    button {{ background: #0f172a; color: white; border: 0; border-radius: 8px; padding: 0.7rem 1rem; font-weight: 600; cursor: pointer; }}
    .error {{ color: #b91c1c; background: #fef2f2; padding: 0.75rem 1rem; border-radius: 8px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.75rem; }}
    .metrics div {{ background: #f8fafc; border-radius: 10px; padding: 0.8rem; }}
    .metrics span {{ display: block; color: #64748b; font-size: 0.8rem; }}
    pre {{ white-space: pre-wrap; background: #f8fafc; padding: 1rem; border-radius: 8px; overflow: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; margin-top: 1rem; }}
    th, td {{ border: 1px solid #e2e8f0; padding: 0.4rem 0.5rem; text-align: left; }}
    .muted {{ color: #64748b; }}
    details {{ color: #475569; }}
  </style>
</head>
<body>
  <h1>Comet AI</h1>
  <p class="muted">Complaint Orchestration &amp; Management Engine for Triage</p>
  <p class="banner">Upload one .txt, .pdf, or .docx complaint. Drafts are shown below and are never sent.</p>
  <form method="post" enctype="multipart/form-data">
    <label for="file">Complaint document</label>
    <input id="file" name="file" type="file" accept="{accept}" required/>
    <button type="submit">Process file</button>
  </form>
  {results}
  <p class="muted">Comet AI v{escape(__version__)}</p>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return _page()


@app.post("/", response_class=HTMLResponse)
async def process_file(
    file: UploadFile = File(...),
) -> HTMLResponse:
    try:
        data = await file.read()
        staged = stage_upload(file.filename or "", data, default_tmp_root())
        settings = build_settings(
            str(staged.parent),
            str(default_output_dir()),
            True,
        )
        summary = run_batch(settings)
    except ConfigurationError as exc:
        return HTMLResponse(_page(error=str(exc)), status_code=400)
    except OSError as exc:
        return HTMLResponse(_page(error=f"The run could not access its files: {exc}"), status_code=500)
    except Exception:
        return HTMLResponse(
            _page(error="The workflow stopped unexpectedly."),
            status_code=500,
        )
    return HTMLResponse(_page(summary=summary))
