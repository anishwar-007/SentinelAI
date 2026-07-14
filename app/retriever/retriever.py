from app.retriever.chunker import chunk_document
from app.retriever.embeddings import EmbeddingService
from app.retriever.schemas import RetrieverResult
from app.retriever.vector_store import VectorStore
from app.tracing.decorators import trace_span


class DocumentRetriever:
    def __init__(
        self,
        embeddings: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
        default_top_k: int = 5,
    ) -> None:
        self._embeddings = embeddings or EmbeddingService()
        self._vector_store = vector_store or VectorStore()
        self._default_top_k = default_top_k

    async def index_document(
        self,
        text: str,
        document_id: str | None = None,
        *,
        source: str | None = None,
    ) -> tuple[str, int]:
        chunks = chunk_document(text, document_id=document_id, source=source)
        if not chunks:
            raise ValueError("Document text is empty; nothing to index.")

        embeddings = await self._embeddings.embed([chunk.content for chunk in chunks])
        indexed = self._vector_store.add(chunks, embeddings)
        return chunks[0].document_id, indexed

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
    if not retrieval.results:
        return (
            "Answer the question using general knowledge. "
            "No retrieved document context was available.\n\n"
            f"Question: {query}"
        )

    blocks: list[str] = []
    for index, item in enumerate(retrieval.results, start=1):
        source = item.chunk.metadata.get("source", item.chunk.document_id)
        blocks.append(
            f"[Chunk {index} | source={source} | score={item.score:.3f}]\n"
            f"{item.chunk.content}"
        )

    context = "\n\n".join(blocks)
    return (
        "Use the retrieved context to answer the question. "
        "If the context is insufficient, say what is missing. "
        "Do not invent facts that are not supported by the context.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}"
    )
