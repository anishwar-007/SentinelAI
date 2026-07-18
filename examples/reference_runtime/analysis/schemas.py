from typing import Literal

from pydantic import BaseModel, Field

PipelineComponent = Literal[
    "planner",
    "retriever",
    "executor",
    "llm",
    "verifier",
    "unknown",
]
Severity = Literal["low", "medium", "high", "critical"]


class ComponentConfidence(BaseModel):
    component: PipelineComponent
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str


class RootCauseAnalysis(BaseModel):
    primary_component: PipelineComponent
    severity: Severity
    confidence: float = Field(..., ge=0.0, le=1.0)
    summary: str
    recommendation: str
    evidence: list[str] = Field(default_factory=list)
    confidence_graph: list[ComponentConfidence] = Field(default_factory=list)
