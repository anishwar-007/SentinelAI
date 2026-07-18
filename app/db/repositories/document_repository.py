from __future__ import annotations

import builtins
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentRecord(BaseModel):
    id: UUID
    filename: str
    storage_path: str
    sha256: str
    embedding_model: str
    chunk_count: int
    status: str
    version: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class DocumentChunkRecord(BaseModel):
    id: UUID
    document_id: UUID
    chunk_index: int
    vector_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentRepository(ABC):
    @abstractmethod
    async def create(self, document: DocumentRecord) -> DocumentRecord:
        raise NotImplementedError

    @abstractmethod
    async def update(self, document: DocumentRecord) -> DocumentRecord:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, document_id: UUID) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get(self, document_id: UUID) -> DocumentRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def list(self) -> builtins.list[DocumentRecord]:
        raise NotImplementedError

    @abstractmethod
    async def find_by_hash(self, sha256: str) -> DocumentRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def add_chunks(self, chunks: builtins.list[DocumentChunkRecord]) -> int:
        raise NotImplementedError
