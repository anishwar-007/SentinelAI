"""CORS configuration for the separate Dashboard application."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

DASHBOARD_ORIGINS_ENV = "SENTINELAI_DASHBOARD_ORIGINS"


def parse_dashboard_origins(raw: str | None = None) -> list[str]:
    """Parse comma-separated dashboard origins from env (or ``raw``)."""
    value = raw if raw is not None else os.getenv(DASHBOARD_ORIGINS_ENV, "")
    return [origin.strip() for origin in value.split(",") if origin.strip()]


def configure_cors(
    app: FastAPI,
    *,
    origins: list[str] | None = None,
) -> list[str]:
    """Attach CORS middleware when at least one dashboard origin is configured.

    Returns the effective allowlist (empty when CORS is not enabled).
    """
    allow_origins = list(origins) if origins is not None else parse_dashboard_origins()
    if not allow_origins:
        return []

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    return allow_origins
