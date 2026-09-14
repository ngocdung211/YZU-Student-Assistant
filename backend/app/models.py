"""Create the two LangChain model roles reused from HaUI."""

import httpx
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from backend.app.config import Settings


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
    embeddings = OpenAIEmbeddings(
        model=settings.require("GEMINI_EMBEDDING_MODEL"),
        check_embedding_ctx_length=False, **shared_options)
    return chat, embeddings


async def check_models(chat: ChatOpenAI, embeddings: OpenAIEmbeddings) -> None:
    """Make two small billable startup checks without printing their output."""
    await chat.ainvoke("Connection check. Reply only with OK.", max_tokens=16)
    vector = await embeddings.aembed_query("YZU connection check")
    if not vector:
        raise RuntimeError("Embedding check returned no vector")
