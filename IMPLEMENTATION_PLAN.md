# YZU Student Assistant Implementation Plan

> **For agentic workers:** Use Superpowers `executing-plans` for sequential execution. The user's checkpoint rule overrides any skill default to execute multiple tasks in a batch. Complete one numbered step, present evidence, and wait for explicit user confirmation before starting the next. Do not delegate or continue automatically.

**Goal:** Run an English YZU information assistant locally, with public chat, cited answers, and one administrator managing manually supplied PDFs and YZU webpages.

**Architecture:** One Next.js frontend and one FastAPI backend. Simplified LangGraph orchestrates Neo4j document retrieval and grounded answers; Google Drive stores publicly readable PDF originals. Chat and embedding models have separate roles, with settings and secrets supplied by the user through local configuration.

**Tech stack:** Next.js, React, TypeScript, Chakra UI, FastAPI, Python, LangGraph, Neo4j, OpenAI model integration, Google Drive, Docling and HTML parsing. Validate compatible versions during Step 1 rather than copying the legacy dependency list unchanged.

**Status:** Steps 1–4 and Step 7 are implemented and accepted by the user, including the cross-page sentence correction. The user authorized Step 8's six-node LangGraph workflow. Step 8 implementation is ready for user-run verification; it is not yet accepted. All work remains local.

## Location and boundaries

Project root: `/Users/admin/Working/2026-S2/YZU Student Assistant`.

Reference source: `/Users/admin/Working/2025/HaUI-library`. It remains unchanged. All paths below are relative to the project root; do not write application files into the earlier discussion workspace.

The user will provision Neo4j and supply connection settings and other secrets. Do not provision a replacement database automatically. Google Drive authentication may require a local credential file referenced from `.env`; confirm the user's credential type during Step 2.

Initial capabilities: English public student chat, one administrator, PDF upload, individual YZU HTML URL ingestion, document listing/replacement/deletion, source references, course explanations from documents, and session context.

Excluded: structured course/book catalogs, Excel imports, generated Cypher, old agent comparison routes, embedded widget, analytics dashboard, incorrect-answer correction UI, crawling, Chinese support, OpenAI Agents SDK migration, MCP, and specialist agents.

## Execution order selected by the user

Keep original step numbers so earlier discussion remains easy to follow.

**First milestone — working PDF chat:** Step 1 → Step 2 → Step 3 → Step 4 → Step 7 → Step 8 → Step 9. Stop for confirmation after every step; approval of this order is not approval to batch the steps.

During this milestone, the administrator uploads PDFs through the authenticated API documentation. The full document-management interface is deferred. Google Drive public links and answer references remain required. Use English PDF sources for retrieval and answer checks; no HTML ingestion is required before the first chat demonstration.

**After the user tries and accepts PDF chat:** return to Step 5 (manual HTML ingestion), Step 6 (document administration and content lifecycle), then Step 10 (broader verification and handover). Each still needs its own review checkpoint.

Focused verification remains part of every step. The assistant provides exact commands and expected results, and the user runs the checks and reports the outcome. Step 9 must include a working end-to-end PDF upload → indexing → retrieval → streamed answer → public reference demonstration before the first milestone is reported ready. Full Step 10 is deferred, not all verification.

## How each checkpoint works

For every numbered step:

1. Announce the scope and the functions/files affected.
2. Implement only that step, adapting selected source code where useful.
3. Provide focused check commands and expected results for the user to run. Use meaningful automated tests for behavior, not tests that merely repeat trivial code; fix reported failures within the same step.
4. Update `ARCHITECTURE.md` and the run instructions where behavior has changed.
5. Present what changed, why, test results, how the user can check it, and any remaining limitations.
6. Mark the step as awaiting review and stop. The next step requires an explicit user confirmation; silence, tool permission, or an unrelated reply is not confirmation.

If the user requests changes, revise the current step and present it again. Confirming the overall plan does not authorize executing all steps. The user has authorized coding through the current step only.

## File responsibilities

```text
YZU Student Assistant/
├── AGENTS.md
├── ARCHITECTURE.md
├── IMPLEMENTATION_PLAN.md
├── README.md
├── .gitignore
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── login/page.tsx
│   │   └── admin/documents/
│   │       ├── page.tsx
│   │       └── [id]/page.tsx
│   ├── components/
│   │   ├── chat/                  # ChatPanel, MarkdownMessage, References
│   │   └── documents/             # UploadForm, UrlForm, DocumentList
│   ├── hooks/useChatSession.ts
│   ├── lib/                       # api.ts, auth.ts, documents.ts, chat.ts
│   ├── tests/
│   ├── public/
│   ├── package.json
│   └── .env.example
└── backend/
    ├── app/
    │   ├── main.py                # Application lifecycle and dependency wiring
    │   ├── config.py              # Validated configuration, no secret logging
    │   ├── auth.py                # Single-administrator authentication
    │   ├── schemas.py             # Requests, passages, references, stream events
    │   ├── models.py              # Chat and embedding model clients
    │   ├── api/                   # health.py, auth.py, documents.py, chat.py
    │   ├── services/              # ingestion.py, retrieval.py, chat.py
    │   ├── ingestion/             # pdf.py, html.py, chunking.py
    │   └── storage/               # neo4j.py, drive.py, documents.py, sessions.py
    ├── tests/
    ├── pyproject.toml
    └── .env.example
```

