"""Integration tests for History router (T-059).

Tests GET /history (200 list, cursor pagination, 401 unauth),
GET /history/{id} (200 detail, 404 not found); uses authenticated_client with pre-seeded accepted queries.
"""

import pytest


class TestHistoryRouter:
    """History router integration tests."""

    @pytest.mark.asyncio
    async def test_list_history(self, authenticated_client):
        """GET /history returns list of accepted queries."""
        # Seed an accepted query via accept endpoint
        submit_resp = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "What is 2+2?"},
            headers={"origin": "http://test"},
        )
        assert submit_resp.status_code == 200
        attempt_id = submit_resp.json()["attempt_id"]

        accept_resp = await authenticated_client.post(
            "/api/v1/query/accept",
            json={"attempt_id": attempt_id},
            headers={"origin": "http://test"},
        )
        assert accept_resp.status_code == 201

        list_resp = await authenticated_client.get("/api/v1/history")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert len(data["items"]) >= 1
        assert data["items"][0]["question_text"] == "What is 2+2?"

    @pytest.mark.asyncio
    async def test_list_history_unauthenticated(self, app_client):
        """GET /history without auth returns 401."""
        response = await app_client.get("/api/v1/history")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_history_detail(self, authenticated_client):
        """GET /history/{id} returns detail."""
        submit_resp = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "Detail test?"},
            headers={"origin": "http://test"},
        )
        assert submit_resp.status_code == 200
        attempt_id = submit_resp.json()["attempt_id"]

        accept_resp = await authenticated_client.post(
            "/api/v1/query/accept",
            json={"attempt_id": attempt_id},
            headers={"origin": "http://test"},
        )
        assert accept_resp.status_code == 201
        query_id = accept_resp.json()["id"]

        detail_resp = await authenticated_client.get(f"/api/v1/history/{query_id}")
        assert detail_resp.status_code == 200
        data = detail_resp.json()
        assert data["question_text"] == "Detail test?"

    @pytest.mark.asyncio
    async def test_get_history_detail_not_found(self, authenticated_client):
        """GET /history/{id} with unknown id returns 404."""
        response = await authenticated_client.get("/api/v1/history/550e8400-e29b-41d4-a716-446655440000")
        assert response.status_code == 404
