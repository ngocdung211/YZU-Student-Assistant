# YZU Student Assistant

An English information assistant for YZU students. **Step 1 is approved; Step 2 connection setup is in progress.** The HaUI-derived interface remains a preview. Gemini and Neo4j live checks pass. Personal Google Drive OAuth is implemented; user consent and public-link verification remain pending. Chat, uploads, and authentication arrive in later approved steps.

## Requirements

- Node.js 20.9+ and npm (verified locally with Node 20.17.0 and npm 10.8.2).
- Python 3.13 and uv (verified locally with Python 3.13.5 and uv 0.11.13).
- No API keys, `.env`, database, or Google Drive credentials are required for Step 1.

## Install

Backend:

```sh
cd "/Users/admin/Working/2026-S2/YZU Student Assistant/backend"
uv sync --frozen
```

Frontend:

```sh
cd "/Users/admin/Working/2026-S2/YZU Student Assistant/frontend"
npm ci
```

Keep `uv.lock` and `package-lock.json` in version control for reproducible installs.

## Run locally

Start the backend in one terminal:

```sh
cd "/Users/admin/Working/2026-S2/YZU Student Assistant/backend"
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in a second terminal:

```sh
cd "/Users/admin/Working/2026-S2/YZU Student Assistant/frontend"
npm run dev
```

- Frontend: <http://localhost:3000>
- API liveness: <http://localhost:8000/health> — expected `{"status":"ok"}`
- Interactive API documentation: <http://localhost:8000/docs>

Both processes listen only on the local machine. Stop each with **Ctrl+C** in its terminal. If a port is occupied, stop your earlier instance or deliberately select another port; do not terminate unrelated processes.

## Verify Step 1

```sh
curl --fail http://localhost:8000/health
```

From `frontend/`, run `npm run build` and `npm run typecheck`. The HaUI-style chat preview should render at desktop and mobile widths and explicitly say chat is not available yet. FAQ buttons fill the input; the Send button stays disabled until chat is implemented. The sidebar switches to a drawer below the original desktop breakpoint. The moon/sun button toggles the original theme. It is not connected to the API yet.

For a production-mode local frontend check, stop the development server, run `npm run build`, then `npm start`.

## Structure

- `frontend/app/layout.tsx`: `RootLayout()` defines English HTML, metadata, and shared styles.
- `frontend/app/page.tsx`: `Chat()` renders the adapted HaUI chat shell, greeting, and inactive composer.
- `backend/app/main.py`: creates the FastAPI app and registers routes.
- `backend/app/api/health.py`: `get_health()` reports process liveness without querying external services.
- `AGENTS.md`: project rules and mandatory step-by-step user checkpoints.
- `ARCHITECTURE.md`: source review, planned structure, and implementation status.
- `IMPLEMENTATION_PLAN.md`: agreed order and acceptance checks.

Configuration and credentials are being implemented in Step 2. Store future local secrets in ignored `.env` files and credential files in an ignored `credentials/` directory. Commit only placeholder `.env.example` files. Selected HaUI frontend theme files, assets, and layout code are reused. No credentials or backend configuration were copied.

The frontend uses the original Chakra UI 2.10.7 theme, primary-button variant, Plus Jakarta Sans font, FAQ sidebar, floating toolbar, message bubble, and rounded input styling. `AppWrappers()` provides the Chakra theme; `SidebarContent()` and `Navbar()` adapt the corresponding source components. The source font stylesheet loads from Google Fonts, as in HaUI-library.

The sidebar, assistant avatar, and faded chat background use the YZU logo supplied by the user, stored unchanged at `frontend/public/img/logo/yzu-logo.png`. Its circular proportions are preserved. The Horizon UI license from the source is preserved in `frontend/LICENSE`. Do not introduce a new visual design or implementation approach without discussing it with the user first.

## Step 2 configuration and review

Keep secrets in ignored `backend/.env`. On a fresh checkout, copy `backend/.env.example` to it. Existing local values are never overwritten. The user selected Gemini through the OpenAI-compatible endpoint and personal Google Drive OAuth.

| Variables | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | Server-side Gemini credential |
| `GEMINI_BASE_URL` | User-configured OpenAI-compatible Gemini endpoint, passed to both LangChain clients |
| `GEMINI_CHAT_MODEL_1` | Active chat model ID |
| `GEMINI_EMBEDDING_MODEL` | Embedding model ID |
| `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` | Existing Neo4j connection |
| `NEO4J_DATABASE` | Database name, default `neo4j` |
| `GOOGLE_DRIVE_FOLDER_ID` | Existing destination folder |
| `GOOGLE_DRIVE_CREDENTIALS_JSON` | Path to downloaded OAuth client JSON, absolute or relative to `backend/` |
| `GOOGLE_DRIVE_TOKEN_FILE` | Optional token path, default `credentials/token.json` |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `AUTH_SECRET` | Reserved for Step 3 |

`GEMINI_CHAT_MODEL_2` is not used in this step. Older blank `OPENAI_*` variables are ignored; no fallback sends Gemini credentials to OpenAI. `load_settings()` preserves literal dollar signs and gives process environment values precedence. The optional frontend `.env` contains only `NEXT_PUBLIC_API_URL`, default `http://localhost:8000`; the chat preview is not connected yet.

