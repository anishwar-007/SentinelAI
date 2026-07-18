from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from sentinelai_platform.api.router import (
    ExecutionNotFoundError,
    TraceNotFoundError,
    router,
)


def create_app(
    *,
    title: str = "SentinelAI",
    version: str = "2.0.0",
    lifespan: Any = None,
) -> FastAPI:
    """Create a FastAPI app exposing SentinelAI execution/trace read APIs."""

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
    app.include_router(router)
    return app


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ExecutionNotFoundError)
    async def execution_not_found_handler(
        _request: object,
        exc: ExecutionNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(TraceNotFoundError)
    async def trace_not_found_handler(
        _request: object,
        exc: TraceNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
