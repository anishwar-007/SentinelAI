import json
from datetime import UTC, datetime
from uuid import UUID

from sentinelai.contracts import Trace
from sentinelai.ports.storage import StorageProvider
from sentinelai.repositories.trace_repository import (
    SpanRecord,
    TraceRecord,
    TraceRepository,
)


class TracePersister:
    """Persist trace metadata in PostgreSQL and full JSON in object storage."""

    def __init__(
        self,
        traces: TraceRepository,
        storage: StorageProvider,
    ) -> None:
        self._traces = traces
        self._storage = storage

    async def persist(self, trace: Trace, execution_id: UUID) -> str:
        storage_path = f"traces/{trace.trace_id}.json"
        await self._storage.upload(
            storage_path,
            trace.model_dump_json(indent=2).encode("utf-8"),
            content_type="application/json",
        )

        trace_id = UUID(trace.trace_id)
        span_records: list[SpanRecord] = []
        for span in trace.spans:
            tokens = span.tokens or {}
            parent_id = UUID(span.parent_span_id) if span.parent_span_id else None
            span_records.append(
                SpanRecord(
                    span_id=UUID(span.id),
                    trace_id=trace_id,
                    parent_span_id=parent_id,
                    span_type=span.name,
                    latency_ms=span.latency_ms,
                    model=span.model,
                    tokens_input=_token_value(tokens, "prompt_tokens"),
                    tokens_output=_token_value(tokens, "completion_tokens"),
                    status=span.status,
                    error=span.error,
                    started_at=span.start_time,
                    ended_at=span.end_time,
                )
            )

        await self._traces.create(
            TraceRecord(
                trace_id=trace_id,
                execution_id=execution_id,
                status="completed",
                span_count=len(trace.spans),
                latency_ms=trace.total_latency_ms,
                storage_path=storage_path,
                created_at=trace.started_at or datetime.now(UTC),
            ),
            span_records,
        )
        return storage_path

    async def load(self, trace_id: UUID) -> dict[str, object]:
        record = await self._traces.get(trace_id)
        storage_path = (
            record.storage_path if record is not None else f"traces/{trace_id}.json"
        )
        try:
            raw = await self._storage.download(storage_path)
        except Exception as exc:
            raise FileNotFoundError(str(trace_id)) from exc

        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError(f"Trace JSON is corrupt: {trace_id}")
        return data


def _token_value(tokens: dict[str, object], key: str) -> int | None:
    value = tokens.get(key)
    if isinstance(value, int):
        return value
    return None
