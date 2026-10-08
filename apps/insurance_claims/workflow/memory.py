"""Merge caller facts and revoke derived access when identity changes."""

from ..schemas.facts import CallerFacts, CaseHints, Observation
from ..schemas.state import Authorization, FollowUp, Outcome, Phase, Session
from .identity import AUTH_FIELDS, normalize, phone_digits


def transition(session: Session, phase: Phase) -> None:
    if session.phase != phase:
        session.phase = phase
        session.phase_history.append(phase)


def merge_memory(session: Session, observation: Observation) -> None:
    had_claim_access = session.verification.verified_party_id is not None
    before = session.memory.model_dump()
    updated = dict(before)
    for key in observation.clear_fields:
        updated[key] = None
    updated.update(observation.facts.model_dump(exclude_none=True))
    session.memory = CallerFacts.model_validate(updated)
    identity_changed = any(
        before[key] != updated[key]
        and (
            before[key] is None
            or updated[key] is None
            or (phone_digits if key == "phone" else normalize)(before[key])
            != (phone_digits if key == "phone" else normalize)(updated[key])
        )
        for key in AUTH_FIELDS
    )
    if identity_changed:
        session.verification.verified_party_id = None
        session.verification.matched_fields = []
        session.authorization = Authorization()
        transition(session, Phase.VERIFY_ID)
        if had_claim_access:
            session.dialogue_start = max(0, len(session.messages) - 1)
        session.selected_case_id = None
        session.outcome = Outcome()
        session.prior_outcomes.clear()
        if had_claim_access:
            session.follow_up = FollowUp()
            session.pending_topics.clear()

    hints = {} if observation.new_case else session.case_hints.model_dump()
    for key in observation.clear_case_fields:
        hints[key] = None
    hints.update(observation.case_hints.model_dump(exclude_none=True))
    updated_hints = CaseHints.model_validate(hints)
    if updated_hints != session.case_hints or observation.new_case:
        session.case_hints = updated_hints
        session.selected_case_id = None
        if session.verification.verified_party_id:
            transition(session, Phase.RESOLVE_INTENT)
    if observation.email_choice != "unknown":
        session.follow_up.choice = observation.email_choice
    if observation.new_case:
        session.pending_topics.clear()
    session.pending_topics = list(dict.fromkeys([*session.pending_topics, *observation.topics]))
