# Architecture review and YZU planning baseline

Reviewed on 2026-09-14. Source: `/Users/admin/Working/2025/HaUI-library/`, working tree at commit `104966d`, including local files. Existing source changes were left untouched. This is a static implementation review, not a runtime certification or an approved YZU design. No application code was copied or changed, and no live databases, model APIs, or deployments were exercised.

## Current implementation: HaUI-library

The application answers HaUI library questions and manages its knowledge sources. It combines a public chat interface, an embeddable chat widget, and an administrator interface with a FastAPI backend. Neo4j stores both graph relationships and searchable document chunks. Google Drive stores uploaded originals. OpenAI supplies chat and embedding models.

### Logical layers

For explanation, the current code can be grouped into five logical layers. These are responsibilities, not five independent services or five AI models; dependencies cross some boundaries.

| Layer | Source location | Responsibility |
| --- | --- | --- |
| 1. Presentation | `frontend-chatbot/app/`, `src/components/`, `src/hooks/` | Public chat, embedded chat, login, document/book/Excel administration, statistics, and response correction UI |
| 2. API and access | `api-chatbot/main.py`, `auth.py`, `routers/` | Request validation, JWT authentication, CRUD endpoints, chat event streams, and health endpoints |
| 3. Agent orchestration | `agents/`, `chains/`, `tools/` | Prompt construction, tool selection, retrieval, generated graph queries, and answer generation |
| 4. Ingestion and persistence | `utils/`, `database/` | Document conversion/chunking, spreadsheet processing, graph operations, history, analytics, and corrected answers |
| 5. External infrastructure | `llm/`, Google Drive utilities, Docker files | Model clients, Neo4j connections, original file storage, and runtime configuration |

### User-facing chat path

`app/page.tsx` → `chatService.streamMessage()` → `POST /chat/enhanced-rag-agent/sse` → `haui_rag_agent` → retrieval tools → answer events.

- `useSessionManager()` stores a UUID and creation time in localStorage. It replaces expired sessions on initialization after 24 hours. Its question-count increment function is currently a no-op.
- `sse_enhanced_agent()` runs LangGraph with the supplied session ID and emits start, content, tool-call, tool-result, completion, and error events.
- Streaming uses server-sent events over an HTTP POST response. The graph uses `stream_mode='updates'`, so this path emits node updates rather than demonstrating token-by-token output.
- `app/embed/chat/page.tsx` uses a separate embed service and the shared session hook. A JavaScript widget is provided under `public/embed/`.
- Other chat routes include `/chat/docs-rag-agent`, `/chat/enhanced-rag-agent`, `/chat/compare-agents`, and an additional `/stream` variant. They do not all follow identical execution paths.

### Agents and model roles

Two alternative agent implementations exist; they are not a supervisor and a worker team.

| Component | Implementation |
| --- | --- |
| Original agent | `rag_agent.py`: LangChain `AgentExecutor`, tool binding, and `RunnableWithMessageHistory` |
| Enhanced agent | `enhanced_rag_agent.py`: LangGraph with `llm` and `action` nodes; `should_continue()` loops while tool calls remain |
| Tool execution | `take_action()` invokes tools sequentially in the process and returns tool messages |
| Conversation model | `get_model_function()`: OpenAI `ChatOpenAI`, selected by `AGENT_MODEL`, temperature 0 |
| Embeddings | `get_embedding_function()`: `OpenAIEmbeddings`, selected by `OPENAI_EMBEDDING` |
| Graph-query model | `get_cypher_model_function()`: hardcoded `gpt-4o-mini`, temperature 0.3 |
| Test model factory | `generate_test_model_function()`: selected by `TEST_MODEL`; not the main chat path |

There are three production model roles visible here: conversation/tool selection, embedding, and Cypher generation. Roles do not imply three distinct model identities or deployments. Private environment values were not inspected. Anthropic is listed as a dependency, but the traced agent factories use OpenAI.

The enhanced agent exposes tools for general document retrieval, corrected-answer retrieval, book graph search, general graph search, and library contact information. OPAC search wrappers exist but are commented out of both active tool lists. Prompts, contact information, graph examples, and presentation text are tied to HaUI and Vietnamese library usage.

### Retrieval and data model

- `semantic_search_chunk_chain.py` builds a Neo4j hybrid vector/keyword index over `Chunk.text`, with vectors in `content_embedding`. Its retriever requests two results with a 0.5 score threshold. Results include file links, filenames, and page metadata.
- `cypher_search.py` uses `GraphCypherQAChain` to translate questions into graph queries. It returns direct query results and enables `allow_dangerous_requests=True`.
- `resolved_wrong_message_search.py` searches administrator-corrected responses, with semantic and keyword search paths. This is retrieval of corrected knowledge, not demonstrated model fine-tuning.
- Document structure: `File → HAS_CHUNK → Chunk`, with adjacent chunks connected by `HAS_NEXT` and `HAS_PREV`.
- Academic catalog: `Major → HAS_SUBJECT → Subject → HAS_DOCUMENT → Document`; majors also link to `ExcelFile` records.
- History uses Neo4j chat-history facilities. Separate database modules implement message/session analytics and `WrongMessage` records.
- `Neo4jClient` combines file, Excel, message, analytics, academic-query, and wrong-message operation classes through multiple inheritance. Both async database operations and separate synchronous LangChain graph clients exist.

