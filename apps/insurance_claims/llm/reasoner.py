"""One shared model with separate extraction and conversational response contracts."""

import json
from pathlib import Path
from typing import Protocol

from langchain_core.utils.function_calling import convert_to_json_schema
from langchain_openrouter import ChatOpenRouter

from ..schemas.facts import Observation
from ..schemas.state import DraftReply, Session
from ..workflow.context import conversation_history
from .calls import TraceSink, discard_trace, structured_call

PROMPTS = Path(__file__).parent / "prompts"


class Reasoner(Protocol):
    def interpret(self, session: Session, *, emit: TraceSink = discard_trace) -> Observation: ...
    def respond(self, context: dict, *, emit: TraceSink = discard_trace) -> DraftReply: ...


class OpenRouterReasoner:
    def __init__(self, model: ChatOpenRouter):
        self.model = model
        self.prompts = {path.stem: path.read_text() for path in PROMPTS.glob("*.md")}
        self.actions = json.loads((PROMPTS / "actions.json").read_text())

    def interpret(self, session: Session, *, emit: TraceSink = discard_trace) -> Observation:
        history = conversation_history(session)
        context = {
            "memory": session.memory.model_dump(mode="json"),
            "case_hints": session.case_hints.model_dump(mode="json"),
            "pending_topics": session.pending_topics,
            "selected_case_id": session.selected_case_id,
            "phase": session.phase.value,
            "last_action": session.last_action,
            "history": history,
            "latest_user_message": session.messages[-1].content,
        }
        return structured_call(
            self.model,
            Observation,
            "extraction",
            [
                {"role": "system", "content": self.prompts["extract"]},
                {"role": "user", "content": json.dumps(context)},
            ],
            emit,
        )

    def respond(self, context: dict, *, emit: TraceSink = discard_trace) -> DraftReply:
        output_schema = convert_to_json_schema(DraftReply)
        for field, ids in (
            ("discussed_evidence_ids", [entry["id"] for entry in context["evidence"]]),
            (
                "next_step_evidence_ids",
                [
                    entry["id"]
                    for entry in context["evidence"]
                    if entry["kind"] in {"guidance", "next_step"}
                ],
            ),
        ):
            if ids:
                output_schema["properties"][field]["items"]["enum"] = ids
            else:
                output_schema["properties"][field]["maxItems"] = 0
        prompt = "\n\n".join(
            [
                self.prompts["common"],
                self.prompts[context["phase"].lower()],
                self.prompts["respond"],
                "Current turn instruction:\n" + self.actions[context["action"]],
            ]
        )
        return structured_call(
            self.model,
            DraftReply,
            "response",
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(context)},
            ],
            emit,
            output_schema=output_schema,
        )
