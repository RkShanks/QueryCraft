"""Acceptance fixture auth regression coverage."""


async def test_authenticated_acceptance_client_signs_in_local_admin(authenticated_acceptance_client):
    """Acceptance auth setup yields a Phase 5-compatible local admin session."""
    response = await authenticated_acceptance_client.get("/api/v1/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "admin"
    assert body["auth_provider"] == "local"
    assert body["role"] == "admin"
    assert body["role_id"]
    assert "query.submit" in body["permissions"]
