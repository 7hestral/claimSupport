"""OpenRouter client configuration; construction does not call the API."""

import os
from pathlib import Path

from dotenv import dotenv_values
from langchain_openrouter import ChatOpenRouter


def create_model() -> ChatOpenRouter:
    settings = {**dotenv_values(Path(__file__).resolve().parents[2] / ".env"), **os.environ}
    api_key = settings.get("OPENROUTER_API_KEY") or ""
    model = settings.get("OPENROUTER_MODEL") or ""
    if not api_key.strip() or not model.strip():
        raise ValueError("Set OPENROUTER_API_KEY and OPENROUTER_MODEL in .env.")
    # ChatOpenRouter's SDK timeout is milliseconds, not seconds.
    return ChatOpenRouter(
        model=model, api_key=api_key, temperature=0, max_retries=0, timeout=60_000
    )
