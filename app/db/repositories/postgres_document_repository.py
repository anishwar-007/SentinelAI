from __future__ import annotations

import builtins
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.document import DocumentChunkModel, DocumentModel
from app.db.repositories.document_repository import (
    DocumentChunkRecord,
    DocumentRecord,
    DocumentRepository,
)


class PostgresDocumentRepository(DocumentRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, document: DocumentRecord) -> DocumentRecord:
        async with self._session_factory() as session:
            row = DocumentModel(
                id=document.id,
                filename=document.filename,
                storage_path=document.storage_path,
                sha256=document.sha256,
                embedding_model=document.embedding_model,
                chunk_count=document.chunk_count,
                status=document.status,
                version=document.version,
                metadata_=document.metadata,
                created_at=document.created_at,
                updated_at=document.updated_at,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _to_document_record(row)

    async def update(self, document: DocumentRecord) -> DocumentRecord:
        async with self._session_factory() as session:
            row = await session.get(DocumentModel, document.id)
            if row is None:
                raise LookupError(f"Document not found: {document.id}")
            row.filename = document.filename
            row.storage_path = document.storage_path
            row.sha256 = document.sha256
            row.embedding_model = document.embedding_model
            row.chunk_count = document.chunk_count
            row.status = document.status
            row.version = document.version
            row.metadata_ = document.metadata
            row.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(row)
            return _to_document_record(row)

    async def delete(self, document_id: UUID) -> None:
        async with self._session_factory() as session:
            row = await session.get(DocumentModel, document_id)
            if row is None:
                raise LookupError(f"Document not found: {document_id}")
            await session.delete(row)
            await session.commit()

    async def get(self, document_id: UUID) -> DocumentRecord | None:
        async with self._session_factory() as session:
            row = await session.get(DocumentModel, document_id)
            if row is None:
                return None
            return _to_document_record(row)

    async def list(self) -> builtins.list[DocumentRecord]:
        async with self._session_factory() as session:
            result = await session.scalars(
                select(DocumentModel).order_by(DocumentModel.created_at.desc())
            )
            return [_to_document_record(row) for row in result.all()]

    async def find_by_hash(self, sha256: str) -> DocumentRecord | None:
        async with self._session_factory() as session:
            result = await session.scalars(
                select(DocumentModel).where(
                    DocumentModel.sha256 == sha256,
                    DocumentModel.status == "ready",
                )
            )
            row = result.first()
            if row is None:
                return None
            return _to_document_record(row)

    async def add_chunks(self, chunks: builtins.list[DocumentChunkRecord]) -> int:
        if not chunks:
            return 0
        async with self._session_factory() as session:
            for chunk in chunks:
                session.add(
                    DocumentChunkModel(
                        id=chunk.id,
                        document_id=chunk.document_id,
                        chunk_index=chunk.chunk_index,
                        vector_id=chunk.vector_id,
                        metadata_=chunk.metadata,
                    )
                )
            await session.commit()
            return len(chunks)


def _to_document_record(row: DocumentModel) -> DocumentRecord:
    return DocumentRecord(
        id=row.id,
        filename=row.filename,
        storage_path=row.storage_path,
        sha256=row.sha256,
        embedding_model=row.embedding_model,
        chunk_count=row.chunk_count,
        status=row.status,
        version=row.version,
        metadata=dict(row.metadata_ or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
