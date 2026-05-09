"""
Streamlit frontend for SmartSupport AI.

Run with:
  streamlit run app.py
"""

import html
import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.pipeline import SupportPipeline, TicketRequest
from data.sample_tickets import SAMPLE_TICKETS


load_dotenv()


st.set_page_config(
    page_title="SmartSupport AI",
    layout="wide",
    initial_sidebar_state="expanded",
)


CUSTOM_CSS = """
<style>
    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 2rem;
        max-width: 1180px;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.4rem;
    }
    .status-pill {
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: 0.2rem 0.65rem;
        font-size: 0.82rem;
        font-weight: 700;
        border: 1px solid rgba(49, 51, 63, 0.18);
    }
    .pill-pass {
        background: rgba(46, 160, 67, 0.12);
        color: rgb(24, 112, 49);
    }
    .pill-warn {
        background: rgba(218, 54, 51, 0.12);
        color: rgb(164, 14, 38);
    }
    .ticket-response {
        border-left: 4px solid #2e7dd1;
        background: rgba(46, 125, 209, 0.07);
        padding: 1rem 1.15rem;
        border-radius: 0.35rem;
        white-space: pre-wrap;
    }
</style>
"""


def get_api_key(sidebar_key: str) -> str | None:
    """Prefer sidebar override, then Streamlit secrets, then .env/environment."""
    if sidebar_key.strip():
        return sidebar_key.strip()

    try:
        secret_key = st.secrets.get("ANTHROPIC_API_KEY")
        if secret_key:
            return secret_key
    except Exception:
        pass

    return os.getenv("ANTHROPIC_API_KEY")


@st.cache_resource(show_spinner=False)
def get_pipeline(api_key: str | None) -> SupportPipeline:
    return SupportPipeline(api_key=api_key)


def sample_label(index: int, ticket: TicketRequest) -> str:
    message = ticket.message.replace("\n", " ")
    preview = message[:58] + ("..." if len(message) > 58 else "")
    return f"{index + 1}. {ticket.customer_name} - {preview}"


def build_request_from_form() -> TicketRequest:
    selected_index = st.session_state.get("sample_ticket_index", 0)
    selected_ticket = SAMPLE_TICKETS[selected_index]

    use_sample = st.session_state.get("use_sample_ticket", True)
    if use_sample:
        message = selected_ticket.message
        customer_name = selected_ticket.customer_name
        customer_tier = selected_ticket.customer_tier
        order_id = selected_ticket.order_id
        prior_contacts = selected_ticket.prior_contacts
        account_age_months = selected_ticket.account_age_months
    else:
        message = st.session_state.get("message", "")
        customer_name = st.session_state.get("customer_name", "Customer")
        customer_tier = st.session_state.get("customer_tier", "standard")
        order_id = st.session_state.get("order_id", "")
        prior_contacts = st.session_state.get("prior_contacts", 0)
        account_age_months = st.session_state.get("account_age_months", 0)

    clean_order_id = order_id.strip() or None if isinstance(order_id, str) else order_id

    return TicketRequest(
        message=message.strip(),
        customer_name=customer_name.strip() or "Customer",
        customer_tier=customer_tier,
        order_id=clean_order_id,
        prior_contacts=int(prior_contacts),
        account_age_months=int(account_age_months),
    )


def render_result(result) -> None:
    status_class = "pill-warn" if result.injection_blocked else "pill-pass"
    status_text = "Blocked by guard" if result.injection_blocked else "Ready for customer"

    st.markdown(f'<span class="status-pill {status_class}">{status_text}</span>', unsafe_allow_html=True)
    st.caption(f"Ticket ID: {result.ticket_id}")

    metric_cols = st.columns(5)
    metric_cols[0].metric("Department", result.department.title())
    metric_cols[1].metric("Priority", result.priority.title())
    metric_cols[2].metric("Sentiment", result.sentiment.title())
    metric_cols[3].metric("Quality", f"{result.quality_score}/100")
    metric_cols[4].metric("Time", f"{result.processing_time_ms:.0f} ms")

    st.subheader("Customer Response")
    safe_response = html.escape(result.final_response)
    st.markdown(f'<div class="ticket-response">{safe_response}</div>', unsafe_allow_html=True)

    if result.injection_blocked:
        st.warning("The security guard stopped this ticket before analysis and response generation.")
        return

    left, right = st.columns([1.05, 0.95], gap="large")

    with left:
        st.subheader("Analysis")
        analysis = result.analysis or {}
        st.write(analysis.get("summary", "No summary returned."))
        st.markdown(f"**Priority reason:** {analysis.get('priority_reason', 'Not provided')}")
        st.markdown(f"**Estimated resolution:** {analysis.get('estimated_resolution_time', 'Unknown')}")

        actions = analysis.get("suggested_actions", [])
        if actions:
            st.markdown("**Suggested actions**")
            for action in actions:
                st.markdown(f"- {action}")

    with right:
        st.subheader("Quality Check")
        st.progress(min(max(result.quality_score, 0), 100) / 100)
        st.markdown(f"**Passed:** {'Yes' if result.quality_passed else 'No'}")
        st.markdown(f"**Shot technique:** {result.shot_technique}")

        if result.quality_issues:
            st.markdown("**Issues found**")
            for issue in result.quality_issues:
                st.markdown(f"- {issue}")
        else:
            st.success("No quality issues reported.")

        with st.expander("Token usage"):
            st.json(result.tokens_used)


