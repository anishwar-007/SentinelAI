from app.llm import OpenRouterClient
from app.prompts import extract_invoice_prompt
from app.schemas import InvoiceExtraction
from app.structured import parse_structured
from app.tracing.decorators import trace_span


class InvoiceExtractor:
    def __init__(self, client: OpenRouterClient) -> None:
        self._client = client

    @trace_span("invoice_extraction")
    async def extract(self, text: str) -> InvoiceExtraction:
        prompt = extract_invoice_prompt(text)
        result = await self._client.generate(prompt)
        return parse_structured(result.response, InvoiceExtraction, result.request_id)
