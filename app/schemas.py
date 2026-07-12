from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(...)
    content: str = Field(...)


class LLMResponse(BaseModel):
    request_id: str = Field(...)
    model: str = Field(...)
    response: str = Field(...)
    usage: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float = Field(...)
    raw_response: dict[str, Any] = Field(default_factory=dict)


class InvoiceExtraction(BaseModel):
    """Structured invoice fields extracted from free-form text.

    Every key must be present in the model JSON. Use null when a value
    cannot be determined so callers never guess from missing keys.
    """

    vendor: str | None
    invoice_number: str | None
    amount: float | None
    currency: str | None
    invoice_date: date | None
    due_date: date | None
