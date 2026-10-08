"""Credential entry, rotation, isolation, and clearing through the actual Streamlit UI."""

import os

import pytest
from streamlit.proto.TextInput_pb2 import TextInput
from streamlit.testing.v1 import AppTest

from apps.insurance_claims import PROJECT_ROOT
from apps.insurance_claims.llm import model
from apps.insurance_claims.schemas.state import DraftReply
from apps.insurance_claims.workflow.presentation import inspector


def use_key(app, value):
    app.text_input[0].set_value(value)
    next(button for button in app.button if button.label == "Use API key").click().run()


@pytest.mark.parametrize("server_key", ["", "server-test-key"])
def test_session_key_controls_requests_without_changing_conversation_or_other_sessions(
    ui_app, monkeypatch, streaming_model, margaret, server_key
):
    monkeypatch.setenv("OPENROUTER_API_KEY", server_key)
    request_keys = []

    def client(**settings):
        request_keys.append(settings["api_key"])
        return streaming_model(
            (margaret, None),
            (DraftReply(reply="Missing records.", discussed_evidence_ids=["claim.denial"]), None),
        )

    monkeypatch.setattr(model, "ChatOpenRouter", client)
    app = ui_app.run()
    assert not app.exception
    assert app.chat_input[0].disabled == (not server_key)
    assert app.button(key="advance_time").disabled == (not server_key)
    assert app.text_input[0].value == ""
    assert app.text_input[0].proto.type == TextInput.PASSWORD
    use_key(app, "  ")
    assert app.error
    assert app.chat_input[0].disabled == (not server_key)

    for key in ("session-key-one", "session-key-two"):
        before = app.session_state["conversation"].model_dump()
        use_key(app, f" {key} ")
        assert not app.exception
        assert not app.chat_input[0].disabled
        assert app.session_state["conversation"].model_dump() == before
        app.chat_input[0].set_value("Margaret sample").run()
        assert not app.error
        assert not app.exception
        assert request_keys[-1] == key
        assert app.session_state["conversation"].selected_case_id == "CL-2048"
        assert key not in str(inspector(app.session_state["conversation"]))
        assert key not in str(app.session_state["llm_traces"])
    assert request_keys == ["session-key-one", "session-key-two"]
    assert os.environ["OPENROUTER_API_KEY"] == server_key

    other = AppTest.from_file(str(PROJECT_ROOT / "app.py")).run()
    assert other.chat_input[0].disabled == (not server_key)
    assert other.session_state["conversation"].messages == []
    assert "openrouter_api_key" not in other.session_state

    app.button(key="new_conversation").click().run()
    assert app.session_state["conversation"].messages == []
    assert not app.chat_input[0].disabled
    app.button(key="clear_api_key").click().run()
    assert not app.exception
    assert "openrouter_api_key" not in app.session_state
    assert "workflow" not in app.session_state
    assert app.text_input[0].value == ""
    assert app.chat_input[0].disabled == (not server_key)
