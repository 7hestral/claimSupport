"""Safe model context, evidence-backed outcomes, and the simulated email draft."""

import re

from .context import recent_history
from .identity import IDENTITY_FIELDS
from .policy import TurnPlan
from .schemas.facts import Observation
from .schemas.state import DraftReply, Event, Message, Phase, Session

PRIVATE_FIELDS = (*IDENTITY_FIELDS, "policy_number", "representative_name")


def redact(text: str, session: Session) -> str:
    for field in PRIVATE_FIELDS:
        value = getattr(session.memory, field)
        if value is not None:
            text = re.sub(re.escape(str(value)), "[provided]", text, flags=re.IGNORECASE)
    return text


def masked_memory(session: Session) -> dict:
    return {
        key: ("[provided]" if value is not None else None)
        if key in PRIVATE_FIELDS
        else redact(value, session)
        if isinstance(value, str)
        else value
        for key, value in session.memory.model_dump(mode="json").items()
    }


def response_context(
    session: Session, observation: Observation, plan: TurnPlan, event: Event
) -> dict:
    # Dialogue is caller context, never evidence. Drop prior dialogue on identity/case changes.
    history = recent_history(
        session, start=session.dialogue_start, include_last=event.kind == "advance_time"
    )
    memory = {
        key: value
        for key, value in masked_memory(session).items()
        if key not in PRIVATE_FIELDS and key != "id_type"
    }
    return {
        "phase": session.phase.value,
        "action": plan.action,
        "memory": memory,
        "scope": observation.scope,
        "event": event.kind,
        "latest_user_message": redact(event.text, session) if event.kind == "message" else None,
        "history": [
            {**message, "content": redact(message["content"], session)} for message in history
        ],
        "identity_verified": session.verification.verified_party_id is not None,
        "supplied_identity_fields": [
            key for key in IDENTITY_FIELDS if getattr(session.memory, key) is not None
        ],
        "authorization_status": session.authorization.status,
        "offer_human": plan.offer_human,
        "candidates": plan.candidates,
        "evidence": [e.model_dump() for e in plan.evidence],
        "outcome": session.outcome.model_dump(),
        "email_choice": session.follow_up.email_choice,
        "email_recipient": session.follow_up.recipient,
        "demo_date": str(session.now.date()),
    }


def save_response(session: Session, plan: TurnPlan, draft: DraftReply) -> None:
    evidence = {e.id: e for e in plan.evidence}
    referenced = set(draft.discussed_evidence_ids + draft.next_step_evidence_ids)
    if not referenced <= evidence.keys():
        raise ValueError("Model referenced evidence outside the authorized context.")
    if any(evidence[key].kind != "next_step" for key in draft.next_step_evidence_ids):
        raise ValueError("Model proposed a next step outside the allowed guidance.")
    if (
        plan.action in {"answer_case", "answer_then_offer_email"}
        and not draft.discussed_evidence_ids
        and not draft.unanswered_question
    ):
        raise ValueError("A case response must cite evidence or record an unanswered question.")
    for field, ids in (
        ("discussed", draft.discussed_evidence_ids),
        ("next_steps", draft.next_step_evidence_ids),
    ):
        entries = {e.id: e for e in getattr(session.outcome, field)}
        entries.update({key: evidence[key] for key in ids})
        setattr(session.outcome, field, list(entries.values()))
    if (
        draft.unanswered_question
        and draft.unanswered_question not in session.outcome.unresolved_questions
    ):
        session.outcome.unresolved_questions.append(redact(draft.unanswered_question, session))
    session.messages.append(Message(role="assistant", content=draft.reply))
    session.last_action = plan.action
    if session.phase == Phase.POST_PROCESS:
        session.follow_up.email_draft = email_draft(session)


def email_draft(session: Session) -> str:
    outcome = session.outcome
    sections = [
        f"Subject: Support summary for claim {outcome.case_id}",
        f"Claim status: {outcome.claim_status}\n{outcome.claim_summary}",
        "Discussed:\n" + "\n".join(f"- {entry.text}" for entry in outcome.discussed),
        "Next steps:\n"
        + (
            "\n".join(f"- {entry.text}" for entry in outcome.next_steps)
            or "- No additional action recorded."
        ),
    ]
    if outcome.unresolved_questions:
        sections.append(
            "Questions for human support:\n"
            + "\n".join(f"- {q}" for q in outcome.unresolved_questions)
        )
    sections.append("Prepared in a demo. No email was sent and no claim was modified.")
    return "\n\n".join(sections)


def inspector(session: Session) -> dict:
    return {
        "session_id": session.session_id,
        "phase": session.phase.value,
        "phase_history": [phase.value for phase in session.phase_history],
        "disposition": session.disposition,
        "demo_time": session.now.isoformat(),
        "memory": masked_memory(session),
        "verification": {
            "verified": session.verification.verified_party_id is not None,
            "matched_field_count": len(session.verification.matched_fields),
            "failed_attempts": session.verification.failed_attempts,
        },
        "authorization": session.authorization.model_dump(mode="json"),
        "selected_case_id": session.selected_case_id,
        "out_of_scope_attempts": session.out_of_scope_attempts,
        "recovery_attempts": session.recovery_attempts,
        "last_action": session.last_action,
        "email_choice": session.follow_up.email_choice,
        "delivery": session.follow_up.delivery,
    }
