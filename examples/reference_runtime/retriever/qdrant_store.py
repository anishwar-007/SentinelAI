from typing import Any
from uuid import UUID, uuid4

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from examples.reference_runtime.retriever.schemas import DocumentChunk, SearchResult
from sentinelai import span

DEFAULT_COLLECTION = "documents"


class QdrantVectorStore:
    def __init__(
        self,
        url: str,
        api_key: str | None = None,
        collection_name: str = DEFAULT_COLLECTION,
        vector_size: int = 384,
    ) -> None:
        self._client = QdrantClient(url=url, api_key=api_key)
        self._collection_name = collection_name
        self._vector_size = vector_size
        self.create_collection()

    def create_collection(self) -> None:
        names = {
            collection.name for collection in self._client.get_collections().collections
        }
        if self._collection_name in names:
            return
        self._client.create_collection(
            collection_name=self._collection_name,
            vectors_config=qmodels.VectorParams(
                size=self._vector_size,
                distance=qmodels.Distance.COSINE,
            ),
        )

    @span("vector_store.add")
    def add(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> int:
        return self.upsert_chunks(chunks, embeddings)

    def upsert_chunks(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> int:
        if not chunks:
            return 0
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length.")

        points: list[qmodels.PointStruct] = []
        for chunk, vector in zip(chunks, embeddings, strict=True):
            point_id = _as_point_id(chunk.id)
            payload = {
                "document_id": chunk.document_id,
                "chunk_id": chunk.id,
                "content": chunk.content,
                **_flatten_metadata(chunk),
            }
            points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )

        self._client.upsert(collection_name=self._collection_name, points=points)
        return len(points)

    @span("vector_store.search")
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[SearchResult]:
        if top_k < 1:
            raise ValueError("top_k must be >= 1.")

        response = self._client.query_points(
            collection_name=self._collection_name,
            query=query_embedding,
            limit=top_k,
            with_payload=True,
        )

        results: list[SearchResult] = []
        for hit in response.points:
            payload = dict(hit.payload or {})
            content = str(payload.get("content", ""))
            document_id = str(payload.get("document_id", ""))
            chunk_id = str(payload.get("chunk_id", hit.id))
            results.append(
                SearchResult(
                    chunk=DocumentChunk(
                        id=chunk_id,
                        document_id=document_id,
                        content=content,
                        metadata=payload,
                    ),
                    score=float(hit.score),
                )
            )
        return results

    def delete_document(self, document_id: str) -> None:
        self._client.delete(
            collection_name=self._collection_name,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="document_id",
                            match=qmodels.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )


def _as_point_id(chunk_id: str) -> str:
    try:
        return str(UUID(chunk_id))
    except ValueError:
        return str(uuid4())


def _flatten_metadata(chunk: DocumentChunk) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key, value in chunk.metadata.items():
        if key in {"content", "chunk_id", "document_id"}:
            continue
        if isinstance(value, (str, int, float, bool)):
            metadata[key] = value
        elif value is None:
            continue
        else:
            metadata[key] = str(value)
    return metadata
