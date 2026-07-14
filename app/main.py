from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.router import router
from app.config import load_settings
from app.executor import Executor
from app.invoice import InvoiceExtractor
from app.llm import OpenRouterClient
from app.planner.planner import Planner
from app.services.orchestrator import AIOrchestrator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = load_settings()
    client = OpenRouterClient(
        api_key=settings.openrouter_api_key,
        model=settings.model,
        base_url=settings.base_url,
    )
    planner = Planner(client)
    executor = Executor(client, InvoiceExtractor(client))
    orchestrator = AIOrchestrator(planner=planner, executor=executor)

    app.state.client = client
    app.state.orchestrator = orchestrator

    try:
        yield
    finally:
        await client.aclose()


app = FastAPI(
    title="TracerAI",
    description="AI observability learning platform",
    version="0.5.0",
    lifespan=lifespan,
)

register_exception_handlers(app)
app.include_router(router)