Four logical layers: presentation, API/access, application workflows, and storage/integrations. Parsing supports ingestion. There are two model roles, answer generation and embeddings; graph nodes are not separate model deployments. Create files as their steps need them, not empty speculative modules. Local Python and Node processes are the initial run method; containerization is not necessary for acceptance.

## Step 1 — Project skeleton and local startup

**Files:** `.gitignore`, `README.md`, `backend/pyproject.toml`, `backend/app/main.py`, `backend/app/api/health.py`, `frontend/package.json`, `frontend/app/layout.tsx`, `frontend/app/page.tsx`, and necessary framework configuration/lockfiles.

- [x] Inspect installed Python/Node runtimes and select compatible, pinned dependency versions using official documentation at execution time.
- [x] Create the frontend/backend skeleton and minimal health response. Reuse the original HaUI chat layout and Chakra theme; no new landing-page design.
- [x] Exclude local environments, `.env` secrets, credential files, caches, and generated builds from version control. Never copy the source `.env`, credentials, `.git`, dependencies, or data.
- [x] Document local start commands: backend from `backend/` with `.venv/bin/python -m uvicorn app.main:app --reload --port 8000`; frontend from `frontend/` with `npm run dev` on port 3000.
- [x] Check the frontend renders, its production build succeeds, and `curl http://localhost:8000/health` returns a successful liveness response without requiring external services.

**User review:** Open the local frontend and API health endpoint; inspect the folder organization. **STOP for confirmation.**

**Visual correction requested by the user:** Replaced the custom landing page with source-derived HaUI sidebar, toolbar, message, composer, theme, and assets. Build, typecheck, desktop/mobile layout, FAQ input, drawer, and theme controls passed. The user-supplied YZU logo now replaces visible HaUI branding in the sidebar, avatar, and background. Still awaiting review.

**Verification:** Production build and TypeScript check passed; live `/health` returned HTTP 200 with `{"status":"ok"}`; OpenAPI lists the health route. Browser review passed at desktop and 390px mobile width with no horizontal overflow or captured console warnings/errors. Secret/dependency ignore rules were checked. No model, database, Drive, login, upload, or chat features are connected yet.

## Step 2 — Configuration and external connections

**Files:** `backend/.env.example`, `backend/app/config.py`, `backend/app/models.py`, `backend/app/storage/neo4j.py`, `backend/app/storage/drive.py`, `backend/app/api/health.py`, `backend/tests/test_config.py`, `frontend/.env.example`, `frontend/lib/api.ts`.

- [x] Establish one set of names for model settings, Neo4j URI/user/password, Drive credentials/folder, administrator credentials, and authentication secret. Examples contain placeholders only.
- [x] Let the user populate the untracked backend `.env` and credential file. Frontend environment values contain only public routing information.
- [x] Initialize clients during application lifecycle, not imports. Make missing configuration errors identify variable names without disclosing values.
- [x] Verify Neo4j connectivity and access to the selected Drive folder; verify the configured chat and embedding models with small, clearly identified connection checks once credentials are supplied.
- [x] Confirm that the user's Drive setup permits public reference links. If it cannot, stop this step and report the specific setup issue.
- [x] Test missing-setting validation and cleanup of connections. Keep liveness distinct from dependency readiness; do not return secret-bearing exception text to browsers.

**User review:** Inspect variable names and the connection-status report. Secret values are never displayed. **STOP for confirmation.**

## Step 3 — Administrator login

**Files:** `backend/app/auth.py`, `backend/app/api/auth.py`, `backend/app/schemas.py`, `backend/tests/test_auth.py`, `frontend/app/login/page.tsx`, `frontend/lib/auth.ts`. Also add `backend/app/api/admin.py` as the shared guarded router; update application lifespan/CORS registration.

- [x] Adapt the login UI; implement one configured administrator with verified password handling and session expiration.
- [x] Use backend-validated authentication for every document-management action; frontend route protection alone is insufficient.
- [x] Provide logout. Keep student chat access public. Replace the legacy hardcoded account and fallback signing secret.
- [x] Test valid/invalid login, expiration, logout behavior, and denial of management access without authentication. Set local cookie/CORS behavior consistently for the chosen origins.

**User review:** Log in and out and try management access while logged out. **STOP for confirmation.**

