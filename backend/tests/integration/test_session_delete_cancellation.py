"""IS-GAP-003 session deletion/query cancellation regressions."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.source_db.adapters import ExecuteResult


class _ControllableProvider:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def generate_sql(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        self.entered.set()
        await self.release.wait()
        return "SELECT 1 AS id"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_is_gap_003_delete_during_provider_invalidates_late_submit(
    authenticated_client,
    query_submit_payload,
):
    """A started DELETE wins over provider completion and returns the private 404."""
    create_response = await authenticated_client.post("/api/v1/sessions")
    assert create_response.status_code == 201
    chat_session_id = create_response.json()["id"]
    provider = _ControllableProvider()

    with (
        patch("app.api.v1.query.LLMProviderFactory.from_config", return_value=provider),
        patch(
            "app.source_db.adapters.PostgresAdapter.execute",
            new=AsyncMock(return_value=ExecuteResult(columns=["id"], rows=[(1,)])),
        ),
    ):
        submit_task = asyncio.create_task(
            authenticated_client.post(
                "/api/v1/query/submit",
                json=query_submit_payload("Controlled cancellation", session_id=chat_session_id),
            )
        )
        await asyncio.wait_for(provider.entered.wait(), timeout=2)
        delete_task = asyncio.create_task(
            authenticated_client.delete(f"/api/v1/sessions/{chat_session_id}")
        )

        try:
            delete_response = await asyncio.wait_for(asyncio.shield(delete_task), timeout=2)
            submit_response = await asyncio.wait_for(asyncio.shield(submit_task), timeout=2)
        finally:
            provider.release.set()
            await asyncio.gather(submit_task, delete_task, return_exceptions=True)

    assert delete_response.status_code == 204
    assert submit_response.status_code == 404
    assert submit_response.json() == {
        "error": "not_found",
        "message_key": "error.notFound",
    }
