class LLMError(Exception):
    pass


class ModelAuthenticationError(LLMError):
    pass


class ModelRateLimitError(LLMError):
    pass


class ModelTimeoutError(LLMError):
    pass


class ModelUnavailableError(LLMError):
    pass


class ModelStructuredOutputError(LLMError):
    pass


class ModelValidationError(LLMError):
    pass
