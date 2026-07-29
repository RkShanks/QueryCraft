"""Structured logging with structlog and OpenTelemetry bootstrap."""

import logging
import sys
from typing import Any

import structlog
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from app.services.audit_redaction import redact_audit_value

_REDACTED = "[REDACTED]"
_LOG_SENSITIVE_KEY_TOKENS = frozenset(
    {
        "claim",
        "cookie",
        "email",
        "filter",
        "header",
        "host",
        "identity",
        "session",
        "subjectid",
        "url",
        "userid",
        "username",
    }
)
_LOG_TRACE_FIELDS = frozenset({"exception", "excinfo", "stack", "stackinfo"})
_LOG_SAFE_FIELDS = frozenset({"count", "durationms", "errorcode", "event", "level", "logger", "method", "statuscode"})


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structlog for JSON output with request-correlated context."""

    # Set up OpenTelemetry with a no-op exporter (Phase 1)
    provider = TracerProvider()
    trace.set_tracer_provider(provider)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            redact_log_event,
            structlog.processors.UnicodeDecoder(),
            _add_otel_context,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard logging to route through structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )


def _normalized_log_key(key: str) -> str:
    return "".join(character for character in key.lower() if character.isalnum())


def _is_sensitive_log_key(key: str) -> bool:
    normalized = _normalized_log_key(key)
    if normalized in _LOG_SAFE_FIELDS:
        return False
    return normalized in _LOG_TRACE_FIELDS or any(token in normalized for token in _LOG_SENSITIVE_KEY_TOKENS)


def _redact_log_fields(log_field: Any) -> Any:
    if isinstance(log_field, dict):
        return {
            key: _REDACTED if _is_sensitive_log_key(key) else _redact_log_fields(nested_field)
            for key, nested_field in log_field.items()
        }
    if isinstance(log_field, list):
        return [_redact_log_fields(nested_field) for nested_field in log_field]
    return log_field


def redact_log_event(
    _logger: structlog.types.WrappedLogger,
    _method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Redact sensitive log fields and values before serialization."""
    return redact_audit_value(_redact_log_fields(event_dict))


def _add_otel_context(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Add OpenTelemetry trace/span IDs to log entries."""
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger instance."""
    return structlog.get_logger(name)