### Ingestion and administration

`routers/files.py:create_file()` validates the upload, saves it temporarily, uploads the original to Google Drive, converts it through Docling to Markdown, chunks the Markdown, and calls `create_file_with_chunks()` to save graph records.

`load_markdown.py` groups content by headings, splits long sections around 2,500 characters with 500-character overlap, and merges small chunks using a 300-character threshold. A separate PDF loader exists, but the traced upload route uses Docling and the Markdown loader.

The backend also supports web-content ingestion, editing chunk text and document metadata, deletion, spreadsheet validation/import, book editing, bulk editing, and export. Large spreadsheet processing can use FastAPI background tasks, with progress stored in an in-memory dictionary. This is not a durable job queue.

Response-quality management detects problematic answers and allows administrators to record corrections. `_check_and_log_problematic_response()` is called from the ordinary answer routes; the primary SSE route does not call it, so automatic logging coverage differs by route.

### Runtime and configuration

| Area | Observed configuration |
| --- | --- |
| Frontend | Next.js `^15.0.0`, React `^18.3.0`, TypeScript `4.9.5`, Chakra UI; declared ranges are not a runtime version audit |
| Backend | FastAPI `0.115.6`, LangChain `0.3.11`, Neo4j driver `5.27.0`; LangGraph and some other requirements are unpinned |
| Containers | Python `3.9-slim` and Node `18-alpine`; Compose runs development commands with mounted source and backend reload |
| Ports | Frontend 3000; API 8000 |
| External services | Neo4j and Google Drive are not provisioned by Compose; OpenAI access is required by the traced initialization path |
| AI environment names | `OPENAI_API_KEY`, `AGENT_MODEL`, `OPENAI_EMBEDDING`; `TEST_MODEL` for the test factory |
| Database names | `NEO4J_URI`, `NEO4J_PASSWORD`; application settings use `NEO4J_USER`, while graph setup and validation use `NEO4J_USERNAME` |
| Drive names | Validation requires `GOOGLE_APPLICATION_CREDENTIALS`; the storage utility uses `GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE` and `GOOGLE_DRIVE_FOLDER_ID` |
| Access and routing | `JWT_SECRET_KEY`, `NEXT_PUBLIC_API_URL`; URL helpers also contain deployment-specific fallback addresses |
| Monitoring | `main.py` activates `health_simple.py` and a daily background database-count check |

### Material limitations to resolve before reuse

These findings come from code inspection; their runtime consequences have not been tested.

1. **History consistency:** the original agent wraps execution with message-history persistence. The enhanced agent reads history, but its graph and SSE route do not show corresponding history writes or a persistent graph checkpointer. Both agents check a ten-question limit against stored history, so the same limit cannot be assumed to work consistently.
2. **Embedding freshness:** document creation and chunk editing write text without an explicit embedding-refresh call. Index initialization occurs in imported retrieval modules. Retrieval freshness after uploads and edits needs an explicit design and verification.
3. **Startup coupling:** graph clients, model clients, and vector setup are created during imports. A review must avoid importing application modules merely to inspect them, because initialization may contact external services.
4. **Upload concurrency:** the document route writes all converted content to `/tmp/tmp_docling.md`, allowing simultaneous uploads to interfere. Temporary upload paths also use supplied filenames.
5. **Access configuration:** `auth.py` contains a fixed administrator account and a fallback JWT secret. The frontend middleware checks cookie presence; backend JWT dependencies protect many administrative routes. This is not an implemented YZU identity/role system.
6. **Graph execution boundary:** generated Cypher is allowed to execute with the configured database credentials. Read-only permissions and bounded queries need consideration if this capability is retained.
7. **Route inconsistency:** the non-streaming enhanced wrapper passes the synchronous `.stream()` result to `wait_for()` even though its caller expects a response dictionary. The other `/stream` variant omits the session configuration required by `call_llm()`. These paths need correction or omission if selected.
8. **Configuration drift:** database and Drive environment names disagree across modules; API URL logic is duplicated; development Compose is not a production deployment definition.
9. **Documentation/test drift:** the README describes WebSockets and a frontend `npm run test`, but the traced chat uses SSE and `package.json` has no test script. Python comparison and streaming scripts exist, but were not executed and do not establish regression coverage. The README's Python 3.10+ statement also differs from the Docker base.

## YZU version one: confirmed product scope

