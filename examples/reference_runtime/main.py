import hashlib
import inspect
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from examples.reference_runtime.analysis.analyzer import RootCauseAnalyzer
from examples.reference_runtime.analysis.prompts import root_cause_analysis_prompt
from examples.reference_runtime.api.demo_runner import build_demo_query_runner
from examples.reference_runtime.api.errors import register_exception_handlers
from examples.reference_runtime.api.router import router as runtime_router
from examples.reference_runtime.config import load_settings
from examples.reference_runtime.db.repositories.postgres_document_repository import (
    PostgresDocumentRepository,
)
from examples.reference_runtime.executor import Executor
from examples.reference_runtime.invoice import InvoiceExtractor
from examples.reference_runtime.llm import OpenRouterClient, create_llm_client
from examples.reference_runtime.planner.planner import Planner
from examples.reference_runtime.planner.prompts import plan_user_query_prompt
from examples.reference_runtime.prompts import extract_invoice_prompt
from examples.reference_runtime.retriever.embeddings import EmbeddingService
from examples.reference_runtime.retriever.qdrant_store import QdrantVectorStore
from examples.reference_runtime.retriever.registry import DocumentRegistry
from examples.reference_runtime.retriever.retriever import (
    DocumentRetriever,
    inject_context,
)
from examples.reference_runtime.services.orchestrator import AIOrchestrator
from examples.reference_runtime.verifier.prompts import verification_prompt
from examples.reference_runtime.verifier.verifier import Verifier
from sentinelai import Contracts, configure
from sentinelai.execution_stream import InMemoryExecutionStream
from sentinelai_platform.api import (
    configure_cors,
)
from sentinelai_platform.api import (
    demo_router as platform_demo_router,
)
from sentinelai_platform.api import (
    register_exception_handlers as register_platform_exception_handlers,
)
from sentinelai_platform.api import (
    v1_router as platform_v1_router,
)
from sentinelai_platform.api.router import router as platform_router
from sentinelai_platform.event_subscribers import register_persistence_subscribers
from sentinelai_platform.execution_store import TracePersister
from sentinelai_platform.persistence.postgres import (
    PostgresExecutionLifecycleRepository,
    PostgresExecutionSnapshotRepository,
    PostgresTraceRepository,
    create_engine,
    create_session_factory,
)
from sentinelai_platform.ports.storage import StorageProvider
from sentinelai_platform.storage.local_provider import LocalStorageProvider
from sentinelai_platform.storage.supabase_provider import SupabaseStorageProvider

load_dotenv()

def _prompt_reference(
    *,
    prompt_id: str,
    version: str,
    name: str,
    source: Callable[..., object],
) -> Contracts.PromptReference:
    source_hash = hashlib.sha256(
        inspect.getsource(source).encode("utf-8")
    ).hexdigest()
    return Contracts.PromptReference(
        prompt_id=prompt_id,
        version=version,
        name=name,
        hash=source_hash,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = load_settings()

    engine = create_engine(
        settings.database_url,
        connect_args=settings.database_connect_args,
    )
    session_factory = create_session_factory(engine)

    document_repository = PostgresDocumentRepository(session_factory)
    execution_repository = PostgresExecutionLifecycleRepository(session_factory)
    execution_snapshot_repository = PostgresExecutionSnapshotRepository(session_factory)
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

    client = create_llm_client(settings)
    planner = Planner(client)
    executor = Executor(client, InvoiceExtractor(client), retriever=retriever)
    verifier = Verifier(client)
    analyzer = RootCauseAnalyzer(client)
    trace_persister = TracePersister(trace_repository, storage)
    execution_stream = InMemoryExecutionStream()
    register_persistence_subscribers(
        execution_stream,
        executions=execution_repository,
        snapshots=execution_snapshot_repository,
        trace_persister=trace_persister,
    )
    model_info = Contracts.ModelInfo(
        provider=settings.model_provider,
        model_name=settings.model,
        reasoning_enabled=False,
    )
    prompt_catalog = {
        "planner": _prompt_reference(
            prompt_id="planner.plan_user_query",
            version="v1",
            name="Query Planner",
            source=plan_user_query_prompt,
        ),
        "executor.chat": _prompt_reference(
            prompt_id="executor.chat",
            version="v1",
            name="Chat Completion",
            source=OpenRouterClient._build_payload,
        ),
        "executor.invoice_extraction": _prompt_reference(
            prompt_id="executor.invoice_extraction",
            version="v1",
            name="Invoice Extraction",
            source=extract_invoice_prompt,
        ),
        "executor.retrieval": _prompt_reference(
            prompt_id="executor.retrieval",
            version="v1",
            name="Retrieval Context Injection",
            source=inject_context,
        ),
        "verifier": _prompt_reference(
            prompt_id="verifier.answer",
            version="v1",
            name="Answer Verification",
            source=verification_prompt,
        ),
        "analyzer": _prompt_reference(
            prompt_id="analyzer.root_cause",
            version="v1",
            name="Root Cause Analysis",
            source=root_cause_analysis_prompt,
        ),
    }
    configure(
        publisher=execution_stream,
        model_info=model_info,
        prompt_catalog=prompt_catalog,
    )
    orchestrator = AIOrchestrator(
        planner=planner,
        executor=executor,
        retriever=retriever,
        verifier=verifier,
        analyzer=analyzer,
    )

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.client = client
    app.state.retriever = retriever
    app.state.orchestrator = orchestrator
    app.state.demo_query_runner = build_demo_query_runner(
        orchestrator,
        trace_persister=trace_persister,
    )
    app.state.execution_repository = execution_snapshot_repository
    app.state.execution_stream = execution_stream
    app.state.trace_persister = trace_persister
    app.state.trace_repository = trace_repository
    app.state.storage = storage
    app.state.vector_store = vector_store

    try:
        yield
    finally:
        await client.aclose()
        await engine.dispose()


app = FastAPI(
    title="SentinelAI Reference Runtime",
    description="Demo customer application built on the SentinelAI SDK",
    version="2.0.0",
    lifespan=lifespan,
)

register_exception_handlers(app)
register_platform_exception_handlers(app)
configure_cors(app)
app.include_router(runtime_router)
app.include_router(platform_router)
app.include_router(platform_v1_router)
app.include_router(platform_demo_router)
