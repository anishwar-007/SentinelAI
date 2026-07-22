"""JWT authentication dependencies for protected Platform APIs."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

import jwt
from fastapi import HTTPException, Request, status
from jwt import InvalidTokenError, PyJWKClient

_LOGGER = logging.getLogger(__name__)
_AUTH_DISABLED_ENV = "SENTINELAI_AUTH_DISABLED"
_JWT_SECRET_ENV = "SUPABASE_JWT_SECRET"
_SUPABASE_URL_ENV = "SUPABASE_URL"
_DISABLED_VALUES = frozenset({"1", "true", "yes", "on"})
_ASYMMETRIC_ALGS = frozenset({"ES256", "RS256", "EdDSA"})


def require_user(request: Request) -> dict[str, Any]:
    """Return validated Supabase JWT claims for a protected request.

    Supports:
    - Legacy HS256 tokens verified with ``SUPABASE_JWT_SECRET``
    - Asymmetric tokens (ES256/RS256/…) verified via Supabase JWKS

    Authentication can only be bypassed when no auth material is configured and
    the explicit local-development opt-out is enabled.
    """
    secret = os.getenv(_JWT_SECRET_ENV, "").strip() or None
    supabase_url = os.getenv(_SUPABASE_URL_ENV, "").strip().rstrip("/") or None

    if not secret and not supabase_url:
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

    try:
        claims = _decode_access_token(
            token,
            secret=secret,
            supabase_url=supabase_url,
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    return dict(claims)


def _decode_access_token(
    token: str,
    *,
    secret: str | None,
    supabase_url: str | None,
) -> dict[str, Any]:
    header = jwt.get_unverified_header(token)
    alg = str(header.get("alg") or "")
    issuer = f"{supabase_url}/auth/v1" if supabase_url else None
    decode_kwargs: dict[str, Any] = {"audience": "authenticated"}
    if issuer is not None:
        decode_kwargs["issuer"] = issuer

    if alg in _ASYMMETRIC_ALGS:
        if not supabase_url:
            raise InvalidTokenError(
                "Asymmetric JWT requires SUPABASE_URL for JWKS verification.",
            )
        signing_key = _jwks_client(supabase_url).get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=list(_ASYMMETRIC_ALGS),
            **decode_kwargs,
        )

    if not secret:
        raise InvalidTokenError(
            "HS256 JWT requires SUPABASE_JWT_SECRET.",
        )
    return jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        **decode_kwargs,
    )


@lru_cache(maxsize=4)
def _jwks_client(supabase_url: str) -> PyJWKClient:
    return PyJWKClient(
        f"{supabase_url}/auth/v1/.well-known/jwks.json",
        cache_keys=True,
        lifespan=3600,
    )


def _bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _auth_is_disabled() -> bool:
    return os.getenv(_AUTH_DISABLED_ENV, "").strip().lower() in _DISABLED_VALUES


__all__ = ["require_user"]
