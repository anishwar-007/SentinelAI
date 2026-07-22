"""Platform API error types (mapped to HTTP in exception handlers)."""


class ExecutionNotFoundError(LookupError):
    """Raised when an execution snapshot cannot be found."""


class TraceNotFoundError(LookupError):
    """Raised when a trace cannot be found for the given id/execution."""


class InvalidFilterError(ValueError):
    """Raised when list/query filters are invalid."""


class PlatformError(RuntimeError):
    """Unexpected Platform failure safe to surface as HTTP 500."""