## Step 4 — PDF ingestion and public Google Drive references

**Files:** `backend/app/api/documents.py`, `backend/app/services/ingestion.py`, `backend/app/ingestion/pdf.py`, `backend/app/ingestion/chunking.py`, `backend/app/storage/documents.py`, `backend/app/storage/drive.py`, `backend/tests/test_pdf_ingestion.py`.

- [x] Adapt `create_file()`, Markdown chunking functions, and Drive upload operations into one ingestion service.
- [x] Validate PDF input and isolate temporary paths per upload. Preserve headings and actual page information when extraction supports it; do not fabricate page numbers.
- [x] Upload the original, grant public read access as required, and store its Drive ID/link with document metadata.
- [x] Extract, chunk, embed, and persist source-linked records. Mark content ready only after indexing succeeds; expose actionable import failures and handle partial work explicitly.
- [x] Test extraction/source metadata, simultaneous upload isolation, and failure handling using controlled fixtures; run one real PDF import into the project services.

**Verification:** 49 backend tests pass. The real 4-page PDF produced 11 chunks and 3,072-dimensional embeddings; Neo4j readback and vector-index checks passed. Anonymous Drive download matched the original SHA-256. See `docs/STEP_4_VERIFICATION.md` for extraction limitations and exact results.

**User review:** Inspect the existing sample and its Drive link first. A repeat upload creates another document. Optionally submit another sample through API documentation. **STOP for confirmation.**

## Step 5 — Manual YZU webpage ingestion

**Files:** `backend/app/ingestion/html.py`, `backend/app/services/ingestion.py`, `backend/app/api/documents.py`, `backend/tests/test_html_ingestion.py`.

- [ ] Adapt `get_content_from_url()` for a single administrator-submitted public YZU URL. Restrict fetches and redirects to the configured YZU website hosts; do not allow arbitrary local/network targets.
- [ ] Extract main text, headings, and useful course tables while excluding navigation noise. Preserve the original source URL and ingestion timestamp.
- [ ] Reuse the chunk/embed/store workflow. Do not crawl links, import linked PDFs automatically, or schedule refreshes.
- [ ] Test table/headings extraction, failed fetches, and disallowed redirects. Import one user-selected English YZU page.

**User review:** Compare extracted content with the webpage and open its stored source link. **STOP for confirmation.**

## Step 6 — Document administration and content lifecycle

**Files:** `frontend/app/admin/documents/page.tsx`, `frontend/app/admin/documents/[id]/page.tsx`, `frontend/components/documents/`, `frontend/lib/documents.ts`, `backend/app/api/documents.py`, `backend/app/services/ingestion.py`, `backend/app/storage/documents.py`, `backend/tests/test_document_lifecycle.py`.

- [ ] Adapt only the document list, upload, URL-entry, and detail components from HaUI-library.
- [ ] Display title, source type, original link, import status, and extracted-content preview.
- [ ] Support PDF replacement, manual webpage refresh, and removal from the knowledge base. Build updated chunks/embeddings before retiring the previous ready content.
- [ ] Clearly distinguish knowledge-base removal from permanent Drive-original deletion in the UI; settle the desired Drive-deletion behavior with the user at this step before enabling it.
- [ ] Test replacement removes obsolete searchable chunks, deletion excludes the source from new retrieval, and failed updates leave a clear status without falsely reporting success.

**User review:** Upload, inspect, replace/refresh, and remove a sample using the UI. Confirm the Drive deletion behavior. **STOP for confirmation.**

## Step 7 — Neo4j retrieval and source records

**Files:** `backend/app/services/retrieval.py`, `backend/app/schemas.py`, `backend/app/storage/documents.py`, `backend/tests/test_retrieval.py`.

- [x] Adapt `get_chunk_retriever()` and hybrid-search configuration, keeping index creation outside module imports.
- [x] Define retrieval output as passages with chunk/document IDs, title, source URL, optional real page/section, and retrieval score. Deduplicate repeated passages.
- [x] Search only ready, current content. Keep result limits and thresholds configurable instead of blindly copying the original two-result setting.
- [x] Prepare expected-evidence questions covering a policy, scholarship, course list, and an absent topic from the user's imported English PDF corpus. Where a topic is absent, verify that absence rather than inventing an expected answer.
- [x] Show retrieved passages before involving answer generation. Check relevant evidence, no-match behavior, source metadata, and exclusion of non-ready records. Full replacement/deletion integration checks follow Step 6.

**Status:** Completed and accepted by the user on 2026-09-15. Safe search evidence is retained under ignored `backend/data/step7/`. Full replacement/deletion integration checks still follow Step 6.

## Step 8 — Simplified LangGraph and conversation context

**Files:** `backend/app/services/chat.py`, `backend/app/storage/sessions.py`, `backend/app/schemas.py`, `backend/tests/test_chat_workflow.py`.

