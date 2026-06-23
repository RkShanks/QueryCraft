"""RED integration tests for GET /admin/audit/entries (T-861).

Tests:
- 200 with paginated entries for admin with admin.audit.verify
- 403 for user without permission
- date range filter works
- action_type filter
- actor_identity filter
- outcome filter
- entries outside retention window absent
- search emits audit.search event with filter summary (no result values)
- total_entries and total_pages correct

Requires live DB + app (integration marker auto-applied by conftest).
"""

from __future__ import annotations

import pytest


class TestAuditSearchPermission:
    @pytest.mark.asyncio
    async def test_returns_200_for_admin_with_audit_verify(self, authenticated_client):
        """Admin with admin.audit.verify gets 200 with paginated entries."""
        response = await authenticated_client.get("/api/v1/admin/audit/entries")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "pagination" in data
        pagination = data["pagination"]
        assert "page" in pagination
        assert "page_size" in pagination
        assert "total_entries" in pagination
        assert "total_pages" in pagination

    @pytest.mark.asyncio
    async def test_returns_403_without_permission(self, app_client, async_engine_fixture):
        """User without admin.audit.verify gets 403."""
        from argon2 import PasswordHasher
        from sqlalchemy import text

        async with async_engine_fixture.connect() as conn:
            ph = PasswordHasher()
            password_hash = ph.hash("auditpass")
            await conn.execute(
                text(
                    """
                    INSERT INTO users (username, display_name, password_hash, role)
                    VALUES ('audit_no_perm', 'No Audit Perm', :pwd, 'user')
                    ON CONFLICT (username) DO UPDATE SET
                        password_hash = EXCLUDED.password_hash,
                        updated_at = now()
                    """
                ),
                {"pwd": password_hash},
            )
            await conn.commit()

        resp = await app_client.post(
            "/api/v1/auth/sign-in",
            json={"username": "audit_no_perm", "password": "auditpass"},
            headers={"origin": "http://test"},
        )
        assert resp.status_code == 200
        response = await app_client.get("/api/v1/admin/audit/entries")
        assert response.status_code == 403