- Project destination: `/Users/admin/Working/2026-S2/YZU Student Assistant`. Run locally on the user's Mac first. The user will provision Neo4j and provide connection settings and other secrets through an untracked local `.env`. Credential files must also remain untracked.
- Audience: YZU students seeking university information, policies, scholarships, and course explanations or lists.
- Public student chat without login. One authenticated administrator uploads, updates, and deletes documents.
- English source documents, interface, and answers first. Documentation, comments, and docstrings are English. Chinese support is deferred.
- Manual PDF uploads and individual YZU webpage URL submissions. Automatic discovery, crawling, and scheduled refresh are deferred.
- Uploaded PDF originals are stored in Google Drive with publicly readable links. HTML references point to the original YZU webpage. Answers provide a reference list so students can read the complete sources used.
- Retain chat/Markdown rendering, SSE, document ingestion and administration, Google Drive integration, and Neo4j document retrieval.
- Use simplified LangGraph for version-one orchestration; the user selected this over switching to OpenAI Agents SDK now.
- Course information uses the same retrieval path as other documents. Structured course filters, academic catalog entities, and Excel catalog management are outside version one.
- Stabilize this system before migrating to MCP client/server architecture and advanced agent management. The user subsequently authorized Step 1 implementation; later steps require their own confirmation.

## Proposed code selection — for design discussion

The feature scope above is confirmed. The file mapping below is a proposal, not authorization to copy files or a completed migration plan. Reuse selected functions and components, not whole directories with unrelated dependencies.

| Source implementation | Proposed destination | Treatment and purpose |
| --- | --- | --- |
| `app/page.tsx`, Markdown/message components | Frontend chat page and `components/chat/` | Reuse rendering and interaction; replace HaUI content and retain only used dependencies |
| `chatService.streamMessage()`, `useSessionManager()` | `lib/chat.ts`, `hooks/useChatSession.ts` | Adapt one SSE contract and session behavior; do not retain the obsolete no-op question counter |
| Document/upload pages and file/document services | `app/admin/documents/`, `lib/documents.ts` | Reuse useful forms/list/detail UI; expose public source links and ingestion failures |
| `routers/chat.py:sse_enhanced_agent()` | `api/chat.py` | Rewrite the route around one workflow; normalize completion/errors/references and preserve session context |
| `routers/files.py:create_file()`, `create_web_content()` | `api/documents.py`, `services/ingestion.py` | Split HTTP handling from ingestion; isolate temporary files and handle Drive/index consistency |
| `load_markdown.py` chunking functions; HTML extraction | `ingestion/` | Reuse parsing/chunking selectively and preserve real page/section metadata; never invent page numbers |
| `upload_file_to_drive()`, `delete_file_from_drive()` | `storage/drive.py` | Adapt file storage and public reference permissions; do not copy source credentials |
| File CRUD and chunk operations | `storage/documents.py` | Retain required graph operations; explicitly refresh embeddings on content changes and remove deleted content from retrieval |
| `get_chunk_retriever()` and hybrid index configuration | `services/retrieval.py` | Retain Neo4j retrieval; make result limits/thresholds configurable and remove import-time provisioning |
| `enhanced_rag_agent.py` workflow | `services/chat.py` | Retain LangGraph and simplify to document retrieval and cited answers; remove library tools and repair history/event handling |
| `get_model_function()`, `get_embedding_function()` | `models.py` | Centralize model configuration and lifecycle; keep secrets server-side |
| Existing auth/login | `auth.py`, `api/auth.py`, frontend login | Reuse UI selectively; replace hardcoded credentials and validate admin access on every management endpoint |

Omit from the proposed initial migration: the original agent and comparison routes; catalog/book/Excel modules; generated-Cypher chains and their model factory; HaUI OPAC/contact tools; embedded widget; answer-correction agents/UI; analytics dashboards; archived backups; deployment-specific scripts and URLs. A minimal health endpoint can be retained for operating the selected services. Omission means not copying into YZU, not deleting from HaUI-library.

## Proposed folder structure — not scaffolded

Four logical application layers: presentation, HTTP API/access, application workflows, and storage/external integrations. They run as one frontend and one backend, not separate services for each layer. Parsing and model factories support those workflows.

Two AI model roles initially: answer generation and embeddings. No Cypher-generation model or independent reviewer/retrieval agents in version one. Exact model identities remain open.

