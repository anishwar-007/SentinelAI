import json
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from app.retriever.schemas import IndexedDocument
from app.tracing.decorators import trace_span

DEFAULT_REGISTRY_PATH = "registry/documents.json"
DocumentStatus = Literal["indexing", "ready", "failed"]


class DocumentNotFoundError(LookupError):
    pass


class DocumentRegistry:
    def __init__(self, path: str = DEFAULT_REGISTRY_PATH) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write({})

    def _read(self) -> dict[str, IndexedDocument]:
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        return {
            key: IndexedDocument.model_validate(value)
            for key, value in raw.items()
        }

    def _write(self, documents: dict[str, IndexedDocument]) -> None:
        payload = {
            key: document.model_dump(mode="json")
            for key, document in documents.items()
        }
        self._path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    @trace_span("registry.register_document")
    def register_document(self, document: IndexedDocument) -> IndexedDocument:
        documents = self._read()
        documents[str(document.document_id)] = document
        self._write(documents)
        return document

    @trace_span("registry.duplicate_check")
    def find_by_hash(self, content_hash: str) -> IndexedDocument | None:
        for document in self._read().values():
            if document.content_hash == content_hash and document.status == "ready":
                return document
        return None

    @trace_span("registry.update_status")
    def update_status(
        self,
        document_id: UUID,
        status: DocumentStatus,
        *,
        chunk_count: int | None = None,
        metadata_updates: dict[str, Any] | None = None,
    ) -> IndexedDocument:
        documents = self._read()
        key = str(document_id)
        document = documents.get(key)
        if document is None:
            raise DocumentNotFoundError(f"Document not found: {document_id}")

        updates: dict[str, Any] = {"status": status}
        if chunk_count is not None:
            updates["chunk_count"] = chunk_count
        if metadata_updates:
            merged = dict(document.metadata)
            merged.update(metadata_updates)
            updates["metadata"] = merged

        updated = document.model_copy(update=updates)
        documents[key] = updated
        self._write(documents)
        return updated

    def get_document(self, document_id: UUID) -> IndexedDocument:
        document = self._read().get(str(document_id))
        if document is None:
            raise DocumentNotFoundError(f"Document not found: {document_id}")
        return document

    def list_documents(self) -> list[IndexedDocument]:
        documents = list(self._read().values())
        documents.sort(key=lambda item: item.indexed_at, reverse=True)
        return documents

    def remove_document(self, document_id: UUID) -> None:
        documents = self._read()
        key = str(document_id)
        if key not in documents:
            raise DocumentNotFoundError(f"Document not found: {document_id}")
        del documents[key]
        self._write(documents)
