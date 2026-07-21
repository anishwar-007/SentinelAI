"""SentinelAI instrumentation SDK."""

from sentinelai.contracts import ExecutionSnapshot, ModelInfo, PromptReference
from sentinelai.execution.active import get_active_execution, record_metadata
from sentinelai.execution.context import ExecutionContext, prompt_reference
from sentinelai.execution_stream import ExecutionStream, InMemoryExecutionStream
from sentinelai.plugins import Plugin
from sentinelai.repositories.execution_repository import ExecutionRepository
from sentinelai.repositories.trace_repository import TraceRepository
from sentinelai.sdk.configure import (
    InstrumentationSettings,
    configure,
    get_settings,
    reset_configuration,
)
from sentinelai.sdk.correlation import (
    get_current_execution_id,
    get_current_execution_latency_ms,
    get_current_trace_id,
)
from sentinelai.sdk.instrumentation import Sentinel, execution, span
from sentinelai.sdk.metadata import ExecutionMetadata, ObservedResult
from sentinelai.sdk.observe_execution import observe_execution
from sentinelai.tracing.observe import observe

from . import contracts as Contracts

# Source-compatible names from the pre-freeze API. They are intentionally
# omitted from __all__ and from customer documentation.
_COMPATIBILITY_EXPORTS = (
    ExecutionContext,
    ExecutionMetadata,
    ExecutionRepository,
    ExecutionSnapshot,
    InMemoryExecutionStream,
    InstrumentationSettings,
    ModelInfo,
    ObservedResult,
    PromptReference,
    TraceRepository,
    get_active_execution,
    get_settings,
    observe,
    observe_execution,
    prompt_reference,
    record_metadata,
    reset_configuration,
)

__all__ = [
    "Contracts",
    "ExecutionStream",
    "Plugin",
    "Sentinel",
    "configure",
    "execution",
    "get_current_execution_id",
    "get_current_execution_latency_ms",
    "get_current_trace_id",
    "span",
]

__version__ = "2.0.0"
