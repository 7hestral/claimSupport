"""Public workflow contracts: phase gates, memory, authorized access, and outcomes."""

import pytest

from apps.insurance_claims.repository import FixtureRepository
from apps.insurance_claims.schemas.facts import CallerFacts, CaseHints, Observation
from apps.insurance_claims.schemas.state import DraftReply, Event, Phase


@pytest.mark.parametrize("choice", ["send", "skip"])
def test_full_conversation_requires_wrapup_and_explicit_email_choice(harness, margaret, choice):
    turn, _, _ = harness(
        margaret,
        Observation(conversation_action="ask_followup", topics=["submission"]),
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
    assert session.follow_up.offer_status == "pending"
    assert session.disposition == "active"
    session = turn(session)
    assert session.disposition == "completed"
    assert session.follow_up.choice == choice
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
    assert session.case_hints.case_month == 1
    assert session.case_hints.case_year is None


def test_identified_claim_does_not_require_an_extracted_intent_string(harness, margaret):
    margaret.conversation_action = "continue"
    turn, _, _ = harness(margaret)
    session = turn()
    assert session.selected_case_id == "CL-2048"
    assert session.phase == Phase.PROCESS_CASE


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
    margaret.case_hints.case_id = "CL-3001"
    turn, model, _ = harness(margaret)
    session = turn()
    assert session.verification.verified_party_id == "P9"
    assert session.phase == Phase.RESOLVE_INTENT
    assert session.selected_case_id is None
    assert model.contexts[-1]["candidates"] == []
    with pytest.raises(PermissionError):
        FixtureRepository().claim_for(session, "CL-3001")


def test_ambiguous_january_claim_requires_clarification(harness, margaret):
    margaret.case_hints.case_status = None
    turn, model, _ = harness(margaret, Observation(case_hints=CaseHints(case_id="CL-2048")))
    session = turn()
    assert session.phase == Phase.RESOLVE_INTENT
    assert {c["case_id"] for c in model.contexts[-1]["candidates"]} == {"CL-2048", "CL-2011"}
    session = turn(session)
    assert session.selected_case_id == "CL-2048"


def test_identity_correction_revokes_access_and_clears_outcome(harness, margaret):
    auto = margaret.model_copy(deep=True)
    auto.case_hints = CaseHints(case_type="auto")
    turn, model, _ = harness(auto, margaret, Observation(facts=CallerFacts(full_name="Ma Tian")))
    session = turn(turn())
    assert "CL-2102" in session.prior_outcomes
    session.messages[-1].content = "The pathology report is missing from CL-2048."
    session = turn(session, Event(text="Actually, my name is Ma Tian."))
    assert session.phase == Phase.VERIFY_ID
    assert session.verification.verified_party_id is None
    assert session.selected_case_id is None
    assert session.outcome.case_id is None
    assert session.prior_outcomes == {}
    assert model.contexts[-1]["evidence"] == []
    assert model.contexts[-1]["outcome"]["discussed"] == []
    assert model.contexts[-1]["history"] == []
    assert "pathology" not in str(model.contexts[-1])
    assert "CL-2102" not in str(model.contexts[-1])
    assert model.contexts[-1]["latest_user_message"] == "Actually, my name is Ma Tian."


def test_ambiguous_correction_reaches_speaker_and_does_not_linger(harness, margaret):
    clarification = {
        "field": "dob",
        "provided_value": "04/03/1985",
        "reason": "ambiguous_date_order",
    }
    correction = Observation.model_validate(
        {"clear_fields": ["dob"], "clarifications": [clarification]}
    )
    turn, model, _ = harness(margaret, correction, Observation(facts=CallerFacts(dob="1985-03-15")))
    session = turn()
    session = turn(session, Event(text="Correction: my DOB is 04/03/1985."))
    assert session.memory.dob is None
    assert session.verification.verified_party_id is None
    assert model.contexts[-1]["evidence"] == []
    assert model.contexts[-1]["clarifications"] == [clarification]

    session = turn(session, Event(text="My correct DOB is March 15, 1985."))
    assert session.verification.verified_party_id == "P9"
    assert model.contexts[-1]["clarifications"] == []
    assert model.contexts[-1]["latest_user_message"] == "My correct DOB is March 15, 1985."
    assert model.contexts[-1]["history"][0]["content"] == "Correction: my DOB is 04/03/1985."


def test_followup_does_not_close_case_or_accept_email_prematurely(harness, margaret):
    turn, _, _ = harness(
        margaret,
        Observation(conversation_action="ask_followup", email_choice="send"),
        Observation(conversation_action="finish_case"),
        Observation(conversation_action="ask_followup", email_choice="send"),
    )
    session = turn(turn())
    assert session.phase == Phase.PROCESS_CASE
    assert session.follow_up.offer_status == "not_offered"
    session = turn(session)
    assert session.phase == Phase.POST_PROCESS
    session = turn(session)
    assert session.disposition == "active"
    assert session.follow_up.offer_status == "pending"


def test_early_email_preference_is_remembered_but_requires_later_confirmation(harness, margaret):
    margaret.email_choice = "send"
    turn, _, _ = harness(margaret, Observation(conversation_action="finish_case"))
    session = turn()
    assert session.follow_up.choice == "send"
    assert session.follow_up.offer_status == "not_offered"
    session = turn(session)
    assert session.follow_up.choice == "send"
    assert session.follow_up.offer_status == "pending"
    assert session.disposition == "active"


def test_same_claim_hint_refinement_preserves_unresolved_need(harness, margaret):
    turn, model, _ = harness(margaret, Observation(case_hints=CaseHints(case_id="CL-2048")))
    question = "Who can explain the approval notice I received?"
    model.respond = lambda context, **kwargs: DraftReply(
        reply="That notice is not in the available record.", unanswered_question=question
    )
    session = turn()
    model.respond = lambda context, **kwargs: DraftReply(
        reply="The current record still shows this claim denied.",
        discussed_evidence_ids=["claim.status"],
    )
    session = turn(session)
    assert session.verification.verified_party_id == "P9"
    assert session.selected_case_id == "CL-2048"
    assert session.outcome.unresolved_questions == [question]


def test_identity_formatting_preserves_representative_consent(harness, margaret):
    margaret.facts.caller_role = "representative"
    margaret.facts.representative_name = "David Chen"
    margaret.facts.phone = "650-521-2836"
    turn, _, _ = harness(
        margaret,
        Observation(facts=CallerFacts(full_name="margaret   chen", phone="+1 (650) 521-2836")),
    )
    session = turn()
    session = turn(session, Event(kind="advance_time", seconds=10))
    assert session.authorization.status == "approved"
    session = turn(session)
    assert session.authorization.status == "approved"
    assert session.verification.verified_party_id == "P9"
    assert session.selected_case_id == "CL-2048"


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
    margaret.topics = ["format"]
    turn, _, _ = harness(
        margaret,
        Observation(
            new_case=True,
            conversation_action="ask_followup",
            case_hints=CaseHints(case_type=case_type),
            topics=["payment", "payment"],
        ),
    )
    session = turn(turn())
    assert session.verification.verified_party_id == "P9"
    assert session.selected_case_id == case_id
    assert session.outcome.claim_status == status
    assert session.outcome.topics == ["payment"]
    assert session.prior_outcomes["CL-2048"].topics == ["format"]
    assert all(entry.id != "claim.denial" for entry in session.outcome.discussed)
    assert any(entry.id == "claim.net_pay" for entry in session.outcome.discussed)


def test_summary_retains_both_discussed_claims_without_mixing_them(harness, margaret):
    margaret.case_hints = CaseHints(case_type="auto")
    turn, _, _ = harness(
        margaret,
        Observation(new_case=True, case_hints=CaseHints(case_type="dental")),
        Observation(conversation_action="finish_case"),
        Observation(email_choice="send"),
    )
    session = turn(turn(turn(turn())))
    summary = session.follow_up.email_draft
    assert "CL-2102" in summary and "CL-1899" in summary
    auto, dental = summary.split("Claim CL-1899", 1)
    assert "3200.00" in auto and "425.00" not in auto
    assert "425.00" in dental and "3200.00" not in dental
