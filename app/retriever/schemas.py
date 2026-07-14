from typing import Any

from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    id: str
    document_id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResult(BaseModel):
    chunk: DocumentChunk
    score: float


class RetrieverResult(BaseModel):
    query: str
    results: list[SearchResult] = Field(default_factory=list)
    top_k: int
