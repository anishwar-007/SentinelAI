import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.retriever.chunker import chunk_document
from app.retriever.embeddings import EmbeddingService
from app.retriever.registry import DocumentRegistry
from app.retriever.schemas import IndexedDocument, RetrieverResult
from app.retriever.vector_store import VectorStore
from app.tracing.decorators import trace_span


class IndexOutcome:
    def __init__(
        self,
        document: IndexedDocument,
        *,
        deduplicated: bool,
    ) -> None:
        self.document = document
        self.deduplicated = deduplicated


class DocumentRetriever:
    def __init__(
        self,
        embeddings: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
        registry: DocumentRegistry | None = None,
        default_top_k: int = 5,
    ) -> None:
        self._embeddings = embeddings or EmbeddingService()
        self._vector_store = vector_store or VectorStore()
        self._registry = registry or DocumentRegistry()
        self._default_top_k = default_top_k

    @property
    def registry(self) -> DocumentRegistry:
        return self._registry

    async def index_document(
        self,
        text: str,
        document_id: str | None = None,
        *,
        filename: str | None = None,
        source: str | None = None,
    ) -> IndexOutcome:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("Document text is empty; nothing to index.")

        content_hash = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
        duplicate = self._registry.find_by_hash(content_hash)
        if duplicate is not None:
            return IndexOutcome(document=duplicate, deduplicated=True)

        doc_uuid = _resolve_document_id(document_id)
        resolved_filename = filename or source or "untitled.txt"
        indexed_at = datetime.now(UTC)

        document = IndexedDocument(
            document_id=doc_uuid,
            filename=resolved_filename,
            content_hash=content_hash,
            indexed_at=indexed_at,
            chunk_count=0,
            embedding_model=self._embeddings.model_name,
            status="indexing",
            metadata={
                "source": source,
            },
        )
        self._registry.register_document(document)

        try:
            chunks = chunk_document(
                cleaned,
                document_id=str(doc_uuid),
                source=source or resolved_filename,
            )
            embeddings = await self._embeddings.embed(
                [chunk.content for chunk in chunks]
            )
            indexed = self._vector_store.add(chunks, embeddings)
            ready = self._registry.update_status(
                doc_uuid,
                "ready",
                chunk_count=indexed,
            )
            return IndexOutcome(document=ready, deduplicated=False)
        except Exception as exc:
            self._registry.update_status(
                doc_uuid,
                "failed",
                metadata_updates={"error": str(exc)},
            )
            raise

    async def search(self, query: str, top_k: int | None = None) -> RetrieverResult:
        cleaned = query.strip()
        if not cleaned:
            raise ValueError("Search query must not be empty.")

        k = top_k if top_k is not None else self._default_top_k
        query_vectors = await self._embeddings.embed([cleaned])
        results = self._vector_store.search(query_vectors[0], top_k=k)
        return RetrieverResult(query=cleaned, results=results, top_k=k)


@trace_span("retrieval.context_injection")
def inject_context(query: str, retrieval: RetrieverResult) -> str:
    context = format_retrieved_context(retrieval)
    if not context:
        return (
            "Answer the question using general knowledge. "
            "No retrieved document context was available.\n\n"
            f"Question: {query}"
        )

    return (
        "Use the retrieved context to answer the question. "
        "If the context is insufficient, say what is missing. "
        "Do not invent facts that are not supported by the context.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}"
    )


def format_retrieved_context(retrieval: RetrieverResult) -> str:
    if not retrieval.results:
        return ""

    blocks: list[str] = []
    for index, item in enumerate(retrieval.results, start=1):
        source = item.chunk.metadata.get("source", item.chunk.document_id)
        blocks.append(
            f"[Chunk {index} | source={source} | score={item.score:.3f}]\n"
            f"{item.chunk.content}"
        )
    return "\n\n".join(blocks)


def _resolve_document_id(document_id: str | None) -> UUID:
    if document_id is None or not document_id.strip():
        return uuid4()
    try:
        return UUID(document_id)
    except ValueError as exc:
        raise ValueError(
            f"document_id must be a valid UUID, got: {document_id!r}"
        ) from exc
