"""Fixture facts and bounded guidance at the real conversation boundary."""

import re
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.insurance_claims.schemas.facts import Observation
from apps.insurance_claims.schemas.state import DraftReply, Session


@pytest.mark.parametrize(
    "case_id,amounts",
    [
        ("CL-2011", (780, 800, 780, 800)),
        ("CL-1899", (425, 450, 425, 450)),
        ("CL-2102", (3200, 3500, 0, 3500)),
    ],
)
def test_payment_evidence_preserves_expected_allowed_paid_and_fee(
    harness, margaret, case_id, amounts
):
    margaret.facts.case_id = case_id
    margaret.topic = "payment"
    turn, model, _ = harness(margaret)
    turn()
    evidence = {entry["id"]: entry["text"] for entry in model.contexts[-1]["evidence"]}
    fields = ("expected_reimbursement_amount", "allowed_max_amount", "net_pay", "net_fee")
    observed = tuple(
        Decimal(re.search(r"USD (\d+\.\d{2})", evidence[f"claim.{field}"])[1]) for field in fields
    )
    assert observed == amounts


@pytest.mark.parametrize("day,target", [(10, "2026-03-17"), (15, "2026-03-18")])
def test_submission_target_is_bounded_and_distinct_from_processing_time(
    harness, margaret, day, target
):
    margaret.topic = "submission_timing"
    turn, model, _ = harness(
        margaret,
        Observation(topic="processing_time", conversation_action="ask_followup"),
        session=Session(now=datetime(2026, 3, day, tzinfo=UTC)),
    )
    session = turn()
    evidence = {entry["id"]: entry["text"] for entry in model.contexts[-1]["evidence"]}
    assert target in evidence["guidance.submission_timing"]
    assert "guidance.processing_time_after_submission" not in evidence
    turn(session)
    evidence = {entry["id"]: entry["text"] for entry in model.contexts[-1]["evidence"]}
    assert "usually less than a week" in evidence["guidance.processing_time_after_submission"]
    assert "guidance.submission_timing" not in evidence


def test_exhausted_document_alternatives_offer_human_without_mutating_claim(harness, margaret):
    turn, model, _ = harness(
        margaret,
        Observation(topic="alternatives", conversation_action="ask_followup"),
        Observation(topic="alternatives", alternatives_exhausted=True),
    )
    session = turn(turn())
    evidence = {entry["id"] for entry in model.contexts[-1]["evidence"]}
    assert {
        "guidance.document_alternative_guidance.pathology_report",
        "guidance.document_alternative_guidance.office_note",
        "step.manual_review",
    } <= evidence
    session = turn(session)
    assert model.contexts[-1]["offer_human"]
    assert session.disposition == "active"  # Offer does not invent acceptance of a transfer.
    assert session.outcome.claim_status == "denied"


def test_summary_preserves_status_discussion_next_steps_and_unresolved_question(harness, margaret):
    question = "Who is my assigned adjuster?"
    turn, model, _ = harness(
        margaret,
        Observation(conversation_action="finish_case"),
        Observation(email_choice="send"),
    )
    model.respond = lambda context, **kwargs: DraftReply(
        reply="The requested documents are missing; request copies from the provider. "
        "The record does not identify your adjuster.",
        discussed_evidence_ids=["claim.denial"],
        next_step_evidence_ids=["step.documents"],
        unanswered_question=question,
    )
    session = turn(turn(turn()))
    draft = session.follow_up.email_draft
    assert session.follow_up.recipient == "margaret@email.com"
    assert session.outcome.claim_status in draft
    assert all(entry.text in draft for entry in session.outcome.discussed)
    assert all(entry.text in draft for entry in session.outcome.next_steps)
    assert question in draft
    assert "4472" not in draft
    assert "1985-03-15" not in draft
