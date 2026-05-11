"""F-9: O-004 — invalid cursor returns 400 Bad Request.

Reproduction: GET /history?cursor=not-a-valid-cursor → expect 400.
"""

import pytest


class TestHistoryCursorValidation:
    """History router cursor validation tests."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_invalid_cursor_returns_400(self, authenticated_client):
        """Malformed cursor returns 400 with structured error."""
        resp = await authenticated_client.get("/api/v1/history?cursor=not-a-valid-cursor")
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data or "message_key" in data
