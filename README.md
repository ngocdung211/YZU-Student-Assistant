# YZU Student Assistant

An English information assistant for YZU students. **Steps 1 and 2 are approved; Step 3 administrator login is implemented.** The HaUI-derived interface remains a preview. Gemini and Neo4j live checks pass. Personal Google Drive OAuth and public-link verification passed. Chat and document uploads arrive in later approved steps.

## Requirements

- Node.js 20.9+ and npm (verified locally with Node 20.17.0 and npm 10.8.2).
- Python 3.13 and pip (verified locally with Python 3.13.5).
- No API keys, `.env`, database, or Google Drive credentials are required for Step 1.

## Install

Backend:

```sh
cd "/Users/admin/Working/2026-S2/YZU Student Assistant/backend"
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

Frontend:

```sh
cd "/Users/admin/Working/2026-S2/YZU Student Assistant/frontend"
npm ci
```

Keep `requirements.txt` and `package-lock.json` in version control for reproducible installs.

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
| `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `AUTH_SECRET` | Administrator login configuration |

`GEMINI_CHAT_MODEL_2` is not used in this step. Older blank `OPENAI_*` variables are ignored; no fallback sends Gemini credentials to OpenAI. `load_settings()` preserves literal dollar signs and gives process environment values precedence. The optional frontend `.env` contains only `NEXT_PUBLIC_API_URL`, default `http://localhost:8000`; the chat preview is not connected yet.

`create_models()` retains HaUI's `ChatOpenAI` / `OpenAIEmbeddings`, sets `base_url` for both, selects Chat Completions, and sends raw embedding text with `check_embedding_ctx_length=False`. See [Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai).

### Personal Drive authorization

The user approved full Drive OAuth scope to use the existing folder. The credential currently provided is a Web OAuth client. In Google Cloud, enable Drive API, configure the consent screen/test user as needed, and register this exact Authorized redirect URI for that client:

```text
http://localhost:8080/
```

From `backend/`, run:

```sh
.venv/bin/python -m app.storage.drive --authorize --check-public
```

Complete Google consent in the browser within three minutes. Authorization is explicit and never opens automatically on API startup. Tokens are stored in the ignored token file with owner-only permissions. Subsequent checks refresh expired access tokens when possible. Do not commit the OAuth JSON or token file.

The command checks destination-folder access, creates `yzu-connection-check.txt`, grants public reader access, reads its exact contents without OAuth, and deletes only that newly created probe. No existing documents are changed. A failed command prints only a safe status or exception class. Retry `--authorize` after correcting OAuth configuration or revoked/expired refresh tokens. Once authorized, repeat the probe without another login using:

```sh
.venv/bin/python -m app.storage.drive --check-public
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
.venv/bin/python -m pytest -q
```

Current result: 13 passing tests, including Gemini request routing/raw embedding text, missing settings, error redaction, lifecycle cleanup, private token permissions, folder validation, and probe cleanup. One Starlette/AnyIO dependency deprecation warning remains. Real Neo4j, Gemini chat, and Gemini embeddings checks passed. Google OAuth and a real public-link probe passed; the temporary probe was deleted. Step 2 is verified and awaiting user approval. Step 3 has not started. All changes remain local; the user manages publishing.

Final checkpoint: the running API returned HTTP 200 from `/ready` with Neo4j, Gemini and Drive ready. One earlier Gemini startup check failed; isolated chat/embedding checks and the final startup passed. The import paths in `app/models.py` and `tests/test_drive.py` were corrected to support the documented backend working directory. The OAuth client JSON is outside this repository and untracked; the token is inside the repository, ignored and untracked. No Git exclusion change was needed.

## Step 3 — Administrator login

The HaUI login layout is adapted at <http://localhost:3000/login>. The public student chat preview remains at `/` and requires no login. The successful login view shows the administrator session, an API documentation link, and logout; document-management screens are still deferred.

Your `ADMIN_USERNAME` is read from `backend/.env`. Configure a password without putting it in shell history or chat:

