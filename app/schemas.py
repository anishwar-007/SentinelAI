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
