from typing import Any

from fastapi import APIRouter

from app.api.deps import OrchestratorDep
from app.api.schemas import HealthResponse, QueryRequest, QueryResponse

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


@router.get("/trace/{trace_id}")
async def get_trace(trace_id: str, orchestrator: OrchestratorDep) -> dict[str, Any]:
    return orchestrator.get_trace(trace_id)
