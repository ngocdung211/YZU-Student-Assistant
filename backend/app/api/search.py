"""Authenticated search inspection endpoints for the local Swagger UI."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.schemas import (CombinedSearchRequest, CombinedSearchResponse,
                         SearchRequest, SearchResponse)
from app.services.retrieval import RetrievalService

router = APIRouter(prefix="/search", tags=["Search inspection"])


def get_retrieval(request: Request, response: Response) -> RetrievalService:
    """Require database setup without requiring Drive or administrator re-login."""
    response.headers["Cache-Control"] = "no-store"
    service = getattr(request.app.state, "retrieval", None)
    if service is None:
        raise HTTPException(503, "Search storage is unavailable. Check /ready and restart the API.")
    return service


@router.post("/semantic", response_model=SearchResponse, summary="Test semantic search only")
async def semantic_search(request: SearchRequest,
                          service: Annotated[RetrievalService, Depends(get_retrieval)]):
    """Return embedding-based candidates without reranking or neighbors."""
    try:
        return await service.semantic_search(request)
    except Exception:
        raise HTTPException(503, "Semantic search failed. Check Gemini embeddings and the Neo4j vector index.") from None


@router.post("/keyword", response_model=SearchResponse, summary="Test keyword search only")
async def keyword_search(request: SearchRequest,
                         service: Annotated[RetrievalService, Depends(get_retrieval)]):
    """Return literal keyword matches without invoking any model."""
    try:
        return await service.keyword_search(request)
    except Exception:
        raise HTTPException(503, "Keyword search failed. Check Neo4j connectivity and full-text index permissions.") from None


@router.post("", response_model=CombinedSearchResponse,
             summary="Test both searches, RRF, reranking, and neighboring context")
async def combined_search(request: CombinedSearchRequest,
                          service: Annotated[RetrievalService, Depends(get_retrieval)]):
    """Inspect retrieval evidence; this endpoint does not generate an answer."""
    try:
        return await service.search(request)
    except Exception:
        raise HTTPException(503, "Search failed. Check Gemini embeddings and Neo4j. Reranker failures normally use RRF fallback.") from None
