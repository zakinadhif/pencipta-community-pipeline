# Persistent Streamlit AI Agent

A minimal password-gated Streamlit chat prototype using the OpenAI Agents SDK and Neon PostgreSQL with pgvector. Conversations and agent-run status are stored server-side; the shared password is only a gate, not a user identity.

## Configure

For local development, copy `.env.example` to `.env` and export its three values in your shell, or place them in `.streamlit/secrets.toml`. For Streamlit Community Cloud, add them in **App settings → Secrets**:

```toml
APP_PASSWORD = "choose-a-strong-shared-password"
OPENAI_API_KEY = "sk-..."
DATABASE_URL = "postgresql://..."
```

Credentials are never rendered in the UI or written to the database. Do not commit `.env` or `.streamlit/secrets.toml`.

## Run locally

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

On first connection the app applies `db/schema.sql`, including `CREATE EXTENSION IF NOT EXISTS vector`. The Neon database role must be allowed to create the extension. A browser receives a random session ID; it is not an account or authentication mechanism. Use **New conversation** to retain the current chat and start another; saved conversations can be reopened from the sidebar.

The prototype limits a message to 4,000 characters, allows at most 10 requests per browser session per minute, and caps an agent execution at four turns. These are lightweight safeguards against accidental shared-key spend, not a billing system.

## Optional RAG

`db/vector.py` stores and searches 1536-dimensional `text-embedding-3-small` vectors. It is deliberately not connected to normal chat, so the app works with no documents. Add an explicit document-ingestion workflow before enabling retrieval in prompts.

## Deploy

Push the repository to GitHub, create a Streamlit Community Cloud app pointing to `app.py`, and add the three secrets. Neon and Streamlit Community Cloud can use their free tiers; OpenAI API usage is billed separately and is not a $0 resource.
