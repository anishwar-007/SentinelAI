import os
from functools import lru_cache
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from examples.reference_runtime.model_plugs import (
    DEFAULT_MODEL_PLUG,
    ModelPlug,
    resolve_model_plug,
)

OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
DEFAULT_QDRANT_COLLECTION: str = "documents"
DEFAULT_EMBEDDING_DIM: int = 384
DEFAULT_LOCAL_STORAGE_DIR: str = "storage"
DEFAULT_TRACES_DIR: str = "traces"


class Settings(BaseModel):
    openrouter_api_key: str = Field(..., min_length=1)
    model_plug: str = DEFAULT_MODEL_PLUG
    model: str
    model_fallbacks: tuple[str, ...] = ()
    model_provider: str = "openrouter"
    base_url: str = OPENROUTER_BASE_URL
    database_url: str = Field(..., min_length=1)
    database_connect_args: dict[str, Any] = Field(default_factory=dict)
    qdrant_url: str = Field(..., min_length=1)
    qdrant_api_key: str | None = None
    qdrant_collection: str = DEFAULT_QDRANT_COLLECTION
    embedding_dim: int = DEFAULT_EMBEDDING_DIM
    supabase_url: str | None = None
    supabase_key: str | None = None
    supabase_bucket: str = "documents"
    storage_backend: str = "supabase"
    local_storage_dir: str = DEFAULT_LOCAL_STORAGE_DIR
    traces_dir: str = DEFAULT_TRACES_DIR

    @property
    def active_model_plug(self) -> ModelPlug:
        return ModelPlug(
            name=self.model_plug,
            model=self.model,
            fallbacks=self.model_fallbacks,
            provider=self.model_provider,
        )


_LIBPQ_ONLY_QUERY_KEYS = frozenset(
    {
        "sslmode",
        "ssl",
        "channel_binding",
        "gssencmode",
        "target_session_attrs",
        "options",
    }
)


def prepare_database_url(url: str) -> tuple[str, dict[str, Any]]:
    """Normalize Neon/libpq URLs for SQLAlchemy + asyncpg.

    Returns (asyncpg_url, connect_args). SSL is passed via connect_args because
    asyncpg rejects several libpq query parameters used by Neon connection URIs.
    """
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    elif not url.startswith("postgresql+asyncpg://"):
        return url, {}

    parts = urlsplit(url)
    query: list[tuple[str, str]] = []
    ssl_required = False
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key == "sslmode":
            if value in {"require", "verify-ca", "verify-full", "prefer"}:
                ssl_required = True
            continue
        if key == "ssl":
            ssl_required = value.lower() in {"1", "true", "require", "yes"}
            continue
        if key in _LIBPQ_ONLY_QUERY_KEYS:
            continue
        query.append((key, value))

    cleaned = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )
    connect_args: dict[str, Any] = {"ssl": True} if ssl_required else {}
    return cleaned, connect_args


def to_asyncpg_url(url: str) -> str:
    cleaned, _ = prepare_database_url(url)
    return cleaned


def _parse_fallbacks(raw: str | None) -> tuple[str, ...] | None:
    if raw is None:
        return None
    parts = tuple(part.strip() for part in raw.split(",") if part.strip())
    return parts


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    load_dotenv()

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set.\n"
            "Fix: copy .env.example to .env and add your key."
        )

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set.")
    async_database_url, database_connect_args = prepare_database_url(database_url)

    qdrant_url = os.getenv("QDRANT_URL")
    if not qdrant_url:
        raise RuntimeError("QDRANT_URL is not set.")

    plug = resolve_model_plug(
        plug_name=os.getenv("OPENROUTER_MODEL_PLUG"),
        model_override=os.getenv("OPENROUTER_MODEL"),
        fallbacks_override=_parse_fallbacks(os.getenv("OPENROUTER_MODEL_FALLBACKS")),
    )

    return Settings(
        openrouter_api_key=api_key,
        model_plug=plug.name,
        model=plug.model,
        model_fallbacks=plug.fallbacks,
        model_provider=plug.provider,
        base_url=os.getenv("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL),
        database_url=async_database_url,
        database_connect_args=database_connect_args,
        qdrant_url=qdrant_url,
        qdrant_api_key=os.getenv("QDRANT_API_KEY"),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", DEFAULT_QDRANT_COLLECTION),
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_key=os.getenv("SUPABASE_KEY"),
        supabase_bucket=os.getenv("SUPABASE_BUCKET", "documents"),
        storage_backend=os.getenv("STORAGE_BACKEND", "supabase"),
        local_storage_dir=os.getenv("LOCAL_STORAGE_DIR", DEFAULT_LOCAL_STORAGE_DIR),
        traces_dir=os.getenv("TRACES_DIR", DEFAULT_TRACES_DIR),
    )
