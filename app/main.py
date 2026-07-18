from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.analysis.analyzer import RootCauseAnalyzer
from app.api.errors import register_exception_handlers
from app.api.router import router
from app.config import load_settings
from app.db.repositories.postgres_document_repository import PostgresDocumentRepository
from app.db.repositories.postgres_execution_repository import PostgresExecutionRepository
from app.db.repositories.postgres_trace_repository import PostgresTraceRepository
from app.db.session import create_engine, create_session_factory
from app.executor import Executor
from app.invoice import InvoiceExtractor
from app.llm import OpenRouterClient
from app.planner.planner import Planner
from app.retriever.embeddings import EmbeddingService
from app.retriever.qdrant_store import QdrantVectorStore
from app.retriever.registry import DocumentRegistry
from app.retriever.retriever import DocumentRetriever
from app.services.orchestrator import AIOrchestrator
from app.storage.local_provider import LocalStorageProvider
from app.storage.provider import StorageProvider
from app.storage.supabase_provider import SupabaseStorageProvider
from app.tracing.persistence import TracePersister
from app.verifier.verifier import Verifier


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = load_settings()

    engine = create_engine(
        settings.database_url,
        connect_args=settings.database_connect_args,
    )
    session_factory = create_session_factory(engine)

    document_repository = PostgresDocumentRepository(session_factory)
    execution_repository = PostgresExecutionRepository(session_factory)
    trace_repository = PostgresTraceRepository(session_factory)

    storage: StorageProvider
    if settings.storage_backend == "supabase":
        if not settings.supabase_url or not settings.supabase_key:
            raise RuntimeError(
                "STORAGE_BACKEND=supabase requires SUPABASE_URL and SUPABASE_KEY."
            )
        storage = SupabaseStorageProvider(
            settings.supabase_url,
            settings.supabase_key,
            settings.supabase_bucket,
        )
    else:
        storage = LocalStorageProvider(settings.local_storage_dir)

    vector_store = QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        collection_name=settings.qdrant_collection,
        vector_size=settings.embedding_dim,
    )
    registry = DocumentRegistry(document_repository, storage)
    embeddings = EmbeddingService()
    retriever = DocumentRetriever(
        embeddings=embeddings,
        vector_store=vector_store,
        registry=registry,
    )

    client = OpenRouterClient(
        api_key=settings.openrouter_api_key,
        model=settings.model,
        base_url=settings.base_url,
    )
    planner = Planner(client)
    executor = Executor(client, InvoiceExtractor(client), retriever=retriever)
    verifier = Verifier(client)
    analyzer = RootCauseAnalyzer(client)
    trace_persister = TracePersister(trace_repository, storage)
    orchestrator = AIOrchestrator(
        planner=planner,
        executor=executor,
        retriever=retriever,
        verifier=verifier,
        analyzer=analyzer,
        executions=execution_repository,
        trace_persister=trace_persister,
    )

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.client = client
    app.state.retriever = retriever
    app.state.orchestrator = orchestrator
    app.state.storage = storage
    app.state.vector_store = vector_store

    try:
        yield
    finally:
        await client.aclose()
        await engine.dispose()


app = FastAPI(
    title="TracerAI",
    description="AI observability learning platform",
    version="0.8.5",
    lifespan=lifespan,
)

register_exception_handlers(app)
app.include_router(router)
