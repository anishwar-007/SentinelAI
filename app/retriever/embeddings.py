import asyncio

from sentence_transformers import SentenceTransformer

from app.tracing.decorators import trace_span

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class EmbeddingService:
    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL) -> None:
        self._model_name = model_name
        self._model: SentenceTransformer | None = None

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
        return self._model

    @trace_span("embedding.generate")
    def embed_sync(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._get_model().encode(texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self.embed_sync, texts)
