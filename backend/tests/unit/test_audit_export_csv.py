"""RED unit tests for AuditExportService CSV output (T-863).

Contract tested:
- CSV output contains correct column headers
- Formula injection prevention: cells starting with =, +, -, @, | are tab-prefixed
- Compliance metadata header row present with required fields:
  export_actor, export_timestamp, filter_summary, record_count, checksum
- Checksum is SHA-256 of data payload (not mutable wrapper/header text)
- 50k limit: raises ExportLimitExceededError when entry count > 50_000
"""

from __future__ import annotations

import csv
import hashlib
import io
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


class TestCsvHeaders:
    """CSV data section contains expected column headers."""

    def test_csv_has_expected_column_headers(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry()]
        metadata = _make_metadata()
        raw = AuditExportService.export_csv(entries, metadata)

        # Skip the metadata section (lines starting with '#') and find the
        # actual CSV header row.
        lines = raw.decode("utf-8").splitlines()
        data_lines = [line for line in lines if not line.startswith("#")]
        assert data_lines, "CSV must contain at least one non-comment line"

        reader = csv.reader(data_lines)
        header = next(reader)
        # Required columns
        for col in ("sequence_number", "timestamp", "actor_identity", "action_type", "outcome"):
            assert col in header, f"Missing column: {col}"

    def test_csv_row_count_matches_entries(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry(seq=i) for i in range(5)]
        metadata = _make_metadata(record_count=5)
        raw = AuditExportService.export_csv(entries, metadata)

        lines = raw.decode("utf-8").splitlines()
        data_lines = [line for line in lines if not line.startswith("#")]
        # header + 5 data rows
        assert len(data_lines) == 6


class TestFormulaInjectionPrevention:
    """Cells starting with =, +, -, @, | must be tab-prefixed."""

    FORMULA_PREFIXES = ("=", "+", "-", "@", "|")

    def _csv_cell_value(self, raw: bytes, col_name: str) -> str:
        """Extract the first data row value for a given column from CSV bytes."""
        lines = raw.decode("utf-8").splitlines()
        data_lines = [line for line in lines if not line.startswith("#")]
        reader = csv.reader(data_lines)
        header = next(reader)
        row = next(reader)
        idx = header.index(col_name)
        return row[idx]

    def test_equals_prefix_tabbed(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry(action_type="=MALICIOUS")]
        metadata = _make_metadata()
        raw = AuditExportService.export_csv(entries, metadata)
        cell = self._csv_cell_value(raw, "action_type")
        assert cell.startswith("\t"), f"Expected tab-prefix, got: {repr(cell)}"
        assert "MALICIOUS" in cell

    def test_plus_prefix_tabbed(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry(actor_identity="+1234567890")]
        metadata = _make_metadata()
        raw = AuditExportService.export_csv(entries, metadata)
        cell = self._csv_cell_value(raw, "actor_identity")
        assert cell.startswith("\t"), f"Expected tab-prefix, got: {repr(cell)}"

    def test_minus_prefix_tabbed(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry(outcome="-1+2")]
        metadata = _make_metadata()
        raw = AuditExportService.export_csv(entries, metadata)
        cell = self._csv_cell_value(raw, "outcome")
        assert cell.startswith("\t"), f"Expected tab-prefix, got: {repr(cell)}"

    def test_at_prefix_tabbed(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry(actor_identity="@badactor")]
        metadata = _make_metadata()
        raw = AuditExportService.export_csv(entries, metadata)
        cell = self._csv_cell_value(raw, "actor_identity")
        assert cell.startswith("\t"), f"Expected tab-prefix, got: {repr(cell)}"

    def test_pipe_prefix_tabbed(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry(action_type="|cmd")]
        metadata = _make_metadata()
        raw = AuditExportService.export_csv(entries, metadata)
        cell = self._csv_cell_value(raw, "action_type")
        assert cell.startswith("\t"), f"Expected tab-prefix, got: {repr(cell)}"

    def test_safe_cell_not_modified(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry(actor_identity="safe@example.com")]
        metadata = _make_metadata()
        raw = AuditExportService.export_csv(entries, metadata)
        # safe@example.com starts with 's', not a formula prefix → no tab
        cell = self._csv_cell_value(raw, "actor_identity")
        assert not cell.startswith("\t"), f"Safe cell should not be tab-prefixed: {repr(cell)}"


