from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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
    """Normalize Neon/libpq URLs for SQLAlchemy + asyncpg."""
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
