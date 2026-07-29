"""Defense-in-depth redaction shared by audit search and export."""

from __future__ import annotations

import base64
import binascii
import html
import re
from typing import Any
from urllib.parse import unquote

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

_NON_SECRET_NORMALIZED: frozenset[str] = frozenset(
    {
        "errorcode",
        "statuscode",
        "postcode",
        "zipcode",
        "hashcode",
    }
)

_REDACTED = "[REDACTED]"
_MAX_DECODE_LENGTH = 8_192
_BASE64_VALUE = re.compile(r"^[A-Za-z0-9+/_=-]+$")

_SENSITIVE_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^[\s\ufeff\x00-\x1f\x7f]*[=+\-@|]"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----|-----BEGIN CERT(?:IFICATE)?-----", re.IGNORECASE),
    re.compile(
        r"\b(?:password|secret|token|api[_-]?key|credential|authorization|"
        r"client[_-]?secret|authorization[_-]?code|samlresponse|assertion)\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:postgresql|postgres|mysql|mssql)(?:\+[a-z0-9_]+)?://\S+", re.IGNORECASE),
    re.compile(r"\b(?:asyncpg|psycopg2|pymysql|pyodbc)\b", re.IGNORECASE),
    re.compile(r"Traceback \(most recent call last\)"),
    re.compile(r"(?:^|\n)\s*at\s+[\w.$<>]+(?:\.[\w$<>]+)*\(.*:\d+\)", re.IGNORECASE),
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b"),
    re.compile(r"\b[a-zA-Z0-9.-]+\.(?:internal|local|corp|com|net|org):\d{2,5}\b", re.IGNORECASE),
    re.compile(r"\b(?:host|hostname|server)\s*[:=]\s*[^\s,;]+", re.IGNORECASE),
    re.compile(r"\b[a-zA-Z0-9.-]+\.(?:internal|local|corp)\b", re.IGNORECASE),
    re.compile(
        r"<(?:samlp?:)?(?:Response|Assertion)\b|<EntityDescriptor\b|<(?:ds:)?X509Certificate\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bignore\s+(?:all\s+)?previous\s+instructions\b|"
        r"\breveal\s+(?:the\s+)?system\s+prompt\b|"
        r"\bbypass\s+(?:rbac|row[- ]level|permission)\b|"
        r"\bdrop\s+(?:table|database|schema)\b",
        re.IGNORECASE,
    ),
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("_", "").replace("-", "")
    if normalized in _NON_SECRET_NORMALIZED:
        return False
    return any(token in normalized for token in _SENSITIVE_TOKENS)


def _decode_base64(value: str) -> str | None:
    candidate = value.strip()
    if not 16 <= len(candidate) <= _MAX_DECODE_LENGTH or not _BASE64_VALUE.fullmatch(candidate):
        return None
    padded = candidate + ("=" * (-len(candidate) % 4))
    try:
        decoded = base64.b64decode(padded, altchars=b"-_", validate=True)
        return decoded.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


def _decoded_variants(value: str) -> set[str]:
    """Return bounded URL/HTML/base64 decoded forms for value inspection."""
    variants = {value}
    frontier = {value}
    for _ in range(2):
        decoded: set[str] = set()
        for candidate in frontier:
            if len(candidate) > _MAX_DECODE_LENGTH:
                continue
            decoded.update({unquote(candidate), html.unescape(candidate)})
            base64_value = _decode_base64(candidate)
            if base64_value is not None:
                decoded.add(base64_value)
        decoded.discard("")
        decoded -= variants
        if not decoded:
            break
        variants.update(decoded)
        frontier = decoded
    return variants


def _is_sensitive_string(value: str) -> bool:
    return any(
        pattern.search(candidate) for candidate in _decoded_variants(value) for pattern in _SENSITIVE_VALUE_PATTERNS
    )


def redact_audit_value(value: Any) -> Any:
    """Recursively redact sensitive keys and secret-shaped string values."""
    if isinstance(value, dict):
        return {key: _REDACTED if _is_sensitive_key(key) else redact_audit_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_audit_value(item) for item in value]
    if isinstance(value, str) and _is_sensitive_string(value):
        return _REDACTED
    return value


def redact_audit_entry(entry: Any) -> dict[str, Any]:
    """Redact every externally visible audit-entry field."""
    values = {
        "sequence_number": entry.sequence_number,
        "timestamp": entry.timestamp,
        "actor_identity": entry.actor_identity,
        "action_type": entry.action_type,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "outcome": entry.outcome,
        "context": entry.context if entry.context is not None else {},
    }
    return redact_audit_value(values)
