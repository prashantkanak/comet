"""Streamlit Cloud UI. Processing runs on the Vercel FastAPI backend."""

from __future__ import annotations

import os
from html import escape

import httpx
import streamlit as st

PRODUCT_NAME = "COMET"
PRODUCT_FULL_FORM = "Complaint Orchestration & Management Engine for Triage"
UPLOAD_TYPES = ["txt", "pdf", "docx"]
PROCESS_TIMEOUT = 60.0


def _api_base() -> str:
    url = os.environ.get("COMET_API_URL", "").strip()
    if not url:
        try:
            url = str(st.secrets.get("COMET_API_URL", "")).strip()
        except Exception:
            url = ""
    return url.rstrip("/")


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
          .block-container { max-width: 100% !important; padding-top: 1.25rem; padding-bottom: 4rem; padding-left: 1.5rem; padding-right: 1.5rem; }
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


def _error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text or f"HTTP {response.status_code}"
    if isinstance(payload, dict) and payload.get("detail"):
        return str(payload["detail"])
    return response.text or f"HTTP {response.status_code}"


def _list_samples(base: str) -> list[dict]:
    try:
        response = httpx.get(f"{base}/api/samples", timeout=15.0)
        response.raise_for_status()
        return list(response.json().get("samples") or [])
    except Exception:
        return []


def _render_sample_downloads(base: str) -> None:
    samples = _list_samples(base)
    if not samples:
        return
    with st.popover("Sample documents"):
        st.caption("Download a fictional .txt, .pdf, or .docx complaint.")
        for sample in samples:
            filename = sample["filename"]
            try:
                response = httpx.get(f"{base}/samples/{filename}", timeout=15.0)
                response.raise_for_status()
                data = response.content
            except Exception:
                continue
            st.download_button(
                f".{filename.rsplit('.', 1)[-1]}",
                data=data,
                file_name=filename,
                mime=sample.get("mime") or "application/octet-stream",
                key=f"sample-{filename}",
                help=sample.get("title") or filename,
                use_container_width=True,
            )


def _tab_labels(documents: list[dict]) -> list[str]:
    labels: list[str] = []
    seen: dict[str, int] = {}
    for document in documents:
        name = document.get("source_file") or document.get("document_id") or "document"
        count = seen.get(name, 0) + 1
        seen[name] = count
        labels.append(name if count == 1 else f"{name} ({count})")
    return labels


def _display_case_fields(case: dict) -> None:
    columns = st.columns(4)
    category = str(case.get("complaint_category") or "unknown").replace("_", " ").title()
    status = str(case.get("overall_case_status") or "unknown").replace("_", " ").title()
    columns[0].metric("Category", category)
    columns[1].metric("Status", status)
    columns[2].metric("Complaint", "Yes" if case.get("is_complaint") else "No")
    columns[3].metric("Escalation", "Yes" if case.get("escalation_required") else "No")


def _display_file_tab(document: dict) -> None:
    if document.get("error_code"):
        st.error(
            f"{document['error_code']}: {document.get('error_message') or document['error_code']}"
        )
        return
    if document.get("case"):
        _display_case_fields(document["case"])
    st.markdown("<p class='artifact-label'>Customer email</p>", unsafe_allow_html=True)
    st.markdown(document.get("customer_email") or "_No email artifact._")
    st.markdown("<p class='artifact-label'>Case summary</p>", unsafe_allow_html=True)
    st.markdown(document.get("case_summary") or "_No summary artifact._")
    st.markdown("<p class='artifact-label'>Structured data</p>", unsafe_allow_html=True)
    st.code(document.get("structured_data") or "{}", language="json")


def _display_results(payload: dict) -> None:
    processed = (payload.get("counts") or {}).get("discovered", 0)
    st.markdown("### Case review")
    st.metric("Documents processed", processed)
    usage = payload.get("token_usage")
    if usage:
        call_col, prompt_col, completion_col, total_col = st.columns(4)
        call_col.metric("LLM calls", usage["calls"])
        prompt_col.metric("Prompt tokens", usage["prompt_tokens"])
        completion_col.metric("Completion tokens", usage["completion_tokens"])
        total_col.metric("Total tokens", usage["total_tokens"])

    st.markdown("#### Consolidated report")
    rows = payload.get("report_rows") or []
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    csv_text = payload.get("report_csv") or ""
    st.download_button(
        "Download report (CSV)",
        data=csv_text.encode("utf-8"),
        file_name="final_report.csv",
        mime="text/csv",
    )

    documents = payload.get("documents") or []
    if not documents:
        return
    st.markdown("#### Documents")
    tabs = st.tabs(_tab_labels(documents))
    for tab, document in zip(tabs, documents, strict=True):
        with tab:
            _display_file_tab(document)


def _process(base: str, files) -> dict:
    uploads = [
        ("files", (item.name, item.getvalue(), item.type or "application/octet-stream"))
        for item in files
    ]
    response = httpx.post(
        f"{base}/api/process",
        files=uploads,
        timeout=PROCESS_TIMEOUT,
    )
    if response.status_code >= 400:
        raise RuntimeError(_error_detail(response))
    return response.json()


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
              <h1>{escape(PRODUCT_NAME)}</h1>
              <p class="expand">{escape(PRODUCT_FULL_FORM)}</p>
            </header>""",
        unsafe_allow_html=True,
    )
    base = _api_base()
    if not base:
        st.error(
            "Set COMET_API_URL to the Vercel backend "
            "(environment variable or Streamlit secrets)."
        )
        return

    with st.container(border=True):
        title_col, sample_col = st.columns([4.2, 1.2], vertical_alignment="bottom")
        with title_col:
            st.markdown("## Upload complaint")
        with sample_col:
            _render_sample_downloads(base)
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
                    with st.spinner(f"Processing {len(files)} document(s)…"):
                        st.session_state["batch_payload"] = _process(base, files)
                    st.success(f"Finished processing {len(files)} document(s).")
                except httpx.RequestError as exc:
                    st.error(f"Could not reach the backend at {base}: {exc}")
                except Exception as exc:
                    st.error(str(exc))

    payload = st.session_state.get("batch_payload")
    if isinstance(payload, dict) and "documents" in payload:
        _display_results(payload)

    st.caption(f"{PRODUCT_NAME}  ·  backend {base}")


if __name__ == "__main__":
    main()
