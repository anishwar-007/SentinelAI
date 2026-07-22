from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from sentinelai_platform.api.cors import configure_cors
from sentinelai_platform.api.demo import router as demo_router
from sentinelai_platform.api.errors import (
    ExecutionNotFoundError,
    InvalidFilterError,
    PlatformError,
    TraceNotFoundError,
)
from sentinelai_platform.api.router import router
from sentinelai_platform.api.v1 import router as v1_router


def create_app(
    *,
    title: str = "SentinelAI",
    version: str = "2.0.0",
    lifespan: Any = None,
    dashboard_origins: Sequence[str] | None = None,
) -> FastAPI:
    """Create a FastAPI app exposing SentinelAI Platform read APIs."""

    @asynccontextmanager
    async def _default_lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield

    app = FastAPI(
        title=title,
        description="AI Execution Intelligence Platform",
        version=version,
        lifespan=lifespan or _default_lifespan,
    )
    register_exception_handlers(app)
    configure_cors(
        app,
        origins=list(dashboard_origins) if dashboard_origins is not None else None,
    )
    app.include_router(router)
    app.include_router(v1_router)
    app.include_router(demo_router)

    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        _request: Request,
        _exc: Exception,
    ) -> JSONResponse:
        # Standalone Platform app only — do not register this when composing
        # into a customer runtime that owns its own Exception handler.
        return JSONResponse(
            status_code=500,
            content={"detail": "Unexpected Platform error."},
        )

    return app


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ExecutionNotFoundError)
    async def execution_not_found_handler(
        _request: Request,
        exc: ExecutionNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(TraceNotFoundError)
    async def trace_not_found_handler(
        _request: Request,
        exc: TraceNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvalidFilterError)
    async def invalid_filter_handler(
        _request: Request,
        exc: InvalidFilterError,
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(PlatformError)
    async def platform_error_handler(
        _request: Request,
        exc: PlatformError,
    ) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": str(exc)})
