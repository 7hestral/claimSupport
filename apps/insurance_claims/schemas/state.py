"""Application-owned session state and bounded model response contracts."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import Field

from .facts import ConversationMemory, IdentityField, OutputModel, StrictModel


class Phase(StrEnum):
    VERIFY_ID = "VERIFY_ID"
    RESOLVE_INTENT = "RESOLVE_INTENT"
    PROCESS_CASE = "PROCESS_CASE"
    POST_PROCESS = "POST_PROCESS"


class Message(StrictModel):
    role: Literal["user", "assistant"]
    content: str


class Authorization(StrictModel):
    status: Literal["not_required", "pending", "approved", "timed_out"] = "not_required"
    requested_at: datetime | None = None
    expires_at: datetime | None = None
    next_check_at: datetime | None = None
    check_index: int = 0


class Verification(StrictModel):
    verified_party_id: str | None = None
    matched_fields: list[IdentityField] = Field(default_factory=list)
    failed_attempts: int = 0
    last_attempt: str | None = None


class Evidence(StrictModel):
    id: str
    text: str
    kind: Literal["fact", "guidance", "next_step"] = "fact"


class Outcome(StrictModel):
    case_id: str | None = None
    claim_status: str | None = None
    claim_summary: str | None = None
    discussed: list[Evidence] = Field(default_factory=list)
    next_steps: list[Evidence] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    handoff_reason: str | None = None


class FollowUp(StrictModel):
    email_choice: Literal["not_asked", "pending", "send", "skip"] = "not_asked"
    recipient: str | None = None
    email_draft: str | None = None
    delivery: Literal["not_requested", "simulated_only"] = "not_requested"


class Session(StrictModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    messages: list[Message] = Field(default_factory=list)
    dialogue_start: int = 0
    memory: ConversationMemory = Field(default_factory=ConversationMemory)
    phase: Phase = Phase.VERIFY_ID
    verification: Verification = Field(default_factory=Verification)
    authorization: Authorization = Field(default_factory=Authorization)
    selected_case_id: str | None = None
    outcome: Outcome = Field(default_factory=Outcome)
    follow_up: FollowUp = Field(default_factory=FollowUp)
    out_of_scope_attempts: int = 0
    recovery_attempts: int = 0
    disposition: Literal["active", "completed", "handoff_requested", "ended"] = "active"
    now: datetime = Field(default_factory=lambda: datetime(2026, 3, 10, 10, tzinfo=UTC))
    consent_scenario: Literal["default", "timeout"] = "default"
    phase_history: list[Phase] = Field(default_factory=lambda: [Phase.VERIFY_ID])
    last_action: str = "collect_identity"


class Event(StrictModel):
    kind: Literal["message", "advance_time"] = "message"
    text: str = ""
    seconds: int = Field(default=0, ge=0, le=86400 * 365)


class DraftReply(OutputModel):
    reply: str = Field(min_length=1, max_length=6000)
    discussed_evidence_ids: list[str] = Field(default_factory=list)
    next_step_evidence_ids: list[str] = Field(default_factory=list)
    unanswered_question: str | None = None
