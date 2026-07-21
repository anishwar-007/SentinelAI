import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from examples.reference_runtime.errors import LLMError
from examples.reference_runtime.retriever.registry import DocumentNotFoundError
from examples.reference_runtime.services.orchestrator import EmptyQueryError

logger = logging.getLogger("tracerai.api")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(EmptyQueryError)
    async def empty_query_handler(
        _request: Request,
        exc: EmptyQueryError,
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(DocumentNotFoundError)
    async def document_not_found_handler(
        _request: Request,
        exc: DocumentNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def value_error_handler(
        _request: Request,
        exc: ValueError,
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": "Invalid request payload."},
        )

    @app.exception_handler(LLMError)
    async def llm_error_handler(
        _request: Request,
        exc: LLMError,
    ) -> JSONResponse:
        logger.exception("LLM request failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "The AI service failed to process the request.",
                "error": str(exc),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        _request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error.", "error": str(exc)},
        )
