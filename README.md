# YZU Student Assistant

An English information assistant for YZU students. **Step 1 provides only the HaUI-derived chat interface preview and API liveness endpoint.** Chat, uploads, authentication, model calls, and storage connections arrive in later approved steps.

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

Configuration and credentials are Step 2. Store future local secrets in ignored `.env` files and credential files in an ignored `credentials/` directory. Commit only placeholder `.env.example` files. Selected HaUI frontend theme files, assets, and layout code are reused. No credentials or backend configuration were copied.

The frontend uses the original Chakra UI 2.10.7 theme, primary-button variant, Plus Jakarta Sans font, FAQ sidebar, floating toolbar, message bubble, and rounded input styling. `AppWrappers()` provides the Chakra theme; `SidebarContent()` and `Navbar()` adapt the corresponding source components. The source font stylesheet loads from Google Fonts, as in HaUI-library.

The sidebar, assistant avatar, and faded chat background use the YZU logo supplied by the user, stored unchanged at `frontend/public/img/logo/yzu-logo.png`. Its circular proportions are preserved. The Horizon UI license from the source is preserved in `frontend/LICENSE`. Do not introduce a new visual design or implementation approach without discussing it with the user first.