def render_report(pipeline: SupportPipeline) -> None:
    report = pipeline.full_report()
    if report.get("message"):
        st.info(report["message"])
        return

    st.subheader("Session Report")
    cols = st.columns(4)
    cols[0].metric("Processed", report["tickets_processed"])
    cols[1].metric("Blocked", report["injection_blocked"])
    cols[2].metric("Avg QA", report["avg_quality_score"])
    cols[3].metric("Avg Time", f"{report['avg_processing_ms']} ms")

    left, right = st.columns(2)
    with left:
        st.markdown("**By department**")
        st.json(report.get("by_department", {}))
    with right:
        st.markdown("**By priority**")
        st.json(report.get("by_priority", {}))


def main() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    with st.sidebar:
        st.title("SmartSupport AI")
        sidebar_key = st.text_input(
            "Anthropic API key",
            type="password",
            help="Optional if ANTHROPIC_API_KEY is already set in .env or Streamlit secrets.",
        )
        api_key = get_api_key(sidebar_key)

        st.divider()
        st.checkbox("Use sample ticket", value=True, key="use_sample_ticket")
        st.selectbox(
            "Sample ticket",
            options=list(range(len(SAMPLE_TICKETS))),
            format_func=lambda i: sample_label(i, SAMPLE_TICKETS[i]),
            key="sample_ticket_index",
            disabled=not st.session_state.get("use_sample_ticket", True),
        )

        st.divider()
        st.caption("Run from the terminal with:")
        st.code("streamlit run app.py", language="bash")

    st.title("SmartSupport AI")
    st.caption("Customer support ticket analyzer, responder, quality checker, and injection guard.")

    if not api_key:
        st.warning("Add `ANTHROPIC_API_KEY` in `.env`, Streamlit secrets, or the sidebar before processing tickets.")

    selected_ticket = SAMPLE_TICKETS[st.session_state.get("sample_ticket_index", 0)]
    use_sample = st.session_state.get("use_sample_ticket", True)

    with st.form("ticket_form"):
        top_cols = st.columns([1.1, 0.9, 0.8])
        with top_cols[0]:
            if use_sample:
                st.text_input("Customer name", value=selected_ticket.customer_name, disabled=True)
            else:
                st.text_input("Customer name", value="Customer", key="customer_name")
        with top_cols[1]:
            tiers = ["standard", "premium", "enterprise"]
            if use_sample:
                st.selectbox(
                    "Customer tier",
                    tiers,
                    index=tiers.index(selected_ticket.customer_tier),
                    disabled=True,
                )
            else:
                st.selectbox("Customer tier", tiers, key="customer_tier")
        with top_cols[2]:
            if use_sample:
                st.text_input("Order ID", value=selected_ticket.order_id or "", disabled=True)
            else:
                st.text_input("Order ID", value="", key="order_id")

        detail_cols = st.columns(2)
        with detail_cols[0]:
            if use_sample:
                st.number_input(
                    "Prior contacts",
                    min_value=0,
                    max_value=20,
                    value=selected_ticket.prior_contacts,
                    step=1,
                    disabled=True,
                )
            else:
                st.number_input("Prior contacts", min_value=0, max_value=20, value=0, step=1, key="prior_contacts")
        with detail_cols[1]:
            if use_sample:
                st.number_input(
                    "Account age in months",
                    min_value=0,
                    max_value=240,
                    value=selected_ticket.account_age_months,
                    step=1,
                    disabled=True,
                )
            else:
                st.number_input(
                    "Account age in months",
                    min_value=0,
                    max_value=240,
                    value=0,
                    step=1,
                    key="account_age_months",
                )

        if use_sample:
            st.text_area("Customer message", value=selected_ticket.message, height=190, disabled=True)
        else:
            st.text_area("Customer message", value="", height=190, key="message")

        submitted = st.form_submit_button("Process ticket", type="primary", disabled=not bool(api_key))

    if submitted:
        request = build_request_from_form()
        if not request.message:
            st.error("Please enter a customer message.")
            return

        try:
            pipeline = get_pipeline(api_key)
            with st.spinner("Processing ticket through guard, analyzer, responder, and QA..."):
                st.session_state["last_result"] = pipeline.process(request)
                st.session_state["pipeline_ready"] = True
        except Exception as exc:
            st.error(f"Ticket processing failed: {exc}")
            return

    if "last_result" in st.session_state:
        st.divider()
        render_result(st.session_state["last_result"])

    if st.session_state.get("pipeline_ready"):
        st.divider()
        render_report(get_pipeline(api_key))


if __name__ == "__main__":
    main()
