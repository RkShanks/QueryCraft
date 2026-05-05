"""Custom exception classes for the QueryCraft backend.

Unified hierarchy (T-128):
- QueryCraftError (base)
  - LLMError
  - EvaluatorError
  - SourceDBError
  - AttemptError
  - SessionError
  - SchemaError

Backward-compatible aliases for US-1 names are provided at module level.
"""


class QueryCraftError(Exception):
    """Base exception for all QueryCraft errors."""

    def __init__(self, message: str = "", message_key: str = "", **kwargs):
        super().__init__(message)
        self.message_key = message_key
        self.extra = kwargs


# ─── LLM ───

class LLMError(QueryCraftError):
    """Base for LLM adapter errors."""


class LLMUnavailable(LLMError):
    """Raised when the LLM provider returns a 5xx or rate-limit (429) response."""

    def __init__(self, provider: str = "", message: str = ""):
        msg = message or (f"LLM provider '{provider}' is unavailable" if provider else "LLM provider is unavailable")
        super().__init__(msg, message_key="error.llmUnavailable", provider=provider)
        self.provider = provider


class LLMTimeout(LLMError):
    """Raised when the LLM request exceeds the configured timeout."""

    def __init__(self, provider: str = "", timeout_s: int = 0):
        super().__init__(
            f"LLM request timed out after {timeout_s}s",
            message_key="error.llmUnavailable",
            provider=provider,
            timeout_s=timeout_s,
        )
        self.provider = provider
        self.timeout_s = timeout_s


class LLMConfigurationError(LLMError):
    """Raised when the factory cannot build an adapter due to missing config."""

    def __init__(self, message: str = "LLM configuration error"):
        super().__init__(message, message_key="error.llmUnavailable")


# ─── Evaluator ───

class EvaluatorError(QueryCraftError):
    """Base for evaluator errors."""


class EvaluatorRejected(EvaluatorError):
    """Raised when the evaluator rejects generated SQL."""

    def __init__(self, failed_rule: str = "", reason: str = ""):
        super().__init__(
            f"Evaluator rejected the generated SQL: {reason}",
            message_key="query.evaluator.rejected",
            failed_rule=failed_rule,
            reason=reason,
        )
        self.failed_rule = failed_rule
        self.reason = reason


# ─── Source DB ───

class SourceDBError(QueryCraftError):
    """Base for source database errors."""


class SourceDBTimeout(SourceDBError):
    """Raised when a source-DB query exceeds the configured timeout."""

    def __init__(self, timeout_seconds: int = 0):
        super().__init__(
            f"Query timed out after {timeout_seconds}s",
            message_key="error.timeout",
            timeout_seconds=timeout_seconds,
        )
        self.timeout_seconds = timeout_seconds


class SourceDBPermissionDenied(SourceDBError):
    """Raised when the source-DB role lacks permission."""

    def __init__(self) -> None:
        super().__init__("Source DB permission denied", message_key="error.forbidden")


class SourceDBConnectionFailed(SourceDBError):
    """Raised when the source-DB connection fails."""

    def __init__(self) -> None:
        super().__init__("Source DB connection failed", message_key="error.llmUnavailable")


# ─── Attempt ───

class AttemptError(QueryCraftError):
    """Base for ephemeral attempt errors."""


class AttemptNotFound(AttemptError):
    """Raised when an attempt_id is not found in Redis."""

    def __init__(self) -> None:
        super().__init__("No active query result to act on", message_key="error.attemptInvalid")


class AttemptExpired(AttemptError):
    """Raised when an attempt_id references an expired Redis key."""

    def __init__(self) -> None:
        super().__init__("This query attempt has expired", message_key="error.attemptExpired")


class AttemptOwnershipViolation(AttemptError):
    """Raised when session_id doesn't match the attempt's owner."""

    def __init__(self) -> None:
        super().__init__("No active query result to act on", message_key="error.attemptInvalid")


# ─── Session ───

class SessionError(QueryCraftError):
    """Base for session errors."""


class SessionBusy(SessionError):
    """Raised when a concurrent submission is detected (Inv 3)."""

    def __init__(self) -> None:
        super().__init__("A question is already being processed", message_key="error.concurrent")


# ─── Schema ───

class SchemaError(QueryCraftError):
    """Base for schema errors."""


class SchemaTokenLimitExceeded(SchemaError):
    """Raised when schema token count exceeds MAX_SCHEMA_TOKENS."""

    def __init__(self, tokens: int = 0, limit: int = 0):
        super().__init__(
            f"Schema token count ({tokens}) exceeds limit ({limit})",
            message_key="error.schemaTokenLimit",
            tokens=tokens,
            limit=limit,
        )
        self.tokens = tokens
        self.limit = limit


# ─── Backward-compatible aliases (US-1 names) ───

EvaluatorRejectionError = EvaluatorRejected
LLMUnavailableError = LLMUnavailable
QueryTimeoutError = SourceDBTimeout
ConcurrentSubmissionError = SessionBusy
AttemptExpiredError = AttemptExpired
AttemptOwnershipError = AttemptOwnershipViolation
