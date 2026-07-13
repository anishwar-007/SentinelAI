import time
import uuid
from types import TracebackType

import httpx

from app.config import OPENROUTER_BASE_URL
from app.errors import (
    LLMError,
    ModelAuthenticationError,
    ModelRateLimitError,
    ModelStructuredOutputError,
    ModelTimeoutError,
    ModelUnavailableError,
    ModelValidationError,
)
from app.schemas import ChatMessage, LLMResponse
from app.tracing.decorators import trace_span

__all__ = [
    "LLMError",
    "ModelAuthenticationError",
    "ModelRateLimitError",
    "ModelStructuredOutputError",
    "ModelTimeoutError",
    "ModelUnavailableError",
    "ModelValidationError",
    "OpenRouterClient",
]


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = OPENROUTER_BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout = timeout
        self._http = httpx.AsyncClient(timeout=timeout)

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

    def _build_payload(self, prompt: str) -> dict[str, object]:
        user_message = ChatMessage(role="user", content=prompt)
        return {
            "model": self._model,
            "messages": [user_message.model_dump()],
        }

    @trace_span("llm.generate")
    async def generate(self, prompt: str) -> LLMResponse:
        request_id = str(uuid.uuid4())
        url = f"{self._base_url}/chat/completions"
        headers = self._build_headers()
        payload = self._build_payload(prompt)

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
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError(
                f"Request {request_id}: Could not parse response: {exc}"
            ) from exc

        return LLMResponse(
            request_id=request_id,
            model=data.get("model", self._model),
            response=content,
            usage=data.get("usage", {}),
            latency_ms=latency_ms,
            raw_response=data,
        )
