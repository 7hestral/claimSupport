"""Conversation history within the current identity boundary.

The demo retains the full relevant dialogue so early requests are not silently dropped.
A production context limit needs explicit summarization before discarding any turns.
"""

from .schemas.state import Session


def conversation_history(session: Session, *, include_last: bool = False) -> list[dict]:
    messages = session.messages[session.dialogue_start :]
    if not include_last:
        messages = messages[:-1]
    return [message.model_dump() for message in messages]
