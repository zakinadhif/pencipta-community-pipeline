"""Minimal server-side PostgreSQL access layer."""
from __future__ import annotations
import uuid
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
import psycopg
from psycopg.rows import dict_row

class DatabaseError(Exception): pass

@contextmanager
def connection(database_url: str) -> Iterator[psycopg.Connection]:
    try:
        with psycopg.connect(database_url, row_factory=dict_row) as conn: yield conn
    except psycopg.Error as error:
        raise DatabaseError("Database operation failed") from error

def init_database(database_url: str) -> None:
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    with connection(database_url) as conn:
        with conn.cursor() as cursor: cursor.execute(schema)

def ensure_session(database_url: str, session_id: str) -> None:
    with connection(database_url) as conn:
        conn.execute("INSERT INTO sessions (id) VALUES (%s) ON CONFLICT (id) DO NOTHING", (session_id,))

def create_conversation(database_url: str, session_id: str, model: str) -> str:
    conversation_id = str(uuid.uuid4())
    with connection(database_url) as conn:
        conn.execute("INSERT INTO conversations (id, session_id, model) VALUES (%s, %s, %s)", (conversation_id, session_id, model))
    return conversation_id

def list_conversations(database_url: str, session_id: str) -> list[dict[str, str]]:
    with connection(database_url) as conn:
        rows = conn.execute("SELECT id, title FROM conversations WHERE session_id = %s ORDER BY updated_at DESC, created_at DESC", (session_id,)).fetchall()
    return [{"id": str(row["id"]), "title": row["title"]} for row in rows]

def conversation_belongs_to_session(database_url: str, conversation_id: str, session_id: str) -> bool:
    with connection(database_url) as conn:
        return conn.execute("SELECT 1 FROM conversations WHERE id = %s AND session_id = %s", (conversation_id, session_id)).fetchone() is not None

def get_messages(database_url: str, conversation_id: str) -> list[dict[str, str]]:
    with connection(database_url) as conn:
        rows = conn.execute("SELECT role, content FROM messages WHERE conversation_id = %s ORDER BY sequence_number", (conversation_id,)).fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in rows]

def store_message(database_url: str, conversation_id: str, role: str, content: str) -> None:
    if role not in {"user", "assistant"}: raise ValueError("Unsupported message role")
    with connection(database_url) as conn:
        # Lock the parent row so concurrent browser reruns cannot choose the same sequence.
        conn.execute("SELECT id FROM conversations WHERE id = %s FOR UPDATE", (conversation_id,)).fetchone()
        row = conn.execute("SELECT COALESCE(MAX(sequence_number), 0) + 1 AS sequence_number FROM messages WHERE conversation_id = %s", (conversation_id,)).fetchone()
        conn.execute("INSERT INTO messages (id, conversation_id, role, content, sequence_number) VALUES (%s, %s, %s, %s, %s)", (str(uuid.uuid4()), conversation_id, role, content, row["sequence_number"]))
        conn.execute("UPDATE conversations SET updated_at = now(), title = CASE WHEN title = 'New conversation' AND %s = 'user' THEN left(%s, 60) ELSE title END WHERE id = %s", (role, content, conversation_id))

def start_agent_run(database_url: str, conversation_id: str, model: str) -> str:
    run_id = str(uuid.uuid4())
    with connection(database_url) as conn:
        conn.execute("INSERT INTO agent_runs (id, conversation_id, model, status) VALUES (%s, %s, %s, 'running')", (run_id, conversation_id, model))
    return run_id

def finish_agent_run(database_url: str, run_id: str, succeeded: bool) -> None:
    status = "completed" if succeeded else "failed"
    error = None if succeeded else "The agent request did not complete."
    with connection(database_url) as conn:
        conn.execute("UPDATE agent_runs SET status = %s, completed_at = now(), error = %s WHERE id = %s", (status, error, run_id))

def record_tool_call(database_url: str, agent_run_id: str, tool_name: str, arguments: str) -> None:
    """Record non-secret local-tool metadata for later run inspection."""
    try:
        parsed_arguments = json.loads(arguments)
    except (TypeError, json.JSONDecodeError):
        parsed_arguments = {}
    with connection(database_url) as conn:
        conn.execute(
            "INSERT INTO tool_calls (id, agent_run_id, tool_name, arguments, status) VALUES (%s, %s, %s, %s::jsonb, 'called')",
            (str(uuid.uuid4()), agent_run_id, tool_name, json.dumps(parsed_arguments)),
        )
