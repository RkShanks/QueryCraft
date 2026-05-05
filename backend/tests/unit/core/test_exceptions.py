"""T-127 — Custom exceptions tests."""

import pytest

from app.core.exceptions import (
    AttemptError,
    AttemptExpired,
    AttemptNotFound,
    AttemptOwnershipViolation,
    EvaluatorRejected,
    LLMConfigurationError,
    LLMTimeout,
    LLMUnavailable,
    QueryCraftError,
    SchemaTokenLimitExceeded,
    SessionBusy,
    SessionError,
    SourceDBConnectionFailed,
    SourceDBError,
    SourceDBPermissionDenied,
    SourceDBTimeout,
)

# --- Base ---

def test_all_inherit_from_querycraft_error():
    exceptions = [
        LLMUnavailable(),
        LLMTimeout(),
        LLMConfigurationError(),
        EvaluatorRejected(),
        SourceDBTimeout(),
        SourceDBPermissionDenied(),
        SourceDBConnectionFailed(),
        AttemptNotFound(),
        AttemptExpired(),
        AttemptOwnershipViolation(),
        SessionBusy(),
        SchemaTokenLimitExceeded(tokens=100, limit=50),
    ]
    for exc in exceptions:
        assert isinstance(exc, QueryCraftError)
        assert isinstance(exc, Exception)


# --- LLM ---

def test_llm_unavailable_attributes():
    exc = LLMUnavailable(provider="anthropic")
    assert exc.provider == "anthropic"
    assert "anthropic" in str(exc)


def test_llm_timeout_attributes():
    exc = LLMTimeout(provider="openai", timeout_s=30)
    assert exc.provider == "openai"
    assert exc.timeout_s == 30


def test_llm_configuration_error_attributes():
    exc = LLMConfigurationError("Missing API key")
    assert "Missing API key" in str(exc)


# --- Evaluator ---

def test_evaluator_rejected_attributes():
    exc = EvaluatorRejected(failed_rule="read_only", reason="INSERT detected")
    assert exc.failed_rule == "read_only"
    assert exc.reason == "INSERT detected"


# --- Source DB ---

def test_source_db_timeout_attributes():
    exc = SourceDBTimeout(timeout_seconds=30)
    assert exc.timeout_seconds == 30


def test_source_db_permission_denied_attributes():
    exc = SourceDBPermissionDenied()
    assert isinstance(exc, SourceDBError)


def test_source_db_connection_failed_attributes():
    exc = SourceDBConnectionFailed()
    assert isinstance(exc, SourceDBError)


# --- Attempt ---

def test_attempt_not_found():
    exc = AttemptNotFound()
    assert isinstance(exc, AttemptError)


def test_attempt_expired():
    exc = AttemptExpired()
    assert isinstance(exc, AttemptError)


def test_attempt_ownership_violation():
    exc = AttemptOwnershipViolation()
    assert isinstance(exc, AttemptError)


# --- Session ---

def test_session_busy():
    exc = SessionBusy()
    assert isinstance(exc, SessionError)


# --- Schema ---

def test_schema_token_limit_exceeded():
    exc = SchemaTokenLimitExceeded(tokens=100, limit=50)
    assert exc.tokens == 100
    assert exc.limit == 50


# --- Chained exceptions ---

def test_chained_exception_preserves_traceback():
    try:
        try:
            raise ValueError("original")
        except ValueError as e:
            raise LLMUnavailable(provider="test") from e
    except LLMUnavailable as caught:
        assert caught.__cause__ is not None
        assert isinstance(caught.__cause__, ValueError)


# --- Catch by base class ---

def test_catch_by_base_class():
    with pytest.raises(QueryCraftError):
        raise LLMUnavailable()
    with pytest.raises(QueryCraftError):
        raise EvaluatorRejected()
    with pytest.raises(QueryCraftError):
        raise SourceDBTimeout()
    with pytest.raises(QueryCraftError):
        raise AttemptExpired()
    with pytest.raises(QueryCraftError):
        raise SessionBusy()
    with pytest.raises(QueryCraftError):
        raise SchemaTokenLimitExceeded(tokens=1, limit=0)
