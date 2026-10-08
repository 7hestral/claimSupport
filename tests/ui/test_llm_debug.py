"""Exercise real streaming, JSON validation, graph events, and the tester console."""

import pytest

from apps.insurance_claims.data.repository import FixtureRepository
from apps.insurance_claims.llm.reasoner import OpenRouterReasoner
from apps.insurance_claims.observability import monitoring
from apps.insurance_claims.schemas.facts import Observation
from apps.insurance_claims.schemas.state import DraftReply, Event, Session
from apps.insurance_claims.ui.debug import record_event, usage_rows
from apps.insurance_claims.workflow.graph import build_workflow


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


def test_ui_retains_failed_call_diagnostics_without_committing_state(
    ui_app, streaming_model, margaret
):
    graph = build_workflow(
        OpenRouterReasoner(
            streaming_model(
                (margaret, {"input_tokens": 11, "output_tokens": 5, "total_tokens": 16}),
                (TimeoutError("private provider error details"), None),
            )
        ),
        FixtureRepository(),
    )
    app = ui_app.run()
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
    app.button(key="new_conversation").click().run()
    assert "llm_traces" not in app.session_state


@pytest.mark.parametrize(
    "connection",
    [
        (None, None, None),
        (None, "test-secret", "https://example.invalid"),
        ("test-public", None, "https://example.invalid"),
        ("test-public", "test-secret", None),
        ("test-public", "test-secret", "  "),
    ],
    ids=["absent", "missing-public", "missing-secret", "missing-url", "blank-url"],
)
def test_streaming_ui_commits_successful_turn_without_complete_monitoring_settings(
    ui_app, streaming_model, margaret, monkeypatch, connection
):
    monkeypatch.setattr(monitoring, "dotenv_values", lambda path: {})
    monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "true")
    for name, value in zip(
        ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL"), connection
    ):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)

    def unexpected_client(**kwargs):
        raise AssertionError("Incomplete monitoring settings must not initialize Langfuse")

    monkeypatch.setattr(monitoring, "Langfuse", unexpected_client)
    graph = build_workflow(
        OpenRouterReasoner(
            streaming_model(
                (margaret, {"input_tokens": 11, "output_tokens": 5, "total_tokens": 16}),
                (
                    DraftReply(reply="Recorded denial.", discussed_evidence_ids=["claim.denial"]),
                    None,
                ),
            )
        ),
        FixtureRepository(),
    )
    app = ui_app.run()
    app.session_state["workflow"] = graph
    app.chat_input[0].set_value("Margaret fixture").run()
    assert not app.exception
    assert not app.error
    assert app.session_state["conversation"].selected_case_id == "CL-2048"
    assert app.session_state["conversation"].messages[-1].content == "Recorded denial."
    assert len(app.session_state["llm_traces"]) == 2
