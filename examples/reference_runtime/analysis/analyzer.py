import json
from typing import Any

from examples.reference_runtime.analysis.prompts import root_cause_analysis_prompt
from examples.reference_runtime.analysis.schemas import ComponentConfidence, RootCauseAnalysis
from examples.reference_runtime.llm import OpenRouterClient
from examples.reference_runtime.planner.schemas import Plan
from examples.reference_runtime.structured import parse_structured
from examples.reference_runtime.verifier.schemas import VerificationResult
from sentinelai import observe
from sentinelai.contracts import Trace


class RootCauseAnalyzer:
    def __init__(self, client: OpenRouterClient) -> None:
        self._client = client

    @observe("root_cause_analysis", capture="analysis", prompt_keys="analyzer")
    async def analyze(
        self,
        *,
        query: str,
        plan: Plan,
        retrieved_context: str | None,
        answer: str,
        verification: VerificationResult | None,
        trace: Trace,
    ) -> RootCauseAnalysis:
        prompt = root_cause_analysis_prompt(
            query=query,
            plan_json=plan.model_dump_json(),
            retrieved_context=retrieved_context or "",
            answer=answer,
            verification_json=_dump_optional(verification),
            trace_json=json.dumps(_trace_snapshot(trace), indent=2),
        )
        result = await self._client.generate(prompt)
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


def _trace_snapshot(trace: Trace) -> dict[str, Any]:
    return {
        "trace_id": trace.trace_id,
        "metadata": trace.metadata,
        "spans": [
            {
                "name": span.name,
                "status": span.status,
                "latency_ms": span.latency_ms,
                "model": span.model,
                "tokens": span.tokens,
                "error": span.error,
                "parent_span_id": span.parent_span_id,
            }
            for span in trace.spans
        ],
    }
