"""Observe actual graph/SDK boundaries without network access or prompt changes."""

import json
from uuid import uuid4

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langfuse import Langfuse
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from apps.insurance_claims import monitoring
from apps.insurance_claims.reasoner import OpenRouterReasoner
from apps.insurance_claims.repository import FixtureRepository
from apps.insurance_claims.schemas.state import DraftReply, Event, Session
from apps.insurance_claims.trace_privacy import TraceMasker
from apps.insurance_claims.workflow import build_workflow


class ObservedFakeModel(FakeListChatModel):
    model_name: str = "offline-model"


def test_sdk_exports_nested_calls_and_decision_without_changing_model_inputs(monkeypatch, margaret):
    monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "true")
    exporter = InMemorySpanExporter()
    public_key = f"pk-lf-offline-{uuid4()}"
    client = Langfuse(
        public_key=public_key,
        secret_key="offline",
        base_url="http://localhost:1",
        tracer_provider=TracerProvider(),
        span_exporter=exporter,
        mask_otel_spans=TraceMasker(),
    )
    monkeypatch.setattr(
        monitoring, "monitoring_client", lambda: monitoring.Monitoring(client, public_key)
    )
    model = ObservedFakeModel(
        responses=[
            margaret.model_dump_json(),
            DraftReply(
                reply="The record lists missing documents.", discussed_evidence_ids=["claim.denial"]
            ).model_dump_json(),
        ]
    )
    graph = build_workflow(OpenRouterReasoner(model), FixtureRepository())
    session = Session()
    event = Event(text="I'm Margaret Chen, born 1985-03-15, SSN last four 4472.")
    with monitoring.observe_turn(session, event, source="offline-test") as trace:
        result = graph.invoke({"session": session, "event": event})
        trace.finish(result["session"])
    client.flush()
    spans = exporter.get_finished_spans()
    names = {span.name for span in spans}
    assert {"support-turn", "extract-facts", "compose-reply", "apply-sop"} <= names
    root = next(span for span in spans if span.name == "support-turn")
    assert all(span.context.trace_id == root.context.trace_id for span in spans)
    assert all(span.parent.span_id == root.context.span_id for span in spans if span != root)
    exported = json.dumps([dict(span.attributes) for span in spans])
    for secret in ("Margaret Chen", "1985-03-15", "4472"):
        assert secret not in exported
    assert "claim.denial" in exported
    assert "prompt_sha256" in exported
    assert "response_format" in exported
    assert "session_id" in exported
    # Masking happens at export, never in the identity check or model-facing state.
    assert result["session"].memory.full_name == "Margaret Chen"
    assert result["session"].verification.verified_party_id == "P9"
    assert event.text.endswith("4472.")
    client.shutdown()
