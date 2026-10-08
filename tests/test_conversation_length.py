"""Long chats retain earlier requests and the identity access boundary."""

import json

from langchain_core.messages import AIMessageChunk

from apps.insurance_claims.reasoner import OpenRouterReasoner
from apps.insurance_claims.schemas.facts import Observation
from apps.insurance_claims.schemas.state import Message, Phase, Session


def test_long_chat_retains_early_requests_without_silently_truncating(harness, margaret):
    class RecordingModel:
        model_name = "test-model"

        def bind(self, **kwargs):
            return self

        def stream(self, messages, config=None):
            self.context = json.loads(messages[-1]["content"])
            yield AIMessageChunk(content=Observation().model_dump_json())

    model = RecordingModel()
    session = Session()
    session.memory = margaret.facts
    session.case_hints = margaret.case_hints
    session.messages = [
        Message(
            role="user",
            content="For my January healthcare denial, can I scan the report and how long is review?",
        )
    ]
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
    assert len(context["history"]) == len(session.messages) - 1
    assert context["latest_user_message"] == "Email, please."
    assert context["history"][-1]["content"].startswith("Would you prefer")
    assert "can I scan the report and how long is review?" in context["history"][0]["content"]
    assert context["case_hints"]["case_month"] == 1
    assert context["case_hints"]["case_type"] == "healthcare"
    assert context["case_hints"]["case_status"] == "denied"
    assert context["memory"]["full_name"] == "Margaret Chen"
    assert session.model_dump_json() == transcript

    turn, speaker, _ = harness(margaret, session=session)
    turn()
    assert (
        "can I scan the report and how long is review?"
        in speaker.contexts[-1]["history"][0]["content"]
    )


def test_many_followups_do_not_force_completion(harness, margaret):
    turn, _, _ = harness(
        margaret,
        *[Observation(conversation_action="ask_followup") for _ in range(60)],
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
