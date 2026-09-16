"""Controlled checks for Step 8 fallback tools."""

import asyncio
from unittest.mock import AsyncMock, Mock

from app.services.fallback_tools import FallbackTools


def make_tools(payload):
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = payload
    client = Mock()
    client.post = AsyncMock(return_value=response)
    return FallbackTools(client, "synthetic-key", "gemini-test"), client


def test_web_search_returns_only_provider_cited_evidence():
    async def scenario():
        tools, client = make_tools({
            "candidates": [{
                "content": {"parts": [{"text": "Official scholarship summary."}]},
                "groundingMetadata": {"groundingChunks": [
                    {"web": {"title": "YZU scholarships", "uri": "https://gao.yzu.edu.tw/scholarships"}},
                    {"web": {"title": "YZU admissions", "uri": "https://gao.yzu.edu.tw/admissions"}},
                    {"web": {"title": "Untrusted result", "uri": "https://example.org/not-yzu"}},
                ]},
            }],
        })

        results = await tools.get_web_search("doctoral scholarship")

        assert [item["source_id"] for item in results] == ["web:0", "web:1"]
        assert all(item["text"] == "Official scholarship summary." for item in results)
        request = client.post.await_args
        assert request.kwargs["headers"] == {"x-goog-api-key": "synthetic-key"}
        assert "site:yzu.edu.tw" in str(request.kwargs["json"])

    asyncio.run(scenario())


def test_web_search_discards_uncited_model_text():
    async def scenario():
        tools, _ = make_tools({
            "candidates": [{"content": {"parts": [{"text": "Uncited answer."}]}}],
        })

        assert await tools.get_web_search("question") == []

    asyncio.run(scenario())


def test_office_contact_is_returned_only_for_relevant_intent():
    async def scenario():
        tools, _ = make_tools({})

        contacts = await tools.get_office_contact(
            "Who should I email about an international scholarship?")

        assert contacts[0]["source_id"] == "office:global_affairs"
        assert contacts[0]["source_url"].startswith("https://gao.yzu.edu.tw/")
        assert await tools.get_office_contact("What time is sunset?") == []

    asyncio.run(scenario())
