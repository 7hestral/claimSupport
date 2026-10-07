"""Two structured model calls with independent prompts and output contracts."""

import json
from pathlib import Path
from typing import Protocol

from langchain_openrouter import ChatOpenRouter

from .schemas.facts import Observation
from .schemas.state import DraftReply, Session

PROMPTS = Path(__file__).parent / "prompts"


class Reasoner(Protocol):
    def interpret(self, session: Session) -> Observation: ...
    def respond(self, context: dict) -> DraftReply: ...


class OpenRouterReasoner:
    def __init__(self, model: ChatOpenRouter):
        self.extractor = model.with_structured_output(
            Observation, method="json_schema", strict=True
        )
        self.speaker = model.with_structured_output(DraftReply, method="json_schema", strict=True)
        self.prompts = {path.stem: path.read_text() for path in PROMPTS.glob("*.md")}

    def interpret(self, session: Session) -> Observation:
        context = {
            "memory": session.memory.model_dump(mode="json"),
            "phase": session.phase.value,
            "last_action": session.last_action,
            "history": [message.model_dump() for message in session.messages[:-1]],
            "latest_user_message": session.messages[-1].content,
        }
        return self.extractor.invoke(
            [
                {"role": "system", "content": self.prompts["extract"]},
                {"role": "user", "content": json.dumps(context)},
            ]
        )

    def respond(self, context: dict) -> DraftReply:
        prompt = "\n\n".join(
            [
                self.prompts["common"],
                self.prompts[context["phase"].lower()],
                self.prompts["respond"],
            ]
        )
        return self.speaker.invoke(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(context)},
            ]
        )
