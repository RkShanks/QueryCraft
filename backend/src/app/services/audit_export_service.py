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
from typing import Any

from app.services.audit_redaction import redact_audit_entry, redact_audit_value

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
# Redaction compatibility helpers
# ---------------------------------------------------------------------------


def redact_audit_export_value(value: Any) -> Any:
    """Backward-compatible name for the shared audit redaction pass."""
    return redact_audit_value(value)


# ---------------------------------------------------------------------------
# Formula injection prevention
# ---------------------------------------------------------------------------


def _safe_csv_cell(value: str) -> str:
    """Conservatively tab-prefix formula-shaped spreadsheet cells."""
    index = 0
    while index < len(value):
        character = value[index]
        if not (character.isspace() or character == "\ufeff" or ord(character) <= 31 or ord(character) == 127):
            break
        index += 1
    if index < len(value) and value[index] in _FORMULA_PREFIXES:
        return "\t" + value
    return value


def _entry_to_csv_row(redacted_entry: dict[str, Any]) -> list[str]:
    """Convert a single entry to a CSV row, applying formula injection prevention."""
    raw_values: dict[str, str] = {
        "sequence_number": str(redacted_entry["sequence_number"]),
        "timestamp": str(redacted_entry["timestamp"]),
        "actor_identity": str(redacted_entry["actor_identity"]) if redacted_entry["actor_identity"] is not None else "",
        "action_type": str(redacted_entry["action_type"]),
        "resource_type": str(redacted_entry["resource_type"]) if redacted_entry["resource_type"] is not None else "",
        "resource_id": str(redacted_entry["resource_id"]) if redacted_entry["resource_id"] is not None else "",
        "outcome": str(redacted_entry["outcome"]),
        "context": json.dumps(redacted_entry["context"], sort_keys=True),
    }
    return [_safe_csv_cell(raw_values[col]) for col in _CSV_COLUMNS]


def _safe_csv_metadata_value(value: Any) -> str:
    """Redact, formula-prefix, and keep one metadata value on one line."""
    safe = _safe_csv_cell(str(redact_audit_value(value)))
    return safe.replace("\r", "\\r").replace("\n", "\\n")


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
            writer.writerow(_entry_to_csv_row(redact_audit_entry(entry)))

        data_payload_str = data_buf.getvalue()

        # ── 2. Compute checksum of data payload only ────────────────────────
        # Strip only the writer's final row terminator. Embedded CR/LF inside
        # quoted cells remain checksum-protected exactly as emitted.
        checksum_input = data_payload_str.removesuffix("\n").encode("utf-8")
        checksum = hashlib.sha256(checksum_input).hexdigest()

        # ── 3. Build metadata comment header ───────────────────────────────
        meta_lines = [
            f"# export_actor = {_safe_csv_metadata_value(metadata['export_actor'])}",
            f"# export_timestamp = {_safe_csv_metadata_value(metadata['export_timestamp'])}",
            f"# filter_summary = {_safe_csv_metadata_value(metadata['filter_summary'])}",
            f"# record_count = {_safe_csv_metadata_value(metadata['record_count'])}",
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
            redacted_entry = redact_audit_entry(entry)
            serialized_entries.append(
                {
                    "sequence_number": redacted_entry["sequence_number"],
                    "timestamp": str(redacted_entry["timestamp"]),
                    "actor_identity": redacted_entry["actor_identity"],
                    "action_type": redacted_entry["action_type"],
                    "resource_type": redacted_entry["resource_type"],
                    "resource_id": redacted_entry["resource_id"],
                    "outcome": redacted_entry["outcome"],
                    "context": redacted_entry["context"],
                }
            )

        # ── 2. Compute checksum of the entries payload ──────────────────────
        entries_payload = json.dumps(serialized_entries, sort_keys=True, ensure_ascii=False)
        checksum = hashlib.sha256(entries_payload.encode("utf-8")).hexdigest()

        # ── 3. Wrap in output envelope ──────────────────────────────────────
        safe_metadata = redact_audit_value(metadata)
        output = {
            "metadata": {
                "export_actor": safe_metadata["export_actor"],
                "export_timestamp": safe_metadata["export_timestamp"],
                "filter_summary": safe_metadata["filter_summary"],
                "record_count": safe_metadata["record_count"],
                "checksum": checksum,
            },
            "entries": serialized_entries,
        }

        return json.dumps(output, ensure_ascii=False, indent=2).encode("utf-8")
