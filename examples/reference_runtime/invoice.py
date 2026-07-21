from examples.reference_runtime.llm import LLMClient
from examples.reference_runtime.prompts import extract_invoice_prompt
from examples.reference_runtime.schemas import InvoiceExtraction
from examples.reference_runtime.structured import parse_structured
from sentinelai import span


class InvoiceExtractor:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    @span("invoice_extraction")
    async def extract(self, text: str) -> InvoiceExtraction:
        prompt = extract_invoice_prompt(text)
        result = await self._client.generate(prompt, json_mode=True)
        return parse_structured(result.response, InvoiceExtraction, result.request_id)