```text
YZU Student Assistant/
├── AGENTS.md
├── ARCHITECTURE.md
├── README.md
├── compose.yaml
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── login/page.tsx
│   │   └── admin/documents/
│   │       ├── page.tsx
│   │       └── [id]/page.tsx
│   ├── components/
│   │   ├── chat/                  # Messages, Markdown, references
│   │   └── documents/             # Upload, URL input, document list
│   ├── hooks/useChatSession.ts
│   ├── lib/                       # Shared HTTP client, chat, documents, auth
│   ├── public/
│   ├── tests/
│   ├── package.json
│   └── .env.example
└── backend/
    ├── app/
    │   ├── main.py                # Startup/shutdown, routes, dependencies
    │   ├── config.py              # Validated environment configuration
    │   ├── auth.py                # Single-admin authentication
    │   ├── schemas.py             # Requests, references, retrieval results
    │   ├── models.py              # Chat and embedding model factories
    │   ├── api/                   # chat.py, documents.py, auth.py, health.py
    │   ├── services/
    │   │   ├── chat.py            # Chosen workflow and grounded answer prompt
    │   │   ├── retrieval.py       # Search returning passages + source metadata
    │   │   └── ingestion.py       # Import, replace, reindex, delete workflow
    │   ├── ingestion/             # pdf.py, html.py, chunking.py
    │   └── storage/               # neo4j.py, documents.py, drive.py, sessions.py
    ├── tests/
    ├── requirements.txt
    └── .env.example
```

This is a design sketch: create files only when they have a required responsibility. Avoid generic repository interfaces, plugin registries, empty future-agent folders, or parallel framework implementations. Ingestion and retrieval exchange plain source-aware records with chat orchestration so a later framework change can be limited, without building a speculative abstraction layer.

### Selected framework: simplified LangGraph

The user selected simplified LangGraph for version one. Repair history, initialization, and event handling while removing unrelated library tools. OpenAI Agents SDK is not an initial dependency or migration task. Its possible future adoption is not required by the later MCP transition.

Proposed minimal workflow: request and session context → retrieve relevant passages → generate an English answer with source references → complete. If retrieval returns insufficient evidence, report the limitation rather than inventing an answer. No specialist agents, autonomous search-retry loop, or intent-based delegation in this version.

`services/chat.py` owns graph state and orchestration; `services/retrieval.py` returns passages with document IDs, source links, and page/section metadata. `api/chat.py` adapts workflow output into SSE events, and `storage/sessions.py` owns session persistence. References must resolve to retrieved sources, not model-invented URLs. Retrieval handling of conversational follow-ups must be specified in the migration plan and verified with multi-turn questions.

This workflow and the proposed file layout are design proposals; the framework selection is confirmed. The choice reduces migration scope and does not imply better answer quality than another framework.

