"""Search behavior without real credentials, model calls, or a database."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from pydantic import ValidationError
from pwdlib import PasswordHash
import pytest

from app import connections
from app.config import Settings
from app.main import app
from app.schemas import Evidence, SearchRequest, CombinedSearchRequest
from app.services import retrieval
from app.services.retrieval import RetrievalService, merge_results, keyword_query


def passage(index, method="semantic", document="source", text=None):
    return Evidence(chunk_id=f"{document}:{index}", document_id=document,
                    title="Scholarships", text=text or f"Passage {index}",
                    source_url="https://drive.google.com/example", page_numbers=[2, 3],
                    chunk_index=index, scores={method: 0.8})


def test_rrf_deduplicates_and_combines_ranks():
    result = merge_results([passage(1), passage(2)], [passage(2, "keyword"), passage(3, "keyword")])
    assert [item.chunk_id for item in result] == ["source:2", "source:1", "source:3"]
    assert result[0].scores == {"semantic": 0.8, "keyword": 0.8}
    assert result[0].rrf_score == pytest.approx(1 / 62 + 1 / 61)


def test_keyword_query_treats_lucene_syntax_as_literal_terms():
    query = keyword_query('PhD OR *:* (title:scholarship)^9')
    assert "*" not in query and ":" not in query and "^" not in query
    assert '"PhD"' in query and '"OR"' in query
    assert keyword_query("?!") == ""


@pytest.mark.parametrize("payload", [{"query": "   "}, {"query": "a" * 1001},
                                     {"query": "test", "limit": 31},
                                     {"query": "test", "filters": {"year": 2025}}])
def test_search_validation(payload):
    with pytest.raises(ValidationError):
        SearchRequest(**payload)


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(retrieval.storage, "prepare_keyword_index", AsyncMock())
    monkeypatch.setattr(retrieval.storage, "semantic_search", AsyncMock(return_value=[passage(1), passage(2)]))
    monkeypatch.setattr(retrieval.storage, "keyword_search", AsyncMock(return_value=[passage(2, "keyword")]))
    monkeypatch.setattr(retrieval.storage, "get_neighbors", AsyncMock(return_value=[passage(0), passage(2), passage(3)]))
    return RetrievalService(Settings({"NEO4J_DATABASE": "test", "GEMINI_EMBEDDING_MODEL": "embedding"}),
                            object(), SimpleNamespace(aembed_query=AsyncMock(return_value=[0.1, 0.2])),
                            SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content='{"chunk_ids":["source:1"]}'))))


def test_keyword_does_not_call_embedding_or_reranker(service):
    result = asyncio.run(service.keyword_search(SearchRequest(query="scholarship")))
    assert len(result.results) == 1
    service.embeddings.aembed_query.assert_not_awaited()
    service.reranker.ainvoke.assert_not_awaited()


def test_combined_reranks_then_expands_unique_neighbors(service):
    result = asyncio.run(service.search(CombinedSearchRequest(query="  PhD  scholarship  ")))
    assert result.normalized_query == "PhD scholarship"
    assert result.rerank_applied
    assert [item.chunk_id for item in result.evidence] == ["source:1"]
    assert all(item.is_neighbor for item in result.neighbors)
    assert len({item.chunk_id for item in result.evidence + result.neighbors}) == len(result.evidence + result.neighbors)
    assert all(item.neighbor_of == ["source:1"] for item in result.neighbors)
    assert result.context_characters <= 20000


@pytest.mark.parametrize("response", ['not JSON', '{"chunk_ids":["fake"]}',
                                     '{"chunk_ids":["source:1","source:1"]}',
                                     '{"chunk_ids":[],"unexpected":true}'])
def test_invalid_rerank_falls_back_to_merged_rank(service, response):
    service.reranker.ainvoke.return_value.content = response
    result = asyncio.run(service.search(CombinedSearchRequest(query="scholarship", include_neighbors=False)))
    assert not result.rerank_applied and result.rerank_reason == "invalid_output"
    assert [item.chunk_id for item in result.evidence] == ["source:2", "source:1"]
    retrieval.storage.get_neighbors.assert_not_awaited()


@pytest.mark.parametrize("error", [TimeoutError(), RuntimeError("secret-provider-text")])
def test_provider_rerank_failure_is_safe_and_nonfatal(service, error):
    service.reranker.ainvoke.side_effect = error
    result = asyncio.run(service.search(CombinedSearchRequest(query="scholarship")))
    assert not result.rerank_applied
    assert "secret-provider" not in result.model_dump_json()
    assert result.evidence[0].chunk_id == "source:2"


def test_missing_reranker_and_irrelevant_candidates(service):
    service.reranker = None
    result = asyncio.run(service.search(CombinedSearchRequest(query="scholarship")))
    assert result.rerank_reason == "not_configured"
    service.reranker = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(content='{"chunk_ids":[]}')))
    result = asyncio.run(service.search(CombinedSearchRequest(query="absent course catalog")))
    assert result.rerank_applied and result.status == "no_relevant_candidates"
    assert not result.evidence and not result.neighbors


def test_no_candidates_does_not_call_reranker(service):
    retrieval.storage.semantic_search.return_value = []
    retrieval.storage.keyword_search.return_value = []
    result = asyncio.run(service.search(CombinedSearchRequest(query="absent")))
    assert result.status == "no_candidates"
    service.reranker.ainvoke.assert_not_awaited()


def test_neighbor_budget_prioritizes_selected_evidence(service):
    retrieval.storage.semantic_search.return_value = [passage(1, text="a" * 2500)]
    retrieval.storage.keyword_search.return_value = []
    retrieval.storage.get_neighbors.return_value = [passage(0, text="b" * 2500), passage(2, text="c" * 2500)]
    result = asyncio.run(service.search(CombinedSearchRequest(query="scholarship", context_char_budget=3000)))
    assert len(result.evidence) == 1 and result.neighbors == []
    assert result.context_characters == 2500 and result.context_limited


def test_search_api_requires_admin_and_exposes_all_modes(monkeypatch, service):
    settings = Settings({"ADMIN_USERNAME": "tester", "ADMIN_PASSWORD_HASH": PasswordHash.recommended().hash("synthetic-password"),
                         "AUTH_SECRET": "synthetic-search-signing-secret-only"})
    monkeypatch.setattr(connections, "load_settings", lambda: settings)
    with TestClient(app, base_url="http://localhost:8000") as client:
        app.state.retrieval = service
        paths = ["/admin/search", "/admin/search/semantic", "/admin/search/keyword"]
        headers = {"X-CSRF-Protection": "1"}
        for path in paths:
            assert client.post(path, headers=headers, json={"query": "PhD"}).status_code == 401
        assert client.post("/auth/token", headers=headers, json={"username": "tester", "password": "synthetic-password"}).status_code == 200
        for path in paths:
            assert client.post(path, json={"query": "PhD"}).status_code == 403
            response = client.post(path, headers=headers, json={"query": "PhD"})
            assert response.status_code == 200
            assert response.json()["normalized_query"] == "PhD"
        assert client.post(paths[0], headers=headers, json={"query": " "}).status_code == 422
        retrieval.storage.semantic_search.side_effect = RuntimeError("secret-provider-text")
        response = client.post(paths[1], headers=headers, json={"query": "PhD"})
        assert response.status_code == 503 and "secret-provider-text" not in response.text


def test_keyword_storage_binds_terms_and_filters_before_limit():
    from app.schemas import SearchFilters
    from app.storage import search

    calls = []

    class Records:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def run(self, query, **parameters):
            calls.append((query, parameters))
            return Records()

    driver = SimpleNamespace(session=lambda **kwargs: Session())
    asyncio.run(search.keyword_search(
        driver, "test", '"PhD"', SearchFilters(document_ids=["chosen"]), 4))

    query, parameters = calls[0]
    assert '"PhD"' not in query
    assert parameters["search_text"] == '"PhD"'
    assert parameters["document_ids"] == ["chosen"]
    assert query.index("d.status = 'ready'") < query.index("LIMIT $limit")


def test_neighbor_storage_groups_anchors_before_projection():
    from app.storage import search

    calls = []

    class Records:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def run(self, query, **parameters):
            calls.append((query, parameters))
            return Records()

    driver = SimpleNamespace(session=lambda **kwargs: Session())
    asyncio.run(search.get_neighbors(driver, "test", [passage(1)]))

    query, parameters = calls[0]
    assert "WITH d, c, collect(DISTINCT anchor.chunk_id) AS neighbor_of" in query
    assert parameters["selected"] == [{
        "chunk_id": "source:1", "document_id": "source", "chunk_index": 1}]
