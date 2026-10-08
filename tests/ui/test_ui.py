"""The test UI must retain graph results and present completion without external actions."""

import pytest
from conftest import ScriptedReasoner

from apps.insurance_claims.data.repository import FixtureRepository
from apps.insurance_claims.schemas.facts import Observation
from apps.insurance_claims.schemas.state import Phase
from apps.insurance_claims.workflow.graph import build_workflow


@pytest.mark.parametrize("timeout", [False, True], ids=["explicit-skip", "timeout"])
def test_chat_ui_renders_outcome_and_resets_conversation(ui_app, margaret, timeout):
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
    if timeout:
        next(select for select in app.selectbox if select.label == "Advance by").set_value(120)
        app.button(key="advance_time").click().run()
        assert app.session_state["conversation"].follow_up.offer_status == "timed_out"
        assert app.session_state["conversation"].follow_up.choice == "skip"
        assert app.session_state["conversation"].follow_up.delivery == "not_requested"
    else:
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


def test_step_timer_closes_idle_chat_and_new_conversation_resets_it(ui_app):
    app = ui_app.run()
    app.session_state["workflow"] = build_workflow(ScriptedReasoner([]), FixtureRepository())
    assert any(
        "3 minutes" in caption.value and "step timer" in caption.value for caption in app.caption
    )
    before = app.session_state["conversation"].model_dump()
    app.run()
    assert app.session_state["conversation"].model_dump() == before
    next(select for select in app.selectbox if select.label == "Advance by").set_value(180)
    app.button(key="advance_time").click().run()
    assert not app.exception and not app.error
    session = app.session_state["conversation"]
    assert session.disposition == "timed_out"
    assert session.follow_up.choice == "skip"
    assert session.follow_up.delivery == "not_requested"
    assert app.chat_input[0].disabled
    assert app.button(key="advance_time").disabled
    app.button(key="new_conversation").click().run()
    session = app.session_state["conversation"]
    assert session.disposition == "active"
    assert (session.inactivity_expires_at - session.now).total_seconds() == 180
