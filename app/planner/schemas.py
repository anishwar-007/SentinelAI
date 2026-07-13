from typing import Literal

from pydantic import BaseModel, Field


class Plan(BaseModel):

    intent: Literal["chat", "invoice_extraction"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
