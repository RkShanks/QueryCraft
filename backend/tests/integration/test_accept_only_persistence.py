"""Invariant 2: Accept-only persistence — reject writes nothing (T-035).

Calls reject and regenerate handlers and asserts they do not add extra rows beyond
the submit auto-save.
"""

import pytest
from sqlalchemy import text


@pytest.mark.usefixtures("deterministic_query_llm")
class TestAcceptOnlyPersistence:
    """Accept-only persistence integration test."""

    @pytest.mark.asyncio
    async def test_reject_does_not_persist(self, authenticated_client, db_session, query_submit_payload):
        """POST /query/reject must not add another accepted_queries row."""
        # Get current count
        result = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
        before = result.scalar()

        # Submit
        submit_resp = await authenticated_client.post(
            "/api/v1/query/submit",
            json=query_submit_payload("Test reject?"),
            headers={"origin": "http://test"},
        )
        assert submit_resp.status_code == 200

        # Reject (stub returns refine)
        reject_resp = await authenticated_client.post(
            "/api/v1/query/reject",
            json={"attempt_id": submit_resp.json()["attempt_id"]},
            headers={"origin": "http://test"},
        )
        assert reject_resp.status_code == 200

        # Submit auto-saves once; reject should not add another row.
        result = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
        after = result.scalar()
        assert after == before + 1

    @pytest.mark.asyncio
    async def test_regenerate_does_not_persist(self, authenticated_client, db_session, query_submit_payload):
        """POST /query/regenerate must not add another accepted_queries row."""
        result = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
        before = result.scalar()

        submit_resp = await authenticated_client.post(
            "/api/v1/query/submit",
            json=query_submit_payload("Test regenerate?"),
            headers={"origin": "http://test"},
        )
        assert submit_resp.status_code == 200

        regen_resp = await authenticated_client.post(
            "/api/v1/query/regenerate",
            json={"attempt_id": submit_resp.json()["attempt_id"]},
            headers={"origin": "http://test"},
        )
        assert regen_resp.status_code == 200

        result = await db_session.execute(text("SELECT COUNT(*) FROM accepted_queries"))
        after = result.scalar()
        assert after == before + 1
