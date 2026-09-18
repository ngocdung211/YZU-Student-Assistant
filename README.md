# YZU Student Assistant

An English retrieval-augmented assistant for Yuan Ze University students. The
application answers questions from indexed YZU documents, preserves conversation
history, and returns links to the original sources.

The project runs locally as three processes:

```text
Next.js frontend :3000
        |
        | HTTP + Server-Sent Events
        v
FastAPI conversation API :8000
        |
        | MCP Streamable HTTP
        v
FastMCP retrieval server :8001
        |
        +-- Gemini chat, embeddings and optional reranking
        +-- Neo4j document vectors, metadata and conversation history
        +-- Google Drive public links for original PDFs
```

## Features

- Public student chat without student accounts.
- Signed anonymous conversation cookies and persistent Neo4j history.
- Three-node LangGraph workflow: query rewrite, retrieval and grounded answer.
- Hybrid semantic and keyword retrieval through a read-only MCP tool.
- Reciprocal-rank fusion, optional Gemini reranking and neighboring context.
- Markdown answers with separately validated source references.
- One configured administrator for PDF upload and source inspection.
- Local PDF extraction with Docling and heading-aware, page-aware chunking.
- Public Google Drive references to the original uploaded documents.

The repository does not include API keys, OAuth tokens, database credentials,
administrator passwords, indexed Neo4j data or the local source-document corpus.

## Requirements

- Python 3.13
- Node.js 20.9 or newer and npm
- A reachable Neo4j database
- Gemini API access through its OpenAI-compatible endpoint
- A Google OAuth client and a writable Google Drive folder

## Installation

Clone the repository and open its root directory.

Create the backend environment:

```sh
cd backend
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

Install the frontend dependencies:

```sh
cd ../frontend
npm ci
```

## Backend configuration

Create the local environment file:

```sh
cd ../backend
cp .env.example .env
```

Configure these values in `backend/.env`:

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Gemini credential used only by backend processes |
| `GEMINI_BASE_URL` | Gemini OpenAI-compatible base URL |
| `GEMINI_CHAT_MODEL_1` | Query rewriting and grounded answer model |
| `GEMINI_CHAT_MODEL_2` | Optional reranking model; failures fall back to RRF order |
| `GEMINI_EMBEDDING_MODEL` | Document and query embedding model |
| `NEO4J_URI` | Neo4j connection URI |
| `NEO4J_USERNAME` | Neo4j username |
| `NEO4J_PASSWORD` | Neo4j password |
| `NEO4J_DATABASE` | Neo4j database name, normally `neo4j` |
| `GOOGLE_DRIVE_FOLDER_ID` | Writable destination folder for original PDFs |
| `GOOGLE_DRIVE_CREDENTIALS_JSON` | Path to the local OAuth client JSON |
| `GOOGLE_DRIVE_TOKEN_FILE` | Local OAuth token path |
| `ADMIN_USERNAME` | Username for the single administrator |
| `MCP_RETRIEVAL_URL` | Retrieval endpoint, normally `http://127.0.0.1:8001/mcp` |

Do not place secrets in `frontend/.env.local` or in variables prefixed with
`NEXT_PUBLIC_`.

### Create the administrator password

Set `ADMIN_USERNAME` in `backend/.env`, then run:

```sh
.venv/bin/python -m app.auth --set-password
```

Enter a new password when prompted. The command stores only an Argon2 hash in
`ADMIN_PASSWORD_HASH` and creates a random `AUTH_SECRET` when one is not already
configured. Restart the API after changing the password.

Every person who clones the repository must perform this step with their own
local `backend/.env`. Administrator credentials are intentionally not shared
through Git.

### Authorize Google Drive

Store the OAuth client JSON outside version control and set its path in
`GOOGLE_DRIVE_CREDENTIALS_JSON`. Then run:

```sh
.venv/bin/python -m app.storage.drive --authorize
.venv/bin/python -m app.storage.drive --check-public
```

The first command opens the local Google consent flow. The second creates,
publicly reads and deletes a small probe file to verify that student source links
will work. OAuth tokens are stored locally under the configured token path.

## Frontend configuration

The default API address is `http://127.0.0.1:8000`. To override it:

```sh
cd ../frontend
cp .env.example .env.local
```

Use the same hostname consistently. Do not mix `localhost` and `127.0.0.1`,
because browser cookies are scoped to the hostname.

## Running locally

Start the MCP retrieval server from `backend/`:

```sh
.venv/bin/python -m app.mcp_server --host 127.0.0.1 --port 8001
```

Start the FastAPI conversation API in a second terminal:

```sh
cd backend
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in a third terminal:

```sh
cd frontend
npm run dev
```

Open:

- Student chat: <http://127.0.0.1:3000>
- Administrator login: <http://127.0.0.1:3000/login>
- API documentation: <http://127.0.0.1:8000/docs>
- Liveness check: <http://127.0.0.1:8000/health>
- Dependency readiness: <http://127.0.0.1:8000/ready>

Stop each process with `Ctrl+C`.

## Adding PDF sources

1. Sign in at `/login` with the locally configured administrator account.
2. Open the API documentation at `http://127.0.0.1:8000/docs`.
3. Use `POST /admin/documents` and set `X-CSRF-Protection` to `1`.
4. Upload a PDF of no more than 20 MiB and 100 pages.
5. Inspect the returned document with `GET /admin/documents/{document_id}`.
6. Open its `source_url` in a signed-out browser to confirm public access.

Import performs extraction, chunking, embedding, Drive publication and atomic
Neo4j storage before reporting the document as ready. Failed imports attempt to
remove their own partially created records and Drive file.

## Verification

Run the backend suite:

```sh
cd backend
.venv/bin/python -m pytest -p no:cacheprovider -q
```

Run the frontend checks:

```sh
cd frontend
npm test
npm run typecheck
npm run build
```

At the latest local verification, all 99 backend tests and all 5 frontend tests
passed. TypeScript checking and the Next.js production build also passed. The
backend suite emits one dependency deprecation warning from Starlette/AnyIO.

## Project structure

```text
backend/app/api/          FastAPI routes
backend/app/services/     ingestion, retrieval and conversation services
backend/app/storage/      Neo4j, Drive, checkpoint and session adapters
backend/app/mcp_server.py independent read-only retrieval server
backend/tests/            backend unit and integration tests
frontend/app/             Next.js routes and providers
frontend/components/      chat, navigation and reference UI
frontend/hooks/           browser conversation state
frontend/lib/             API and SSE clients
frontend/tests/           frontend rendering and stream tests
ARCHITECTURE.md            detailed architecture and data flow
SYSTEM_PRESENTATION.md    concise presentation source
```

## Current limitations

- Local Mac-oriented deployment; production hosting is not configured.
- English interface, sources and answers only.
- PDF upload is available; HTML ingestion and a full document-management UI are
  not implemented.
- Administrator sessions are in-memory and intended for one local API process.
- PDF extraction quality depends on the structure Docling can recover from each
  source document.
- Model and provider requests can fail because of quota, credentials or network
  availability.

## Security and source handling

- Never commit `.env`, OAuth JSON, tokens, private keys or local import progress.
- Rotate any credential that has previously appeared in source control.
- Student chat receives source text as untrusted evidence, not executable
  instructions.
- Source URLs returned to students come from stored metadata rather than model
  generated links.

The frontend visual style adapts material from the HaUI reference project and
Horizon UI. The retained MIT license is available at `frontend/LICENSE`. The YZU
logo is supplied for this project.
