"""Configuration precedence at the OpenRouter client boundary; no network calls."""

import pytest

from apps.insurance_claims.llm import model


@pytest.mark.parametrize(
    "session_key,environment_key,expected_key",
    [
        (None, None, "file-key"),
        (None, "env-key", "env-key"),
        (" session-key ", "env-key", "session-key"),
    ],
)
def test_model_uses_session_then_environment_then_file_credentials(
    monkeypatch, session_key, environment_key, expected_key
):
    monkeypatch.setattr(
        model,
        "dotenv_values",
        lambda path: {"OPENROUTER_API_KEY": "file-key", "OPENROUTER_MODEL": "file-model"},
    )
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    if environment_key is not None:
        monkeypatch.setenv("OPENROUTER_API_KEY", environment_key)
    monkeypatch.setenv("OPENROUTER_MODEL", "env-model")
    client = model.create_model(api_key=session_key)
    assert client.openrouter_api_key.get_secret_value() == expected_key
    assert client.model_name == "env-model"


def test_model_starts_without_dotenv_and_rejects_missing_credentials(monkeypatch):
    monkeypatch.setattr(model, "dotenv_values", lambda path: {})
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    with pytest.raises(ValueError, match="OpenRouter API key"):
        model.create_model()
    with pytest.raises(ValueError, match="OpenRouter API key"):
        model.create_model(api_key="  ")
    client = model.create_model(api_key="session-key")
    assert client.model_name == "anthropic/claude-sonnet-4.6"
    assert "session-key" not in model.load_model_settings(api_key="session-key").model_dump_json()