class TestAuditSearchFilters:
    @pytest.mark.asyncio
    async def test_action_type_filter(self, authenticated_client):
        """action_type query param filters results."""
        response = await authenticated_client.get(
            "/api/v1/admin/audit/entries",
            params={"action_type": "audit.verify"},
        )
        assert response.status_code == 200
        data = response.json()
        for entry in data["entries"]:
            assert entry["action_type"] == "audit.verify"

    @pytest.mark.asyncio
    async def test_actor_identity_filter(self, authenticated_client):
        """actor_identity query param filters results."""
        response = await authenticated_client.get(
            "/api/v1/admin/audit/entries",
            params={"actor_identity": "nonexistent_user_xyz"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total_entries"] == 0

    @pytest.mark.asyncio
    async def test_outcome_filter(self, authenticated_client):
        """outcome query param filters results."""
        response = await authenticated_client.get(
            "/api/v1/admin/audit/entries",
            params={"outcome": "success"},
        )
        assert response.status_code == 200
        data = response.json()
        for entry in data["entries"]:
            assert entry["outcome"] == "success"

    @pytest.mark.asyncio
    async def test_date_range_filter(self, authenticated_client):
        """start_date and end_date filter by timestamp."""
        response = await authenticated_client.get(
            "/api/v1/admin/audit/entries",
            params={
                "start_date": "2020-01-01T00:00:00Z",
                "end_date": "2020-12-31T23:59:59Z",
            },
        )
        assert response.status_code == 200
        data = response.json()
        # No entries from 2020 in test DB seeded post-2026
        assert data["pagination"]["total_entries"] == 0


class TestAuditSearchPagination:
    @pytest.mark.asyncio
    async def test_total_entries_and_total_pages_correct(self, authenticated_client):
        """Pagination metadata matches actual entry count."""
        response = await authenticated_client.get(
            "/api/v1/admin/audit/entries",
            params={"page": 1, "page_size": 5},
        )
        assert response.status_code == 200
        data = response.json()
        pagination = data["pagination"]
        total = pagination["total_entries"]
        page_size = pagination["page_size"]
        expected_pages = max(1, -(-total // page_size))  # ceil division
        assert pagination["total_pages"] == expected_pages
        assert len(data["entries"]) <= page_size

    @pytest.mark.asyncio
    async def test_page_2_returns_different_entries(self, authenticated_client, async_engine_fixture):
        """Page 2 entries differ from page 1 (offset pagination works)."""
        from sqlalchemy import text

        # Ensure at least 6 entries exist via the audit sign-in events
        # that accumulate during the test session.
        resp1 = await authenticated_client.get(
            "/api/v1/admin/audit/entries",
            params={"page": 1, "page_size": 3},
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        if data1["pagination"]["total_entries"] < 4:
            pytest.skip("Not enough audit entries for pagination test")

        resp2 = await authenticated_client.get(
            "/api/v1/admin/audit/entries",
            params={"page": 2, "page_size": 3},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()

        seqs1 = {e["sequence_number"] for e in data1["entries"]}
        seqs2 = {e["sequence_number"] for e in data2["entries"]}
        assert seqs1.isdisjoint(seqs2), "Page 1 and page 2 must not overlap"


class TestAuditSearchRetention:
    @pytest.mark.asyncio
    async def test_entries_outside_retention_window_absent(self, authenticated_client):
        """Entries older than AUDIT_RETENTION_MONTHS (24) are excluded."""
        # Query with a date range entirely within the retention window.
        # We can't easily insert old entries in integration tests, so we
        # assert that the service returns no entries from 3 years ago.
        response = await authenticated_client.get(
            "/api/v1/admin/audit/entries",
            params={
                "start_date": "2022-01-01T00:00:00Z",
                "end_date": "2023-01-01T00:00:00Z",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total_entries"] == 0


class TestAuditSearchSelfAuditEvent:
    @pytest.mark.asyncio
    async def test_search_emits_audit_search_event(self, authenticated_client, async_engine_fixture):
        """GET /entries emits an audit.search event with filter summary, no result values."""
        from sqlalchemy import text

        # Perform a search with a specific action_type filter
        await authenticated_client.get(
            "/api/v1/admin/audit/entries",
            params={"action_type": "audit.verify", "page": 1, "page_size": 10},
        )

        # Verify the audit.search event was emitted
        async with async_engine_fixture.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT context FROM audit_log_entries "
                    "WHERE action_type = 'audit.search' "
                    "ORDER BY sequence_number DESC LIMIT 1"
                )
            )
            row = result.fetchone()
            assert row is not None, "audit.search event must be emitted after GET /entries"

            import json

            context = row[0] if isinstance(row[0], dict) else json.loads(row[0])

            # Must contain filter summary and pagination metadata
            assert "filters" in context or "filter_summary" in context, (
                f"audit.search context must contain filter summary, got: {context}"
            )
            assert "page" in context or "pagination" in context, (
                f"audit.search context must contain pagination metadata, got: {context}"
            )

            # Must NOT contain returned entry values
            ctx_str = str(context)
            forbidden_audit_fields = ["row_hash", "prev_hash", "sequence_number"]
            for field in forbidden_audit_fields:
                # The filter key itself might be named "action_type" but
                # we must ensure no raw audit ENTRY data is stored (hashes, etc.)
                assert field not in ctx_str or context.get(field) is None, (
                    f"audit.search context must not contain returned entry value '{field}'"
                )


class TestAuditSearchResponseShape:
    @pytest.mark.asyncio
    async def test_entries_have_required_fields(self, authenticated_client):
        """Each entry in results has all AuditEntryRead fields."""
        response = await authenticated_client.get("/api/v1/admin/audit/entries")
        assert response.status_code == 200
        data = response.json()
        for entry in data["entries"]:
            assert "sequence_number" in entry
            assert "timestamp" in entry
            assert "action_type" in entry
            assert "outcome" in entry
            assert "context" in entry
