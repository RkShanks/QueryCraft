"""Defense-in-depth redaction shared by audit search and export."""

from __future__ import annotations

import re
from typing import Any

_SENSITIVE_TOKENS: set[str] = {
    "password",
    "secret",
    "token",
    "apikey",
    "credential",
    "certificate",
    "privatekey",
    "assertion",
    "samlresponse",
    "authorization",
    "encryptionkey",
    "bearer",
    "jwt",
    "nonce",
    "state",
    "code",
    "accesstoken",
    "idtoken",
    "refreshtoken",
}

_REDACTED = "[REDACTED]"

_SENSITIVE_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----|-----BEGIN CERT(?:IFICATE)?-----", re.IGNORECASE),
    re.compile(r"\b(?:password|secret|token|api[_-]?key|credential|authorization)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\b(?:postgresql|postgres|mysql|mssql)://\S+", re.IGNORECASE),
    re.compile(r"\b(?:asyncpg|psycopg2|pymysql|pyodbc)\b", re.IGNORECASE),
    re.compile(r"Traceback \(most recent call last\)"),
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b"),
    re.compile(r"\b[a-zA-Z0-9.-]+\.(?:internal|local|corp|com|net|org):\d{2,5}\b", re.IGNORECASE),
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("_", "").replace("-", "")
    return any(token in normalized for token in _SENSITIVE_TOKENS)


def _is_sensitive_string(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SENSITIVE_VALUE_PATTERNS)


def redact_audit_value(value: Any) -> Any:
    """Recursively redact sensitive keys and secret-shaped string values."""
    if isinstance(value, dict):
        return {key: _REDACTED if _is_sensitive_key(key) else redact_audit_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_audit_value(item) for item in value]
    if isinstance(value, str) and _is_sensitive_string(value):
        return _REDACTED
    return value
