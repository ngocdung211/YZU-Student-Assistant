"""Validated administrator request and response payloads."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class LoginCredentials(BaseModel):
    """Keep passwords out of model representations."""

    username: str
    password: SecretStr


class ChatQuestion(BaseModel):
    """One bounded public-chat question."""

    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=1000)

    @field_validator("question")
    @classmethod
    def trim_and_reject_blank(cls, value: str) -> str:
        """Do not spend a graph turn on an empty question."""
        value = value.strip()
        if not value:
            raise ValueError("Enter a question.")
        return value


class AdminSession(BaseModel):
    """Expose identity and expiry without returning the cookie token."""

    username: str
    expires_at: int


class SearchFilters(BaseModel):
    """Only explicit, currently stored source metadata is filterable."""

    model_config = ConfigDict(extra="forbid")
    document_ids: list[str] = Field(default_factory=list, max_length=20)
    source_type: Literal["pdf", "html"] | None = None


class SearchRequest(BaseModel):
    """Bound the query and candidate work performed by either search tool."""

    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=1000, examples=["What are the PhD scholarship requirements?"])
    filters: SearchFilters = Field(default_factory=SearchFilters)
    limit: int = Field(default=10, ge=1, le=30)
    min_semantic_score: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("query")
    @classmethod
    def reject_blank_query(cls, value: str) -> str:
        """Preserve the original text while rejecting whitespace-only input."""
        if not value.strip():
            raise ValueError("Enter a question or keywords.")
        return value


class CombinedSearchRequest(SearchRequest):
    """Select a bounded evidence set and optional adjacent source context."""

    top_k: int = Field(default=4, ge=1, le=6)
    include_neighbors: bool = True
    context_char_budget: int = Field(default=20000, ge=2500, le=30000)


class Evidence(BaseModel):
    """Source-backed passage; search scores are not answer confidence."""

    chunk_id: str
    document_id: str
    title: str
    text: str
    source_url: str
    page_numbers: list[int]
    chunk_index: int
    heading_path: str = ""
    scores: dict[str, float] = Field(default_factory=dict)
    rrf_score: float | None = None
    is_neighbor: bool = False
    neighbor_of: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """Inspect an independent search before fusion or reranking."""

    query: str
    normalized_query: str
    method: Literal["semantic", "keyword"]
    results: list[Evidence]


class CombinedSearchResponse(BaseModel):
    """Separate ranked evidence from context and expose fallback explicitly."""

    query: str
    normalized_query: str
    candidates: list[Evidence]
    evidence: list[Evidence]
    neighbors: list[Evidence]
    rerank_applied: bool
    rerank_reason: str
    status: Literal["candidates_found", "no_candidates", "no_relevant_candidates"]
    evidence_check: Literal["not_evaluated"] = "not_evaluated"
    context_characters: int
    context_limited: bool


class RerankOrder(BaseModel):
    """Only ordered, relevant candidate IDs may come back from the model."""

    model_config = ConfigDict(extra="forbid")
    chunk_ids: list[str] = Field(max_length=20)
