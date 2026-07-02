"""AuditExportService — CSV and JSON export of audit log entries.

T-865.

Constraints (from tasks.md and orchestration-log.md):
- Export output must pass a central redaction pass before serialization.
- CSV formula injection prevention: tab-prefix cells starting with =, +, -, @, |.
- CSV metadata header row must include:
  export_actor, export_timestamp, filter_summary, record_count, checksum.
- JSON output wraps entries in {"metadata": {...}, "entries": [...]}.
- Checksum must be SHA-256 of the data payload (non-comment CSV lines / JSON entries
  section), NOT of mutable wrapper/header text.
- Enforce 50_000 export limit; raise ExportLimitExceededError when exceeded.
- No raw sensitive values in export output, even if stored audit context contains one.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from typing import Any

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ExportLimitExceededError(Exception):
    """Raised when the number of entries to export exceeds EXPORT_LIMIT."""

    def __init__(self, count: int, limit: int = 50_000) -> None:
        super().__init__(f"Export limit exceeded: requested {count} entries but limit is {limit}.")
        self.count = count
        self.limit = limit


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPORT_LIMIT: int = 50_000

#: Cell prefixes that must be tab-prefixed to prevent CSV formula injection.
_FORMULA_PREFIXES: tuple[str, ...] = ("=", "+", "-", "@", "|")

#: CSV column order for audit entry rows.
_CSV_COLUMNS: tuple[str, ...] = (
    "sequence_number",
    "timestamp",
    "actor_identity",
    "action_type",
    "resource_type",
    "resource_id",
    "outcome",
    "context",
)


# ---------------------------------------------------------------------------
# Redaction helpers
# ---------------------------------------------------------------------------

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


def redact_audit_export_value(value: Any) -> Any:
    """Recursively redact sensitive audit export keys and obvious secret-shaped values."""
    if isinstance(value, dict):
        return {k: _REDACTED if _is_sensitive_key(k) else redact_audit_export_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_audit_export_value(i) for i in value]
    if isinstance(value, str) and _is_sensitive_string(value):
        return _REDACTED
    return value


def _redact_entry_context(entry: Any) -> dict:
    """Apply redaction to an entry's context dict."""
    ctx = entry.context if entry.context is not None else {}
    return redact_audit_export_value(ctx)


# ---------------------------------------------------------------------------
# Formula injection prevention
# ---------------------------------------------------------------------------


def _safe_csv_cell(value: str) -> str:
    """Tab-prefix string cells that start with formula injection characters."""
    if value and value[0] in _FORMULA_PREFIXES:
        return "\t" + value
    return value


def _entry_to_csv_row(entry: Any, redacted_context: dict) -> list[str]:
    """Convert a single entry to a CSV row, applying formula injection prevention."""
    raw_values: dict[str, str] = {
        "sequence_number": str(entry.sequence_number),
        "timestamp": str(entry.timestamp),
        "actor_identity": str(entry.actor_identity) if entry.actor_identity is not None else "",
        "action_type": str(entry.action_type),
        "resource_type": str(entry.resource_type) if entry.resource_type is not None else "",
        "resource_id": str(entry.resource_id) if entry.resource_id is not None else "",
        "outcome": str(entry.outcome),
        "context": json.dumps(redacted_context, sort_keys=True),
    }
    return [_safe_csv_cell(raw_values[col]) for col in _CSV_COLUMNS]


# ---------------------------------------------------------------------------
# AuditExportService
# ---------------------------------------------------------------------------


