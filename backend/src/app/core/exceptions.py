"""Custom exception classes for the QueryCraft backend."""


class QueryCraftError(Exception):
    """Base exception for all QueryCraft errors."""

    def __init__(self, message: str = "", message_key: str = "", **kwargs):
        super().__init__(message)
        self.message_key = message_key
        self.extra = kwargs


class EvaluatorRejectionError(QueryCraftError):
    """Raised when the evaluator rejects generated SQL."""

    def __init__(self, violations: list | None = None):
        super().__init__(
            message="Evaluator rejected the generated SQL",
            message_key="query.evaluator.rejected",
        )
        self.violations = violations or []


class LLMUnavailableError(QueryCraftError):
    """Raised when the LLM provider is unreachable."""

    def __init__(self, provider: str = ""):
        super().__init__(
            message=f"LLM provider '{provider}' is unavailable",
            message_key="error.llmUnavailable",
            provider=provider,
        )
        self.provider = provider


class QueryTimeoutError(QueryCraftError):
    """Raised when a source-DB query exceeds the configured timeout."""

    def __init__(self, timeout_seconds: int = 0):
        super().__init__(
            message=f"Query timed out after {timeout_seconds}s",
            message_key="error.timeout",
            timeout_seconds=timeout_seconds,
        )
        self.timeout_seconds = timeout_seconds


class ConcurrentSubmissionError(QueryCraftError):
    """Raised when a user tries to submit while another query is processing."""

    def __init__(self):
        super().__init__(
            message="A question is already being processed",
            message_key="error.concurrent",
        )


class AttemptExpiredError(QueryCraftError):
    """Raised when an attempt_id references an expired or missing Redis key."""

    def __init__(self):
        super().__init__(
            message="This query attempt has expired",
            message_key="error.attemptExpired",
        )


class AttemptOwnershipError(QueryCraftError):
    """Raised when session_id doesn't match the attempt's owner."""

    def __init__(self):
        super().__init__(
            message="No active query result to act on",
            message_key="error.attemptInvalid",
        )


class SchemaTokenLimitExceeded(QueryCraftError):
    """Raised when schema token count exceeds MAX_SCHEMA_TOKENS."""

    def __init__(self, tokens: int = 0, limit: int = 0):
        super().__init__(
            message=f"Schema token count ({tokens}) exceeds limit ({limit})",
            message_key="error.schemaTokenLimit",
            tokens=tokens,
            limit=limit,
        )
        self.tokens = tokens
        self.limit = limit