class TestComplianceMetadataHeader:
    """CSV must have a compliance metadata section with required fields."""

    REQUIRED_META_FIELDS = {
        "export_actor",
        "export_timestamp",
        "filter_summary",
        "record_count",
        "checksum",
    }

    def _parse_meta_section(self, raw: bytes) -> dict:
        """Extract key=value pairs from # comment lines."""
        meta = {}
        for line in raw.decode("utf-8").splitlines():
            if line.startswith("#"):
                stripped = line.lstrip("#").strip()
                if "=" in stripped:
                    key, _, value = stripped.partition("=")
                    meta[key.strip()] = value.strip()
        return meta

    def test_metadata_section_present(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry()]
        metadata = _make_metadata()
        raw = AuditExportService.export_csv(entries, metadata)

        lines = raw.decode("utf-8").splitlines()
        comment_lines = [l for l in lines if l.startswith("#")]
        assert comment_lines, "Expected metadata comment lines in CSV output"

    def test_all_required_fields_present(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry()]
        metadata = _make_metadata()
        raw = AuditExportService.export_csv(entries, metadata)
        meta = self._parse_meta_section(raw)

        for field in self.REQUIRED_META_FIELDS:
            assert field in meta, f"Missing metadata field: {field}"

    def test_export_actor_value_correct(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry()]
        metadata = _make_metadata(export_actor="audit_admin@corp.com")
        raw = AuditExportService.export_csv(entries, metadata)
        meta = self._parse_meta_section(raw)
        assert meta["export_actor"] == "audit_admin@corp.com"

    def test_record_count_value_correct(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry(seq=i) for i in range(3)]
        metadata = _make_metadata(record_count=3)
        raw = AuditExportService.export_csv(entries, metadata)
        meta = self._parse_meta_section(raw)
        assert meta["record_count"] == "3"


class TestChecksumIntegrity:
    """Checksum must be SHA-256 of the data payload, not the metadata wrapper."""

    def _parse_meta(self, raw: bytes) -> dict:
        meta = {}
        for line in raw.decode("utf-8").splitlines():
            if line.startswith("#"):
                stripped = line.lstrip("#").strip()
                if "=" in stripped:
                    k, _, v = stripped.partition("=")
                    meta[k.strip()] = v.strip()
        return meta

    def _extract_data_payload(self, raw: bytes) -> bytes:
        """Return only the non-comment portion of the CSV as bytes."""
        data_lines = [
            line for line in raw.decode("utf-8").splitlines()
            if not line.startswith("#")
        ]
        return "\n".join(data_lines).encode("utf-8")

    def test_checksum_is_sha256_of_data_payload(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry()]
        metadata = _make_metadata()
        raw = AuditExportService.export_csv(entries, metadata)

        meta = self._parse_meta(raw)
        reported_checksum = meta["checksum"]

        data_payload = self._extract_data_payload(raw)
        expected_checksum = hashlib.sha256(data_payload).hexdigest()

        assert reported_checksum == expected_checksum, (
            f"Checksum mismatch: got {reported_checksum!r}, expected {expected_checksum!r}"
        )

    def test_checksum_changes_with_data(self):
        """Checksums of different datasets must differ."""
        from app.services.audit_export_service import AuditExportService

        entries_a = [_make_entry(seq=1, outcome="success")]
        entries_b = [_make_entry(seq=1, outcome="blocked")]
        meta = _make_metadata()

        raw_a = AuditExportService.export_csv(entries_a, meta)
        raw_b = AuditExportService.export_csv(entries_b, meta)

        meta_a = self._parse_meta(raw_a)
        meta_b = self._parse_meta(raw_b)

        assert meta_a["checksum"] != meta_b["checksum"]

    def test_checksum_not_of_full_output(self):
        """Checksum must NOT be of the full output (which includes the checksum itself).

        We verify this by checking the checksum is consistent with only
        the non-comment (data) section.
        """
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry()]
        metadata = _make_metadata()
        raw = AuditExportService.export_csv(entries, metadata)

        meta = self._parse_meta(raw)
        reported_checksum = meta["checksum"]

        # SHA-256 of full output would differ from SHA-256 of data section
        full_checksum = hashlib.sha256(raw).hexdigest()
        # They may or may not be equal — we just want to confirm the reported
        # value matches the data payload checksum (tested in previous test).
        # This test is documentation that we verified the distinction.
        data_payload = self._extract_data_payload(raw)
        expected = hashlib.sha256(data_payload).hexdigest()
        assert reported_checksum == expected


class TestExportLimit:
    """Service raises ExportLimitExceededError when entry count > 50_000."""

    def test_raises_when_over_50k(self):
        from app.services.audit_export_service import AuditExportService, ExportLimitExceededError

        # Use a list of 50_001 lightweight stubs
        entries = [_make_entry(seq=i) for i in range(50_001)]
        metadata = _make_metadata(record_count=50_001)

        try:
            AuditExportService.export_csv(entries, metadata)
            raise AssertionError("Expected ExportLimitExceededError to be raised")
        except ExportLimitExceededError:
            pass  # expected

    def test_exactly_50k_does_not_raise(self):
        from app.services.audit_export_service import AuditExportService

        entries = [_make_entry(seq=i) for i in range(50_000)]
        metadata = _make_metadata(record_count=50_000)
        # Should not raise
        raw = AuditExportService.export_csv(entries, metadata)
        assert raw  # non-empty bytes

    def test_error_message_contains_limit(self):
        from app.services.audit_export_service import AuditExportService, ExportLimitExceededError

        entries = [_make_entry(seq=i) for i in range(50_001)]
        metadata = _make_metadata(record_count=50_001)

        try:
            AuditExportService.export_csv(entries, metadata)
        except ExportLimitExceededError as exc:
            assert "50" in str(exc) or "limit" in str(exc).lower()
        else:
            raise AssertionError("Expected ExportLimitExceededError")
