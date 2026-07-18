import json

from pydantic import BaseModel, ValidationError

from examples.reference_runtime.errors import ModelStructuredOutputError, ModelValidationError


def parse_structured[T: BaseModel](
    content: str,
    model_type: type[T],
    request_id: str,
) -> T:
    try:
        data = json.loads(content)
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
