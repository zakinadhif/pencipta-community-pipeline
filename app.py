"""Password-protected Streamlit interface for the persistent agent prototype."""
from __future__ import annotations
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone
import streamlit as st
from agent.agent import AgentConfigurationError, run_agent_stream
from components.sidebar import render_sidebar
from db.client import DatabaseError, conversation_belongs_to_session, create_conversation, ensure_session, finish_agent_run, get_messages, init_database, list_conversations, record_tool_call, record_tool_result, start_agent_run, store_message

MAX_MESSAGE_CHARS = 4_000
MAX_REQUESTS_PER_MINUTE = 10

def secret(name: str) -> str | None:
    try:
        value = st.secrets.get(name)
    except FileNotFoundError:
        value = None
    return value or os.environ.get(name)

def ensure_browser_session() -> str:
    session_id = st.session_state.get("session_id") or st.query_params.get("session")
    try:
        session_id = str(uuid.UUID(str(session_id)))
    except (TypeError, ValueError, AttributeError):
        session_id = str(uuid.uuid4())
    st.query_params["session"] = session_id
    st.session_state.session_id = session_id
    return session_id

def password_gate() -> bool:
    configured_password = secret("APP_PASSWORD")
    if not configured_password:
        st.error("This app is not configured yet. Add APP_PASSWORD to server secrets.")
        return False
    if st.session_state.get("authenticated"):
        return True
    st.title("Agent prototype")
    with st.form("password_gate"):
        supplied_password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Continue", type="primary")
    if submitted:
        if hmac.compare_digest(supplied_password, configured_password):
            st.session_state.authenticated = True
            st.rerun()
        st.error("Incorrect password.")
    return False

def request_is_allowed() -> bool:
    """A small in-memory safety brake; it is not an authentication mechanism."""
    now = datetime.now(timezone.utc)
    recent = [item for item in st.session_state.get("request_times", []) if item > now - timedelta(minutes=1)]
    if len(recent) >= MAX_REQUESTS_PER_MINUTE:
        st.error("Too many requests. Please wait a minute before trying again.")
        return False
    st.session_state.request_times = recent + [now]
    return True

def main() -> None:
    st.set_page_config(page_title="Persistent AI Agent", page_icon="💬", layout="centered")
    if not password_gate(): return
    database_url = secret("DATABASE_URL")
    if not database_url:
        st.error("This app is not configured yet. Add DATABASE_URL to server secrets.")
        return
    try:
        init_database(database_url)
        session_id = ensure_browser_session()
        ensure_session(database_url, session_id)
    except DatabaseError:
        st.error("The conversation database is unavailable. Please try again later.")
        return
    try:
        conversations = list_conversations(database_url, session_id)
    except DatabaseError:
        st.error("Unable to load saved conversations. Please try again later.")
        return
    model, show_activity, new_conversation, selected_conversation_id = render_sidebar(conversations, st.session_state.get("conversation_id"))
    if selected_conversation_id:
        st.session_state.conversation_id = selected_conversation_id
        st.query_params["conversation"] = selected_conversation_id
        st.rerun()
    conversation_id = st.session_state.get("conversation_id") or st.query_params.get("conversation")
    try:
        conversation_is_valid = bool(uuid.UUID(str(conversation_id))) and conversation_belongs_to_session(database_url, str(conversation_id), session_id)
    except (TypeError, ValueError, AttributeError):
        conversation_is_valid = False
    except DatabaseError:
        st.error("Unable to load this conversation. Please try again later.")
        return
    if new_conversation or not conversation_is_valid:
        try: st.session_state.conversation_id = create_conversation(database_url, session_id, model)
        except DatabaseError:
            st.error("Unable to create a conversation. Please try again later.")
            return
        st.query_params["conversation"] = st.session_state.conversation_id
        if new_conversation: st.rerun()
    else:
        st.session_state.conversation_id = str(conversation_id)
    st.title("Persistent AI Agent")
    st.caption("This conversation is saved on the server. Reset starts a new one and keeps prior history.")
    try: messages = get_messages(database_url, st.session_state.conversation_id)
    except DatabaseError:
        st.error("Unable to load this conversation. Please try again later.")
        return
    for message in messages:
        with st.chat_message(message["role"]): st.markdown(message["content"])
    prompt = st.chat_input("Message the agent")
    if not prompt: return
    if len(prompt) > MAX_MESSAGE_CHARS:
        st.error(f"Messages are limited to {MAX_MESSAGE_CHARS:,} characters.")
        return
    if not request_is_allowed(): return
    try: store_message(database_url, st.session_state.conversation_id, "user", prompt)
    except DatabaseError:
        st.error("Your message could not be saved. Please try again.")
        return
    with st.chat_message("user"): st.markdown(prompt)
    with st.chat_message("assistant"):
        output = st.empty()
        activity = st.status("Agent is thinking…", expanded=False) if show_activity else None
        answer_parts: list[str] = []
        def on_delta(delta: str) -> None:
            answer_parts.append(delta); output.markdown("".join(answer_parts) + "▌")
        def on_activity(message: str) -> None:
            if activity: activity.write(message)
        def on_tool_call(tool_name: str, arguments: str, tool_call_id: str | None) -> None:
            if run_id:
                try: record_tool_call(database_url, run_id, tool_name, arguments, tool_call_id)
                except DatabaseError: pass
        def on_tool_result(tool_call_id: str | None, result: str) -> None:
            if run_id:
                try: record_tool_result(database_url, run_id, tool_call_id, result)
                except DatabaseError: pass
        run_id = None
        try:
            run_id = start_agent_run(database_url, st.session_state.conversation_id, model)
            answer = run_agent_stream(secret("OPENAI_API_KEY") or "", model, messages + [{"role": "user", "content": prompt}], on_delta, on_activity, on_tool_call, on_tool_result)
            output.markdown(answer)
            if activity: activity.update(label="Finished", state="complete")
            store_message(database_url, st.session_state.conversation_id, "assistant", answer)
            finish_agent_run(database_url, run_id, succeeded=True)
        except AgentConfigurationError as error:
            if run_id: finish_agent_run(database_url, run_id, succeeded=False)
            if activity: activity.update(label="Request failed", state="error")
            st.error(str(error))
        except DatabaseError:
            if run_id: finish_agent_run(database_url, run_id, succeeded=False)
            st.error("The response was generated but could not be saved. Please try again.")
        except Exception:
            if run_id:
                try: finish_agent_run(database_url, run_id, succeeded=False)
                except DatabaseError: pass
            if activity: activity.update(label="Request failed", state="error")
            st.error("The AI service is unavailable or the configured key cannot make this request.")

if __name__ == "__main__": main()
