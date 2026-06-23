"""RED/GREEN unit tests for export redaction defense-in-depth (T-866).

Simulates stored audit entries whose context contains sensitive values that
bypassed storage-time redaction. Verifies AuditExportService applies its own
central redaction pass before serialization — so the sensitive values never
appear in CSV or JSON export output.

This verifies the defense-in-depth layer:
  Storage-time redaction (AuditService._redact_value)
  +
  Export-time redaction (AuditExportService central pass)
  = defense-in-depth — two independent layers.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any


def _make_entry_with_context(context: dict, seq: int = 1) -> Any:
    """Build a fake audit entry with an arbitrary context dict."""
    from unittest.mock import MagicMock

    e = MagicMock()
    e.sequence_number = seq
    e.timestamp = datetime(2026, 1, 10, 12, 0, 0, tzinfo=UTC)
    e.actor_identity = "alice@example.com"
    e.action_type = "query.submit"
    e.resource_type = None
    e.resource_id = None
    e.outcome = "success"
    e.context = context
    return e


def _make_metadata() -> dict:
    return {
        "export_actor": "admin@example.com",
        "export_timestamp": datetime(2026, 1, 10, 13, 0, 0, tzinfo=UTC).isoformat(),
        "filter_summary": "none",
        "record_count": 1,
    }


# ---------------------------------------------------------------------------
# CSV defense-in-depth
# ---------------------------------------------------------------------------


class TestCsvRedactionDefenseInDepth:
    """CSV export must redact sensitive context values even if they slipped storage."""

    def test_password_not_in_csv_output(self):
        """A context key named 'password' must be redacted in CSV export."""
        from app.services.audit_export_service import AuditExportService

        leaked_secret = "leaked_password_value_abc"
        entry = _make_entry_with_context({"password": leaked_secret})
        raw = AuditExportService.export_csv([entry], _make_metadata())
        assert leaked_secret not in raw.decode("utf-8"), "Leaked password must not appear in CSV export output"

    def test_token_not_in_csv_output(self):
        """A context key containing 'token' must be redacted."""
        from app.services.audit_export_service import AuditExportService

        leaked_token = "leaked_bearer_token_xyz789"
        entry = _make_entry_with_context({"access_token": leaked_token})
        raw = AuditExportService.export_csv([entry], _make_metadata())
        assert leaked_token not in raw.decode("utf-8"), "Leaked token must not appear in CSV export output"

    def test_secret_key_not_in_csv_output(self):
        """A context key 'secret' must be redacted."""
        from app.services.audit_export_service import AuditExportService

        leaked_secret = "my_super_secret_api_key_val"
        entry = _make_entry_with_context({"secret": leaked_secret})
        raw = AuditExportService.export_csv([entry], _make_metadata())
        assert leaked_secret not in raw.decode("utf-8"), "Leaked secret must not appear in CSV export output"

    def test_nested_sensitive_not_in_csv_output(self):
        """Nested context dict with sensitive key must be redacted in CSV."""
        from app.services.audit_export_service import AuditExportService

        leaked = "nested_apikey_secret_def"
        entry = _make_entry_with_context({"config": {"apikey": leaked}})
        raw = AuditExportService.export_csv([entry], _make_metadata())
        assert leaked not in raw.decode("utf-8"), "Nested sensitive value must not appear in CSV export output"

    def test_non_sensitive_context_preserved_in_csv(self):
        """Non-sensitive context values must appear in CSV output."""
        from app.services.audit_export_service import AuditExportService

        entry = _make_entry_with_context({"query_id": "q-001", "user_id": "u-999"})
        raw = AuditExportService.export_csv([entry], _make_metadata())
        output = raw.decode("utf-8")
        assert "q-001" in output
        assert "u-999" in output

    def test_redacted_placeholder_in_csv_output(self):
        """Sensitive context values replaced with [REDACTED] placeholder."""
        from app.services.audit_export_service import AuditExportService

        entry = _make_entry_with_context({"password": "should_be_gone"})
        raw = AuditExportService.export_csv([entry], _make_metadata())
        assert "[REDACTED]" in raw.decode("utf-8"), (
            "CSV export must contain [REDACTED] placeholder for sensitive values"
        )

    def test_credential_key_not_in_csv_output(self):
        """A context key 'credential' must be redacted."""
        from app.services.audit_export_service import AuditExportService

        leaked = "leaked_credential_abc123"
        entry = _make_entry_with_context({"credential": leaked})
        raw = AuditExportService.export_csv([entry], _make_metadata())
        assert leaked not in raw.decode("utf-8")


# ---------------------------------------------------------------------------
# JSON defense-in-depth
# ---------------------------------------------------------------------------


class TestJsonRedactionDefenseInDepth:
    """JSON export must redact sensitive context values even if they slipped storage."""

    def test_password_not_in_json_output(self):
        """A context key named 'password' must be redacted in JSON export."""
        from app.services.audit_export_service import AuditExportService

        leaked_secret = "json_leaked_password_12345"
        entry = _make_entry_with_context({"password": leaked_secret})
        raw = AuditExportService.export_json([entry], _make_metadata())
        assert leaked_secret not in raw.decode("utf-8"), "Leaked password must not appear in JSON export output"

    def test_token_not_in_json_output(self):
        """A context key containing 'token' must be redacted in JSON export."""
        from app.services.audit_export_service import AuditExportService

        leaked_token = "json_leaked_token_abc999"
        entry = _make_entry_with_context({"refresh_token": leaked_token})
        raw = AuditExportService.export_json([entry], _make_metadata())
        assert leaked_token not in raw.decode("utf-8")

    def test_nested_sensitive_not_in_json_output(self):
        """Nested context sensitive key redacted in JSON export."""
        from app.services.audit_export_service import AuditExportService

        leaked = "json_nested_jwt_secret_xyz"
        entry = _make_entry_with_context({"auth": {"jwt": leaked}})
        raw = AuditExportService.export_json([entry], _make_metadata())
        assert leaked not in raw.decode("utf-8")

    def test_non_sensitive_context_preserved_in_json(self):
        """Non-sensitive context values must appear in JSON output."""
        from app.services.audit_export_service import AuditExportService

        entry = _make_entry_with_context({"query_id": "q-002", "role": "analyst"})
        raw = AuditExportService.export_json([entry], _make_metadata())
        parsed = json.loads(raw.decode("utf-8"))
        ctx = parsed["entries"][0]["context"]
        assert ctx["query_id"] == "q-002"
        assert ctx["role"] == "analyst"

    def test_redacted_placeholder_in_json_output(self):
        """Sensitive context values replaced with [REDACTED] in JSON."""
        from app.services.audit_export_service import AuditExportService

        entry = _make_entry_with_context({"secret": "should_be_gone"})
        raw = AuditExportService.export_json([entry], _make_metadata())
        parsed = json.loads(raw.decode("utf-8"))
        ctx = parsed["entries"][0]["context"]
        assert ctx["secret"] == "[REDACTED]", (
            "JSON export must contain [REDACTED] placeholder for sensitive context values"
        )

    def test_apikey_not_in_json_output(self):
        """A context key 'apikey' must be redacted."""
        from app.services.audit_export_service import AuditExportService

        leaked = "leaked_api_key_value_def456"
        entry = _make_entry_with_context({"apikey": leaked})
        raw = AuditExportService.export_json([entry], _make_metadata())
        assert leaked not in raw.decode("utf-8")

    def test_multiple_entries_all_redacted(self):
        """Redaction applies to every entry in the export, not just the first."""
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry_with_context({"password": f"secret_{i}"}, seq=i) for i in range(5)]
        raw = AuditExportService.export_json(entries, _make_metadata())
        output = raw.decode("utf-8")
        for i in range(5):
            assert f"secret_{i}" not in output, f"Entry {i} password must be redacted in JSON export"
