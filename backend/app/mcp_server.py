"""Independent FastMCP server for YZU hybrid document retrieval."""

import argparse
from contextlib import AsyncExitStack, asynccontextmanager

from fastmcp import Context, FastMCP
import httpx

from app.config import Settings, load_settings
from app.models import check_embeddings, create_embeddings, create_reranker
from app.schemas import CombinedSearchRequest, CombinedSearchResponse
from app.services.retrieval import RetrievalService
from app.storage.neo4j import check_database, create_driver

MCP_SERVER_NAME = "yzu_knowledge_mcp"
MCP_TOOL_NAME = "yzu_search_documents"


def _require_server_settings(settings: Settings) -> None:
    """Fail startup with variable names only, never credential values."""
    names = (
        "GEMINI_API_KEY",
        "GEMINI_BASE_URL",
        "GEMINI_EMBEDDING_MODEL",
        "NEO4J_URI",
        "NEO4J_USERNAME",
        "NEO4J_PASSWORD",
        "NEO4J_DATABASE",
    )
    missing = [name for name in names
               if not (settings.values.get(name) or "").strip()]
    if missing:
        raise RuntimeError(
            "Missing MCP server configuration: " + ", ".join(missing))


@asynccontextmanager
async def retrieval_lifespan(_server):
    """Own the RAG server's Neo4j and Gemini clients."""
    settings = load_settings()
    _require_server_settings(settings)
    async with AsyncExitStack() as stack:
        driver = create_driver(settings)
        stack.push_async_callback(driver.close)
        await check_database(driver, settings.require("NEO4J_DATABASE"))

        http_client = stack.enter_context(httpx.Client(timeout=20))
        http_async_client = await stack.enter_async_context(
            httpx.AsyncClient(timeout=20))
        embeddings = create_embeddings(
            settings, http_client, http_async_client)
        await check_embeddings(embeddings)
        reranker = create_reranker(
            settings, http_client, http_async_client)

        yield {
            "retrieval": RetrievalService(
                settings, driver, embeddings, reranker),
        }


def create_mcp_server(lifespan=retrieval_lifespan) -> FastMCP:
    """Build the one-tool server; tests may inject an isolated lifespan."""
    server = FastMCP(
        name=MCP_SERVER_NAME,
        instructions=(
            "Search indexed YZU PDFs and webpages. Return only stored evidence "
            "and source metadata; do not answer beyond the retrieved content."
        ),
        lifespan=lifespan,
        mask_error_details=True,
    )

    @server.tool(
        name=MCP_TOOL_NAME,
        description=(
            "Search indexed YZU documents using semantic and keyword retrieval, "
            "rank fusion, optional reranking, and adjacent source context."
        ),
        annotations={
            "title": "Search YZU documents",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
        timeout=45.0,
    )
    async def yzu_search_documents(
            request: CombinedSearchRequest,
            context: Context) -> CombinedSearchResponse:
        """Return bounded, source-linked evidence for one student query.

        Use this tool for questions that may be answered by indexed YZU PDFs or
        webpages. The request controls result count, metadata filters, neighboring
        context, and the total context-character budget. It never modifies stored
        documents or conversation state.
        """
        retrieval = context.lifespan_context["retrieval"]
        return await retrieval.search(request)

    return server


mcp = create_mcp_server()


def main() -> None:
    """Run the local Streamable HTTP server on its dedicated port."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8001, type=int)
    arguments = parser.parse_args()
    try:
        mcp.run(
            transport="http",
            host=arguments.host,
            port=arguments.port,
            stateless_http=True,
        )
    except KeyboardInterrupt:
        # Ctrl+C is the documented local shutdown path.
        pass


if __name__ == "__main__":
    main()
