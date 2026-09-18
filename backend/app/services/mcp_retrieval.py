"""Call the independent YZU retrieval server through MCP over HTTP."""

from fastmcp import Client

from app.schemas import CombinedSearchRequest, CombinedSearchResponse


class McpRetrievalClient:
    """Expose the retrieval interface expected by the conversation graph."""

    TOOL_NAME = "yzu_search_documents"

    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint

    async def check(self) -> None:
        """Verify that the configured server exposes the required RAG tool."""
        try:
            async with Client(self.endpoint) as client:
                tools = await client.list_tools()
                if self.TOOL_NAME not in {tool.name for tool in tools}:
                    raise RuntimeError("Required MCP retrieval tool is unavailable.")
        except Exception as error:
            raise RuntimeError("MCP retrieval server is unavailable.") from error

    async def search(
            self, request: CombinedSearchRequest) -> CombinedSearchResponse:
        """Call the read-only RAG tool and validate its structured response."""
        try:
            async with Client(self.endpoint) as client:
                result = await client.call_tool(
                    self.TOOL_NAME,
                    {"request": request.model_dump(mode="json")},
                    timeout=45.0,
                )
        except Exception as error:
            raise RuntimeError("MCP document retrieval failed.") from error
        if result.structured_content is None:
            raise RuntimeError("MCP document retrieval returned no structured data.")
        return CombinedSearchResponse.model_validate(result.structured_content)
