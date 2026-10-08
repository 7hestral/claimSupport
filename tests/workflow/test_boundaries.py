"""Output validation, session isolation, and atomic turn updates."""

import pytest

from apps.insurance_claims.schemas.state import DraftReply, Event, Session
from apps.insurance_claims.workflow.presentation import inspector


def test_untrusted_output_cannot_reference_unauthorized_evidence(harness, margaret):
    turn, model, initial = harness(margaret)
    model.respond = lambda context, **kwargs: DraftReply(
        reply="Made up", discussed_evidence_ids=["foreign.claim"]
    )
    with pytest.raises(ValueError, match="outside the authorized"):
        turn()
    assert initial.messages == []
    assert initial.verification.verified_party_id is None
    assert initial.outcome.case_id is None


@pytest.mark.parametrize(
    "reference,accepted",
    [("guidance.document_guidance.pathology_report", True), ("claim.status", False)],
)
def test_next_steps_can_use_authorized_guidance_but_not_claim_facts(
    harness, margaret, reference, accepted
):
    margaret.topics = ["format"]
    turn, model, _ = harness(margaret)
    model.respond = lambda context, **kwargs: DraftReply(
        reply="Prepare a complete readable copy, confirming any original requirement with support.",
        discussed_evidence_ids=["guidance.document_guidance.pathology_report"],
        next_step_evidence_ids=[reference],
    )
    if accepted:
        session = turn()
        assert [entry.id for entry in session.outcome.next_steps] == [reference]
    else:
        with pytest.raises(ValueError, match="outside the allowed guidance"):
            turn()


def test_conversations_are_isolated_and_debug_state_shows_caller_values(harness, margaret):
    turn, _, initial = harness(margaret)
    finished_turn = turn()
    other = Session()
    assert initial.messages == other.messages == []
    assert other.verification.verified_party_id is None
    assert other.session_id != finished_turn.session_id
    view = str(inspector(finished_turn))
    assert "4472" in view
    assert "1985-03-15" in view
    assert "Margaret Chen" in view


def test_failed_model_call_does_not_commit_extracted_identity(harness, margaret):
    turn, model, initial = harness(margaret)

    def fail(context, **kwargs):
        raise TimeoutError("Model unavailable")

    model.respond = fail
    with pytest.raises(TimeoutError):
        turn()
    assert initial.memory.full_name is None
    assert initial.messages == []


def test_clock_tick_does_not_count_as_user_identity_attempt(harness):
    turn, _, initial = harness()
    session = turn(initial, Event(kind="advance_time", seconds=30))
    assert session.verification.failed_attempts == 0
    assert all(message.role != "user" for message in session.messages)
