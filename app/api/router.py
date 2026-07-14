from typing import Any

from fastapi import APIRouter

from app.api.deps import OrchestratorDep
from app.api.schemas import (
    DocumentIndexRequest,
    DocumentIndexResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="healthy")


@router.post("/query", response_model=QueryResponse)
async def query(
    body: QueryRequest,
    orchestrator: OrchestratorDep,
) -> QueryResponse:
    result = await orchestrator.run(body.query)
    return QueryResponse(
        trace_id=result.trace_id,
        intent=result.intent,
        confidence=result.confidence,
        result=result.result,
        latency_ms=result.latency_ms,
    )


@router.post("/documents", response_model=DocumentIndexResponse)
async def index_document(
    body: DocumentIndexRequest,
    orchestrator: OrchestratorDep,
) -> DocumentIndexResponse:
    result = await orchestrator.index_document(
        body.content,
        document_id=body.document_id,
        source=body.source,
    )
    return DocumentIndexResponse(
        document_id=result.document_id,
        chunks_indexed=result.chunks_indexed,
        trace_id=result.trace_id,
        latency_ms=result.latency_ms,
    )


@router.get("/trace/{trace_id}")
async def get_trace(trace_id: str, orchestrator: OrchestratorDep) -> dict[str, Any]:
    return orchestrator.get_trace(trace_id)
