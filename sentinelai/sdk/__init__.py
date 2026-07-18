"""Convenience re-exports matching the documented SDK surface."""

from sentinelai.contracts import ExecutionSnapshot, ModelInfo, PromptReference
from sentinelai.execution.active import get_active_execution, record_metadata
from sentinelai.execution.context import ExecutionContext, prompt_reference
from sentinelai.execution_stream import ExecutionStream, InMemoryExecutionStream
from sentinelai.repositories.execution_repository import ExecutionRepository
from sentinelai.repositories.trace_repository import TraceRepository
from sentinelai.sdk.configure import (
    InstrumentationSettings,
    configure,
    get_settings,
    reset_configuration,
)
from sentinelai.sdk.metadata import ExecutionMetadata, ObservedResult
from sentinelai.sdk.observe_execution import observe_execution
from sentinelai.tracing.observe import observe

__all__ = [
    "ExecutionContext",
    "ExecutionMetadata",
    "ExecutionRepository",
    "ExecutionSnapshot",
    "ExecutionStream",
    "InMemoryExecutionStream",
    "InstrumentationSettings",
    "ModelInfo",
    "ObservedResult",
    "PromptReference",
    "TraceRepository",
    "configure",
    "get_active_execution",
    "get_settings",
    "observe",
    "observe_execution",
    "prompt_reference",
    "record_metadata",
    "reset_configuration",
]