The [official Agents SDK overview](https://developers.openai.com/api/docs/guides/agents/sdk) describes an application-owned runtime with tools, streaming/state capabilities, and MCP integration. Its [orchestration guide](https://developers.openai.com/api/docs/guides/agents/orchestration) distinguishes specialists used as tools under a manager from handoffs that transfer conversation ownership. The manager-owned pattern matches the user's later workflow. SDK documentation was checked during this discussion; exact APIs and dependencies must be rechecked when implementation starts.

### Proposed stability checks

- A PDF upload becomes searchable and its reference opens the complete original without sign-in.
- An individually submitted YZU webpage becomes searchable and retains its original URL.
- English policy, scholarship, and course answers cite passages that support their claims; absent evidence produces an explicit limitation rather than invented details.
- Course lists are described as limited to the indexed source material unless completeness is established.
- Replacing a source updates searchable content; deleting it removes its chunks from new answers.
- Concurrent uploads remain isolated; failed imports do not appear successfully indexed.
- Chat streams have clear completion/error behavior and follow-up questions retain the intended session context without crossing student sessions.
- Public users can chat but cannot upload, modify, or delete knowledge sources.

These checks are proposed acceptance criteria, not passed tests. Session retention, file-size limits, initial corpus size, verified Neo4j connectivity, exact models, and reference test questions remain implementation-planning inputs. The initial runtime target is the user's local Mac.

## Later phase: MCP and advanced workflow

User-requested direction: intent routing/manager planning → retrieval specialist that normalizes terms and retries searches → reviewer that removes unrelated material and determines support → manager that refines the final answer and replies.

Proposed refinements, not yet approved: review passages with metadata rather than titles; have the reviewer return supporting evidence and explicit gaps; use a shared retrieval budget (three attempts suggested) and stop or clarify when evidence remains insufficient. Preserve references through final answer generation. Roles do not necessarily require separate model identities.

MCP capability exposure and specialist scheduling are separate design responsibilities. Choose transports, server boundaries, run status/cancellation, and retry policy after version one is stable. Do not add placeholder MCP or sub-agent code now. Crawling and Chinese support are also deferred; their order relative to this phase has not been chosen.

## Implementation checkpoints

See `IMPLEMENTATION_PLAN.md` for ten sequential implementation steps and their verification criteria. The user requires an explicit review and confirmation after each step. Step 1 is approved. Step 2 configuration is in progress; live verification and Drive setup remain pending. Secret values belong in untracked local configuration; committed examples contain placeholders only. The plan uses local Python/Node processes initially; the earlier `compose.yaml` sketch is optional and is not an initial deliverable.

## First milestone sequence

The user selected Steps 1 → 2 → 3 → 4 → 7 → 8 → 9 to reach a working PDF-based chat first. Initial PDF uploads use authenticated API documentation. Manual HTML ingestion and the full document-management UI remain in the agreed scope but are deferred until after the chat trial. Focused checks and a full PDF-to-chat demonstration are required before milestone acceptance; broad handover follows later. Stop after every step for explicit user confirmation.

## Implemented Step 1 — corrected to reuse the HaUI style

The user rejected the newly designed landing page and required reuse of the previous project's actual code/style. That landing-page design has been removed. The user has now approved this Step 1 interface and authorized Step 2.

| New file/function | Source and purpose |
| --- | --- |
| `frontend/app/page.tsx:Chat()` | Adapted from HaUI `app/page.tsx` and root layout: greeting bubble, 300px desktop sidebar allocation, scrollable content, faded background, and rounded bottom composer |
| `frontend/app/AppWrappers.tsx:AppWrappers()` | Adapted source Chakra provider, without unrelated auth/API state |
| `frontend/components/sidebar/SidebarContent.tsx` | Source sidebar content structure, button spacing/dividers and shadows; English YZU questions fill the input |
| `frontend/components/navbar/Navbar.tsx` | Source floating toolbar and mobile drawer structure, with its menu and light/dark theme control |
| `frontend/theme/styles.ts` | Direct copy of the source global palette and body styling |
| `frontend/theme/button.ts` | Original primary-button variant extracted from source button styles |
| `frontend/theme/theme.ts` | Combines reused styles and sets the source font and initial light theme |
| `frontend/app/globals.css` | Direct copy of source `src/styles/App.css` |
| `frontend/public/img/` | Original chat background and library logo/avatar images; branding choice pending |
| `frontend/LICENSE` | Source Horizon UI license retained for reused material |
| `backend/app/main.py`, `api/health.py:get_health()` | Step 1 API foundation unchanged; liveness does not require external services |

The reused layout is adapted to the current Next.js server/client boundary. Unrelated admin routing, browser API-key storage, library endpoints, and live chat logic are not copied. The Send button is disabled and the page explicitly says chat is not available yet. No substitute logo or new visual design was introduced; the original HaUI assets remain until the user chooses their treatment.

Pinned core versions remain Next.js 16.3.5, React 19.3.0, TypeScript 5.9.3, FastAPI 0.141.1, and Uvicorn 0.53.0. The visual correction adds Chakra UI 2.10.7 (the source version), Chakra theme tools 2.2.9, Emotion React 11.14.0, Emotion Styled 11.14.1, Framer Motion 12.43.0, and React Icons 5.7.0. The npm lockfile records the resolved graph. Runtime remains local Node 20.17.0 and Python 3.13.5.

Verification after the correction: production build and TypeScript check passed; desktop at 1440px and mobile at 390px reviewed visually; no horizontal overflow at 390px; FAQ selection fills the composer; mobile drawer opens and closes after selection; original light/dark control works; no captured browser console warnings/errors. Original theme/styles/assets were compared byte-for-byte with their source copies. Backend behavior was not changed.

The earlier plain-CSS landing-page design and its proposed deferral of Chakra are superseded by this correction. Only the interface shell is ready, not chat functionality. `README.md` retains local startup instructions. The user subsequently approved Step 1 and authorized Step 2.

## User-supplied YZU logo

The user supplied and requested the YZU logo. `Chat()` now uses `frontend/public/img/logo/yzu-logo.png` for the assistant avatar and decorative background; `SidebarContent()` uses the same asset for the sidebar/mobile drawer. The source image is copied without pixel changes. Contained sizing preserves the circular seal: 80px sidebar logo, existing 40px avatar, and a 400px background limited by the viewport. This resolves the previously pending logo choice and supersedes the temporary HaUI-logo notes above. The HaUI-derived colors and layout remain.

## Step 2 implementation in progress

The application boundaries remain frontend presentation, backend HTTP API, application services/model integration, and storage adapters. No agent graph, new AI role, MCP server, or specialist agent was added. The two model roles remain chat and embeddings, both selected in backend configuration.

| File/function | Responsibility and reuse |
| --- | --- |
| `app/config.py:load_settings()` | Consolidates HaUI dotenv configuration into one backend file, preserves environment overrides, and reports names without values |
| `app/models.py:create_models()` | Adapts HaUI `ChatOpenAI` and `OpenAIEmbeddings`; removes stdout callbacks and import-time configuration loading |
| `app/models.py:check_models()` | Short startup chat/embedding checks; output is discarded |
| `app/storage/neo4j.py:create_driver()` | Reuses HaUI async Neo4j approach, with no fallback password |
| `app/storage/neo4j.py:check_database()` | Checks connectivity and selected-database read access using `RETURN 1` |
| `app/connections.py:lifespan()` | Owns HTTP transports/driver, performs startup checks, retains successful clients on app state, closes resources even after partial failure |
| `app/api/health.py:get_readiness()` | HTTP 503 until all startup checks pass; safe cached status, no repeated model requests |
| `frontend/lib/api.ts` | Public API address for later chat integration; no secrets or interface changes |

Backend dependencies added: LangChain OpenAI 1.6.2, Neo4j 6.3.0, python-dotenv 1.2.3, HTTPX 0.28.1, and pytest 9.1.1. The single `requirements.txt` pins the direct application and test dependencies. Clients are created during lifespan, not module import. Startup checks are snapshots, not continuous monitoring, and each configured startup uses a small amount of OpenAI API quota.

Drive integration is deliberately pending the user's authentication choice. Service accounts cannot own files and require Shared Drive storage or user delegation; see the [official Google Drive guide](https://developers.google.com/workspace/drive/api/guides/about-shareddrives). Folder access alone will not establish that public reference creation works. Actual public-link verification remains required before Step 2 completion.

OpenAI configuration was checked against [OpenAI Docs](https://developers.openai.com/api/docs/quickstart) and the [embedding guide](https://developers.openai.com/api/docs/guides/embeddings); reused client APIs were checked against [LangChain ChatOpenAI documentation](https://docs.langchain.com/oss/python/integrations/chat/openai). Six offline tests pass. No real external credentials have been verified. Work stays local on `codex/step-2-configuration`; the user controls publishing.

## Step 2 provider and OAuth update

This section supersedes the earlier pending authentication choice and `OPENAI_*` configuration notes. The user selected personal Google Drive via OAuth and Gemini's OpenAI-compatible endpoint. `create_models()` passes the required `GEMINI_BASE_URL` and `GEMINI_API_KEY` to both LangChain clients. Chat uses `GEMINI_CHAT_MODEL_1`; embeddings use `GEMINI_EMBEDDING_MODEL` and raw text, avoiding OpenAI token IDs. `GEMINI_CHAT_MODEL_2` is unused. No extra model role was introduced.

`storage/drive.py:authorize()` provides explicit local browser consent with the user's approved full Drive scope for the existing folder. `create_service()` loads/refreshes the ignored OAuth token; `check_folder()` checks destination type and upload capability. `check_public_reference()` creates a dedicated test file, shares it, verifies anonymous content access, then deletes it in `finally`. Startup never launches consent or creates public probe files. `lifespan()` owns and closes the Google API client alongside the Neo4j and model transports. `/ready` reports connection readiness; the explicit CLI probe separately establishes public-reference support.

Google Drive OAuth dependencies are pinned in `requirements.txt`. The supplied OAuth credential is a Web client; the Google Cloud console must register `http://localhost:8080/`. A token has not yet been verified. Live Gemini chat, Gemini embeddings and Neo4j checks passed; 13 offline tests passed. User consent and the real Drive public-reference check remain required before completing Step 2. Setup and commands are documented in `README.md`.

## Step 2 verification checkpoint

This checkpoint supersedes the earlier pending OAuth notes. Personal Drive authorization, writable folder access, and anonymous reading of a newly created public probe passed; the probe was deleted. The restarted local API returned HTTP 200 from `/ready` with all three dependencies ready. One initial Gemini check failed transiently; subsequent individual model checks and startup passed. Thirteen offline tests pass. Corrected package imports in `app/models.py` and `tests/test_drive.py` match the documented backend startup directory. OAuth client credentials are outside the repository; the local token is ignored and untracked. Step 2 awaits user approval; Step 3 has not started.

## Step 3 — Administrator authentication

Steps 1 and 2 are approved. This step adds no AI model role or application layer. The HaUI login UI, password verification, signed JWT, and HttpOnly cookie approach are reused. Backend validation and revocable sessions replace the source's hardcoded account, fallback secret, and browser localStorage token handling.

| File/function | Responsibility |
| --- | --- |
| `app/auth.py:AdminAuth.login()` | Verify the configured Argon2 password hash; issue a signed one-hour session |
| `app/auth.py:AdminAuth.validate()` | Check JWT signature, subject, required claims, expiry, and active session ID |
| `app/auth.py:require_admin()` | Backend dependency used by the entire admin router |
| `app/auth.py:protect_mutation()` | Require an explicit CSRF header and reject foreign browser origins |
| `app/auth.py:configure_password()` | Hidden local password prompt; save only hash and create a signing secret if needed |
| `app/api/auth.py:login()` / `logout()` | Set HttpOnly cookie; revoke session and delete cookie |
| `app/api/admin.py:get_session()` | Verify administrator access for the login page; future management routes use this guarded router |
| `app/schemas.py` | Login credentials and safe identity/expiry response |
| `frontend/lib/auth.ts` | Credentialed fetch calls, with no localStorage token or provider keys |
| `frontend/app/login/page.tsx:LoginPage()` | Original HaUI form layout, English text, signed-in state and logout |

`lifespan()` creates authentication state from the same backend settings and clears sessions on shutdown. Sessions are in-memory for the agreed single local process; restarting invalidates them. Authentication is not tied to Neo4j or model availability. CORS permits credentialed GET/POST from the two local frontend origins. All unsafe authenticated actions require an explicit CSRF header, including future upload APIs. `/docs` can exercise the cookie flow directly.

Dependencies: `pwdlib[argon2]==0.3.1` and `pyjwt==2.14.0`. Hashing follows the [FastAPI password/JWT guide](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/). Cookies are HTTP-local only in this milestone; public HTTPS and multiple API workers are not supported by this session configuration yet.

Verification: 28 offline backend tests passed; frontend production build and typecheck passed. User administrator setup and live browser login/logout are pending. Step 4 has not started.

Browser verification: the HaUI-derived form fits desktop and 390px mobile widths; password visibility and the missing-setup message work. The back link opens public chat without login. The hung local frontend process was restarted. Live administrator login/logout awaits the user choosing a local password.


## Step 4 — Implemented PDF ingestion

This checkpoint supersedes the pending Step 3 notes: the user confirmed administrator authentication is complete and authorized Step 4. The four planned YZU application layers and two remote model roles remain unchanged. Docling's local layout/OCR/table models support PDF extraction; they are not additional conversational agents. No LangGraph workflow, retrieval endpoint, MCP server, or specialist agent is added in this step.

```text
Authenticated API: api/admin.py -> api/documents.py
  POST /admin/documents (multipart PDF, CSRF header)
    services/ingestion.py: IngestionService.ingest()
      isolated temporary PDF, size/type validation, SHA-256
      ingestion/pdf.py: extract_pdf() -> Docling Markdown per physical page
      ingestion/chunking.py: chunk_pages() -> text + heading path + page/index
      configured Gemini embeddings through GEMINI_BASE_URL (batches of 16)
      storage/documents.py: prepare_indexes()
      storage/drive.py: upload_pdf() -> publish_pdf() -> public original URL
      storage/documents.py: save_document() -> one Neo4j transaction
  GET /admin/documents/{document_id}
    get_document() -> source metadata and ordered chunks without vector arrays
```

Reuse follows HaUI's `create_file()` and heading-based Markdown splitter. The shared temporary Markdown filename and fake page-zero metadata were removed. The 2,500-character size and 500-character overlap are retained; splitting is bounded by physical pages and recognized Markdown headings. Short sections are not merged into unrelated headings. `heading_path` represents extracted Markdown headings, not a guaranteed legal/article hierarchy. Docling can reorder a title or classify article labels as list items. A sentence crossing pages is stored in separate chunks; retrieval quality and context expansion must be assessed in Step 7.

Neo4j uses a separate `YZUDocument -[:HAS_CHUNK]-> YZUChunk` namespace. Documents store UUID, filename, source type/URL, Drive ID, SHA-256, physical page count, chunk count, embedding model/dimensions, UTC creation time, and ready status. Chunks store text, heading path, page number, zero-based index, document/chunk IDs, source URL, and embedding. Unique ID constraints and the cosine `yzu_chunk_embedding` vector index are created explicitly on import, with the dimension checked before upload. Ready documents and all vectors are committed atomically. The supplied model returned 3,072 dimensions. Changing the embedding model requires a later explicit re-embedding/index migration; dimensions alone do not identify a compatible vector space.

`IngestionService` holds one lock for the shared Drive transport and completes in-flight work before removing temporary files if a request is cancelled. It validates embedding counts/dimensions and finite, nonzero vectors. Extraction, embedding, and index setup happen before Drive upload. Public permission is required for success. Database-write failures trigger compensation for that import alone; an uncertain database rollback retains the original rather than leaving stored references broken. Unresolved cleanup and ambiguous upload responses leave safe recovery metadata in ignored `backend/data/failed-imports/`. This local process has no crash-safe queue; a process crash can require manual recovery using the import ID stored in Drive app properties. Repeat uploads intentionally create separate documents.

Runtime additions are locked Docling 2.127.0, langchain-text-splitters 1.1.2, and python-multipart 0.0.32. Extraction runs in a worker thread, uses local cached model assets after first download, and rejects incomplete/no-text conversions. Limits are 20 MiB and 100 pages per PDF. No new secret variables are required. Admin routes keep the Step 3 cookie and CSRF guards; student chat preview remains public.

Verification: 49 offline tests passed, including authenticated upload/inspection, invalid vectors, isolated concurrent paths, source metadata, and failure compensation. The live sample yielded four pages, eleven chunks, and 3,072-dimensional vectors. Neo4j readback, ONLINE index, self-vector lookup, and anonymous original checksum passed. Detailed extraction observations are in `docs/STEP_4_VERIFICATION.md`. Await user acceptance before Step 7.


## Cross-page chunking correction

The user requested this ingestion correction before Step 7. It supersedes the Step 4 statement that physical pages are chunk boundaries. `chunk_pages()` now accumulates sections across pages, joins plain-text continuations at page breaks, and splits with paragraph/sentence preference and the existing size/overlap limits. Explicit Markdown headings still delimit sections. Character spans preserve physical source attribution through overlapping splits: `page_numbers` contains every contributing page; `page_number` remains the first. `get_document()` exposes both fields. No extra model or application layer is added.

Regression tests reproduce the original page-2/page-3 sentence split and cover repeated text, overlap, and heading/list boundaries. The scholarship sample's new embeddings and chunks replaced its old chunks in one Neo4j transaction, retaining its document ID and Drive original. This was a targeted repair, not a general replacement endpoint. Docling's title order and imperfect heading labels are unchanged. Very long sentences can still exceed the size cap and require smaller splits; lowercase-continuation detection is deliberately limited to the current English corpus.

## Step 7 — Implemented retrieval and source records

Step 7 is complete and accepted by the user. `storage/search.py` owns parameterized Neo4j vector, Lucene full-text, and neighboring-chunk queries; only ready documents are searchable. `services/retrieval.py` exposes independent semantic and keyword search, combines candidates with reciprocal rank fusion, asks `GEMINI_CHAT_MODEL_2` to return a validated subset/order, and falls back to RRF order on missing configuration, timeouts, provider errors, or invalid IDs. Selected evidence and same-document neighbors retain source URLs and full `page_numbers` provenance within a bounded character budget.

Authenticated FastAPI inspection routes are available at `POST /admin/search/semantic`, `/admin/search/keyword`, and `/admin/search`. Search results are evidence candidates, not answer-confidence judgments; evidence sufficiency, conversational query preparation, and grounded answer generation remain Step 8 responsibilities. Safe Step 7 live-search artifacts are retained under ignored `backend/data/step7/`. The user performs future verification runs from commands supplied by the assistant.

## Step 8 — Simplified three-node LangGraph agent

The user replaced the earlier design with START → rewrite_query → retrieve → answer → END. `services/chat.py:ChatService` compiles this graph with `Neo4jSaver`. There is no evidence-evaluation, policy-reasoning, clarification, interrupt, or autonomous retry node. Action requests are still reported as deferred.

`rewrite_query()` reads bounded recent completed history and prepares a standalone query only for contextual follow-ups. `retrieve_documents()` reuses Step 7. `generate_answer()` validates source IDs, builds references from application-owned metadata, and saves the completed turn idempotently. Document evidence always takes priority. Only when document retrieval is empty may the answer node call `get_web_search` and `get_office_contact` from `services/fallback_tools.py`.

Web fallback sends at most one billable Gemini native Google Search grounding request and keeps at most five cited HTTPS results from YZU domains. The contact tool returns the maintained Office of Global Affairs record only for relevant scholarship, admission, exchange, or contact intents. Either tool may fail without aborting the other; if neither returns evidence, the answer explicitly reports insufficient information. These are ordinary services inside the answer node, not MCP tools or specialist agents. ID validation establishes provenance, not factual entailment. Language tasks and web grounding use existing Gemini model 1; embeddings and reranking retain their Step 7 roles.

`storage/checkpoints.py` implements asynchronous checkpoint lookup, listing, snapshot writes, pending writes, and thread deletion. Neo4j stores typed serialized snapshots under unique keys. `storage/sessions.py` stores completed turns as `YZUChatSession -[:HAS_TURN]-> YZUChatTurn`, assigns a monotonically increasing per-session sequence, and retrieves the newest six exchanges within 12,000 characters. A session-existence query avoids first-use warnings for nonexistent turn properties and relationships. Checkpoint thread IDs carry a graph-version prefix, preventing unfinished snapshots from the superseded graph from resuming while completed conversation history remains available. Snapshots and turns persist until session reset. `ChatService.reset()` removes only the selected session's turn/checkpoint nodes and returns a new UUID.

`connections.py:lifespan()` creates the checkpoint constraints, fallback tools, and chat service using managed clients. LangGraph 1.2.11 is pinned. `app.chat_cli` gives the user a local interface for questions, retry, and disposable-session reset. Local session locks assume one process; Step 9 must enforce browser ownership before exposing session access.

Status: the revised implementation passed 18 focused tests and 66 broader backend tests excluding an unrelated stale PDF-ingestion import. Live document-first answering, contextual follow-up, and session reset passed. Gemini returned HTTP 429 during the live web-fallback probe; the graph correctly returned an evidence limitation. The user accepted Step 8 on 2026-09-15 and authorized frontend/SSE integration in Step 9.
