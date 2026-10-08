"""Session-scoped OpenRouter credentials, separate from conversation and trace data."""

import streamlit as st

from ..llm.model import load_model_settings


def clear_session_key() -> None:
    st.session_state.pop("openrouter_api_key", None)
    st.session_state.pop("workflow", None)
    st.session_state.api_key_input = ""


def connection_controls() -> bool:
    """Render connection setup and report whether a key is configured."""
    session_key = st.session_state.get("openrouter_api_key")
    settings = load_model_settings(api_key=session_key)
    with st.sidebar:
        st.subheader("Connect to OpenRouter")
        st.caption(f"Model: {settings.model}")
        if session_key:
            st.success("Session key configured.")
        elif settings.api_key:
            st.info("Server key configured. Enter your own key to use your OpenRouter credits.")
        else:
            st.info("Enter your OpenRouter API key to start chatting.")
        with st.form("openrouter_connection", clear_on_submit=True):
            key = st.text_input(
                "OpenRouter API key",
                type="password",
                key="api_key_input",
                placeholder="sk-or-...",
                help="Your key is checked by OpenRouter when you send a message.",
            )
            if st.form_submit_button("Use API key", use_container_width=True):
                if not key.strip():
                    st.error("Enter a non-empty OpenRouter API key.")
                else:
                    st.session_state.openrouter_api_key = key.strip()
                    st.session_state.pop("workflow", None)
                    st.rerun()
        st.link_button("Get an OpenRouter API key", "https://openrouter.ai/settings/keys")
        st.caption(
            "Your key stays in server memory for this browser session. It is not saved to .env "
            "or included in chat exports. Model calls use OpenRouter credits."
        )
        if session_key:
            st.button(
                "Clear session key",
                key="clear_api_key",
                on_click=clear_session_key,
                use_container_width=True,
            )
            st.caption("Clearing uses the server key if one is configured.")
        st.divider()
    return bool(settings.api_key)
