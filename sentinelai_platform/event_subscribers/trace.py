"""Platform subscriber that persists completed traces."""

import logging

from sentinelai.contracts import Trace
from sentinelai.execution_stream import ExecutionEvent, TraceCompleted
from sentinelai_platform.execution_store import TracePersister

logger = logging.getLogger("sentinelai.platform.event_subscribers")


class TraceCompletedSubscriber:
    def __init__(self, trace_persister: TracePersister) -> None:
        self._trace_persister = trace_persister

    async def handle(self, event: ExecutionEvent) -> None:
        if not isinstance(event, TraceCompleted):
            return
        # Events keep payload frozen (MappingProxy); thaw before domain validate
        # so Trace.model_dump_json does not see non-serializable proxies.
        raw_trace = event.payload_dict().get("trace")
        if raw_trace is None:
            raise ValueError("TraceCompleted payload requires a trace.")
        trace = Trace.model_validate(raw_trace)
        try:
            await self._trace_persister.persist(trace, event.execution_id)
        except Exception:
            # Preserve existing runtime behavior: trace persistence is
            # best-effort and must not fail an otherwise valid execution.
            logger.exception("Failed to persist trace %s", trace.trace_id)