```sh
cd "/Users/admin/Working/2026-S2/YZU Student Assistant/backend"
.venv/bin/python -m app.auth --set-password
```

Enter and confirm a password of 12–1024 characters. The helper saves an Argon2 hash in `ADMIN_PASSWORD_HASH`. If `AUTH_SECRET` is empty or shorter than 32 characters, this explicit command replaces it with a random signing secret. Neither value is printed. The `.env` file is kept owner-readable/writable. Process environment overrides still apply; remove stale overrides if a changed file is not taking effect.

Restart the backend after configuration, then open `/login`. Test your credentials, reload the page to confirm the cookie session, click **Log out**, and check that <http://localhost:8000/admin/session> returns HTTP 401. Wrong credentials return HTTP 401; missing or invalid administrator setup returns HTTP 503. Existing `/health` and `/ready` retain their Step 2 meanings; provider readiness is not administrator configuration readiness.

### Local session contract

- `POST /auth/token`: JSON `username`/`password`, returns identity/expiry and sets an HttpOnly, SameSite=Lax cookie. It never returns the token in JSON or stores it in browser localStorage.
- `GET /admin/session`: protected identity/expiry check; HTTP 401 without a valid session.
- `POST /auth/logout`: revokes the current session and deletes the cookie; copied cookies from that session are rejected afterward.
- Mutating authentication/management requests require `X-CSRF-Protection: 1`. Browser origins are restricted to the approved local frontend/API addresses. The frontend supplies the header automatically. FastAPI `/docs` exposes this header for testing: enter `1` when executing login/logout or future management actions.
- Sessions expire after one hour. Active session IDs live in the single backend process; restart/reload logs every administrator session out. The signed JWT follows HaUI's approach with explicit server-side revocation added for logout.
- `app/api/admin.py:router` applies `require_admin()` at router level. Future document-management routes must use this guard; client-side checks do not grant access. PDF upload and inspection now use this same guard (see Step 4 below).

Use the same hostname for frontend/API (`localhost` for both, or configure `127.0.0.1` for both). Cookies intentionally have `Secure=False` for this HTTP localhost milestone. Multi-worker or public HTTPS deployment requires a shared session store and reviewed cookie/origin configuration; it is outside this local step.

Verification: 28 backend tests pass, including login, invalid credentials, expiration, token tampering, logout replay, protected management mutations, missing configuration, and CSRF/CORS behavior. Production frontend build and TypeScript checks pass. The login form retains HaUI's spacing, input/password toggle, blue submit button and back button. User password setup and live browser login/logout remain the final review check. No remote repository actions were performed.

Browser verification: the HaUI-derived form fits desktop and 390px mobile widths; password visibility and the missing-setup message work. The back link opens public chat without login. The hung local frontend process was restarted. Live administrator login/logout awaits the user choosing a local password.


## Step 4 — PDF import (ready for review)

The user has confirmed Step 3 authentication is complete. PDF import now reuses HaUI's Docling/Markdown pipeline, followed by explicit Gemini embeddings, public Drive upload, and atomic Neo4j storage. The frontend design is unchanged. Retrieval and chat are the next approved-order steps, not yet implemented.

From `backend/`, install the updated dependencies with `.venv/bin/python -m pip install -r requirements.txt`, then start or restart the API using the existing startup command. Docling downloads its local PDF/OCR model files on first conversion; that first run can take several minutes. Subsequent conversions use cached assets. PDF import is synchronous and the request waits for the result; this version has no progress UI or durable background job queue.

### Inspect the imported scholarship sample

1. Log in yourself at <http://localhost:3000/login>. Use the same `localhost` hostname for the API. A backend restart clears the previous session.
2. Open <http://localhost:8000/docs> and expand `GET /admin/documents/{document_id}`.
3. Choose **Try it out**, enter `7289437e-be9a-49b8-82df-110fa9439676`, and execute. Expect HTTP 200 with document metadata and 11 chunks, including actual pages 1–4, heading metadata, and embedding dimensions. Vector arrays are intentionally omitted.
4. Open the returned `source_url` in a private/signed-out browser. It should display the complete original PDF.

