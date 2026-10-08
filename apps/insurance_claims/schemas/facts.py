"""Untrusted caller memory and the model's per-turn interpretation."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

IdentityField = Literal["full_name", "dob", "phone", "email", "id_last4"]
MemoryField = Literal[
    "full_name",
    "dob",
    "phone",
    "email",
    "id_last4",
    "id_type",
    "policy_number",
    "caller_role",
    "representative_name",
    "intent_hint",
    "case_type",
    "case_status",
    "case_month",
    "case_year",
    "case_id",
]
Topic = Literal[
    "status",
    "denial",
    "documents",
    "alternatives",
    "submission",
    "format",
    "submission_timing",
    "processing_time",
    "receipt",
    "payment",
    "general",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def require_output_keys(schema: dict) -> None:
    """LLM wire objects have every key; unknown values are explicit nulls."""
    schema["required"] = list(schema["properties"])
    for field in schema["properties"].values():
        field.pop("default", None)


class OutputModel(StrictModel):
    model_config = ConfigDict(json_schema_extra=require_output_keys)


class CallerFacts(OutputModel):
    """Identity fields describe the policyholder, including for representatives."""

    full_name: str | None = None
    dob: date | None = None
    phone: str | None = None
    email: str | None = None
    id_last4: str | None = Field(default=None, pattern=r"^[0-9]{4}$")
    id_type: Literal["ssn_last4", "national_id_last4"] | None = None
    policy_number: str | None = None
    caller_role: Literal["policyholder", "representative"] | None = None
    representative_name: str | None = None
    intent_hint: str | None = None
    case_type: Literal["healthcare", "dental", "auto"] | None = None
    case_status: Literal["denied", "open", "closed"] | None = None
    case_month: int | None = Field(default=None, ge=1, le=12)
    case_year: int | None = Field(default=None, ge=1900, le=2100)
    case_id: str | None = None


class ConversationMemory(CallerFacts):
    summary_preference: Literal["unknown", "send", "skip"] = "unknown"


class Observation(OutputModel):
    """Language understanding only; cannot grant access or advance phases."""

    facts: CallerFacts = Field(default_factory=CallerFacts)
    clear_fields: list[MemoryField] = Field(default_factory=list)
    scope: Literal["in_scope", "out_of_scope", "mixed"] = "in_scope"
    topic: Topic = "general"
    refuses_verification: bool = False
    conversation_action: Literal[
        "continue", "ask_followup", "finish_case", "request_human", "end_conversation"
    ] = "continue"
    alternatives_exhausted: bool = False
    email_choice: Literal["unknown", "send", "skip"] = "unknown"
    new_case: bool = False
