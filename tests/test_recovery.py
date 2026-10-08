"""Scope, attempt limits, refusal handling, and consent-time contracts."""

from datetime import UTC, date, datetime

import pytest

from apps.insurance_claims.schemas.facts import CallerFacts, Observation
from apps.insurance_claims.schemas.state import Event, Phase, Session


def test_repeated_irrelevant_questions_are_rejected_then_offer_human(harness):
    turn, model, _ = harness(*[Observation(scope="out_of_scope") for _ in range(3)])
    session = turn(turn(turn()))
    assert session.phase == Phase.VERIFY_ID
    assert session.out_of_scope_attempts == 3
    assert "human representative" in session.messages[-1].content
    assert model.contexts == []  # Out-of-scope replies cannot invoke free-form generation.


def test_three_distinct_failed_submissions_limit_verification(harness, margaret):
    invalid = margaret.model_copy(deep=True)
    invalid.facts.dob = date(1985, 3, 16)
    turn, model, _ = harness(
        invalid,
        Observation(),
        Observation(facts=CallerFacts(dob="1985-03-17")),
        Observation(facts=CallerFacts(dob="1985-03-18")),
    )
    session = turn()
    assert session.verification.failed_attempts == 1
    session = turn(session)
    assert session.verification.failed_attempts == 1
    session = turn(turn(session))
    assert session.verification.failed_attempts == 3
    assert model.contexts[-1]["action"] == "verification_limit"
    assert model.contexts[-1]["offer_human"]


@pytest.mark.parametrize("role", [None, "policyholder"])
def test_repeated_refusal_offers_human_without_bypassing_gate(harness, role):
    turn, model, _ = harness(
        Observation(
            facts=CallerFacts(caller_role=role),
            refuses_verification=True,
        ),
        Observation(refuses_verification=True),
        Observation(conversation_action="request_human"),
    )
    session = turn(turn())
    assert model.contexts[-1]["offer_human"]
    assert session.verification.verified_party_id is None
    session = turn(session)
    assert session.disposition == "handoff_requested"
    assert session.outcome.handoff_reason == "Caller requested human support."


def test_emotional_process_questions_reach_speaker_without_counting_as_refusal(harness):
    turn, model, initial = harness(
        Observation(facts=CallerFacts(full_name="Margaret Chen", caller_role="policyholder")),
        Observation(),
        Observation(),
    )
    session = turn(initial, Event(text="I'm Margaret Chen, the policyholder."))
    session = turn(session, Event(text="I'm anxious. Why do you need to know that?"))
    session = turn(session, Event(text="I'm still confused. Can you explain the options?"))
    context = model.contexts[-1]
    assert session.recovery_attempts == 0
    assert not context["offer_human"]
    assert context["latest_user_message"] == "I'm still confused. Can you explain the options?"
    assert any("I'm anxious" in message["content"] for message in context["history"])
    assert not context["evidence"]


@pytest.mark.parametrize(
    "scenario,seconds,expected",
    [
        ("default", 10, "approved"),
        ("default", 120, "timed_out"),
        ("timeout", 120, "timed_out"),
    ],
)
def test_representative_consent_checks_status_and_expiry(
    harness, margaret, scenario, seconds, expected
):
    margaret.facts.caller_role = "representative"
    margaret.facts.representative_name = "David Chen"
    turn, model, _ = harness(margaret, session=Session(consent_scenario=scenario))
    session = turn()
    assert session.authorization.status == "pending"
    assert session.phase == Phase.VERIFY_ID
    assert session.verification.verified_party_id is None
    assert model.contexts[-1]["evidence"] == []
    session = turn(session, Event(kind="advance_time", seconds=seconds))
    assert session.authorization.status == expected
    if expected == "approved":
        assert session.phase == Phase.PROCESS_CASE
        assert session.selected_case_id == "CL-2048"
    else:
        assert session.phase == Phase.VERIFY_ID
        assert session.disposition == "handoff_requested"
        assert session.outcome.case_id is None


def test_expired_deadline_changes_guidance_without_ending_process(harness, margaret):
    margaret.topics = ["submission_timing", "processing_time"]
    turn, model, _ = harness(margaret, session=Session(now=datetime(2026, 10, 7, tzinfo=UTC)))
    session = turn()
    assert session.phase == Phase.PROCESS_CASE
    assert session.disposition == "active"
    evidence = {e["id"] for e in model.contexts[-1]["evidence"]}
    assert "step.expired" in evidence
    assert "guidance.submission_timing" not in evidence
    assert "guidance.processing_time_after_submission" not in evidence
    assert model.contexts[-1]["offer_human"]
