"""Public workflow contracts: phase gates, memory, authorized access, and outcomes."""

import pytest

from apps.insurance_claims.repository import FixtureRepository
from apps.insurance_claims.schemas.facts import CallerFacts, Observation
from apps.insurance_claims.schemas.state import Event, Phase


@pytest.mark.parametrize("choice", ["send", "skip"])
def test_full_conversation_requires_wrapup_and_explicit_email_choice(harness, margaret, choice):
    turn, _, _ = harness(
        margaret,
        Observation(topic="submission", conversation_action="ask_followup"),
        Observation(conversation_action="finish_case"),
        Observation(email_choice=choice),
    )
    session = turn()
    assert session.phase == Phase.PROCESS_CASE
    assert session.verification.verified_party_id == "P9"
    assert session.selected_case_id == "CL-2048"
    assert session.phase_history == [Phase.VERIFY_ID, Phase.RESOLVE_INTENT, Phase.PROCESS_CASE]
    assert session.outcome.claim_status == "denied"
    assert session.disposition == "active"
    session = turn(session)
    assert session.phase == Phase.PROCESS_CASE
    assert "guidance.submission_method" in {e.id for e in session.outcome.discussed}
    session = turn(session)
    assert session.phase == Phase.POST_PROCESS
    assert session.follow_up.email_choice == "pending"
    assert session.disposition == "active"
    session = turn(session)
    assert session.disposition == "completed"
    assert session.follow_up.email_choice == choice
    assert session.follow_up.delivery == ("simulated_only" if choice == "send" else "not_requested")
    assert "pathology report" in session.follow_up.email_draft
    assert "4472" not in session.follow_up.email_draft
    assert "1985-03-15" not in session.follow_up.email_draft
    assert "no email was sent" in session.messages[-1].content.lower()
    with pytest.raises(ValueError, match="closed"):
        turn(session)


def test_early_case_hint_survives_partial_identity_without_claim_access(harness, margaret):
    partial = margaret.model_copy(deep=True)
    partial.facts.dob = None
    partial.facts.id_last4 = None
    partial.facts.id_type = None
    turn, model, _ = harness(
        partial, Observation(facts=CallerFacts(dob="1985-03-15", phone="650-521-2836"))
    )
    session = turn()
    assert session.phase == Phase.VERIFY_ID
    assert model.contexts[-1]["evidence"] == []
    assert model.contexts[-1]["candidates"] == []
    assert session.verification.failed_attempts == 0
    with pytest.raises(PermissionError):
        FixtureRepository().claims_for(session)
    session = turn(session)
    assert session.selected_case_id == "CL-2048"
    assert session.memory.case_month == 1
    assert session.memory.case_year is None


@pytest.mark.parametrize(
    "name,dob,digits,party",
    [
        ("Ma Tian", "1964-09-10", "6688", "P12"),
        ("Yaven Li", "1989-12-03", "5317", "P13"),
    ],
)
def test_national_id_and_explicit_fixture_aliases_count(harness, name, dob, digits, party):
    turn, _, _ = harness(
        Observation(
            facts=CallerFacts(
                full_name=name,
                dob=dob,
                id_last4=digits,
                id_type="national_id_last4",
                caller_role="policyholder",
            )
        )
    )
    session = turn()
    assert session.verification.verified_party_id == party
    assert len(session.verification.matched_fields) == 3


@pytest.mark.parametrize(
    "change",
    [
        {"id_last4": None},  # Policy number is not a third PII field.
        {"id_type": "national_id_last4"},  # Correct digits, wrong ID type.
        {"email": "wrong@example.com"},  # Contradictory extra PII must not be ignored.
        {"full_name": "Ma Tian"},  # Fields cannot be combined across people.
    ],
)
def test_identity_gate_rejects_incomplete_or_conflicting_data(harness, margaret, change):
    margaret.facts = margaret.facts.model_copy(update=change)
    turn, model, _ = harness(margaret)
    session = turn()
    assert session.verification.verified_party_id is None
    assert session.selected_case_id is None
    assert not model.contexts[-1]["evidence"]


