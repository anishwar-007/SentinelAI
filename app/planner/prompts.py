def plan_user_query_prompt(user_query: str) -> str:
    return f"""You are a routing planner for an AI application.

Decide which capability should handle the user query.

Capabilities:
- "chat": general questions, conversation, jokes, explanations, anything that is not invoice extraction
- "invoice_extraction": the user wants invoice fields extracted from text, or the query itself looks like invoice content

Return ONLY a single valid JSON object. Do not explain. Do not wrap the JSON
in markdown fences or any other text.

The JSON object must contain exactly these keys:
- "intent": "chat" or "invoice_extraction"
- "confidence": number between 0 and 1
- "reasoning": short string explaining the choice

User query:
\"\"\"
{user_query}
\"\"\"
"""
