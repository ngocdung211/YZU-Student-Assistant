# YZU Student Assistant

## 1. Project Introduction

YZU Student Assistant with knowledge base contains more than 50 official PDF documents
collected from YZU websites. 

### Main interfaces

| Interface | Purpose |
|---|---|
| `POST /chat` | Ask a question and receive answer and reference events. |
| `POST /chat/new` | Delete the current conversation and start a new one. |
| `/admin/documents` | Upload and manage indexed PDF documents. |
| `yzu_search_documents` | Search the knowledge base through MCP. |

## 2. Data Ingestion Pipeline

Data preparation strongly affects retrieval quality. The ingestion pipeline is
therefore an important part of the system.

```text
Official YZU PDF
        |
        v
Docling converts the PDF into Markdown
        |
        v
Heading-aware Markdown chunking
        |
        v
Gemini creates a vector for every chunk
        |
        +--------------------------+
        |                          |
        v                          v
Original PDF in Google Drive   Document, chunks and vectors in Neo4j
        |                          |
        +---------- public source link ----------+
```

### Ingestion settings

| Setting | Current value |
|---|---|
| PDF conversion | Docling, running locally |
| Minimum chunk size | 700 characters |
| Maximum chunk size | 2,500 characters |
| Chunk overlap | 500 characters |
| Embedding model | `gemini-embedding-2` |
| Embedding dimensions | 3,072 |
| Document storage | Public Google Drive reference |
| Vector and metadata storage | Neo4j |

## 3. System Architecture

```text
Student
   |
   v
Next.js Frontend :3000
   |
   | HTTP + Server-Sent Events
   v
FastAPI Conversation Client :8000
   |
   | LangGraph: rewrite -> retrieve -> answer
   |
   | MCP Streamable HTTP
   v
FastMCP Retrieval Server :8001/mcp
   |
   +--> Gemini query embedding
   +--> Neo4j semantic vector search
   +--> Neo4j keyword search
   +--> Reciprocal-rank fusion
   +--> Optional reranking
   +--> Neighboring chunk expansion
```

## 4. Conversation Workflow

The LangGraph workflow contains only three application nodes:

```text
User question
    |
    v
1. Rewrite query
   Convert a contextual or ambiguous follow-up into a standalone query.
    |
    v
2. Retrieve documents
   Call the MCP tool and receive structured evidence.
    |
    v
3. Generate answer
   Answer from the evidence, validate selected sources and create references.
    |
    v
Answer event + separate References event
```

Inside the MCP server, retrieval combines semantic vector search and English
full-text keyword search. Reciprocal-rank fusion combines both result lists. An
optional Gemini reranker selects the strongest passages, and adjacent chunks can
be added to recover surrounding context.


## 5. Current Limitations

- Human in the loop: In the future have advance and dangerouse feature need human apporve before do

- Interuption: Stop and ask user before final anwser if needed

- Exception case: Handle exception case

- Memory management: Not optimize now