`create_models()` retains HaUI's `ChatOpenAI` / `OpenAIEmbeddings`, sets `base_url` for both, selects Chat Completions, and sends raw embedding text with `check_embedding_ctx_length=False`. See [Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai).

### Personal Drive authorization

The user approved full Drive OAuth scope to use the existing folder. The credential currently provided is a Web OAuth client. In Google Cloud, enable Drive API, configure the consent screen/test user as needed, and register this exact Authorized redirect URI for that client:

```text
http://localhost:8080/
```

From `backend/`, run:

```sh
uv run python -m app.storage.drive --authorize --check-public
```

Complete Google consent in the browser within three minutes. Authorization is explicit and never opens automatically on API startup. Tokens are stored in the ignored token file with owner-only permissions. Subsequent checks refresh expired access tokens when possible. Do not commit the OAuth JSON or token file.

The command checks destination-folder access, creates `yzu-connection-check.txt`, grants public reader access, reads its exact contents without OAuth, and deletes only that newly created probe. No existing documents are changed. A failed command prints only a safe status or exception class. Retry `--authorize` after correcting OAuth configuration or revoked/expired refresh tokens. Once authorized, repeat the probe without another login using:

```sh
uv run python -m app.storage.drive --check-public
```

### Startup and verification

Restart the backend after configuration changes or completing OAuth. Every startup with complete Gemini configuration makes one short chat and embedding request; these use API quota, including development reloads. `/ready` reads cached startup results without additional provider calls. It is a startup snapshot, not continuous monitoring.

- `/health`: HTTP 200 when the process is alive.
- `/ready`: HTTP 200 when all dependency checks pass; otherwise HTTP 503 with safe per-service status. Drive folder readiness does not by itself prove public sharing; the explicit probe above is the acceptance check.
- `oauth_authorization_required`: complete the browser consent command.
- `invalid_drive_folder` / `drive_folder_not_writable`: correct the folder selection or account access.
- `connection_failed`: check local credentials/provider availability; provider exception bodies are not exposed.

Run offline tests from `backend/`:

```sh
uv run python -m pytest -q
```

Current result: 13 passing tests, including Gemini request routing/raw embedding text, missing settings, error redaction, lifecycle cleanup, private token permissions, folder validation, and probe cleanup. One Starlette/AnyIO dependency deprecation warning remains. Real Neo4j, Gemini chat, and Gemini embeddings checks passed. Google OAuth consent and a real public-link probe remain pending; Step 2 is not yet complete. Step 3 has not started. All changes remain local; the user manages publishing.
