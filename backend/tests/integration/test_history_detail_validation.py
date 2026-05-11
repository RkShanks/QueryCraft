"""F-6: G-003/O-005 — history detail UUID validation.

Reproduction: GET /history/not-a-uuid → expect 422 (FastAPI validation).
"""

import pytest


class TestHistoryDetailValidation:
    """History detail endpoint validation tests."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_invalid_uuid_returns_422(self, authenticated_client):
        """Non-UUID path parameter returns 422, not 500."""
        resp = await authenticated_client.get("/api/v1/history/not-a-uuid")
        assert resp.status_code == 422

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_valid_uuid_returns_404(self, authenticated_client):
        """Valid UUID but not found returns 404."""
        resp = await authenticated_client.get("/api/v1/history/550e8400-e29b-41d4-a716-446655440000")
        assert resp.status_code == 404
