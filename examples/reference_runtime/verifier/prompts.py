def verification_prompt(query: str, context: str, answer: str) -> str:
    context_block = context.strip() if context.strip() else "(No retrieved context was provided.)"
    return f"""You are an answer verifier for an AI platform.

You do NOT write a new answer. You only evaluate the given answer.

Evaluate the answer against the user query and retrieved context.

Dimensions to score (each score must be between 0.0 and 1.0):
- Groundedness: are claims supported by the retrieved context?
- Completeness: does the answer address the user query?
- Hallucination: high score means little/no fabrication; low score means unsupported claims
- Relevance: is the answer on-topic for the query?

For Hallucination, passed=true means the answer does NOT appear to hallucinate.

Verdict rules:
- approved: answer is usable with minor or no issues
- needs_revision: usable but has notable gaps or weak support
- rejected: serious unsupported claims or fails the query

Return ONLY a single valid JSON object. Do not explain. Do not wrap the JSON
in markdown fences or any other text.

The JSON object must contain exactly these keys:
- "verdict": "approved" or "needs_revision" or "rejected"
- "confidence": number between 0 and 1
- "summary": short overall evaluation string
- "scores": array of objects with keys
  "name", "score", "passed", "explanation"

Include at least the Groundedness, Completeness, Hallucination, and Relevance scores.

User query:
\"\"\"
{query}
\"\"\"

Retrieved context:
\"\"\"
{context_block}
\"\"\"

Generated answer:
\"\"\"
{answer}
\"\"\"
"""
