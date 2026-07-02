"""RED integration tests for POST /admin/audit/export (T-867).

Tests:
- POST with format="csv" returns file download (200, Content-Disposition)
- POST with format="json" returns JSON file download
- 422 when filtered result exceeds 50k entries
- 403 without admin.audit.verify permission
- 429 when daily export quota exhausted
- Emits audit.export event with filter summary and record_count (no exported data)
- CSV contains formula injection prevention (tab-prefixed cells)

Requires live DB + app (integration marker auto-applied by conftest).
"""

from __future__ import annotations

import pytest


class TestAuditExportPermission:
    @pytest.mark.asyncio
    async def test_export_403_without_permission(self, app_client, async_engine_fixture):
        """User without admin.audit.verify gets 403.

        Uses an admin-role user with no role_id (empty permissions) so that
        local sign-in succeeds (local login is admin-only) but the
        admin.audit.verify permission check fails.
        """
        from argon2 import PasswordHasher
        from sqlalchemy import text

        async with async_engine_fixture.connect() as conn:
            ph = PasswordHasher()
            password_hash = ph.hash("exportpass")
            await conn.execute(
                text(
                    """
                    INSERT INTO users (username, display_name, password_hash, role)
                    VALUES ('export_no_perm', 'No Export Perm', :pwd, 'admin')
                    ON CONFLICT (username) DO UPDATE SET
                        password_hash = EXCLUDED.password_hash,
                        role_id = NULL,
                        updated_at = now()
                    """
                ),
                {"pwd": password_hash},
            )
            await conn.commit()

        resp = await app_client.post(
            "/api/v1/auth/sign-in",
            json={"username": "export_no_perm", "password": "exportpass"},
            headers={"origin": "http://test"},
        )
        assert resp.status_code == 200, f"Sign-in failed: {resp.text}"
        response = await app_client.post(
            "/api/v1/admin/audit/export",
            json={"format": "csv"},
            headers={"origin": "http://test"},
        )
        assert response.status_code == 403


