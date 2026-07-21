import json
import re

from pydantic import BaseModel, ValidationError

from examples.reference_runtime.errors import ModelStructuredOutputError, ModelValidationError

_FENCE_RE = re.compile(
    r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```",
    re.DOTALL | re.IGNORECASE,
)


def _extract_json_text(content: str) -> str:
    """Best-effort extraction of a JSON document from model text."""
    text = content.strip()
    if not text:
        return text

    fenced = _FENCE_RE.search(text)
    if fenced is not None:
        return fenced.group(1).strip()

    if text.startswith("{") or text.startswith("["):
        return text

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return text


def parse_structured[T: BaseModel](
    content: str,
    model_type: type[T],
    request_id: str,
) -> T:
    candidate = _extract_json_text(content)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ModelStructuredOutputError(
            f"Request {request_id}: Model did not return valid JSON. "
            f"Raw content: {content!r}"
        ) from exc

    if not isinstance(data, dict):
        raise ModelStructuredOutputError(
            f"Request {request_id}: Expected a JSON object, got {type(data).__name__}."
        )

    try:
        return model_type.model_validate(data)
    except ValidationError as exc:
        raise ModelValidationError(
            f"Request {request_id}: {model_type.__name__} JSON failed validation: {exc}"
        ) from exc
