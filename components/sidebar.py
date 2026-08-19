"""Sidebar controls for the prototype UI."""
from __future__ import annotations
import streamlit as st
MODELS = ("gpt-4.1-mini", "gpt-4.1", "gpt-5-mini")
def render_sidebar(conversations: list[dict[str, str]], current_conversation_id: str | None) -> tuple[str, bool, bool, str | None]:
    with st.sidebar:
        st.header("Settings")
        st.selectbox("AI provider", ("OpenAI",), disabled=True)
        model = st.selectbox("Model", MODELS)
        show_activity = st.toggle("Show agent activity", value=True)
        new_conversation = st.button("+ New conversation", use_container_width=True)
        st.caption("Your saved conversations")
        selected_conversation_id = None
        for conversation in conversations:
            label = conversation["title"] or "Untitled conversation"
            if st.button(label, key=f"conversation-{conversation['id']}", use_container_width=True, type="primary" if conversation["id"] == current_conversation_id else "secondary"):
                selected_conversation_id = conversation["id"]
        st.divider(); st.caption("Credentials remain server-side in Streamlit Secrets.")
    return model, show_activity, new_conversation, selected_conversation_id
