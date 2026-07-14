from pathlib import Path
from typing import Any, cast

import chromadb

from app.retriever.schemas import DocumentChunk, SearchResult
from app.tracing.decorators import trace_span

DEFAULT_CHROMA_DIR = "chroma_data"
DEFAULT_COLLECTION = "documents"


class VectorStore:
    def __init__(
        self,
        persist_dir: str = DEFAULT_CHROMA_DIR,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> None:
        path = Path(persist_dir)
        path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(path))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @trace_span("vector_store.add")
    def add(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> int:
        if not chunks:
            return 0
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length.")

        self._collection.add(
            ids=[chunk.id for chunk in chunks],
            embeddings=cast(Any, embeddings),
            documents=[chunk.content for chunk in chunks],
            metadatas=[_flatten_metadata(chunk) for chunk in chunks],
        )
        return len(chunks)

    @trace_span("vector_store.search")
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[SearchResult]:
        if top_k < 1:
            raise ValueError("top_k must be >= 1.")

        raw = self._collection.query(
            query_embeddings=cast(Any, [query_embedding]),
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        ids = (raw.get("ids") or [[]])[0]
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]

        results: list[SearchResult] = []
        for chunk_id, document, metadata, distance in zip(
            ids,
            documents,
            metadatas,
            distances,
            strict=False,
        ):
            meta = dict(metadata or {})
            document_id = str(meta.get("document_id", chunk_id.split(":", 1)[0]))
            results.append(
                SearchResult(
                    chunk=DocumentChunk(
                        id=str(chunk_id),
                        document_id=document_id,
                        content=str(document or ""),
                        metadata=meta,
                    ),
                    score=_distance_to_score(float(distance)),
                )
            )
        return results


def _flatten_metadata(chunk: DocumentChunk) -> dict[str, Any]:
    metadata: dict[str, Any] = {"document_id": chunk.document_id}
    for key, value in chunk.metadata.items():
        if isinstance(value, (str, int, float, bool)):
            metadata[key] = value
        elif value is None:
            continue
        else:
            metadata[key] = str(value)
    return metadata


def _distance_to_score(distance: float) -> float:
    return max(0.0, 1.0 - distance)