class AuditExportService:
    """Export audit entries to CSV or JSON with redaction and integrity metadata."""

    @staticmethod
    def export_csv(entries: list[Any], metadata: dict) -> bytes:
        """Serialize audit entries to CSV bytes with compliance metadata header.

        Parameters
        ----------
        entries:
            List of AuditEntryRead-compatible objects (sequence_number, timestamp,
            actor_identity, action_type, resource_type, resource_id, outcome, context).
        metadata:
            Dict with keys: export_actor, export_timestamp, filter_summary, record_count.
            The checksum field is computed internally and must NOT be passed in.

        Returns
        -------
        bytes
            UTF-8 encoded CSV bytes with # metadata comment header, column header row,
            and one data row per entry.

        Raises
        ------
        ExportLimitExceededError
            If len(entries) > EXPORT_LIMIT (50_000).
        """
        count = len(entries)
        if count > EXPORT_LIMIT:
            raise ExportLimitExceededError(count)

        # ── 1. Build data payload (column header + data rows) ──────────────
        data_buf = io.StringIO()
        writer = csv.writer(data_buf, lineterminator="\n")
        writer.writerow(list(_CSV_COLUMNS))

        for entry in entries:
            redacted_ctx = _redact_entry_context(entry)
            writer.writerow(_entry_to_csv_row(entry, redacted_ctx))

        data_payload_str = data_buf.getvalue()

        # ── 2. Compute checksum of data payload only ────────────────────────
        # Derive the checksum using the same splitlines→rejoin method that a
        # verifier would use when reading the final output (strip trailing newline
        # so the checksum is stable regardless of trailing-newline variations).
        data_lines = data_payload_str.splitlines()
        checksum_input = "\n".join(data_lines).encode("utf-8")
        checksum = hashlib.sha256(checksum_input).hexdigest()

        # ── 3. Build metadata comment header ───────────────────────────────
        meta_lines = [
            f"# export_actor = {metadata['export_actor']}",
            f"# export_timestamp = {metadata['export_timestamp']}",
            f"# filter_summary = {metadata['filter_summary']}",
            f"# record_count = {metadata['record_count']}",
            f"# checksum = {checksum}",
        ]
        meta_section = "\n".join(meta_lines) + "\n"

        # ── 4. Concatenate: metadata header + data payload ─────────────────
        return (meta_section + data_payload_str).encode("utf-8")

    @staticmethod
    def export_json(entries: list[Any], metadata: dict) -> bytes:
        """Serialize audit entries to JSON bytes wrapped in metadata.

        Parameters
        ----------
        entries:
            List of AuditEntryRead-compatible objects.
        metadata:
            Dict with keys: export_actor, export_timestamp, filter_summary, record_count.

        Returns
        -------
        bytes
            UTF-8 encoded JSON bytes: {"metadata": {..., "checksum": "..."}, "entries": [...]}.

        Raises
        ------
        ExportLimitExceededError
            If len(entries) > EXPORT_LIMIT (50_000).
        """
        count = len(entries)
        if count > EXPORT_LIMIT:
            raise ExportLimitExceededError(count)

        # ── 1. Build entries list with redaction applied ────────────────────
        serialized_entries: list[dict] = []
        for entry in entries:
            redacted_ctx = _redact_entry_context(entry)
            serialized_entries.append(
                {
                    "sequence_number": entry.sequence_number,
                    "timestamp": str(entry.timestamp),
                    "actor_identity": entry.actor_identity,
                    "action_type": entry.action_type,
                    "resource_type": entry.resource_type,
                    "resource_id": entry.resource_id,
                    "outcome": entry.outcome,
                    "context": redacted_ctx,
                }
            )

        # ── 2. Compute checksum of the entries payload ──────────────────────
        entries_payload = json.dumps(serialized_entries, sort_keys=True, ensure_ascii=False)
        checksum = hashlib.sha256(entries_payload.encode("utf-8")).hexdigest()

        # ── 3. Wrap in output envelope ──────────────────────────────────────
        output = {
            "metadata": {
                "export_actor": metadata["export_actor"],
                "export_timestamp": metadata["export_timestamp"],
                "filter_summary": metadata["filter_summary"],
                "record_count": metadata["record_count"],
                "checksum": checksum,
            },
            "entries": serialized_entries,
        }

        return json.dumps(output, ensure_ascii=False, indent=2).encode("utf-8")
