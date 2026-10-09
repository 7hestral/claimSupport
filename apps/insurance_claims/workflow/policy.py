"""Deterministic turn policy: authorization, bounded case selection, and closing."""

from datetime import timedelta

from pydantic import Field

from ..data.repository import FixtureRepository
from ..schemas.facts import Observation, StrictModel
from ..schemas.state import Event, Evidence, FollowUp, Outcome, Phase, Session
from .guidance import claim_evidence
from .identity import IDENTITY_FIELDS, authorize_representative, verify
from .memory import transition

EMAIL_CHOICE_TIMEOUT_SECONDS = 120


class TurnPlan(StrictModel):
    action: str
    evidence: list[Evidence] = Field(default_factory=list)
    candidates: list[dict[str, str]] = Field(default_factory=list)
    offer_human: bool = False
    fixed_reply: str | None = None


def handoff(session: Session, reason: str) -> TurnPlan:
    session.disposition = "handoff_requested"
    session.outcome.handoff_reason = reason
    return TurnPlan(
        action="handoff",
        fixed_reply=(
            "I've recorded a request for a human claims representative. "
            "This demo does not make a real transfer. Your support outcome is available below."
        ),
    )


def identity_plan(session: Session, repository: FixtureRepository) -> TurnPlan | None:
    if session.verification.verified_party_id:
        return None
    if session.memory.caller_role is None:
        return TurnPlan(action="confirm_caller_role", offer_human=session.recovery_attempts >= 2)
    if session.verification.failed_attempts >= 3:
        return TurnPlan(action="verification_limit", offer_human=True)
    customer = verify(session, repository)
    if customer is None:
        supplied = sum(getattr(session.memory, key) is not None for key in IDENTITY_FIELDS)
        action = "verification_mismatch" if supplied >= 3 else "collect_identity"
        if session.verification.failed_attempts >= 3:
            action = "verification_limit"
        return TurnPlan(
            action=action,
            offer_human=(
                session.recovery_attempts >= 2 or session.verification.failed_attempts >= 3
            ),
        )
    if session.memory.caller_role == "representative":
        action = authorize_representative(session, customer, repository)
        if action != "authorized":
            return TurnPlan(
                action=action,
                offer_human=(
                    action == "representative_unavailable" or session.recovery_attempts >= 2
                ),
            )
    session.verification.verified_party_id = customer.party_id
    session.recovery_attempts = 0
    transition(session, Phase.RESOLVE_INTENT)
    return None


def resolve_case(session: Session, repository: FixtureRepository) -> TurnPlan | None:
    claims = repository.claims_for(session)
    facts = session.case_hints
    candidates = claims
    if facts.case_id:
        candidates = [c for c in candidates if c.case_id.casefold() == facts.case_id.casefold()]
    else:
        for field, value in (("case_type", facts.case_type), ("status", facts.case_status)):
            if value:
                candidates = [c for c in candidates if getattr(c, field) == value]
        if facts.case_month:
            candidates = [c for c in candidates if c.created_at.month == facts.case_month]
        if facts.case_year:
            candidates = [c for c in candidates if c.created_at.year == facts.case_year]
    if len(candidates) != 1:
        action = "clarify_case" if candidates else "case_not_found"
        return TurnPlan(
            action=action,
            offer_human=not claims,
            candidates=[
                {
                    "case_id": c.case_id,
                    "case_type": c.case_type,
                    "created_at": str(c.created_at),
                    "status": c.status,
                }
                for c in candidates
            ],
        )
    claim = candidates[0]
    session.selected_case_id = claim.case_id
    if session.outcome.case_id != claim.case_id:
        if session.outcome.case_id:
            session.prior_outcomes[session.outcome.case_id] = session.outcome
        session.outcome = session.prior_outcomes.pop(
            claim.case_id,
            Outcome(case_id=claim.case_id, claim_status=claim.status, claim_summary=claim.summary),
        )
        session.follow_up = FollowUp(choice=session.follow_up.choice)
    session.follow_up.offer_status = "not_offered"
    session.follow_up.expires_at = None
    transition(session, Phase.PROCESS_CASE)
    return None


