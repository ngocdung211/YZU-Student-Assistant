"""Verify the MCP tool contract and real Streamable HTTP client path."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastmcp import Client
from fastmcp.utilities.tests import run_server_async

from app.mcp_server import MCP_TOOL_NAME, create_mcp_server
from app.schemas import CombinedSearchRequest, CombinedSearchResponse
from app.services.mcp_retrieval import McpRetrievalClient


def empty_response(query: str) -> CombinedSearchResponse:
    """Return a valid structured response without external dependencies."""
    return CombinedSearchResponse(
        query=query,
        normalized_query=query,
        candidates=[],
        evidence=[],
        neighbors=[],
        rerank_applied=False,
        rerank_reason="no_candidates",
        status="no_candidates",
        context_characters=0,
        context_limited=False,
    )


def test_mcp_http_client_lists_and_calls_the_rag_tool():
    async def scenario():
        retrieval = SimpleNamespace(
            search=AsyncMock(return_value=empty_response("Scholarships")))

        @asynccontextmanager
        async def test_lifespan(_server):
            yield {"retrieval": retrieval}

        server = create_mcp_server(test_lifespan)
        async with run_server_async(server) as endpoint:
            async with Client(endpoint) as protocol_client:
                tools = await protocol_client.list_tools()
                assert [tool.name for tool in tools] == [MCP_TOOL_NAME]
                assert tools[0].annotations.read_only_hint is True

            client = McpRetrievalClient(endpoint)
            await client.check()
            result = await client.search(
                CombinedSearchRequest(query="Scholarships"))

        assert result.status == "no_candidates"
        request = retrieval.search.await_args.args[0]
        assert isinstance(request, CombinedSearchRequest)
        assert request.query == "Scholarships"

    asyncio.run(scenario())
