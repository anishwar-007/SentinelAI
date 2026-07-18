"""Deprecated compatibility imports.

Import shared DTOs from :mod:`sentinelai.contracts` instead.
"""

from sentinelai.contracts.execution import (
    CURRENT_REPOSITORY_VERSION,
    ExecutionRecord,
    ExecutionSnapshot,
    ExecutionStatus,
    ExecutionSummary,
    ModelInfo,
    PromptReference,
    SnapshotCreationMetrics,
    TerminalExecutionStatus,
)

__all__ = [
    "CURRENT_REPOSITORY_VERSION",
    "ExecutionRecord",
    "ExecutionSnapshot",
    "ExecutionStatus",
    "ExecutionSummary",
    "ModelInfo",
    "PromptReference",
    "SnapshotCreationMetrics",
    "TerminalExecutionStatus",
]
