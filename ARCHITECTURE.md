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
    ├── pyproject.toml
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

See `IMPLEMENTATION_PLAN.md` for ten sequential implementation steps and their verification criteria. The user requires an explicit review and confirmation after each step. Step 1 is implemented and verified, awaiting user review; no later step has started. Secret values belong in untracked local configuration; committed examples contain placeholders only. The plan uses local Python/Node processes initially; the earlier `compose.yaml` sketch is optional and is not an initial deliverable.

## First milestone sequence

The user selected Steps 1 → 2 → 3 → 4 → 7 → 8 → 9 to reach a working PDF-based chat first. Initial PDF uploads use authenticated API documentation. Manual HTML ingestion and the full document-management UI remain in the agreed scope but are deferred until after the chat trial. Focused checks and a full PDF-to-chat demonstration are required before milestone acceptance; broad handover follows later. Stop after every step for explicit user confirmation.

## Implemented Step 1 — corrected to reuse the HaUI style

The user rejected the newly designed landing page and required reuse of the previous project's actual code/style. That landing-page design has been removed. This is still Step 1, awaiting review; no later implementation step is authorized.

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

The earlier plain-CSS landing-page design and its proposed deferral of Chakra are superseded by this correction. Only the interface shell is ready, not chat functionality. `README.md` retains local startup instructions. User review is required before proceeding to Step 2.

## User-supplied YZU logo

The user supplied and requested the YZU logo. `Chat()` now uses `frontend/public/img/logo/yzu-logo.png` for the assistant avatar and decorative background; `SidebarContent()` uses the same asset for the sidebar/mobile drawer. The source image is copied without pixel changes. Contained sizing preserves the circular seal: 80px sidebar logo, existing 40px avatar, and a 400px background limited by the viewport. This resolves the previously pending logo choice and supersedes the temporary HaUI-logo notes above. The HaUI-derived colors and layout remain.
