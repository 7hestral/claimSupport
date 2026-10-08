"""The evaluation boundary accepts wording variation and preserves review evidence."""

import json
from types import SimpleNamespace

import pytest

from apps.insurance_claims.data.repository import FixtureRepository
from apps.insurance_claims.schemas.facts import Observation
from apps.insurance_claims.schemas.state import DraftReply, Session
from apps.insurance_claims.workflow.graph import build_workflow
from apps.insurance_claims.workflow.policy import TurnPlan
from evals import __main__ as cli
from evals.runner import Case, Step, check_step, load_cases, run_case


def test_structured_checks_allow_free_text_and_unordered_extra_fields():
    step = Step(
        event={"text": "Caller input"},
        expect={"session.phase": "PROCESS_CASE"},
        present=["session.intent", "session.amount", "session.consent"],
        includes={"session.fields": ["name", "dob"]},
    )
    actual = {
        "session": {
            "phase": "PROCESS_CASE",
            "intent": "Help me understand the decision",
            "amount": 0,
            "consent": False,
            "fields": ["email", "dob", "name"],
        }
    }
    assert check_step(step, actual) == []
    actual["session"]["intent"] = "Explain my denied claim"
    assert check_step(step, actual) == []
    actual["session"]["intent"] = ""
    actual["session"]["phase"] = "VERIFY_ID"
    actual["session"]["fields"] = ["name"]
    failures = check_step(step, actual)
    assert len(failures) == 3
    assert all(
        any(path in failure for failure in failures) for path in ("phase", "intent", "fields")
    )
    del actual["session"]["intent"]
    assert "session.intent: missing field" in check_step(step, actual)


def test_report_saves_summary_and_before_state_even_when_an_expectation_fails(harness, margaret):
    _, reasoner, session = harness(
        margaret,
        Observation(conversation_action="finish_case"),
        Observation(email_choice="send"),
    )
    graph = build_workflow(reasoner, FixtureRepository())
    case = Case(
        id="report",
        review="Review actual replies against the recorded evidence and summary.",
        steps=[
            {"event": {"text": "Identity and case hint"}, "expect": {"session.phase": "VERIFY_ID"}},
            {"event": {"text": "Done with questions"}},
            {"event": {"text": "Send"}},
        ],
    )
    turns = list(run_case(graph, case))
    assert len(turns) == 3  # A state failure must not discard later review evidence.
    assert turns[0]["failures"]
    assert turns[0]["before"]["verification"]["verified_party_id"] is None
    assert turns[0]["plan"]["evidence"]
    assert turns[0]["draft"]["discussed_evidence_ids"]
    assert turns[-1]["before"]["follow_up"]["offer_status"] == "pending"
    assert turns[-1]["session"]["follow_up"]["choice"] == "send"
    assert turns[-1]["session"]["follow_up"]["email_draft"]
    assert turns[-1]["session"]["outcome"]["next_steps"]
    assert session.messages == []


def test_workflow_error_retains_event_and_stops_that_case(harness, margaret):
    _, reasoner, _ = harness(margaret)

    def fail(context, **kwargs):
        raise TimeoutError("Model unavailable")

    reasoner.respond = fail
    graph = build_workflow(reasoner, FixtureRepository())
    case = Case(
        id="failure",
        review="Incomplete execution is not a semantic pass.",
        steps=[{"event": {"text": "Identity"}}, {"event": {"text": "Skipped"}}],
    )
    turns = list(run_case(graph, case))
    assert len(turns) == 1
    assert turns[0]["event"]["text"] == "Identity"
    assert turns[0]["before"]["verification"]["verified_party_id"] is None
    assert turns[0]["error"]["type"] == "TimeoutError"
    assert turns[0]["failures"]
    assert "draft" not in turns[0]


def test_cli_finishes_other_cases_but_exits_failed_and_keeps_text_review_pending(
    harness, margaret, monkeypatch, tmp_path
):
    _, reasoner, _ = harness(margaret, margaret)
    original_respond = reasoner.respond
    calls = 0

    def respond(context, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("First case failed")
        return original_respond(context, **kwargs)

    reasoner.respond = respond
    cases = [
        Case(id=name, review="Review text separately", steps=[{"event": {"text": "Identity"}}])
        for name in ("first", "second")
    ]
    output = tmp_path / "report.json"
    monkeypatch.setattr(cli, "load_cases", lambda: cases)
    monkeypatch.setattr(cli, "create_model", lambda: SimpleNamespace(model_name="scripted"))
    monkeypatch.setattr(cli, "OpenRouterReasoner", lambda model: reasoner)
    monkeypatch.setattr("sys.argv", ["cli", "--case", "all", "--output", str(output)])

    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    report = json.loads(output.read_text())
    assert report["selected_cases"] == ["first", "second"]
    assert report["execution_status"] == "completed_with_failures"
    assert report["finished_at"]
    assert report["semantic_review"] == "pending"
    assert report["cases"][0]["turns"][0]["error"]["type"] == "TimeoutError"
    assert report["cases"][1]["turns"][0]["failures"] == []
    assert report["cases"][1]["turns"][0]["session"]["selected_case_id"] == "CL-2048"


@pytest.mark.parametrize("case", load_cases(), ids=lambda case: case.id)
def test_scenario_assertion_paths_belong_to_the_recorded_contract(case):
    # Prevent a misspelled scenario path from wasting live calls or silently omitting a check.
    actual = {
        "session": Session().model_dump(mode="json"),
        "observation": Observation().model_dump(mode="json"),
        "plan": TurnPlan(action="collect_identity").model_dump(mode="json"),
        "draft": DraftReply(reply="Any wording").model_dump(mode="json"),
    }
    for step in case.steps:
        failures = check_step(step, actual)
        assert not [failure for failure in failures if failure.endswith(": missing field")]
