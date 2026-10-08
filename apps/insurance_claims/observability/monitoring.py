"""Optional Langfuse telemetry at application boundaries; no authority over SOP state."""

import hashlib
import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import lru_cache

from dotenv import dotenv_values
from langfuse import Langfuse, propagate_attributes
from langfuse.langchain import CallbackHandler

from .. import PROJECT_ROOT
from ..schemas.state import Event, Session
from .privacy import TraceMasker


@dataclass(frozen=True)
class Monitoring:
    client: Langfuse
    public_key: str


ACTIVE_CLIENT: ContextVar[Monitoring | None] = ContextVar("insurance_monitoring", default=None)
ENV_FILE = PROJECT_ROOT / ".env"


@lru_cache(maxsize=1)
def monitoring_client() -> Monitoring | None:
    settings = {**dotenv_values(ENV_FILE), **os.environ}
    if settings.get("LANGFUSE_TRACING_ENABLED", "true").lower() == "false":
        return None
    public = (settings.get("LANGFUSE_PUBLIC_KEY") or "").strip()
    secret = (settings.get("LANGFUSE_SECRET_KEY") or "").strip()
    base_url = (settings.get("LANGFUSE_BASE_URL") or "").strip()
    if not all((public, secret, base_url)):
        return None
    client = Langfuse(
        public_key=public,
        secret_key=secret,
        base_url=base_url,
        environment=settings.get("LANGFUSE_TRACING_ENVIRONMENT", "development"),
        mask_otel_spans=TraceMasker(),
    )
    return Monitoring(client, public)


@dataclass
class TurnTrace:
    span: object | None
    client: Langfuse | None

    def finish(self, session: Session) -> None:
        if self.span is not None:
            self.span.update(
                output=session.messages[-1].content,
                metadata={
                    "after": session.model_dump(mode="json", exclude={"messages"}),
                    "phase": session.phase.value,
                    "action": session.last_action,
                },
            )

    def reference(self) -> dict | None:
        if self.span is None:
            return None
        return {
            "trace_id": self.span.trace_id,
            "url": self.client.get_trace_url(trace_id=self.span.trace_id),
        }


@contextmanager
def observe_turn(session: Session, event: Event, *, source: str, case_id: str | None = None):
    monitoring = monitoring_client()
    if monitoring is None:
        yield TurnTrace(None, None)
        return
    client = monitoring.client
    metadata = {"source": source, "session_id": session.session_id}
    if case_id is not None:
        metadata["case_id"] = case_id
    with (
        propagate_attributes(
            session_id=session.session_id, tags=["insurance-sop", source], metadata=metadata
        ),
        client.start_as_current_observation(
            name="support-turn",
            as_type="agent",
            input=event.text if event.kind == "message" else {"advance_seconds": event.seconds},
            metadata={"before": session.model_dump(mode="json", exclude={"messages"})},
        ) as span,
    ):
        token = ACTIVE_CLIENT.set(monitoring)
        try:
            yield TurnTrace(span, client)
        finally:
            ACTIVE_CLIENT.reset(token)


def generation_config(stage: str, messages: list[dict], response_format: dict) -> dict:
    monitoring = ACTIVE_CLIENT.get()
    if monitoring is None:
        return {}
    return {
        "callbacks": [CallbackHandler(public_key=monitoring.public_key)],
        "run_name": "extract-facts" if stage == "extraction" else "compose-reply",
        "metadata": {
            "stage": stage,
            "prompt_sha256": hashlib.sha256(messages[0]["content"].encode()).hexdigest(),
            "response_format": response_format,
        },
    }


def record_decision(session: Session, observation, plan) -> None:
    monitoring = ACTIVE_CLIENT.get()
    if monitoring is None:
        return
    with monitoring.client.start_as_current_observation(
        name="apply-sop",
        as_type="span",
        input=observation.model_dump(mode="json"),
        output={
            "phase": session.phase.value,
            "verification": session.verification.model_dump(mode="json"),
            "authorization": session.authorization.model_dump(mode="json"),
            "memory": session.memory.model_dump(mode="json"),
            "case_hints": session.case_hints.model_dump(mode="json"),
            "pending_topics": session.pending_topics,
            "plan": plan.model_dump(mode="json"),
        },
    ):
        pass


def flush_monitoring() -> None:
    monitoring = monitoring_client()
    if monitoring is not None:
        monitoring.client.flush()
