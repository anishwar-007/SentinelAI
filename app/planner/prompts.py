def plan_user_query_prompt(user_query: str) -> str:
    return f"""You are a routing planner for an AI application.

Decide which capability should handle the user query.

Capabilities:
- "chat": general questions, conversation, jokes, explanations,
  and anything that does not need uploaded documents or invoice extraction
- "invoice_extraction": the user wants invoice fields extracted from text,
  or the query itself looks like invoice content
- "retrieval": the user asks about information that should be looked up from
  indexed documents / a knowledge base (e.g. "according to the docs",
  "what's in our handbook", questions about uploaded policies or content)

Return ONLY a single valid JSON object. Do not explain. Do not wrap the JSON
in markdown fences or any other text.

The JSON object must contain exactly these keys:
- "intent": "chat" or "invoice_extraction" or "retrieval"
- "confidence": number between 0 and 1
- "reasoning": short string explaining the choice

User query:
\"\"\"
{user_query}
\"\"\"
"""
