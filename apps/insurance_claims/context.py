"""Bounded dialogue shared by extraction and response context builders."""

import json

from .schemas.state import Session

HISTORY_CHAR_BUDGET = 24_000


def recent_history(session: Session, *, start: int = 0, include_last: bool = False) -> list[dict]:
    messages = session.messages[start:] if include_last else session.messages[start:-1]
    history = []
    size = 2
    for message in reversed(messages):
        entry = message.model_dump()
        cost = len(json.dumps(entry)) + (2 if history else 0)
        if size + cost > HISTORY_CHAR_BUDGET:
            break
        history.append(entry)
        size += cost
    return list(reversed(history))
