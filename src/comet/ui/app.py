"""Streamlit dashboard for launching and reviewing complaint-processing runs."""

from pathlib import Path

import streamlit as st

from comet import __version__
from comet.config import Settings
from comet.exceptions import ConfigurationError
from comet.ui.pipeline import (
    UPLOAD_TYPES,
    build_settings,
    read_text,
    report_rows,
    run_batch,
    stage_upload,
)
from comet.workflow.batch import BatchRunSummary


def _display_case(result) -> None:
    case = result.case
    if case is None:
        return
    st.markdown("#### Extracted case")
    columns = st.columns(4)
    columns[0].metric("Category", case.complaint_category.value)
    columns[1].metric("Status", case.overall_case_status.value)
    columns[2].metric("Complaint", "Yes" if case.is_complaint else "No")
    columns[3].metric("Escalation", "Yes" if case.escalation_required else "No")
    st.write(
        {
            "Customer": case.customer_name,
            "Email": str(case.email) if case.email else None,
            "Phone": case.phone_number,
            "Issue": case.issue_description,
            "Resolution noted": case.resolution_provided,
            "Supporting document": case.supporting_document_available,
        }
    )


def _display_results(summary: BatchRunSummary) -> None:
    st.divider()
    st.subheader("Results")
    counts = summary.counts
    columns = st.columns(4)
    columns[0].metric("Documents", counts["discovered"])
    columns[1].metric("Successful", counts["successful"])
    columns[2].metric("Failed", counts["failed"])
    columns[3].metric("Skipped", counts["skipped"])

    for result in summary.results:
        st.markdown(f"### `{Path(result.source_file).name}`")
        st.caption(f"document_id `{result.document_id}` · status `{result.status.value}`")
        if result.error_code:
            st.error(f"{result.error_code}: {result.error_message or result.error_code}")
            continue
        _display_case(result)
        email_md = read_text(result.customer_email_path)
        summary_md = read_text(result.case_summary_path)
        structured = read_text(result.structured_data_path)
        email_tab, summary_tab, json_tab = st.tabs(
            ["Customer email", "Internal summary", "Structured JSON"]
        )
        with email_tab:
            st.markdown(email_md or "_No email artifact._")
        with summary_tab:
            st.markdown(summary_md or "_No summary artifact._")
        with json_tab:
            st.code(structured or "{}", language="json")

    st.dataframe(report_rows(summary.report_path), use_container_width=True, hide_index=True)
    st.download_button(
        "Download final report (CSV)",
        data=summary.report_path.read_bytes(),
        file_name="final_report.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.caption(f"Staged input: {summary.results[0].source_file if summary.results else ''}")
    st.caption(f"Artifacts: {summary.report_path.parent.resolve()}")


def main() -> None:
    """Render and run the optional Streamlit interface."""
    st.set_page_config(page_title="Comet AI", page_icon="📨", layout="wide")
    st.title("Comet AI")
    st.caption("Complaint Orchestration & Management Engine for Triage")
    st.info(
        "Upload one `.txt`, `.pdf`, or `.docx` complaint. "
        "It is saved under `tmp/`, processed there, and drafts are shown below. "
        "Nothing is sent."
    )

    defaults = Settings()
    uploaded = st.file_uploader(
        "Complaint document",
        type=UPLOAD_TYPES,
        help="Only .txt, .pdf, and .docx files are accepted.",
    )
    with st.expander("Processing options", expanded=False):
        provider = st.selectbox(
            "LLM provider",
            options=["mock", "openai", "gemini"],
            index=["mock", "openai", "gemini"].index(defaults.llm_provider),
            help="Mock mode needs no API key. Real-provider API keys are read from .env.",
        )
        model_name = st.text_input(
            "Model name (optional)",
            value=defaults.model_name or "",
            help="Leave blank to use the provider default.",
        )
        max_attempts = st.slider(
            "Maximum extraction attempts",
            min_value=1,
            max_value=3,
            value=defaults.max_llm_attempts,
        )
        output_dir = st.text_input("Output directory", value=str(defaults.output_dir))

    process = st.button("Process file", type="primary", disabled=uploaded is None)

    if process:
        if uploaded is None:
            st.error("Choose a .txt, .pdf, or .docx file first.")
        else:
            try:
                staged = stage_upload(uploaded.name, uploaded.getvalue())
                settings = build_settings(
                    str(staged.parent),
                    output_dir,
                    provider,
                    model_name,
                    max_attempts,
                    True,
                )
                with st.spinner(f"Processing {staged.name}…"):
                    st.session_state["batch_summary"] = run_batch(settings)
                st.success(f"Finished processing `{staged.name}`.")
            except ConfigurationError as exc:
                st.error(str(exc))
            except OSError as exc:
                st.error(f"The run could not access its files: {exc}")
            except Exception:
                st.exception("The workflow stopped unexpectedly. Check logs/application.log.")

    summary = st.session_state.get("batch_summary")
    if isinstance(summary, BatchRunSummary):
        _display_results(summary)

    st.caption(f"Comet AI v{__version__}")


if __name__ == "__main__":
    main()
