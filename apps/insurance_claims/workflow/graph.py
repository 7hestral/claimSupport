"""One LangGraph pipeline per input event; the UI retains its returned session."""

from datetime import timedelta
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import StreamWriter

from ..data.repository import FixtureRepository
from ..llm.reasoner import Reasoner
from ..observability.monitoring import record_decision
from ..schemas.facts import Observation
from ..schemas.state import INACTIVITY_TIMEOUT_SECONDS, DraftReply, Event, Message, Session
from .memory import merge_memory
from .policy import TurnPlan, plan_turn
from .presentation import response_context, save_response


class TurnState(TypedDict):
    session: Session
    event: Event
    observation: Observation
    plan: TurnPlan
    draft: DraftReply


def build_workflow(reasoner: Reasoner, repository: FixtureRepository):
    def interpret(state: TurnState, writer: StreamWriter) -> dict:
        session = state["session"].model_copy(deep=True)
        event = state["event"]
        if session.disposition != "active":
            raise ValueError("This conversation is closed. Start a new conversation.")
        if event.kind == "advance_time":
            if event.seconds <= 0:
                raise ValueError("Advance time requires a positive duration.")
            session.now += timedelta(seconds=event.seconds)
            observation = Observation()
        elif session.now >= session.inactivity_expires_at:
            observation = Observation()
        else:
            if not event.text.strip() or len(event.text) > 12000:
                raise ValueError("Enter a message between 1 and 12000 characters.")
            session.inactivity_expires_at = session.now + timedelta(
                seconds=INACTIVITY_TIMEOUT_SECONDS
            )
            session.messages.append(Message(role="user", content=event.text.strip()))
            observation = reasoner.interpret(session, emit=writer)
            merge_memory(session, observation)
        return {"session": session, "observation": observation}

    def decide(state: TurnState) -> dict:
        plan = plan_turn(state["session"], state["observation"], repository)
        record_decision(state["session"], state["observation"], plan)
        return {"plan": plan}

    def compose(state: TurnState, writer: StreamWriter) -> dict:
        plan = state["plan"]
        if plan.fixed_reply:
            draft = DraftReply(reply=plan.fixed_reply)
        else:
            draft = reasoner.respond(
                response_context(state["session"], state["observation"], plan, state["event"]),
                emit=writer,
            )
        return {"draft": draft}

    def record(state: TurnState) -> dict:
        save_response(state["session"], state["plan"], state["draft"])
        return {"session": state["session"]}

    graph = StateGraph(TurnState)
    graph.add_node("interpret", interpret)
    graph.add_node("decide", decide)
    graph.add_node("compose", compose)
    graph.add_node("record", record)
    graph.add_edge(START, "interpret")
    graph.add_edge("interpret", "decide")
    graph.add_edge("decide", "compose")
    graph.add_edge("compose", "record")
    graph.add_edge("record", END)
    return graph.compile()
