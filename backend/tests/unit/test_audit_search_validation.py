"""Phase 6C validation regressions for audit search and export filters."""

from __future__ import annotations

from datetime import UTC

import pytest
from pydantic import ValidationError

from app.schemas.audit_search import AuditExportRequest, AuditSearchParams


class TestAuditSearchFilterValidation:
    @pytest.mark.parametrize(
        "payload",
        [
            {"action_type": "not.a.real.audit.action"},
            {"outcome": "not-a-real-outcome"},
            {"actor_identity": "actor\x00identity"},
            {"resource_type": "database\nforged"},
        ],
    )
    def test_invalid_enum_and_control_character_values_are_rejected(self, payload):
        with pytest.raises(ValidationError):
            AuditSearchParams(**payload)

    def test_inverted_date_range_is_rejected(self):
        with pytest.raises(ValidationError):
            AuditSearchParams(
                start_date="2026-07-30T00:00:00Z",
                end_date="2026-07-29T00:00:00Z",
            )

    def test_overflow_page_is_rejected(self):
        with pytest.raises(ValidationError):
            AuditSearchParams(page=2**63)

    def test_naive_dates_are_normalized_to_utc(self):
        params = AuditSearchParams(start_date="2026-07-29T00:00:00")

        assert params.start_date is not None
        assert params.start_date.tzinfo is UTC

    def test_unicode_and_sql_like_free_text_remain_valid(self):
        params = AuditSearchParams(
            actor_identity="مدير'; DROP TABLE audit_log_entries; --",
            resource_type="قاعدة بيانات",
        )

        assert params.actor_identity == "مدير'; DROP TABLE audit_log_entries; --"
        assert params.resource_type == "قاعدة بيانات"


class TestAuditExportFilterValidation:
    def test_export_rejects_inverted_date_range(self):
        with pytest.raises(ValidationError):
            AuditExportRequest(
                format="json",
                start_date="2026-07-30T00:00:00Z",
                end_date="2026-07-29T00:00:00Z",
            )

    @pytest.mark.parametrize(
        "payload",
        [
            {"format": "json", "action_type": "not.a.real.audit.action"},
            {"format": "csv", "outcome": "not-a-real-outcome"},
            {"format": "json", "actor_identity": "actor\tidentity"},
        ],
    )
    def test_export_rejects_invalid_enum_and_control_values(self, payload):
        with pytest.raises(ValidationError):
            AuditExportRequest(**payload)
