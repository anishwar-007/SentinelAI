from __future__ import annotations

import pytest
from pydantic import BaseModel

from examples.reference_runtime.errors import ModelStructuredOutputError
from examples.reference_runtime.structured import parse_structured


class _Sample(BaseModel):
    intent: str
    confidence: float


def test_parse_structured_accepts_raw_json() -> None:
    result = parse_structured(
        '{"intent":"chat","confidence":0.9}',
        _Sample,
        "req-1",
    )
    assert result.intent == "chat"
    assert result.confidence == 0.9


def test_parse_structured_extracts_fenced_json() -> None:
    result = parse_structured(
        'Here you go:\n```json\n{"intent":"retrieval","confidence":0.8}\n```\n',
        _Sample,
        "req-2",
    )
    assert result.intent == "retrieval"


def test_parse_structured_rejects_safety_classifier_text() -> None:
    with pytest.raises(ModelStructuredOutputError, match="did not return valid JSON"):
        parse_structured("User Safety: safe", _Sample, "req-3")
