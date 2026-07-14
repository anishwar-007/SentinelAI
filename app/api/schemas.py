from typing import Any

from pydantic import BaseModel, Field

from app.retriever.schemas import IndexedDocument


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)


class QueryResponse(BaseModel):
    trace_id: str
    intent: str
    confidence: float
    result: Any
    latency_ms: float


class HealthResponse(BaseModel):
    status: str


class DocumentIndexRequest(BaseModel):
    content: str = Field(..., min_length=1)
    document_id: str | None = None
    filename: str | None = None
    source: str | None = None


class DocumentIndexResponse(BaseModel):
    document_id: str
    filename: str
    chunks_indexed: int
    status: str
    deduplicated: bool
    trace_id: str
    latency_ms: float
    content_hash: str
    embedding_model: str


class DocumentListResponse(BaseModel):
    documents: list[IndexedDocument]
