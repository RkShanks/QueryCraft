"""F-3: O-002 — limit query parameter server-side bounds [1, 1000].

Reproduction: GET /history?limit=999999999 → should 422.
"""

import pytest


class TestHistoryLimitValidation:
    """History router limit validation tests."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_limit_upper_bound_enforced(self, authenticated_client):
        """limit=1001 returns 422."""
        resp = await authenticated_client.get("/api/v1/history?limit=1001")
        assert resp.status_code == 422

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_limit_lower_bound_enforced(self, authenticated_client):
        """limit=0 returns 422."""
        resp = await authenticated_client.get("/api/v1/history?limit=0")
        assert resp.status_code == 422

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_limit_negative_enforced(self, authenticated_client):
        """limit=-1 returns 422."""
        resp = await authenticated_client.get("/api/v1/history?limit=-1")
        assert resp.status_code == 422

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_limit_boundary_1000_ok(self, authenticated_client):
        """limit=1000 returns 200."""
        resp = await authenticated_client.get("/api/v1/history?limit=1000")
        assert resp.status_code == 200

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_limit_default_100_ok(self, authenticated_client):
        """Default limit (no param) returns 200."""
        resp = await authenticated_client.get("/api/v1/history")
        assert resp.status_code == 200

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_limit_1_ok(self, authenticated_client):
        """limit=1 returns 200."""
        resp = await authenticated_client.get("/api/v1/history?limit=1")
        assert resp.status_code == 200
