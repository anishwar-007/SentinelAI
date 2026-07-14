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
from app.retriever.embeddings import EmbeddingService
from app.retriever.registry import DocumentRegistry
from app.retriever.retriever import DocumentRetriever
from app.retriever.vector_store import VectorStore
from app.services.orchestrator import AIOrchestrator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = load_settings()
    client = OpenRouterClient(
        api_key=settings.openrouter_api_key,
        model=settings.model,
        base_url=settings.base_url,
    )
    embeddings = EmbeddingService()
    vector_store = VectorStore()
    registry = DocumentRegistry()
    retriever = DocumentRetriever(
        embeddings=embeddings,
        vector_store=vector_store,
        registry=registry,
    )
    planner = Planner(client)
    executor = Executor(
        client,
        InvoiceExtractor(client),
        retriever=retriever,
    )
    orchestrator = AIOrchestrator(
        planner=planner,
        executor=executor,
        retriever=retriever,
    )

    app.state.client = client
    app.state.retriever = retriever
    app.state.orchestrator = orchestrator

    try:
        yield
    finally:
        await client.aclose()


app = FastAPI(
    title="TracerAI",
    description="AI observability learning platform",
    version="0.6.1",
    lifespan=lifespan,
)

register_exception_handlers(app)
app.include_router(router)
