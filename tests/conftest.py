"""Script model observations while exercising the real graph and fixture services."""

from collections import deque

import pytest

from apps.insurance_claims.repository import FixtureRepository
from apps.insurance_claims.schemas.facts import CallerFacts, Observation
from apps.insurance_claims.schemas.state import DraftReply, Event, Session
from apps.insurance_claims.workflow import build_workflow


class ScriptedReasoner:
    def __init__(self, observations):
        self.observations = deque(observations)
        self.contexts = []

    def interpret(self, session):
        return self.observations.popleft()

    def respond(self, context):
        self.contexts.append(context)
        evidence = (
            context["evidence"]
            if context["action"] in {"answer_case", "answer_then_offer_email"}
            else []
        )
        return DraftReply(
            reply=f"Response for {context['action']}.",
            discussed_evidence_ids=[e["id"] for e in evidence],
            next_step_evidence_ids=[e["id"] for e in evidence if e["kind"] == "next_step"],
        )


@pytest.fixture
def margaret():
    return Observation(
        facts=CallerFacts(
            full_name="Margaret Chen",
            dob="1985-03-15",
            id_last4="4472",
            id_type="ssn_last4",
            caller_role="policyholder",
            policy_number="POL-9921",
            intent_hint="Explain my denial",
            case_hint="denied healthcare claim from January",
            case_type="healthcare",
            case_status="denied",
            case_month=1,
        ),
        topic="denial",
        has_followup=True,
    )


@pytest.fixture
def harness():
    def create(*observations, session=None):
        reasoner = ScriptedReasoner(observations)
        graph = build_workflow(reasoner, FixtureRepository())
        initial = session or Session()

        def turn(current=initial, event=None):
            return graph.invoke(
                {"session": current, "event": event or Event(text="Scripted caller turn")}
            )["session"]

        return turn, reasoner, initial

    return create
