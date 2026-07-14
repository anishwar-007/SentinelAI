from typing import Literal

from pydantic import BaseModel, Field


class VerificationScore(BaseModel):
    name: str
    score: float = Field(..., ge=0.0, le=1.0)
    passed: bool
    explanation: str


class VerificationResult(BaseModel):
    verdict: Literal["approved", "needs_revision", "rejected"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    scores: list[VerificationScore] = Field(default_factory=list)
    summary: str
