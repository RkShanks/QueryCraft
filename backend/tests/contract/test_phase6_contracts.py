"""Phase 6 contract tests for new admin security surfaces."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/admin/quotas",
        "/api/v1/admin/detection/config",
        "/api/v1/admin/audit/entries",
    ],
)
async def test_phase6_admin_endpoints_reject_unauthenticated_requests(path):
    """New Phase 6 admin endpoints must not expose data without auth."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(path, headers={"origin": "http://test"})

    assert response.status_code == 401
    assert response.json()["message_key"] == "error.unauthorized"
