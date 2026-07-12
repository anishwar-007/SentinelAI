import json
import time
import uuid

import httpx
from pydantic import ValidationError

from app.config import OPENROUTER_BASE_URL
from app.prompts import extract_invoice_prompt
from app.schemas import ChatMessage, InvoiceExtraction, LLMResponse


class LLMError(Exception):
    pass


class ModelAuthenticationError(LLMError):
    pass


class ModelRateLimitError(LLMError):
    pass


class ModelTimeoutError(LLMError):
    pass


class ModelUnavailableError(LLMError):
    pass


class ModelStructuredOutputError(LLMError):
    """Raised when the model response is not valid JSON."""


class ModelValidationError(LLMError):
    """Raised when JSON does not match the expected Pydantic schema."""


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

    async def generate(self, prompt: str) -> LLMResponse:
        request_id = str(uuid.uuid4())
        url = f"{self._base_url}/chat/completions"
        headers = self._build_headers()
        payload = self._build_payload(prompt)

        start = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                http_response = await client.post(url, headers=headers, json=payload)
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

    async def extract_invoice(self, text: str) -> InvoiceExtraction:

        prompt = extract_invoice_prompt(text)
        result = await self.generate(prompt)
        return self._parse_invoice_extraction(result.response, result.request_id)

    def _parse_invoice_extraction(
        self,
        content: str,
        request_id: str,
    ) -> InvoiceExtraction:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ModelStructuredOutputError(
                f"Request {request_id}: Model did not return valid JSON. "
                f"Raw content: {content!r}"
            ) from exc

        if not isinstance(data, dict):
            raise ModelStructuredOutputError(
                f"Request {request_id}: Expected a JSON object, got {type(data).__name__}."
            )

        try:
            return InvoiceExtraction.model_validate(data)
        except ValidationError as exc:
            raise ModelValidationError(
                f"Request {request_id}: Invoice JSON failed validation: {exc}"
            ) from exc

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