**Status:** Implemented; awaiting user verification and acceptance. See `docs/STEP_8_PLAN.md` and `docs/STEP_8_VERIFICATION.md`. The graph uses understand → retrieve → evaluate → reason → answer, with an interrupting clarify → retrieve branch. Neo4j stores checkpoints and conversation turns across restarts. The local reset operation deletes the selected session's records; frontend reset wiring follows in Step 9.

- [x] Adapt the enhanced graph into the approved six-node workflow. Remove book/contact tools, generated Cypher, agent comparison, and autonomous retry loops.
- [x] For a conversational follow-up, use bounded recent history to form a standalone retrieval question with the same chat model. This is query preparation, not a specialist agent or a new model role.
- [x] Generate English answers from retrieved evidence. Preserve policy qualifications and dates, acknowledge gaps, and avoid claiming a course list is complete without evidence.
- [x] Use source IDs for citations and resolve links from stored retrieval metadata. Treat document text as evidence, never as instructions authorizing actions.
- [x] Persist conversation turns and LangGraph checkpoints in Neo4j, isolate sessions, and delete one session on reset. Do not inherit the original ten-question limit.
- [ ] User verifies answer support, valid citation IDs, absent information, pause/resume clarification, context-dependent follow-ups, restart persistence, reset, and session isolation using `docs/STEP_8_VERIFICATION.md`.

**User review:** Inspect full answers and follow-ups against the cited sources. Confirm session behavior. **STOP for confirmation.**

## Step 9 — Student chat, Markdown, and SSE

**Files:** `backend/app/api/chat.py`, `frontend/app/page.tsx`, `frontend/components/chat/ChatPanel.tsx`, `frontend/components/chat/MarkdownMessage.tsx`, `frontend/components/chat/References.tsx`, `frontend/hooks/useChatSession.ts`, `frontend/lib/chat.ts`, `frontend/tests/chat_stream.test.ts`, `backend/tests/test_chat_stream.py`.

- [ ] Adapt the chat page, Markdown rendering, and `streamMessage()` into one event contract: start, answer content, references, completion, or error.
- [ ] Map the chosen LangGraph execution/streaming API to SSE and handle events split across network chunks. Do not label whole-message updates as token streaming.
- [ ] Render source references from structured metadata and provide a new-conversation action. Show user-appropriate errors and clear loading/completion states.
- [ ] Test split events, normal completion, interrupted streams, errors, Markdown tables, and source-link rendering.
- [ ] Demonstrate public student chat in the local browser with the backend and imported PDF knowledge base. Verify the complete authenticated PDF upload → indexing → question → streamed cited answer flow, including signed-out access to the Drive original, conversational follow-ups, and missing-evidence behavior. Publish local start instructions so the user can try it.

**User review:** Ask policy, scholarship, and course questions; follow references and start a new conversation. **STOP for confirmation.**

## Step 10 — End-to-end verification and local handover

**Files:** `README.md`, `ARCHITECTURE.md`, relevant existing tests, and `backend/tests/test_end_to_end.py` only for integration checks not already covered.

- [ ] Run the established backend tests, frontend tests, and production build; fix failures before reporting completion.
- [ ] Verify the full PDF/HTML → indexing → question → cited answer flow with the agreed English corpus.
- [ ] Recheck public Drive references, admin-only mutations, source replacement/deletion, session isolation, absent evidence, and interrupted ingestion/chat behavior.
- [ ] Verify restart behavior and document exact startup/shutdown commands, dependency versions, environment names, and recovery steps for failed imports.
- [ ] Report passed checks and remaining limitations with concrete examples. Ensure no source-project credentials, HaUI defaults, or excluded modules were copied.

**User review:** Run the system from the documented instructions and accept version one or request corrections. **STOP. No MCP or advanced work begins automatically.**

## Later versions — separate plans

After version-one acceptance, discuss MCP client/server boundaries and the requested manager/intent routing → retrieval with bounded retries → evidence reviewer → final manager response. Chinese support and automatic crawling also need separate scope and acceptance decisions. No dates, order between these enhancements, or automatic framework switch is implied.


## Step 7 discussion decisions and prerequisite correction

The completed Step 7 provides two independent semantic/keyword search functions, RRF result fusion, reranking with `GEMINI_CHAT_MODEL_2`, and fallback to merged rank if reranking fails or returns invalid data. Up to one previous/next chunk may supplement each selected result, with deduplication and a bounded context budget. Query understanding and evidence evaluation belong to the Step 8 graph.

The prerequisite ingestion fix removes forced page boundaries and records all source pages in `page_numbers`, with `page_number` as the first page. The real scholarship sample was re-embedded and repaired under its existing document ID and Drive reference. The user accepted Step 7 and moved the project to Step 8.
