"""OpenRouter client configuration; construction does not call the API."""

import os

from dotenv import dotenv_values
from langchain_openrouter import ChatOpenRouter
from pydantic import BaseModel, SecretStr

from .. import PROJECT_ROOT

DEFAULT_MODEL = "anthropic/claude-sonnet-4.6"


class ModelSettings(BaseModel):
    api_key: SecretStr
    model: str


def load_model_settings(*, api_key: str | None = None) -> ModelSettings:
    """Resolve a session key before environment and project-file settings."""
    settings = {**dotenv_values(PROJECT_ROOT / ".env"), **os.environ}
    key = api_key if api_key is not None else settings.get("OPENROUTER_API_KEY") or ""
    model = (settings.get("OPENROUTER_MODEL") or "").strip() or DEFAULT_MODEL
    return ModelSettings(api_key=SecretStr(key.strip()), model=model)


def create_model(*, api_key: str | None = None) -> ChatOpenRouter:
    settings = load_model_settings(api_key=api_key)
    if not settings.api_key:
        raise ValueError("Enter an OpenRouter API key in the UI or set OPENROUTER_API_KEY.")
    # ChatOpenRouter's SDK timeout is milliseconds, not seconds.
    return ChatOpenRouter(
        model=settings.model,
        api_key=settings.api_key.get_secret_value(),
        temperature=0,
        max_retries=0,
        timeout=60_000,
        stream_usage=True,
    )
