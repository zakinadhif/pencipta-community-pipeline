"""Optional pgvector helpers. RAG is not required for ordinary chat."""
from __future__ import annotations
import uuid
from typing import Any
from pgvector.psycopg import register_vector
from db.client import connection
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536

def store_chunk(database_url: str, document_id: str, content: str, embedding: list[float], metadata: dict[str, Any] | None = None) -> str:
    if len(embedding) != EMBEDDING_DIMENSIONS: raise ValueError(f"Expected a {EMBEDDING_DIMENSIONS}-dimension embedding.")
    chunk_id = str(uuid.uuid4())
    with connection(database_url) as conn:
        register_vector(conn)
        conn.execute("INSERT INTO document_chunks (id, document_id, content, metadata, embedding) VALUES (%s, %s, %s, %s, %s)", (chunk_id, document_id, content, metadata or {}, embedding))
    return chunk_id

def search_chunks(database_url: str, embedding: list[float], limit: int = 5) -> list[dict[str, Any]]:
    if len(embedding) != EMBEDDING_DIMENSIONS: raise ValueError(f"Expected a {EMBEDDING_DIMENSIONS}-dimension embedding.")
    with connection(database_url) as conn:
        register_vector(conn)
        return conn.execute("SELECT id, document_id, content, metadata, embedding <=> %s AS distance FROM document_chunks WHERE embedding IS NOT NULL ORDER BY embedding <=> %s LIMIT %s", (embedding, embedding, limit)).fetchall()
