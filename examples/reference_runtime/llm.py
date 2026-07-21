import time
import uuid
from collections.abc import Sequence
from types import TracebackType
from typing import Protocol

import httpx

from examples.reference_runtime.config import OPENROUTER_BASE_URL, Settings
from examples.reference_runtime.errors import (
    LLMError,
    ModelAuthenticationError,
    ModelRateLimitError,
    ModelStructuredOutputError,
    ModelTimeoutError,
    ModelUnavailableError,
    ModelValidationError,
)
from examples.reference_runtime.schemas import ChatMessage, LLMResponse
from sentinelai import span

__all__ = [
    "LLMClient",
    "LLMError",
    "ModelAuthenticationError",
    "ModelRateLimitError",
    "ModelStructuredOutputError",
    "ModelTimeoutError",
    "ModelUnavailableError",
    "ModelValidationError",
    "OpenRouterClient",
    "create_llm_client",
]


class LLMClient(Protocol):
    """Provider-agnostic chat client used by planner / executor / verifier."""

    async def generate(self, prompt: str, *, json_mode: bool = False) -> LLMResponse: ...

    async def aclose(self) -> None: ...


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        fallbacks: Sequence[str] = (),
        base_url: str = OPENROUTER_BASE_URL,
        timeout: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._fallbacks = tuple(fallbacks)
        self._base_url = base_url
        self._timeout = timeout
        self._http = httpx.AsyncClient(timeout=timeout)

    @property
    def model(self) -> str:
        return self._model

    @property
    def fallbacks(self) -> tuple[str, ...]:
        return self._fallbacks

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "OpenRouterClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost",
            "X-Title": "AI Observability Platform",
        }

    def _build_payload(self, prompt: str, *, json_mode: bool = False) -> dict[str, object]:
        user_message = ChatMessage(role="user", content=prompt)
        payload: dict[str, object] = {
            "model": self._model,
            "messages": [user_message.model_dump()],
        }
        # OpenRouter model-layer failover: try next model on rate limit / downtime.
        if self._fallbacks:
            payload["models"] = list(self._fallbacks)
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    @span("llm.generate")
    async def generate(self, prompt: str, *, json_mode: bool = False) -> LLMResponse:
        request_id = str(uuid.uuid4())
        url = f"{self._base_url}/chat/completions"
        headers = self._build_headers()
        payload = self._build_payload(prompt, json_mode=json_mode)

        start = time.perf_counter()

        try:
            http_response = await self._http.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ModelTimeoutError(
                f"Request {request_id} timed out after {self._timeout}s."
            ) from exc
        except httpx.RequestError as exc:
            raise ModelUnavailableError(
                f"Request {request_id} network error: {exc}"
            ) from exc

        latency_ms = (time.perf_counter() - start) * 1000

        self._raise_for_status(http_response, request_id)
        return self._parse_response(http_response, request_id, latency_ms)

    def _raise_for_status(self, http_response: httpx.Response, request_id: str) -> None:
        status = http_response.status_code

        if status == 200:
            return
        if status == 401:
            raise ModelAuthenticationError(
                f"Request {request_id}: Unauthorized (401). Check your API key."
            )
        if status == 429:
            raise ModelRateLimitError(
                f"Request {request_id}: Rate limited (429). Slow down and retry."
            )
        if status >= 500:
            raise ModelUnavailableError(
                f"Request {request_id}: Server error ({status}). Try again later."
            )

        raise LLMError(
            f"Request {request_id}: Unexpected response ({status}): {http_response.text}"
        )

    def _parse_response(
        self,
        http_response: httpx.Response,
        request_id: str,
        latency_ms: float,
    ) -> LLMResponse:
        try:
            data = http_response.json()
        except ValueError as exc:
            raise LLMError(
                f"Request {request_id}: Response was not valid JSON."
            ) from exc

        # OpenRouter free models often return HTTP 200 with an error object
        # and no choices (rate limit, provider overload, etc.).
        if isinstance(data, dict) and "error" in data and "choices" not in data:
            error = data["error"]
            if isinstance(error, dict):
                message = str(error.get("message") or error)
                code = error.get("code")
            else:
                message = str(error)
                code = None
            detail = f"Request {request_id}: Upstream model error"
            if code is not None:
                detail += f" ({code})"
            detail += f": {message}"
            if code in {429, "429"} or "rate" in message.lower():
                raise ModelRateLimitError(detail)
            raise ModelUnavailableError(detail)

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(
                f"Request {request_id}: Could not parse response "
                f"(missing choices): {data!r}"
            ) from exc

        if not isinstance(content, str):
            raise LLMError(
                f"Request {request_id}: Model returned non-text content: {content!r}"
            )

        return LLMResponse(
            request_id=request_id,
            model=data.get("model", self._model),
            response=content,
            usage=data.get("usage", {}),
            latency_ms=latency_ms,
            raw_response=data,
        )


def create_llm_client(settings: Settings) -> OpenRouterClient:
    """Build the configured LLM client from settings (plug-and-play entrypoint)."""
    if settings.model_provider != "openrouter":
        raise ValueError(
            f"Unsupported model provider {settings.model_provider!r}. "
            "Add a client factory branch for new providers."
        )
    return OpenRouterClient(
        api_key=settings.openrouter_api_key,
        model=settings.model,
        fallbacks=settings.model_fallbacks,
        base_url=settings.base_url,
    )
