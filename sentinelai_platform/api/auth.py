"""JWT authentication dependencies for protected Platform APIs."""

from __future__ import annotations

import logging
import os
from typing import Any

import jwt
from fastapi import HTTPException, Request, status
from jwt import InvalidTokenError

_LOGGER = logging.getLogger(__name__)
_AUTH_DISABLED_ENV = "SENTINELAI_AUTH_DISABLED"
_JWT_SECRET_ENV = "SUPABASE_JWT_SECRET"
_SUPABASE_URL_ENV = "SUPABASE_URL"
_DISABLED_VALUES = frozenset({"1", "true", "yes", "on"})


def require_user(request: Request) -> dict[str, Any]:
    """Return validated Supabase JWT claims for a protected request.

    Authentication can only be bypassed when no JWT secret is configured and
    the explicit local-development opt-out is enabled.
    """
    secret = os.getenv(_JWT_SECRET_ENV)
    if not secret:
        if _auth_is_disabled():
            _LOGGER.warning(
                "Platform JWT authentication is disabled by %s; local development only.",
                _AUTH_DISABLED_ENV,
            )
            return {}
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth not configured.",
        )

    token = _bearer_token(request.headers.get("Authorization"))
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    decode_kwargs: dict[str, Any] = {
        "algorithms": ["HS256"],
        "audience": "authenticated",
    }
    issuer = _supabase_issuer()
    if issuer is not None:
        decode_kwargs["issuer"] = issuer

    try:
        claims = jwt.decode(token, secret, **decode_kwargs)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    return dict(claims)


def _bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _auth_is_disabled() -> bool:
    return os.getenv(_AUTH_DISABLED_ENV, "").strip().lower() in _DISABLED_VALUES


def _supabase_issuer() -> str | None:
    url = os.getenv(_SUPABASE_URL_ENV, "").strip().rstrip("/")
    return f"{url}/auth/v1" if url else None


__all__ = ["require_user"]
