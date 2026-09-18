"""Create the two LangChain model roles reused from HaUI."""

import httpx
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import Settings


def create_models(settings: Settings, http_client: httpx.Client,
                  http_async_client: httpx.AsyncClient
                  ) -> tuple[ChatOpenAI, OpenAIEmbeddings]:
    """Build chat and embedding clients with application-owned HTTP transports."""
    shared_options = {
        "api_key": settings.require("GEMINI_API_KEY"),
        "base_url": settings.require("GEMINI_BASE_URL"),
        "http_client": http_client,
        "http_async_client": http_async_client,
        "max_retries": 0,
        "timeout": 20,
    }
    # No stdout streaming callback: student content must not become console logs.
    chat = ChatOpenAI(model=settings.require("GEMINI_CHAT_MODEL_1"),
                      streaming=True, use_responses_api=False, **shared_options)
    embeddings = create_embeddings(settings, http_client, http_async_client)
    return chat, embeddings


def create_embeddings(settings: Settings, http_client: httpx.Client,
                      http_async_client: httpx.AsyncClient) -> OpenAIEmbeddings:
    """Build the embedding client required by the independent RAG server."""
    return OpenAIEmbeddings(
        model=settings.require("GEMINI_EMBEDDING_MODEL"),
        api_key=settings.require("GEMINI_API_KEY"),
        base_url=settings.require("GEMINI_BASE_URL"),
        http_client=http_client,
        http_async_client=http_async_client,
        check_embedding_ctx_length=False,
        max_retries=0,
        timeout=20,
    )


async def check_models(chat: ChatOpenAI, embeddings: OpenAIEmbeddings) -> None:
    """Make two small billable startup checks without printing their output."""
    await chat.ainvoke("Connection check. Reply only with OK.", max_tokens=16)
    await check_embeddings(embeddings)


async def check_embeddings(embeddings: OpenAIEmbeddings) -> None:
    """Verify the embedding provider without printing its response."""
    vector = await embeddings.aembed_query("YZU connection check")
    if not vector:
        raise RuntimeError("Embedding check returned no vector")



def create_reranker(settings: Settings, http_client: httpx.Client,
                    http_async_client: httpx.AsyncClient):
    """Use model 2 only for reranking; missing configuration enables RRF fallback."""
    if not (settings.values.get("GEMINI_CHAT_MODEL_2") or "").strip():
        return None
    return ChatOpenAI(
        model=settings.require("GEMINI_CHAT_MODEL_2"),
        api_key=settings.require("GEMINI_API_KEY"),
        base_url=settings.require("GEMINI_BASE_URL"),
        http_client=http_client, http_async_client=http_async_client,
        streaming=False, use_responses_api=False, timeout=20, max_retries=0,
    ).bind(response_format={"type": "json_object"})
