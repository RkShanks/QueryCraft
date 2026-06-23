"""RED unit tests for AuditExportService JSON output (T-864).

Contract tested:
- JSON output is valid JSON
- Metadata wrapper present with required fields:
  export_actor, export_timestamp, filter_summary, record_count, checksum
- No formula injection concerns (JSON inherently safe — verify no tab-prefixing added)
- 50k limit respected (ExportLimitExceededError raised on > 50_000)
- Defense-in-depth redaction: mock entry with unexpected sensitive value in context
  must not appear in export output
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any


def _make_entry(
    seq: int = 1,
    action_type: str = "query.submit",
    actor_identity: str | None = "alice@example.com",
    outcome: str = "success",
    resource_type: str | None = None,
    resource_id: str | None = None,
    context: dict | None = None,
) -> Any:
    """Build a minimal fake AuditEntryRead-compatible object."""
    from unittest.mock import MagicMock

    e = MagicMock()
    e.sequence_number = seq
    e.timestamp = datetime(2026, 1, 10, 12, 0, 0, tzinfo=UTC)
    e.actor_identity = actor_identity
    e.action_type = action_type
    e.resource_type = resource_type
    e.resource_id = resource_id
    e.outcome = outcome
    e.context = context or {}
    return e


def _make_metadata(
    export_actor: str = "admin@example.com",
    filter_summary: str = "action_type=query.submit",
    record_count: int = 1,
) -> dict:
    return {
        "export_actor": export_actor,
        "export_timestamp": datetime(2026, 1, 10, 13, 0, 0, tzinfo=UTC).isoformat(),
        "filter_summary": filter_summary,
        "record_count": record_count,
    }


class TestJsonOutputValid:
    """JSON output must be valid and parseable."""

    def test_json_is_parseable(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry()]
        metadata = _make_metadata()
        raw = AuditExportService.export_json(entries, metadata)

        parsed = json.loads(raw.decode("utf-8"))
        assert isinstance(parsed, dict)

    def test_json_contains_entries_key(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry()]
        metadata = _make_metadata()
        raw = AuditExportService.export_json(entries, metadata)

        parsed = json.loads(raw.decode("utf-8"))
        assert "entries" in parsed

    def test_entries_list_length_matches_input(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry(seq=i) for i in range(5)]
        metadata = _make_metadata(record_count=5)
        raw = AuditExportService.export_json(entries, metadata)

        parsed = json.loads(raw.decode("utf-8"))
        assert len(parsed["entries"]) == 5

    def test_entry_has_expected_fields(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry(seq=42, actor_identity="bob@example.com", outcome="blocked")]
        metadata = _make_metadata()
        raw = AuditExportService.export_json(entries, metadata)

        parsed = json.loads(raw.decode("utf-8"))
        entry = parsed["entries"][0]
        assert entry["sequence_number"] == 42
        assert entry["actor_identity"] == "bob@example.com"
        assert entry["outcome"] == "blocked"


class TestJsonMetadataWrapper:
    """JSON output must include a metadata wrapper with required fields."""

    REQUIRED_META_FIELDS = {
        "export_actor",
        "export_timestamp",
        "filter_summary",
        "record_count",
        "checksum",
    }

    def _parse(self, raw: bytes) -> dict:
        return json.loads(raw.decode("utf-8"))

    def test_metadata_key_present(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry()]
        metadata = _make_metadata()
        raw = AuditExportService.export_json(entries, metadata)

        parsed = self._parse(raw)
        assert "metadata" in parsed

    def test_all_required_fields_in_metadata(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry()]
        metadata = _make_metadata()
        raw = AuditExportService.export_json(entries, metadata)

        parsed = self._parse(raw)
        meta = parsed["metadata"]
        for field in self.REQUIRED_META_FIELDS:
            assert field in meta, f"Missing metadata field: {field}"

    def test_export_actor_value_correct(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry()]
        metadata = _make_metadata(export_actor="audit_admin@corp.com")
        raw = AuditExportService.export_json(entries, metadata)

        parsed = self._parse(raw)
        assert parsed["metadata"]["export_actor"] == "audit_admin@corp.com"

    def test_record_count_value_correct(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry(seq=i) for i in range(3)]
        metadata = _make_metadata(record_count=3)
        raw = AuditExportService.export_json(entries, metadata)

        parsed = self._parse(raw)
        assert parsed["metadata"]["record_count"] == 3

    def test_checksum_present_and_non_empty(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry()]
        metadata = _make_metadata()
        raw = AuditExportService.export_json(entries, metadata)

        parsed = self._parse(raw)
        checksum = parsed["metadata"]["checksum"]
        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA-256 hex


class TestJsonNoFormulaTabbing:
    """JSON is inherently safe; no tab-prefixing should be applied to JSON values."""

    def test_formula_prefix_not_tab_modified_in_json(self):
        """Values like '=FORMULA' must appear verbatim in JSON (no tab injection)."""
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry(action_type="=formula_injection_attempt")]
        metadata = _make_metadata()
        raw = AuditExportService.export_json(entries, metadata)

        parsed = json.loads(raw.decode("utf-8"))
        # In JSON there is no formula injection risk; value must be verbatim
        entry = parsed["entries"][0]
        assert entry["action_type"] == "=formula_injection_attempt"
        assert not entry["action_type"].startswith("\t")


class TestJsonExportLimit:
    """Service raises ExportLimitExceededError when entry count > 50_000."""

    def test_raises_when_over_50k(self):
        from app.services.audit_export_service import AuditExportService, ExportLimitExceededError

        entries = [_make_entry(seq=i) for i in range(50_001)]
        metadata = _make_metadata(record_count=50_001)

        try:
            AuditExportService.export_json(entries, metadata)
            raise AssertionError("Expected ExportLimitExceededError to be raised")
        except ExportLimitExceededError:
            pass  # expected

    def test_exactly_50k_does_not_raise(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry(seq=i) for i in range(50_000)]
        metadata = _make_metadata(record_count=50_000)
        raw = AuditExportService.export_json(entries, metadata)
        parsed = json.loads(raw.decode("utf-8"))
        assert len(parsed["entries"]) == 50_000


class TestJsonDefenseInDepthRedaction:
    """Export must apply defense-in-depth redaction even for JSON.

    Simulates a stored audit entry whose context contains a sensitive value
    that bypassed storage-time redaction — the export must not output it.
    """

    def test_sensitive_key_in_context_redacted(self):
        """A context key named 'password' must not appear in export output."""
        from app.services.audit_export_service import AuditExportService

        secret_value = "supersecret_password_12345"
        entries = [_make_entry(context={"password": secret_value, "user_id": "abc123"})]
        metadata = _make_metadata()
        raw = AuditExportService.export_json(entries, metadata)

        output_str = raw.decode("utf-8")
        assert secret_value not in output_str, (
            "Sensitive value from context must be redacted in export output"
        )

    def test_sensitive_token_key_redacted(self):
        """A context key containing 'token' must not expose its value."""
        from app.services.audit_export_service import AuditExportService

        secret_token = "Bearer_secret_jwt_token_xyz"
        entries = [_make_entry(context={"access_token": secret_token})]
        metadata = _make_metadata()
        raw = AuditExportService.export_json(entries, metadata)

        output_str = raw.decode("utf-8")
        assert secret_token not in output_str, (
            "Token value must be redacted in export output"
        )

    def test_nested_sensitive_value_redacted(self):
        """Nested dict with sensitive key must also be redacted."""
        from app.services.audit_export_service import AuditExportService

        nested_secret = "nested_api_key_secret_abc"
        entries = [_make_entry(context={"config": {"apikey": nested_secret}})]
        metadata = _make_metadata()
        raw = AuditExportService.export_json(entries, metadata)

        output_str = raw.decode("utf-8")
        assert nested_secret not in output_str, (
            "Nested sensitive value must be redacted in export output"
        )

    def test_safe_context_value_preserved(self):
        """Non-sensitive context values must appear in output unchanged."""
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry(context={"user_id": "user-001", "query_id": "q-999"})]
        metadata = _make_metadata()
        raw = AuditExportService.export_json(entries, metadata)

        parsed = json.loads(raw.decode("utf-8"))
        entry = parsed["entries"][0]
        # Context key 'user_id' is not sensitive — value preserved
        assert entry["context"]["user_id"] == "user-001"