class TestAuditExportCsv:
    @pytest.mark.asyncio
    async def test_csv_export_returns_file_download(self, authenticated_client):
        """POST with format='csv' returns 200 with file download headers."""
        response = await authenticated_client.post(
            "/api/v1/admin/audit/export",
            json={"format": "csv"},
        )
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got: {content_type}"
        content_disp = response.headers.get("content-disposition", "")
        assert "attachment" in content_disp, f"Expected attachment Content-Disposition, got: {content_disp}"
        assert ".csv" in content_disp, f"Expected .csv filename in Content-Disposition, got: {content_disp}"

    @pytest.mark.asyncio
    async def test_csv_export_has_compliance_metadata(self, authenticated_client):
        """CSV export includes compliance metadata comment lines."""
        response = await authenticated_client.post(
            "/api/v1/admin/audit/export",
            json={"format": "csv"},
        )
        assert response.status_code == 200
        text = response.content.decode("utf-8")
        lines = text.splitlines()
        comment_lines = [ln for ln in lines if ln.startswith("#")]
        assert comment_lines, "CSV export must contain compliance metadata comment lines"
        meta_keys = {ln.lstrip("#").split("=")[0].strip() for ln in comment_lines if "=" in ln}
        for required_key in ("export_actor", "export_timestamp", "record_count", "checksum"):
            assert required_key in meta_keys, (
                f"Missing metadata key '{required_key}' in CSV comment header. Got: {meta_keys}"
            )

    @pytest.mark.asyncio
    async def test_csv_formula_injection_prevention(self, authenticated_client, async_engine_fixture):
        """CSV export tab-prefixes cells starting with formula injection characters."""
        # Seed an audit entry with a formula-like actor_identity
        from sqlalchemy import text

        async with async_engine_fixture.connect() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO audit_log_entries
                        (sequence_number, row_hash, prev_hash, timestamp,
                         actor_identity, action_type, resource_type, outcome, context)
                    VALUES
                        (9999001,
                         md5(random()::text),
                         md5(random()::text),
                         now(),
                         '=MALICIOUS()',
                         'audit.verify',
                         'audit_chain',
                         'success',
                         '{}')
                    ON CONFLICT (sequence_number) DO NOTHING
                    """
                )
            )
            await conn.commit()

        response = await authenticated_client.post(
            "/api/v1/admin/audit/export",
            json={"format": "csv", "action_type": "audit.verify"},
        )
        assert response.status_code == 200
        text_body = response.content.decode("utf-8")
        # Tab-prefixed cells appear as \t= in the CSV output (after CSV unquoting)
        # The raw bytes will contain the tab character before the '='
        assert "\t=MALICIOUS()" in text_body or "=MALICIOUS()" not in text_body, (
            "Formula injection: '=MALICIOUS()' should be tab-prefixed in CSV output"
        )


class TestAuditExportJson:
    @pytest.mark.asyncio
    async def test_json_export_returns_file_download(self, authenticated_client):
        """POST with format='json' returns 200 with JSON file download headers."""
        response = await authenticated_client.post(
            "/api/v1/admin/audit/export",
            json={"format": "json"},
        )
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type, f"Expected application/json, got: {content_type}"
        content_disp = response.headers.get("content-disposition", "")
        assert "attachment" in content_disp, f"Expected attachment Content-Disposition, got: {content_disp}"
        assert ".json" in content_disp, f"Expected .json filename in Content-Disposition, got: {content_disp}"

    @pytest.mark.asyncio
    async def test_json_export_has_metadata_wrapper(self, authenticated_client):
        """JSON export is wrapped in {metadata: {...}, entries: [...]} envelope."""
        import json as _json

        response = await authenticated_client.post(
            "/api/v1/admin/audit/export",
            json={"format": "json"},
        )
        assert response.status_code == 200
        data = _json.loads(response.content)
        assert "metadata" in data, f"JSON export must have 'metadata' key, got: {list(data.keys())}"
        assert "entries" in data, f"JSON export must have 'entries' key, got: {list(data.keys())}"
        meta = data["metadata"]
        for required_key in ("export_actor", "export_timestamp", "record_count", "checksum"):
            assert required_key in meta, (
                f"Missing metadata key '{required_key}' in JSON export metadata. Got: {list(meta.keys())}"
            )

    @pytest.mark.asyncio
    async def test_json_export_entries_have_required_fields(self, authenticated_client):
        """JSON export entries contain all required audit entry fields."""
        import json as _json

        response = await authenticated_client.post(
            "/api/v1/admin/audit/export",
            json={"format": "json"},
        )
        assert response.status_code == 200
        data = _json.loads(response.content)
        for entry in data["entries"]:
            assert "sequence_number" in entry
            assert "timestamp" in entry
            assert "action_type" in entry
            assert "outcome" in entry
            assert "context" in entry


class TestAuditExportLimitEnforcement:
    @pytest.mark.asyncio
    async def test_422_when_result_exceeds_50k(self, authenticated_client):
        """Returns 422 with localized message_key when filtered result > 50,000."""
        from unittest.mock import AsyncMock, patch

        from app.services.audit_export_service import ExportLimitExceededError

        # Simulate AuditExportService raising ExportLimitExceededError
        with patch(
            "app.services.audit_search_service.AuditSearchService.search",
            new=AsyncMock(
                side_effect=None,
                return_value=_make_large_response(),
            ),
        ):
            with patch(
                "app.services.audit_export_service.AuditExportService.export_csv",
                side_effect=ExportLimitExceededError(count=50001, limit=50000),
            ):
                response = await authenticated_client.post(
                    "/api/v1/admin/audit/export",
                    json={"format": "csv"},
                )
        assert response.status_code == 422
        body = response.json()
        assert "message_key" in body or "message_key" in str(body), f"Expected message_key in 422 response, got: {body}"


class TestAuditExportQuotaEnforcement:
    @pytest.mark.asyncio
    async def test_429_when_export_quota_exhausted(self, authenticated_client):
        """Returns 429 with localized message_key when export quota is exhausted."""
        from unittest.mock import AsyncMock, patch

        from app.core.exceptions import QuotaExceededError

        with patch(
            "app.services.quota_service.QuotaService.check_and_increment",
            new=AsyncMock(
                side_effect=QuotaExceededError(
                    dimension="exports",
                    reset_at="2026-06-24T00:00:00+00:00",
                )
            ),
        ):
            response = await authenticated_client.post(
                "/api/v1/admin/audit/export",
                json={"format": "csv"},
            )
        assert response.status_code == 429
        body = response.json()
        assert "message_key" in body or "message_key" in str(body), f"Expected message_key in 429 response, got: {body}"

    @pytest.mark.asyncio
    async def test_503_when_quota_service_unavailable(self, authenticated_client):
        """Returns 503 with localized message_key when quota service (Redis) is unavailable."""
        from unittest.mock import AsyncMock, patch

        from app.core.exceptions import QuotaUnavailableError

        with patch(
            "app.services.quota_service.QuotaService.check_and_increment",
            new=AsyncMock(side_effect=QuotaUnavailableError()),
        ):
            response = await authenticated_client.post(
                "/api/v1/admin/audit/export",
                json={"format": "csv"},
            )
        assert response.status_code == 503
        body = response.json()
        assert "message_key" in body or "message_key" in str(body), f"Expected message_key in 503 response, got: {body}"


class TestAuditExportSelfAuditEvent:
    @pytest.mark.asyncio
    async def test_export_emits_audit_export_event(self, authenticated_client, async_engine_fixture):
        """POST /export emits an audit.export event with filter_summary and record_count."""
        from sqlalchemy import text

        # Trigger an export
        response = await authenticated_client.post(
            "/api/v1/admin/audit/export",
            json={"format": "csv", "action_type": "audit.verify"},
        )
        assert response.status_code == 200

        # Verify audit.export event was emitted
        async with async_engine_fixture.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT context FROM audit_log_entries "
                    "WHERE action_type = 'audit.export' "
                    "ORDER BY sequence_number DESC LIMIT 1"
                )
            )
            row = result.fetchone()
            assert row is not None, "audit.export event must be emitted after POST /export"

            import json

            context = row[0] if isinstance(row[0], dict) else json.loads(row[0])

            # Must contain filter_summary and record_count
            assert "filter_summary" in context or "filters" in context, (
                f"audit.export context must contain filter summary, got: {context}"
            )
            assert "record_count" in context, f"audit.export context must contain record_count, got: {context}"

            # Must NOT contain exported entry values
            ctx_str = str(context)
            assert "row_hash" not in ctx_str, (
                f"audit.export context must not contain raw entry field 'row_hash': {context}"
            )
            assert "prev_hash" not in ctx_str, (
                f"audit.export context must not contain raw entry field 'prev_hash': {context}"
            )

    @pytest.mark.asyncio
    async def test_export_context_no_exported_entry_values(self, authenticated_client, async_engine_fixture):
        """Audit.export event context must never include exported entry content."""
        from sqlalchemy import text

        response = await authenticated_client.post(
            "/api/v1/admin/audit/export",
            json={"format": "json"},
        )
        assert response.status_code == 200

        async with async_engine_fixture.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT context FROM audit_log_entries "
                    "WHERE action_type = 'audit.export' "
                    "ORDER BY sequence_number DESC LIMIT 1"
                )
            )
            row = result.fetchone()
            if row is None:
                pytest.skip("No audit.export event found")

            import json

            context = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            # The context keys should be: filter_summary (or filters), record_count only
            # No entry-level fields like sequence_number, row_hash, actor_identity values
            allowed_keys = {"filter_summary", "filters", "record_count", "format"}
            extra_keys = set(context.keys()) - allowed_keys
            assert not extra_keys, (
                f"audit.export context contains unexpected keys: {extra_keys}. Only {allowed_keys} are permitted."
            )

    @pytest.mark.asyncio
    async def test_export_redacts_sensitive_filter_values_in_metadata_and_audit(
        self,
        authenticated_client,
        async_engine_fixture,
    ):
        """Sensitive caller-supplied filter values must not persist in export metadata or audit.export."""
        from sqlalchemy import text

        sensitive_filter = "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signature"
        response = await authenticated_client.post(
            "/api/v1/admin/audit/export",
            json={"format": "csv", "actor_identity": sensitive_filter},
        )
        assert response.status_code == 200
        body = response.content.decode("utf-8")
        assert sensitive_filter not in body
        assert "[REDACTED]" in body

        async with async_engine_fixture.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT context FROM audit_log_entries "
                    "WHERE action_type = 'audit.export' "
                    "ORDER BY sequence_number DESC LIMIT 1"
                )
            )
            row = result.fetchone()
            assert row is not None, "audit.export event must be emitted after POST /export"

            import json

            context = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            context_text = str(context)
            assert sensitive_filter not in context_text
            assert "[REDACTED]" in context_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_large_response():
    """Return a fake AuditSearchResponse with enough entries to pass pagination."""
    from datetime import UTC, datetime

    from app.schemas.audit_search import AuditEntryRead, AuditSearchPagination, AuditSearchResponse

    entries = [
        AuditEntryRead(
            sequence_number=i,
            timestamp=datetime.now(UTC),
            actor_identity="system",
            action_type="test.action",
            outcome="success",
            context={},
        )
        for i in range(100)
    ]
    return AuditSearchResponse(
        entries=entries,
        pagination=AuditSearchPagination(
            page=1,
            page_size=100,
            total_entries=100,
            total_pages=1,
        ),
    )
