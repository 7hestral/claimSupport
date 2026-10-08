"""Exercise real streaming, JSON validation, graph events, and the tester console."""

from streamlit.testing.v1 import AppTest

from apps.insurance_claims.debug_ui import record_event, usage_rows
from apps.insurance_claims.reasoner import OpenRouterReasoner
from apps.insurance_claims.repository import FixtureRepository
from apps.insurance_claims.schemas.facts import Observation
from apps.insurance_claims.schemas.state import DraftReply, Event, Session
from apps.insurance_claims.workflow import build_workflow


def test_streamed_calls_report_separate_usage_and_fixed_reply_skips_speaker(
    streaming_model, margaret
):
    model = streaming_model(
        (margaret, {"input_tokens": 11, "output_tokens": 5, "total_tokens": 16}),
        (
            DraftReply(
                reply="Missing pathology report and office note.",
                discussed_evidence_ids=["claim.denial"],
            ),
            {"input_tokens": 23, "output_tokens": 7, "total_tokens": 30},
        ),
        (
            Observation(scope="out_of_scope"),
            {"input_tokens": 13, "output_tokens": 4, "total_tokens": 17},
        ),
    )
    graph = build_workflow(OpenRouterReasoner(model), FixtureRepository())
    session = Session()
    traces = {}
    kinds = []
    for text in ("Margaret's fixture details", "What is RL?"):
        for mode, update in graph.stream(
            {"session": session, "event": Event(text=text)}, stream_mode=["custom", "updates"]
        ):
            if mode == "custom":
                kinds.append(update["type"])
                trace = record_event(traces, update)
                if update["type"] == "delta":
                    assert trace.parsed is None  # Never pass partial JSON off as validated output.
            elif "record" in update:
                session = update["record"]["session"]
    assert kinds.count("start") == kinds.count("finish") == 3
    calls = list(traces.values())
    assert [call.stage for call in calls] == ["extraction", "response", "extraction"]
    assert all(call.status == "succeeded" for call in calls)
    assert calls[0].parsed["facts"]["full_name"] == "Margaret Chen"
    assert calls[1].parsed["reply"] == "Missing pathology report and office note."
    rows = {row["LLM"]: row for row in usage_rows(calls)}
    assert rows["extraction"]["Input tokens"] == 24
    assert rows["extraction"]["Output tokens"] == 9
    assert rows["response"]["Total tokens"] == 30
    assert session.last_action == "redirect_scope"
    assert session.selected_case_id == "CL-2048"


def test_ui_retains_failed_call_diagnostics_without_committing_state(streaming_model, margaret):
    graph = build_workflow(
        OpenRouterReasoner(
            streaming_model(
                (margaret, {"input_tokens": 11, "output_tokens": 5, "total_tokens": 16}),
                (TimeoutError("private provider error details"), None),
            )
        ),
        FixtureRepository(),
    )
    app = AppTest.from_file("../app.py").run()
    app.session_state["workflow"] = graph
    app.chat_input[0].set_value("Margaret fixture").run()
    assert not app.exception
    assert app.session_state["conversation"].messages == []
    assert app.session_state["conversation"].verification.verified_party_id is None
    calls = list(app.session_state["llm_traces"].values())
    assert len(calls) == 2
    assert calls[-1].status == "failed"
    assert calls[-1].output_text == '{"reply":"partial'
    assert calls[-1].usage is None
    assert calls[-1].error_type == "TimeoutError"
    assert all("private provider" not in error.value for error in app.error)
    assert len(app.table) == 1
    rows = {row["LLM"]: row for row in usage_rows(calls)}
    assert rows["response"]["Input tokens"] is None
    assert rows["response"]["Usage unavailable"] == 1
    assert any(code.value == '{"reply":"partial' for code in app.code)
    app.button[0].click().run()
    assert "llm_traces" not in app.session_state
