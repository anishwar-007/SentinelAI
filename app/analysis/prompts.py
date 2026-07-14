def root_cause_analysis_prompt(
    *,
    query: str,
    plan_json: str,
    retrieved_context: str,
    answer: str,
    verification_json: str,
    trace_json: str,
) -> str:
    return f"""You are a root cause analyzer for an AI pipeline.

You do NOT rewrite answers. You analyze where the pipeline likely went wrong
(or why it succeeded) using probabilistic evidence across components.

Pipeline components to score:
- planner
- retriever
- executor
- llm
- verifier
- unknown

For EACH component except unknown (unless nothing else fits), estimate how
likely it contributed to a poor outcome as confidence in [0.0, 1.0], with
short reasoning. Failures often propagate: retrieval can cause LLM hallucination,
so multiple components may share confidence mass.

Then:
- Set primary_component to the component with the highest confidence
- Set confidence to that same highest score
- Choose severity: low | medium | high | critical
- Provide summary, recommendation, and evidence bullets from the inputs
- Include confidence_graph covering at least planner, retriever, llm, verifier

If the request looks successful overall, still produce a confidence_graph,
set primary_component to the least concerning contributor (often "verifier"
or "planner" with low confidence), severity low, and recommend monitoring.

Return ONLY a single valid JSON object. Do not explain. Do not wrap JSON
in markdown fences.

Required keys:
- "primary_component": one of planner|retriever|executor|llm|verifier|unknown
- "severity": low|medium|high|critical
- "confidence": number 0..1
- "summary": string
- "recommendation": string
- "evidence": array of strings
- "confidence_graph": array of objects with
  "component", "confidence", "reasoning"

User query:
\"\"\"
{query}
\"\"\"

Plan JSON:
\"\"\"
{plan_json}
\"\"\"

Retrieved context:
\"\"\"
{retrieved_context or "(none)"}
\"\"\"

Generated answer:
\"\"\"
{answer}
\"\"\"

Verification JSON:
\"\"\"
{verification_json}
\"\"\"

Trace JSON (spans so far):
\"\"\"
{trace_json}
\"\"\"
"""
