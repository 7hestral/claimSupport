"""Local chat and state inspector. Each browser session owns its conversation."""

import json
from datetime import UTC, date, datetime, time

import streamlit as st

from ..data.repository import FixtureRepository
from ..llm.model import create_model
from ..llm.reasoner import OpenRouterReasoner
from ..observability.monitoring import observe_turn
from ..schemas.state import Event, Session
from ..workflow.graph import build_workflow
from ..workflow.presentation import inspector
from .connection import connection_controls
from .debug import debug_console, record_event

SAMPLE = (
    "I'm the policyholder. My name is Margaret Chen, policy POL-9921. "
    "I'm calling about my denied healthcare claim from January. "
    "DOB is 1985-03-15, SSN last four is 4472."
)


def submit(event: Event) -> None:
    traces = st.session_state.setdefault("llm_traces", {})
    live_debug = st.empty()
    try:
        if "workflow" not in st.session_state:
            st.session_state.workflow = build_workflow(
                OpenRouterReasoner(
                    create_model(api_key=st.session_state.get("openrouter_api_key"))
                ),
                FixtureRepository(),
            )
        result = None
        with observe_turn(st.session_state.conversation, event, source="ui") as turn_trace:
            for mode, update in st.session_state.workflow.stream(
                {"session": st.session_state.conversation, "event": event},
                stream_mode=["custom", "updates"],
            ):
                if mode == "custom":
                    trace = record_event(traces, update)
                    if update["type"] == "start":
                        with live_debug.container():
                            st.caption(
                                f"Live debug · {trace.stage} · {trace.model} · unvalidated output"
                            )
                            with st.expander("Input messages and output schema"):
                                st.json(trace.messages, expanded=False)
                                st.json(trace.response_format, expanded=False)
                            output = st.empty()
                    output.code(trace.output_text, language="json")
                elif "record" in update:
                    result = update["record"]
            if result is None:
                raise RuntimeError("Workflow ended without a recorded turn.")
            turn_trace.finish(result["session"])
    except Exception as error:  # noqa: BLE001 - one outer UI boundary, with a visible failure.
        # UI boundary: do not display SDK request bodies, secrets, or partial graph state.
        st.error(
            f"The turn failed ({type(error).__name__}). Your conversation was not changed. "
            "Check your OpenRouter key, credits, and model setting, then retry. "
            "The LLM debug tab has call details."
        )
        return
    st.session_state.conversation = result["session"]
    st.rerun()


def controls(session: Session, *, model_ready: bool) -> None:
    with st.sidebar:
        st.subheader("Demo controls")
        scenario = st.selectbox("Representative consent", ["default", "timeout"])
        demo_date = st.date_input("New conversation date", value=date(2026, 3, 10))
        if st.button("New conversation", key="new_conversation", use_container_width=True):
            st.session_state.pop("workflow", None)
            st.session_state.pop("llm_traces", None)
            st.session_state.conversation = Session(
                consent_scenario=scenario,
                now=datetime.combine(demo_date, time(10), tzinfo=UTC),
            )
            st.rerun()
        st.caption("Scenario and start date apply to new conversations.")
        st.write(f"Clock: {session.now:%Y-%m-%d %H:%M:%S} UTC")
        advance = st.selectbox(
            "Advance by",
            [10, 30, 120, 86400],
            format_func=lambda n: f"{n} seconds" if n < 86400 else "1 day",
        )
        if st.button(
            "Advance time",
            key="advance_time",
            disabled=not model_ready or session.disposition != "active",
            use_container_width=True,
        ):
            with st.spinner("Checking time-dependent conditions..."):
                submit(Event(kind="advance_time", seconds=advance))
        st.caption("The clock moves only with this control. Consent expires after 120 seconds.")
        with st.expander("Margaret sample"):
            st.code(SAMPLE, language=None)
        st.caption(
            "Use the sample fixture identities. No emails, transfers, or claim changes occur."
        )


def outcome_view(session: Session) -> None:
    outcome = session.outcome
    if not outcome.case_id and not outcome.handoff_reason:
        return
    st.subheader("Support outcome" if session.disposition != "active" else "Outcome so far")
    if outcome.case_id:
        st.write(f"**{outcome.case_id}** · {outcome.claim_status}")
        st.write(outcome.claim_summary)
    for title, entries in (("Discussed", outcome.discussed), ("Next steps", outcome.next_steps)):
        if entries:
            st.markdown(f"**{title}**")
            for entry in entries:
                st.markdown(f"- {entry.text}")
    if outcome.unresolved_questions:
        st.markdown("**Questions for human support**")
        for question in outcome.unresolved_questions:
            st.markdown(f"- {question}")
    if outcome.handoff_reason:
        st.info(f"Human support requested: {outcome.handoff_reason} No actual transfer was made.")
    if session.follow_up.email_draft:
        with st.expander("Email summary draft", expanded=session.disposition == "completed"):
            st.caption(f"Choice: {session.follow_up.choice}. Delivery is simulated; no email sent.")
            st.text(session.follow_up.email_draft)
    if session.disposition != "active":
        export = {
            "outcome": outcome.model_dump(),
            "prior_outcomes": {
                key: value.model_dump() for key, value in session.prior_outcomes.items()
            },
            "email_choice": session.follow_up.choice,
            "delivery": session.follow_up.delivery,
            "disposition": session.disposition,
        }
        st.download_button(
            "Download outcome",
            json.dumps(export, indent=2),
            file_name="support-outcome.json",
            mime="application/json",
        )


def main() -> None:
    st.set_page_config(page_title="Claims Support · SOP Demo", page_icon="💬", layout="wide")
    if "conversation" not in st.session_state:
        st.session_state.conversation = Session()
    session = st.session_state.conversation
    st.title("Claims support")
    st.caption("A conversational SOP demo · LangGraph + OpenRouter · simulated follow-up")
    model_ready = connection_controls()
    if not model_ready:
        st.info("To start the demo, enter your API key under Connect to OpenRouter.")
    controls(session, model_ready=model_ready)
    chat, state_panel = st.columns([3, 2], gap="large")
    with chat:
        if not session.messages:
            with st.chat_message("assistant"):
                st.write(
                    "Hello! I can help with your insurance claim. Tell me what you need, and we'll verify your identity before discussing claim details."
                )
        for message in session.messages:
            with st.chat_message(message.role):
                st.write(message.content)
        st.caption(
            "For date of birth, we recommend YYYY-MM-DD (year-month-day), for example 1990-12-31, "
            "to avoid day/month confusion."
        )
        text = st.chat_input(
            "Message claims support" if model_ready else "Enter an OpenRouter API key to chat",
            disabled=not model_ready or session.disposition != "active",
            max_chars=12000,
        )
        if text:
            with st.spinner("Working through your request..."):
                submit(Event(text=text))
        if session.disposition != "active":
            st.success(
                f"Conversation {session.disposition.replace('_', ' ')}. Start a new conversation to test another scenario."
            )
        outcome_view(session)
    with state_panel:
        state_tab, debug_tab = st.tabs(["Workflow state", "LLM debug"])
        with state_tab:
            st.subheader("Workflow state")
            st.badge(session.phase.value, color="blue")
            st.caption("Caller values and workflow state for the demo tester.")
            st.json(inspector(session), expanded=2)
        with debug_tab:
            debug_console(st.session_state.get("llm_traces", {}))
