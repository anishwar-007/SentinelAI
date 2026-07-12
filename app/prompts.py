def extract_invoice_prompt(text: str) -> str:
    """Build a prompt that asks the model for invoice fields as JSON only.

    Prompt engineering here is the control surface for structured outputs:
    we specify the exact schema, forbid prose/markdown, and allow nulls so
    the model does not invent values when the source text is incomplete.
    """
    return f"""Extract invoice information from the text below.

Return ONLY a single valid JSON object. Do not explain. Do not wrap the JSON
in markdown fences or any other text.

The JSON object must contain exactly these keys:
- "vendor": string or null
- "invoice_number": string or null
- "amount": number or null
- "currency": string (ISO 4217, e.g. "USD") or null
- "invoice_date": string (YYYY-MM-DD) or null
- "due_date": string (YYYY-MM-DD) or null

Rules:
- Infer currency from symbols when present (e.g. $ means USD).
- Use null when a field is missing or unclear. Never invent values.
- amount must be a JSON number, not a string.

Invoice text:
\"\"\"
{text}
\"\"\"
"""
