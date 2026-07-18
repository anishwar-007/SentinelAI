from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMResponse(BaseModel):
    request_id: str
    model: str
    response: str
    usage: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float
    raw_response: dict[str, Any] = Field(default_factory=dict)


class InvoiceExtraction(BaseModel):
    vendor: str | None
    invoice_number: str | None
    amount: float | None
    currency: str | None
    invoice_date: date | None
    due_date: date | None