def plan_turn(
    session: Session, observation: Observation, repository: FixtureRepository, event: Event
) -> TurnPlan:
    follow_up = session.follow_up
    if (
        session.phase == Phase.POST_PROCESS
        and follow_up.offer_status == "pending"
        and follow_up.expires_at is not None
        and session.now >= follow_up.expires_at
        and follow_up.expires_at <= session.inactivity_expires_at
    ):
        follow_up.choice = "skip"
        follow_up.offer_status = "timed_out"
        follow_up.delivery = "not_requested"
        session.disposition = "completed"
        return TurnPlan(
            action="email_timeout",
            fixed_reply=(
                "The email-summary choice timed out on the demo clock, so I've skipped the email. "
                "No email was sent. Your support summary and next steps are available below."
            ),
        )
    authorization = session.authorization
    if (
        authorization.status == "pending"
        and authorization.expires_at is not None
        and session.now >= authorization.expires_at
        and authorization.expires_at <= session.inactivity_expires_at
    ):
        authorization.status = "timed_out"
        return handoff(session, "Representative consent expired while pending.")
    if session.now >= session.inactivity_expires_at:
        follow_up.choice = "skip"
        follow_up.delivery = "not_requested"
        if follow_up.offer_status == "pending":
            follow_up.offer_status = "timed_out"
        session.disposition = "timed_out"
        return TurnPlan(
            action="inactivity_timeout",
            fixed_reply=(
                "This conversation timed out after 3 minutes without a caller message on the "
                "demo clock. No email was sent. Start a new conversation to continue."
            ),
        )
    if event.kind == "advance_time" and follow_up.offer_status == "pending":
        seconds = int((follow_up.expires_at - session.now).total_seconds())
        unit = "second" if seconds == 1 else "seconds"
        return TurnPlan(
            action="offer_email",
            fixed_reply=(
                f"You have {seconds} {unit} left on the demo clock to confirm send or skip "
                f"for the summary to {follow_up.recipient}. The choice is still pending; "
                "if the time expires, it defaults to skip. This demo prepares a draft "
                "and records your choice; no email is actually sent."
            ),
        )
    if observation.conversation_action == "request_human":
        return handoff(session, "Caller requested human support.")
    if observation.conversation_action == "end_conversation":
        session.disposition = "ended"
        return TurnPlan(
            action="ended",
            fixed_reply="I've ended this support conversation. No email was sent or claim action taken.",
        )
    if observation.scope == "out_of_scope":
        session.out_of_scope_attempts += 1
        offer = session.out_of_scope_attempts >= 3
        text = "I can help with insurance claims and this support process. What would you like to know about your claim?"
        if offer:
            text = "I can only help with insurance claims here. Would you like me to record a request for a human representative?"
        return TurnPlan(action="redirect_scope", offer_human=offer, fixed_reply=text)
    blocked = identity_plan(session, repository)
    if blocked:
        return blocked
    if session.phase == Phase.RESOLVE_INTENT:
        clarification = resolve_case(session, repository)
        if clarification:
            return clarification
    claim = repository.claim_for(session, session.selected_case_id)
    evidence = claim_evidence(claim, repository, session.now.date(), session.pending_topics)
    offer_human = observation.alternatives_exhausted or any(
        e.id == "step.expired" for e in evidence
    )
    if session.phase == Phase.PROCESS_CASE:
        if observation.conversation_action == "finish_case" and session.outcome.discussed:
            transition(session, Phase.POST_PROCESS)
            session.follow_up.offer_status = "pending"
            session.follow_up.expires_at = session.now + timedelta(
                seconds=EMAIL_CHOICE_TIMEOUT_SECONDS
            )
            customer = repository.customer(session.verification.verified_party_id)
            session.follow_up.recipient = customer.email
            return TurnPlan(action="offer_email", evidence=evidence, offer_human=offer_human)
        return TurnPlan(action="answer_case", evidence=evidence, offer_human=offer_human)
    if observation.conversation_action == "ask_followup":
        session.follow_up.expires_at = session.now + timedelta(seconds=EMAIL_CHOICE_TIMEOUT_SECONDS)
        return TurnPlan(
            action="answer_then_offer_email", evidence=evidence, offer_human=offer_human
        )
    if observation.email_choice in {"send", "skip"}:
        session.follow_up.offer_status = "confirmed"
        session.follow_up.delivery = (
            "simulated_only" if observation.email_choice == "send" else "not_requested"
        )
        session.disposition = "completed"
        if observation.email_choice == "send":
            reply = (
                "Your summary draft is ready, and I've recorded your choice to send it to "
                f"{session.follow_up.recipient}. This is a demo; no email was sent. "
                "You can review your support outcome and next steps below."
            )
        else:
            reply = (
                "Understood, I'll skip the email. Your support summary and next steps are "
                "available below. No email was sent."
            )
        return TurnPlan(action="finish", fixed_reply=reply)
    return TurnPlan(action="offer_email", evidence=evidence, offer_human=offer_human)
