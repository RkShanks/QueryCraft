"""Custom exceptions for LLM adapters.

These are created here for adapter use; T-128 will consolidate into core/exceptions.py.
"""


class LLMUnavailable(Exception):
    """Raised when the LLM provider returns a 5xx or rate-limit (429) response."""

    def __init__(self, provider: str = "", message: str = "LLM provider is unavailable"):
        super().__init__(message)
        self.provider = provider


class LLMTimeout(Exception):
    """Raised when the LLM request exceeds the configured timeout."""

    def __init__(self, provider: str = "", timeout_s: int = 0):
        super().__init__(f"LLM request timed out after {timeout_s}s")
        self.provider = provider
        self.timeout_s = timeout_s


class LLMConfigurationError(Exception):
    """Raised when the factory cannot build an adapter due to missing config."""

    def __init__(self, message: str = "LLM configuration error"):
        super().__init__(message)
