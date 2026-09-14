"""FastAPI entrypoint for Vercel. Streamlit is local-only; Vercel needs ASGI."""

from __future__ import annotations

import logging
from html import escape
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from comet import __version__
from comet.exceptions import ConfigurationError
from comet.ui.pipeline import (
    PRODUCT_FULL_FORM,
    PRODUCT_NAME,
    SAMPLE_DOCUMENTS,
    UPLOAD_TYPES,
    build_settings,
    default_output_dir,
    default_tmp_root,
    display_report_rows,
    read_text,
    run_batch,
    stage_uploads,
)
from comet.workflow.batch import BatchRunSummary

logger = logging.getLogger(__name__)
app = FastAPI(title=PRODUCT_NAME)
_SAMPLE_FILES = {path.name: (path, mime) for _label, _title, path, mime in SAMPLE_DOCUMENTS}


def _page(*, error: str | None = None, summary: BatchRunSummary | None = None) -> str:
    results = ""
    if error:
        results = f'<p class="error">{escape(error)}</p>'
    elif summary is not None:
        processed = summary.counts["discovered"]
        blocks = [
            "<section class='results'>",
            "<h2>Case review</h2>",
            f"<div class='metric'><span>Documents processed</span><strong>{processed}</strong></div>",
            "<h3>Consolidated report</h3>",
        ]
        rows = display_report_rows(summary.report_path)
        if rows:
            headers = "".join(f"<th>{escape(key)}</th>" for key in rows[0])
            body = "".join(
                "<tr>"
                + "".join(f"<td>{escape(value)}</td>" for value in row.values())
                + "</tr>"
                for row in rows
            )
            blocks.append(
                f"<table><thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table>"
            )
        if summary.results:
            blocks.append("<h3>Documents</h3><div class='tabs'>")
            for index, result in enumerate(summary.results):
                name = escape(Path(result.source_file).name)
                checked = " checked" if index == 0 else ""
                blocks.append(
                    f"<input class='tab-input' type='radio' name='doc-tab' "
                    f"id='doc-{index}'{checked}/>"
                    f"<label class='tab-label' for='doc-{index}'>{name}</label>"
                )
            for index, result in enumerate(summary.results):
                blocks.append(f"<article class='tab-panel' id='panel-{index}'>")
                if result.error_code:
                    blocks.append(
                        f"<p class='error'>{escape(result.error_code)}: "
                        f"{escape(result.error_message or result.error_code)}</p></article>"
                    )
                    continue
                case = result.case
                if case is not None:
                    blocks.append(
                        "<div class='metrics'>"
                        f"<div><span>Category</span><strong>"
                        f"{escape(case.complaint_category.value.replace('_', ' ').title())}"
                        "</strong></div>"
                        f"<div><span>Status</span><strong>"
                        f"{escape(case.overall_case_status.value.replace('_', ' ').title())}"
                        "</strong></div>"
                        f"<div><span>Complaint</span><strong>"
                        f"{'Yes' if case.is_complaint else 'No'}</strong></div>"
                        f"<div><span>Escalation</span><strong>"
                        f"{'Yes' if case.escalation_required else 'No'}</strong></div>"
                        "</div>"
                    )
                email_md = read_text(result.customer_email_path) or ""
                summary_md = read_text(result.case_summary_path) or ""
                structured = read_text(result.structured_data_path) or "{}"
                blocks.append(
                    "<p class='artifact-label'>Customer email</p>"
                    f"<pre>{escape(email_md) or 'No email artifact.'}</pre>"
                    "<p class='artifact-label'>Case summary</p>"
                    f"<pre>{escape(summary_md) or 'No summary artifact.'}</pre>"
                    "<p class='artifact-label'>Structured data</p>"
                    f"<pre>{escape(structured)}</pre></article>"
                )
            blocks.append("</div>")
        tab_css = "".join(
            f".tabs .tab-input:nth-of-type({i + 1}):checked ~ #panel-{i} {{ display: block; }}"
            for i in range(len(summary.results))
        )
        if tab_css:
            blocks.append(f"<style>{tab_css}</style>")
        blocks.append("</section>")
        results = "".join(blocks)

    accept = ",".join(f".{ext}" for ext in UPLOAD_TYPES)
    sample_links = "".join(
        f'<a href="/samples/{escape(path.name)}">.{escape(path.suffix.lstrip("."))}</a>'
        for _label, _title, path, _mime in SAMPLE_DOCUMENTS
        if path.is_file()
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{escape(PRODUCT_NAME)} — {escape(PRODUCT_FULL_FORM)}</title>
  <style>
    :root {{
      --paper: #f4f4f5; --surface: #ffffff; --ink: #18181b; --muted: #71717a;
      --rule: rgba(24, 24, 27, .1); --stamp: #172554;
    }}
    html, body {{ background: var(--paper); color: var(--ink); font-family: ui-sans-serif, system-ui, sans-serif; margin: 0; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 1.25rem 1.25rem 4rem; }}
    .app-header {{
      align-items: baseline; background: var(--stamp); border-radius: 12px; color: #f8fafc;
      display: flex; flex-wrap: wrap; gap: .55rem 1.15rem; margin: 0 0 1.25rem; padding: 1rem 1.25rem;
    }}
    .app-header h1 {{ color: #fff; font-size: 22px; font-weight: 700; margin: 0; text-wrap: balance; }}
    .app-header .expand {{ color: #cbd5e1; font-size: 13px; margin: 0; text-wrap: pretty; }}
    .card {{ background: var(--surface); border: 1px solid var(--rule); border-radius: 12px; padding: 1.15rem 1.25rem 1.3rem; }}
    .upload-head {{ align-items: baseline; display: flex; justify-content: space-between; gap: 1rem; }}
    .upload-head h2 {{ font-size: 1.2rem; margin: 0; }}
    .samples-hover {{ position: relative; }}
    .samples-link {{ color: var(--stamp); cursor: pointer; font-size: 13px; font-weight: 600; text-decoration: underline; }}
    .samples-menu {{
      background: var(--surface); border: 1px solid var(--rule); border-radius: 8px; display: none;
      flex-direction: column; min-width: 8.5rem; padding: .35rem; position: absolute; right: 0;
      top: calc(100% + .35rem); z-index: 20;
    }}
    .samples-hover:hover .samples-menu, .samples-hover:focus-within .samples-menu {{ display: flex; }}
    .samples-menu a {{ border-radius: 6px; color: var(--ink); font-size: 13px; font-weight: 600; padding: .4rem .55rem; text-decoration: none; }}
    .samples-menu a:hover, .samples-menu a:focus {{ background: #f4f4f5; }}
    .hint {{ color: var(--muted); font-size: .92rem; margin: .45rem 0 1rem; }}
    input[type=file] {{ display: block; width: 100%; margin: 0 0 1rem; }}
    button[type=submit] {{
      background: var(--stamp); border: 0; border-radius: 8px; color: #fff; font-weight: 600;
      padding: .65rem 1rem; cursor: pointer;
    }}
    .error {{ background: #fef2f2; border-radius: 8px; color: #b91c1c; padding: .75rem 1rem; }}
    .metric, .metrics div {{ background: #fafafa; border: 1px solid var(--rule); border-radius: 10px; padding: .8rem 1rem; width: fit-content; margin: .75rem 0 1rem; }}
    .metric span, .metrics span {{ color: var(--muted); display: block; font-size: .8rem; }}
    .metrics {{ display: grid; gap: .75rem; grid-template-columns: repeat(4, 1fr); }}
    table {{ border-collapse: collapse; font-size: .8rem; width: 100%; }}
    th, td {{ border: 1px solid #e4e4e7; padding: .4rem .5rem; text-align: left; }}
    .tabs {{ display: flex; flex-wrap: wrap; gap: .35rem 0; margin-top: 1rem; }}
    .tab-input {{ position: absolute; opacity: 0; pointer-events: none; }}
    .tab-label {{
      background: #fafafa; border: 1px solid var(--rule); border-bottom: 0; border-radius: 8px 8px 0 0;
      cursor: pointer; font-size: .85rem; font-weight: 600; margin-right: .35rem; padding: .5rem .8rem;
    }}
    .tab-panel {{
      background: var(--surface); border: 1px solid var(--rule); border-radius: 0 8px 8px 8px;
      display: none; order: 99; padding: 1rem; width: 100%;
    }}
    .tab-input:checked + .tab-label {{ background: #fff; }}
    .tabs .tab-input:nth-of-type(1):checked ~ #panel-0 {{ display: block; }}
    pre {{ background: #fafafa; border-radius: 8px; overflow: auto; padding: 1rem; white-space: pre-wrap; }}
    .artifact-label {{ color: var(--muted); font-size: 12px; font-weight: 700; margin: 1.1rem 0 .4rem; }}
    .foot {{ color: var(--muted); font-size: .82rem; margin-top: 1.5rem; }}
  </style>
</head>
<body>
  <main>
    <header class="app-header">
      <h1>{escape(PRODUCT_NAME)}</h1>
      <p class="expand">{escape(PRODUCT_FULL_FORM)}</p>
    </header>
    <section class="card">
      <div class="upload-head">
        <h2>Upload complaint</h2>
        <div class="samples-hover">
          <span class="samples-link" tabindex="0">Sample documents</span>
          <div class="samples-menu">{sample_links}</div>
        </div>
      </div>
      <p class="hint">Add one or more .txt, .pdf, or .docx files. Drafts are never sent.</p>
      <form method="post" enctype="multipart/form-data">
        <input id="files" name="files" type="file" accept="{accept}" multiple required/>
        <button type="submit">Process files</button>
      </form>
      {results}
    </section>
    <p class="foot">{escape(PRODUCT_NAME)} v{escape(__version__)}</p>
  </main>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return _page()


@app.get("/samples/{filename}")
def download_sample(filename: str) -> FileResponse:
    item = _SAMPLE_FILES.get(filename)
    if item is None or not item[0].is_file():
        raise HTTPException(status_code=404, detail="Sample not found")
    path, mime = item
    return FileResponse(path, media_type=mime, filename=path.name)


@app.post("/", response_class=HTMLResponse)
async def process_files(files: list[UploadFile] = File(...)) -> HTMLResponse:
    try:
        payloads = [(item.filename or "", await item.read()) for item in files]
        input_dir = stage_uploads(payloads, default_tmp_root())
        settings = build_settings(str(input_dir), str(default_output_dir()), True)
        summary = run_batch(settings)
    except ConfigurationError as exc:
        return HTMLResponse(_page(error=str(exc)), status_code=400)
    except OSError as exc:
        logger.exception("ui_process_os_error")
        return HTMLResponse(
            _page(error=f"The run could not access its files: {exc}"),
            status_code=500,
        )
    except Exception as exc:
        logger.exception("ui_process_failed")
        return HTMLResponse(
            _page(
                error=(
                    "The workflow stopped unexpectedly. "
                    f"{type(exc).__name__}: {exc}"
                )
            ),
            status_code=500,
        )
    return HTMLResponse(_page(summary=summary))
