from typing import Any

from pydantic import BaseModel, Field


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
    source: str | None = None


class DocumentIndexResponse(BaseModel):
    document_id: str
    chunks_indexed: int
    trace_id: str
    latency_ms: float
