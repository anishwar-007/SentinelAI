import json
from collections.abc import Mapping
from typing import Any

from examples.reference_runtime.analysis.prompts import root_cause_analysis_prompt
from examples.reference_runtime.analysis.schemas import ComponentConfidence, RootCauseAnalysis
from examples.reference_runtime.llm import LLMClient
from examples.reference_runtime.planner.schemas import Plan
from examples.reference_runtime.structured import parse_structured
from examples.reference_runtime.verifier.schemas import VerificationResult
from sentinelai import span


class RootCauseAnalyzer:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    @span("root_cause_analysis")
    async def analyze(
        self,
        *,
        query: str,
        plan: Plan,
        retrieved_context: str | None,
        answer: str,
        verification: VerificationResult | None,
        trace_snapshot: Mapping[str, Any] | None = None,
    ) -> RootCauseAnalysis:
        prompt = root_cause_analysis_prompt(
            query=query,
            plan_json=plan.model_dump_json(),
            retrieved_context=retrieved_context or "",
            answer=answer,
            verification_json=_dump_optional(verification),
            trace_json=json.dumps(_trace_snapshot(trace_snapshot), indent=2),
        )
        result = await self._client.generate(prompt, json_mode=True)
        analysis = parse_structured(
            result.response,
            RootCauseAnalysis,
            result.request_id,
        )
        return _align_primary_component(analysis)


def unknown_analysis(reason: str) -> RootCauseAnalysis:
    return RootCauseAnalysis(
        primary_component="unknown",
        severity="low",
        confidence=0.0,
        summary="Root cause analysis was unavailable.",
        recommendation="Inspect the saved trace manually and retry analysis later.",
        evidence=[reason],
        confidence_graph=[
            ComponentConfidence(
                component="unknown",
                confidence=1.0,
                reasoning=reason,
            )
        ],
    )


def _align_primary_component(analysis: RootCauseAnalysis) -> RootCauseAnalysis:
    if not analysis.confidence_graph:
        return analysis

    best = max(analysis.confidence_graph, key=lambda item: item.confidence)
    return analysis.model_copy(
        update={
            "primary_component": best.component,
            "confidence": best.confidence,
        }
    )


def _dump_optional(value: VerificationResult | None) -> str:
    if value is None:
        return "(none)"
    return value.model_dump_json()


def _trace_snapshot(trace: Mapping[str, Any] | None) -> dict[str, Any]:
    if trace is None:
        return {}
    spans = trace.get("spans")
    span_items = spans if isinstance(spans, list) else []
    return {
        "trace_id": trace.get("trace_id"),
        "metadata": trace.get("metadata", {}),
        "spans": [
            {
                "name": item.get("name"),
                "status": item.get("status"),
                "latency_ms": item.get("latency_ms"),
                "model": item.get("model"),
                "tokens": item.get("tokens"),
                "error": item.get("error"),
                "parent_span_id": item.get("parent_span_id"),
            }
            for item in span_items
            if isinstance(item, dict)
        ],
    }
