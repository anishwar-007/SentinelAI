from typing import Annotated, cast

from fastapi import Depends, Request

from app.services.orchestrator import AIOrchestrator


def get_orchestrator(request: Request) -> AIOrchestrator:
    return cast(AIOrchestrator, request.app.state.orchestrator)


OrchestratorDep = Annotated[AIOrchestrator, Depends(get_orchestrator)]
