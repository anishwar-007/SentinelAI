from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from app.db.repositories.document_repository import (
    DocumentChunkRecord,
    DocumentRecord,
    DocumentRepository,
)
from app.retriever.schemas import IndexedDocument
from app.storage.provider import StorageProvider
from app.tracing.decorators import trace_span

DocumentStatus = Literal["indexing", "ready", "failed"]


class DocumentNotFoundError(LookupError):
    pass


class DocumentRegistry:
    """Application catalog over DocumentRepository + object storage."""

    def __init__(
        self,
        documents: DocumentRepository,
        storage: StorageProvider,
    ) -> None:
        self._documents = documents
        self._storage = storage

    @trace_span("registry.duplicate_check")
    async def find_by_hash(self, content_hash: str) -> IndexedDocument | None:
        record = await self._documents.find_by_hash(content_hash)
        if record is None:
            return None
        return _to_indexed(record)

    @trace_span("registry.register_document")
    async def register_document(
        self,
        document: IndexedDocument,
        *,
        content: bytes | None = None,
    ) -> IndexedDocument:
        storage_path = document.metadata.get("storage_path")
        if not isinstance(storage_path, str) or not storage_path:
            storage_path = f"documents/{document.document_id}/{document.filename}"

        if content is not None:
            await self._storage.upload(
                storage_path,
                content,
                content_type="text/plain",
            )

        now = datetime.now(UTC)
        record = DocumentRecord(
            id=document.document_id,
            filename=document.filename,
            storage_path=storage_path,
            sha256=document.content_hash,
            embedding_model=document.embedding_model,
            chunk_count=document.chunk_count,
            status=document.status,
            version=1,
            metadata={
                **document.metadata,
                "storage_path": storage_path,
            },
            created_at=document.indexed_at or now,
            updated_at=now,
        )
        created = await self._documents.create(record)
        return _to_indexed(created)

    @trace_span("registry.update_status")
    async def update_status(
        self,
        document_id: UUID,
        status: DocumentStatus,
        *,
        chunk_count: int | None = None,
        metadata_updates: dict[str, Any] | None = None,
    ) -> IndexedDocument:
        record = await self._documents.get(document_id)
        if record is None:
            raise DocumentNotFoundError(f"Document not found: {document_id}")

        metadata = dict(record.metadata)
        if metadata_updates:
            metadata.update(metadata_updates)

        updated = DocumentRecord(
            id=record.id,
            filename=record.filename,
            storage_path=record.storage_path,
            sha256=record.sha256,
            embedding_model=record.embedding_model,
            chunk_count=record.chunk_count if chunk_count is None else chunk_count,
            status=status,
            version=record.version,
            metadata=metadata,
            created_at=record.created_at,
            updated_at=datetime.now(UTC),
        )
        saved = await self._documents.update(updated)
        return _to_indexed(saved)

    async def get_document(self, document_id: UUID) -> IndexedDocument:
        record = await self._documents.get(document_id)
        if record is None:
            raise DocumentNotFoundError(f"Document not found: {document_id}")
        return _to_indexed(record)

    async def list_documents(self) -> list[IndexedDocument]:
        records = await self._documents.list()
        return [_to_indexed(record) for record in records]

    async def remove_document(self, document_id: UUID) -> None:
        record = await self._documents.get(document_id)
        if record is None:
            raise DocumentNotFoundError(f"Document not found: {document_id}")
        if record.storage_path:
            await self._storage.delete(record.storage_path)
        await self._documents.delete(document_id)

    async def save_chunks(
        self,
        document_id: UUID,
        chunks: list[tuple[str, int, dict[str, Any]]],
    ) -> int:
        records = [
            DocumentChunkRecord(
                id=uuid4(),
                document_id=document_id,
                chunk_index=chunk_index,
                vector_id=vector_id,
                metadata=metadata,
            )
            for vector_id, chunk_index, metadata in chunks
        ]
        return await self._documents.add_chunks(records)


def _to_indexed(record: DocumentRecord) -> IndexedDocument:
    status = cast(Literal["indexing", "ready", "failed"], record.status)
    return IndexedDocument(
        document_id=record.id,
        filename=record.filename,
        content_hash=record.sha256,
        indexed_at=record.created_at,
        chunk_count=record.chunk_count,
        embedding_model=record.embedding_model,
        status=status,
        metadata=record.metadata,
    )
