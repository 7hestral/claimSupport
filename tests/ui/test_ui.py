"""The test UI must retain graph results and present completion without external actions."""

from conftest import ScriptedReasoner

from apps.insurance_claims.data.repository import FixtureRepository
from apps.insurance_claims.schemas.facts import Observation
from apps.insurance_claims.schemas.state import Phase
from apps.insurance_claims.workflow.graph import build_workflow


def test_chat_ui_renders_outcome_and_resets_conversation(ui_app, margaret):
    app = ui_app.run()
    app.session_state["workflow"] = build_workflow(
        ScriptedReasoner(
            [
                margaret,
                Observation(conversation_action="finish_case"),
                Observation(email_choice="skip"),
            ]
        ),
        FixtureRepository(),
    )
    app.chat_input[0].set_value("Margaret sample").run()
    assert not app.exception
    assert not app.error
    assert app.session_state["conversation"].phase == Phase.PROCESS_CASE
    app.chat_input[0].set_value("That is all").run()
    app.chat_input[0].set_value("Skip email").run()
    assert not app.exception
    assert not app.error
    assert app.session_state["conversation"].disposition == "completed"
    assert app.chat_input[0].disabled
    assert any(heading.value == "Support outcome" for heading in app.subheader)
    app.button(key="new_conversation").click().run()
    assert app.session_state["conversation"].phase == Phase.VERIFY_ID
    assert app.session_state["conversation"].messages == []
    assert not app.chat_input[0].disabled


def test_advance_time_control_resumes_pending_representative_consent(ui_app, margaret):
    margaret.facts.caller_role = "representative"
    margaret.facts.representative_name = "David Chen"
    app = ui_app.run()
    app.session_state["workflow"] = build_workflow(
        ScriptedReasoner([margaret]),
        FixtureRepository(),
    )
    app.chat_input[0].set_value("Representative sample").run()
    assert app.session_state["conversation"].authorization.status == "pending"
    app.button(key="advance_time").click().run()
    assert not app.exception
    assert not app.error
    assert app.session_state["conversation"].authorization.status == "approved"
    assert app.session_state["conversation"].selected_case_id == "CL-2048"