def test_foreign_case_id_never_retrieves_another_customers_claim(harness, margaret):
    margaret.facts.case_id = "CL-3001"
    turn, model, _ = harness(margaret)
    session = turn()
    assert session.verification.verified_party_id == "P9"
    assert session.phase == Phase.RESOLVE_INTENT
    assert session.selected_case_id is None
    assert model.contexts[-1]["candidates"] == []
    with pytest.raises(PermissionError):
        FixtureRepository().claim_for(session, "CL-3001")


def test_ambiguous_january_claim_requires_clarification(harness, margaret):
    margaret.facts.case_status = None
    turn, model, _ = harness(margaret, Observation(facts=CallerFacts(case_id="CL-2048")))
    session = turn()
    assert session.phase == Phase.RESOLVE_INTENT
    assert {c["case_id"] for c in model.contexts[-1]["candidates"]} == {"CL-2048", "CL-2011"}
    session = turn(session)
    assert session.selected_case_id == "CL-2048"


def test_identity_correction_revokes_access_and_clears_outcome(harness, margaret):
    turn, model, _ = harness(margaret, Observation(facts=CallerFacts(full_name="Ma Tian")))
    session = turn()
    session.messages[-1].content = "The pathology report is missing from CL-2048."
    session = turn(session, Event(text="Actually, my name is Ma Tian."))
    assert session.phase == Phase.VERIFY_ID
    assert session.verification.verified_party_id is None
    assert session.selected_case_id is None
    assert session.outcome.case_id is None
    assert model.contexts[-1]["evidence"] == []
    assert model.contexts[-1]["outcome"]["discussed"] == []
    assert model.contexts[-1]["history"] == []
    assert "pathology" not in str(model.contexts[-1])
    assert model.contexts[-1]["latest_user_message"] == "Actually, my name is [provided]."


def test_followup_does_not_close_case_or_accept_email_prematurely(harness, margaret):
    turn, _, _ = harness(
        margaret,
        Observation(conversation_action="ask_followup", topic="format", email_choice="send"),
        Observation(conversation_action="finish_case"),
        Observation(conversation_action="ask_followup", topic="receipt", email_choice="send"),
    )
    session = turn(turn())
    assert session.phase == Phase.PROCESS_CASE
    assert session.follow_up.email_choice == "not_asked"
    session = turn(session)
    assert session.phase == Phase.POST_PROCESS
    session = turn(session)
    assert session.disposition == "active"
    assert session.follow_up.email_choice == "pending"


def test_early_email_preference_is_remembered_but_requires_later_confirmation(harness, margaret):
    margaret.email_choice = "send"
    turn, _, _ = harness(margaret, Observation(conversation_action="finish_case"))
    session = turn()
    assert session.memory.summary_preference == "send"
    assert session.follow_up.email_choice == "not_asked"
    session = turn(session)
    assert session.memory.summary_preference == "send"
    assert session.follow_up.email_choice == "pending"
    assert session.disposition == "active"


@pytest.mark.parametrize(
    "case_type,case_id,status",
    [
        ("auto", "CL-2102", "open"),
        ("dental", "CL-1899", "closed"),
    ],
)
def test_switching_cases_reuses_identity_and_replaces_case_outcome(
    harness, margaret, case_type, case_id, status
):
    turn, _, _ = harness(
        margaret,
        Observation(
            new_case=True,
            topic="payment",
            conversation_action="ask_followup",
            facts=CallerFacts(case_type=case_type, intent_hint="Explain payment"),
        ),
    )
    session = turn(turn())
    assert session.verification.verified_party_id == "P9"
    assert session.selected_case_id == case_id
    assert session.outcome.claim_status == status
    assert all(entry.id != "claim.denial" for entry in session.outcome.discussed)
    assert any(entry.id == "claim.net_pay" for entry in session.outcome.discussed)
