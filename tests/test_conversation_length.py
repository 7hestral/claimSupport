"""Long chats retain workflow state while limiting model history."""

import json

from langchain_core.messages import AIMessageChunk

from apps.insurance_claims.reasoner import OpenRouterReasoner
from apps.insurance_claims.schemas.facts import Observation
from apps.insurance_claims.schemas.state import Message, Phase, Session


def test_long_chat_windows_model_input_without_losing_memory(margaret):
    class RecordingModel:
        model_name = "test-model"

        def bind(self, **kwargs):
            return self

        def stream(self, messages, config=None):
            self.context = json.loads(messages[-1]["content"])
            yield AIMessageChunk(content=Observation().model_dump_json())

    model = RecordingModel()
    session = Session()
    session.memory = session.memory.model_copy(update=margaret.facts.model_dump())
    session.messages = [Message(role="user", content="Old hint: January healthcare denial.")]
    for _ in range(40):
        session.messages.extend(
            [
                Message(role="user", content="Long prior question. " * 100),
                Message(role="assistant", content="Long prior answer. " * 100),
            ]
        )
    session.messages.extend(
        [
            Message(role="assistant", content="Would you prefer email or phone for verification?"),
            Message(role="user", content="Email, please."),
        ]
    )
    transcript = session.model_dump_json()

    OpenRouterReasoner(model).interpret(session)

    context = model.context
    assert context["history_truncated"]
    assert len(json.dumps(context["history"])) <= 24_000
    assert context["latest_user_message"] == "Email, please."
    assert context["history"][-1]["content"].startswith("Would you prefer")
    assert "Old hint:" not in json.dumps(context["history"])
    assert context["memory"]["case_month"] == 1
    assert context["memory"]["case_type"] == "healthcare"
    assert context["memory"]["case_status"] == "denied"
    assert context["memory"]["full_name"] == "Margaret Chen"
    assert session.model_dump_json() == transcript


def test_many_followups_do_not_force_completion(harness, margaret):
    turn, _, _ = harness(
        margaret,
        *[Observation(topic="format", conversation_action="ask_followup") for _ in range(60)],
        Observation(conversation_action="finish_case"),
        Observation(email_choice="skip"),
    )
    session = turn()
    for _ in range(60):
        session = turn(session)
        assert session.phase == Phase.PROCESS_CASE
        assert session.disposition == "active"
    assert session.selected_case_id == "CL-2048"
    session = turn(turn(session))
    assert session.disposition == "completed"
