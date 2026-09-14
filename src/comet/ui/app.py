"""Production Streamlit dashboard for complaint intake and case review."""

from __future__ import annotations

from html import escape
from pathlib import Path

import streamlit as st

from comet import __version__
from comet.exceptions import ConfigurationError
from comet.ui.pipeline import (
    UPLOAD_TYPES,
    build_settings,
    default_output_dir,
    display_report_rows,
    read_text,
    run_batch,
    stage_uploads,
)
from comet.workflow.batch import BatchRunSummary

PRODUCT_NAME = "COMET"
PRODUCT_FULL_FORM = (
    "Complaint Orchestration & Management Engine for Triage"
)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SAMPLES = _REPO_ROOT / "data" / "samples"
SAMPLE_DOCUMENTS = (
    ("TXT sample", "Billing complaint", _SAMPLES / "billing_complaint.txt", "text/plain"),
    ("PDF sample", "Product-quality incident", _SAMPLES / "product_quality.pdf", "application/pdf"),
    (
        "DOCX sample",
        "Service-delay complaint",
        _SAMPLES / "service_issue.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
)


def _inject_theme() -> None:
    st.markdown(
        """
        <style>
          :root {
            --paper: #f4f4f5;
            --surface: #ffffff;
            --ink: #18181b;
            --muted: #71717a;
            --rule: rgba(24, 24, 27, .1);
            --stamp: #172554;
          }
          html, .stApp { background: var(--paper); color: var(--ink); -webkit-font-smoothing: antialiased; }
          .block-container { max-width: 1180px; padding-top: 1.25rem; padding-bottom: 4rem; }
          .stDeployButton { display: none !important; }
          footer { visibility: hidden; }
          [data-testid="stMetric"] { font-variant-numeric: tabular-nums; }
          [data-testid="stFileUploader"] {
            background: #fafafa;
            border: 1px dashed rgba(24, 24, 27, .22);
            border-radius: 10px;
            padding: .15rem .55rem .4rem;
          }
          [data-testid="stButton"] button { border-radius: 8px; font-weight: 600; }
          .app-header {
            align-items: baseline;
            background: var(--stamp);
            border-radius: 12px;
            color: #f8fafc;
            display: flex;
            flex-wrap: wrap;
            gap: .55rem 1.15rem;
            margin: 0 0 1.25rem;
            padding: 1rem 1.25rem;
          }
          .app-header h1 {
            color: #ffffff;
            font-size: 22px;
            font-weight: 700;
            line-height: 1.1;
            margin: 0;
            text-wrap: balance;
          }
          .app-header .expand {
            color: #cbd5e1;
            font-size: 13px;
            line-height: 1.4;
            margin: 0;
            text-wrap: pretty;
          }
          .upload-head {
            align-items: baseline;
            display: flex;
            gap: 1rem;
            justify-content: space-between;
            margin: 0 0 .35rem;
          }
          .upload-head h2 { font-size: 1.2rem; font-weight: 700; margin: 0; text-wrap: balance; }
          [data-testid="stPopover"] button {
            background: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            color: var(--stamp) !important;
            font-size: 13px !important;
            font-weight: 600 !important;
            min-height: auto !important;
            padding: 0 !important;
            text-decoration: underline;
          }
          .artifact-label {
            color: var(--muted);
            font-size: 12px;
            font-weight: 700;
            margin: 1.1rem 0 .4rem;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_sample_downloads() -> None:
    with st.popover("Sample documents"):
        st.caption("Download a fictional .txt, .pdf, or .docx complaint.")
        for _label, title, path, mime in SAMPLE_DOCUMENTS:
            if not path.is_file():
                continue
            st.download_button(
                f".{path.suffix.lstrip('.')}",
                data=path.read_bytes(),
                file_name=path.name,
                mime=mime,
                key=f"sample-{path.suffix}",
                help=title,
                use_container_width=True,
            )


def _tab_labels(results) -> list[str]:
    labels: list[str] = []
    seen: dict[str, int] = {}
    for result in results:
        name = Path(result.source_file).name
        count = seen.get(name, 0) + 1
        seen[name] = count
        labels.append(name if count == 1 else f"{name} ({count})")
    return labels


def _display_case_fields(result) -> None:
    case = result.case
    if case is None:
        return
    columns = st.columns(4)
    columns[0].metric("Category", case.complaint_category.value.replace("_", " ").title())
    columns[1].metric("Status", case.overall_case_status.value.replace("_", " ").title())
    columns[2].metric("Complaint", "Yes" if case.is_complaint else "No")
    columns[3].metric("Escalation", "Yes" if case.escalation_required else "No")


def _display_file_tab(result) -> None:
    if result.error_code:
        st.error(f"{result.error_code}: {result.error_message or result.error_code}")
        return
    _display_case_fields(result)
    email_md = read_text(result.customer_email_path)
    summary_md = read_text(result.case_summary_path)
    structured = read_text(result.structured_data_path)
    st.markdown("<p class='artifact-label'>Customer email</p>", unsafe_allow_html=True)
    st.markdown(email_md or "_No email artifact._")
    st.markdown("<p class='artifact-label'>Case summary</p>", unsafe_allow_html=True)
    st.markdown(summary_md or "_No summary artifact._")
    st.markdown("<p class='artifact-label'>Structured data</p>", unsafe_allow_html=True)
    st.code(structured or "{}", language="json")


def _display_results(summary: BatchRunSummary) -> None:
    processed = summary.counts["discovered"]
    st.markdown("### Case review")
    st.metric("Documents processed", processed)

    st.markdown("#### Consolidated report")
    st.dataframe(
        display_report_rows(summary.report_path),
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Download report (CSV)",
        data=summary.report_path.read_bytes(),
        file_name="final_report.csv",
        mime="text/csv",
    )

    if not summary.results:
        return
    st.markdown("#### Documents")
    tabs = st.tabs(_tab_labels(summary.results))
    for tab, result in zip(tabs, summary.results, strict=True):
        with tab:
            _display_file_tab(result)


def main() -> None:
    st.set_page_config(
        page_title=f"{PRODUCT_NAME} — {PRODUCT_FULL_FORM}",
        page_icon="📨",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _inject_theme()
    st.markdown(
        f"""<header class="app-header">
              <h1>{PRODUCT_NAME}</h1>
              <p class="expand">{PRODUCT_FULL_FORM}</p>
            </header>""",
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        title_col, sample_col = st.columns([4.2, 1.2], vertical_alignment="bottom")
        with title_col:
            st.markdown("## Upload complaint")
        with sample_col:
            _render_sample_downloads()
        st.caption("Add one or more .txt, .pdf, or .docx files. Drafts are never sent.")
        uploaded = st.file_uploader(
            "Complaint documents",
            type=UPLOAD_TYPES,
            accept_multiple_files=True,
            help="Supported formats: .txt, .pdf, and .docx.",
            label_visibility="collapsed",
        )
        files = uploaded or []
        process = st.button("Process files", type="primary", disabled=not files)
        if process:
            if not files:
                st.error("Choose at least one .txt, .pdf, or .docx file.")
            else:
                try:
                    payloads = [(item.name, item.getvalue()) for item in files]
                    input_dir = stage_uploads(payloads)
                    settings = build_settings(
                        str(input_dir), str(default_output_dir()), True
                    )
                    with st.spinner(f"Processing {len(payloads)} document(s)…"):
                        st.session_state["batch_summary"] = run_batch(settings)
                    st.success(f"Finished processing {len(payloads)} document(s).")
                except ConfigurationError as exc:
                    st.error(str(exc))
                except OSError as exc:
                    st.error(f"The run could not access its files: {exc}")
                except Exception:
                    st.exception("The workflow stopped unexpectedly. Check logs/application.log.")

    summary = st.session_state.get("batch_summary")
    if isinstance(summary, BatchRunSummary):
        _display_results(summary)

    st.caption(f"{PRODUCT_NAME} v{__version__}")


if __name__ == "__main__":
    main()
