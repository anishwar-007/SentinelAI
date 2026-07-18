from uuid import UUID

from fastapi import APIRouter

from examples.reference_runtime.api.deps import OrchestratorDep
from examples.reference_runtime.api.schemas import (
    DocumentIndexRequest,
    DocumentIndexResponse,
    DocumentListResponse,
    QueryRequest,
    QueryResponse,
)
from examples.reference_runtime.retriever.schemas import IndexedDocument

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(
    body: QueryRequest,
    orchestrator: OrchestratorDep,
) -> QueryResponse:
    observed = await orchestrator.run(body.query)
    return QueryResponse(
        execution_id=observed.metadata.execution_id,
        trace_id=observed.metadata.trace_id or "",
        intent=observed.value.intent,
        confidence=observed.value.confidence,
        result=observed.value.result,
        latency_ms=observed.metadata.latency_ms or 0.0,
        verification=observed.value.verification,
        verification_status=observed.value.verification_status,
        analysis=observed.value.analysis,
    )


@router.post("/documents", response_model=DocumentIndexResponse)
async def index_document(
    body: DocumentIndexRequest,
    orchestrator: OrchestratorDep,
) -> DocumentIndexResponse:
    observed = await orchestrator.index_document(
        body.content,
        document_id=body.document_id,
        filename=body.filename,
        source=body.source,
    )
    document = observed.value.document
    return DocumentIndexResponse(
        document_id=str(document.document_id),
        filename=document.filename,
        chunks_indexed=document.chunk_count,
        status=document.status,
        deduplicated=observed.value.deduplicated,
        trace_id=observed.metadata.trace_id or "",
        latency_ms=observed.metadata.latency_ms or 0.0,
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