The sample is already stored; you do not need to upload it again. Local readback is saved in `backend/data/step4/stored-chunks.json` (ignored by Git). See `docs/STEP_4_VERIFICATION.md` for the full check and known extraction limitations.

### Upload a PDF yourself

In `/docs`, expand `POST /admin/documents`, choose **Try it out**, set `x-csrf-protection` to `1`, choose a PDF, and execute. Your existing administrator cookie is sent by the browser; do not paste credentials into code. Expect HTTP 201 with `status: ready`, `document_id`, `page_count`, `chunk_count`, and `source_url`. Use the returned ID with the inspection endpoint.

Uploads accept `.pdf` files up to 20 MiB and 100 pages. Each upload uses a separate temporary directory and is processed one at a time in the local API process. Long Markdown sections use a 2,500-character limit and up to 500-character overlap within a heading section, including across physical pages. Each chunk stores `page_numbers` for all contributing pages and keeps `page_number` as the first page; heading recognition is only as accurate as Docling's output. The configured `GEMINI_EMBEDDING_MODEL` is called through `GEMINI_BASE_URL`. Each import uses embedding quota and Drive storage. Uploading the same PDF again creates a new document and Drive file; replacement/deduplication is deferred.

Failures return a safe stage and message: invalid/unreadable PDF (422), file too large (413), unavailable clients (503), or embedding/Drive/Neo4j failure (502). Unauthenticated access is 401; a missing CSRF header is 403. A failed import attempts to remove only its own new records and Drive file. If `cleanup_required` is true, inspect the matching ignored `backend/data/failed-imports/<document_id>.json` before retrying. It records IDs and the failed stage, not credentials. An uncertain Drive upload can be located using its `yzu_document_id` app property. There is no automated recovery UI yet.

Verification: **49 backend tests passed**; the supplied 4-page PDF was imported using the real configured services. Eleven 3,072-dimensional vectors were read back, the Neo4j index is ONLINE, a self-vector lookup matched the source, and an anonymous download matched the original SHA-256. One Starlette/AnyIO dependency deprecation warning remains. All work is local; no push was performed. Stop for Step 4 review before Step 7.


### Cross-page sentence correction

The chunker no longer flushes at every physical page break. It joins plain-text continuations, preserves explicit heading/list boundaries, and prefers paragraph/sentence boundaries before falling back to smaller splits under the 2,500-character cap. Source character spans map each chunk to `page_numbers`; `page_number` remains its first page for compatibility. An oversized sentence may still need splitting to respect the size limit.

The existing scholarship sample was re-embedded and its chunks replaced atomically under the same document ID and Drive URL. The complete sentence “The review standard may be increased by colleges based on the nature of the field.” is now present in a chunk attributed to pages `[2, 3]`. The sample still has 11 chunks. See `backend/data/step4/stored-chunks.json` for current readback. This correction does not repair Docling's separate heading/reading-order limitations.

Step 7 is complete and accepted. Authenticated inspection endpoints expose independent semantic and keyword searches plus combined RRF fusion, optional `GEMINI_CHAT_MODEL_2` reranking with safe fallback, and bounded neighboring context. Safe live-search evidence is retained under ignored `backend/data/step7/`.

## Step 8 — Simplified LangGraph agent

The workflow is `rewrite_query → retrieve → answer`, with persistent Neo4j checkpoints/history. Document retrieval is always attempted first. If it returns no passages, the answer node may try a billable Gemini search restricted to official YZU sites and a maintained Global Affairs contact. From `backend/`, run `.venv/bin/python -m app.chat_cli` to start a disposable local conversation. Restart with `--session YOUR_SESSION_UUID` to continue it. `/retry` resumes failed work; `/reset` permanently deletes that session's history/checkpoints; `/quit` exits.

Follow [Step 8 verification](docs/STEP_8_VERIFICATION.md) for exact offline and live checks. Public browser chat, session ownership controls, and SSE follow in Step 9.
