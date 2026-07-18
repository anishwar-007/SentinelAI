from typing import Any
from uuid import UUID

from fastapi import APIRouter

from app.api.deps import OrchestratorDep
from app.api.schemas import (
    DocumentIndexRequest,
    DocumentIndexResponse,
    DocumentListResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
)
from app.retriever.schemas import IndexedDocument

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
        verification=result.verification,
        verification_status=result.verification_status,
        analysis=result.analysis,
    )


@router.post("/documents", response_model=DocumentIndexResponse)
async def index_document(
    body: DocumentIndexRequest,
    orchestrator: OrchestratorDep,
) -> DocumentIndexResponse:
    result = await orchestrator.index_document(
        body.content,
        document_id=body.document_id,
        filename=body.filename,
        source=body.source,
    )
    document = result.document
    return DocumentIndexResponse(
        document_id=str(document.document_id),
        filename=document.filename,
        chunks_indexed=document.chunk_count,
        status=document.status,
        deduplicated=result.deduplicated,
        trace_id=result.trace_id,
        latency_ms=result.latency_ms,
        content_hash=document.content_hash,
        embedding_model=document.embedding_model,
    )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(orchestrator: OrchestratorDep) -> DocumentListResponse:
    return DocumentListResponse(documents=await orchestrator.list_documents())


@router.get("/documents/{document_id}", response_model=IndexedDocument)
async def get_document(
    document_id: UUID,
    orchestrator: OrchestratorDep,
) -> IndexedDocument:
    return await orchestrator.get_document(str(document_id))


@router.get("/trace/{trace_id}")
async def get_trace(trace_id: str, orchestrator: OrchestratorDep) -> dict[str, Any]:
    return await orchestrator.get_trace(trace_id)
