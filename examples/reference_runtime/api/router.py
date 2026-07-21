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
from examples.reference_runtime.errors import LLMError
from examples.reference_runtime.retriever.schemas import IndexedDocument
from sentinelai import (
    get_current_execution_id,
    get_current_execution_latency_ms,
    get_current_trace_id,
)

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(
    body: QueryRequest,
    orchestrator: OrchestratorDep,
) -> QueryResponse:
    outcome = await orchestrator.run(body.query)
    execution_id = get_current_execution_id()
    trace_id = get_current_trace_id()
    if execution_id is None or trace_id is None:
        raise LLMError("Orchestrator finished without execution correlation.")
    return QueryResponse(
        execution_id=execution_id,
        trace_id=trace_id,
        intent=outcome.intent,
        confidence=outcome.confidence,
        result=outcome.result,
        latency_ms=get_current_execution_latency_ms() or 0.0,
        verification=outcome.verification,
        verification_status=outcome.verification_status,
        analysis=outcome.analysis,
    )


@router.post("/documents", response_model=DocumentIndexResponse)
async def index_document(
    body: DocumentIndexRequest,
    orchestrator: OrchestratorDep,
) -> DocumentIndexResponse:
    outcome = await orchestrator.index_document(
        body.content,
        document_id=body.document_id,
        filename=body.filename,
        source=body.source,
    )
    trace_id = get_current_trace_id()
    if trace_id is None:
        raise LLMError("Indexing finished without execution correlation.")
    document = outcome.document
    return DocumentIndexResponse(
        document_id=str(document.document_id),
        filename=document.filename,
        chunks_indexed=document.chunk_count,
        status=document.status,
        deduplicated=outcome.deduplicated,
        trace_id=trace_id,
        latency_ms=get_current_execution_latency_ms() or 0.0,
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
