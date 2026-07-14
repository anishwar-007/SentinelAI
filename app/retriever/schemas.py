from datetime import datetime
from typing import Any, Literal
from uuid import UUID

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


class IndexedDocument(BaseModel):
    document_id: UUID
    filename: str
    content_hash: str
    indexed_at: datetime
    chunk_count: int
    embedding_model: str
    status: Literal["indexing", "ready", "failed"]
    metadata: dict[str, Any] = Field(default_factory=dict)
