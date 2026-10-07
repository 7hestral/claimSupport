"""Merge caller facts and revoke derived access when identity changes."""

from .identity import AUTH_FIELDS
from .schemas.facts import ConversationMemory, Observation
from .schemas.state import Authorization, FollowUp, Outcome, Phase, Session

CASE_FIELDS = ("case_id", "case_type", "case_status", "case_month", "case_year", "case_hint")


def transition(session: Session, phase: Phase) -> None:
    if session.phase != phase:
        session.phase = phase
        session.phase_history.append(phase)


def merge_memory(session: Session, observation: Observation) -> None:
    before = session.memory.model_dump()
    updated = dict(before)
    if observation.new_case:
        for key in CASE_FIELDS:
            updated[key] = None
    for key in observation.clear_fields:
        updated[key] = None
    updated.update(observation.facts.model_dump(exclude_none=True))
    if observation.email_choice != "unknown":
        updated["summary_preference"] = observation.email_choice
    session.memory = ConversationMemory.model_validate(updated)
    identity_changed = any(before[key] != updated[key] for key in AUTH_FIELDS)
    case_changed = observation.new_case or any(
        before[key] != updated[key] for key in CASE_FIELDS if key != "case_hint"
    )
    if identity_changed:
        session.verification.verified_party_id = None
        session.verification.matched_fields = []
        session.authorization = Authorization()
        transition(session, Phase.VERIFY_ID)
    if identity_changed or case_changed:
        session.selected_case_id = None
        session.outcome = Outcome()
        session.follow_up = FollowUp()
        if not identity_changed and session.verification.verified_party_id:
            transition(session, Phase.RESOLVE_INTENT)
