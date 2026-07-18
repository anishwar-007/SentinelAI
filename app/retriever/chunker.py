import re
import uuid

from app.retriever.schemas import DocumentChunk

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")


def chunk_document(
    text: str,
    document_id: str | None = None,
    *,
    source: str | None = None,
) -> list[DocumentChunk]:
    cleaned = text.strip()
    if not cleaned:
        return []

    doc_id = document_id or str(uuid.uuid4())
    paragraphs = [part.strip() for part in _PARAGRAPH_SPLIT.split(cleaned) if part.strip()]
    if not paragraphs:
        paragraphs = [cleaned]

    chunks: list[DocumentChunk] = []
    for index, paragraph in enumerate(paragraphs):
        metadata: dict[str, object] = {
            "document_id": doc_id,
            "chunk_index": index,
            "char_count": len(paragraph),
        }
        if source is not None:
            metadata["source"] = source

        chunks.append(
            DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                content=paragraph,
                metadata=metadata,
            )
        )
    return chunks
