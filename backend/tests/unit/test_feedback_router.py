"""Unit tests for feedback router — require_active_user integration (PR #62 fix).

Tests that PATCH /feedback/{attempt_id}:
- Uses require_active_user (not request.state.session directly)
- Forwards the validated user_id to the repository
- Returns 401 when require_active_user raises 401 (stale session / missing DB user)
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import FastAPI, HTTPException, Request
from httpx import ASGITransport, AsyncClient

from app.api.v1.feedback import _get_repo
from app.api.v1.feedback import router as feedback_router
from app.core.dependencies import get_db, get_redis, require_active_user


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch):
    """Ensure DB/Redis env vars are set so get_settings / get_db don't fail."""
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5433/test",
    )
    monkeypatch.setenv(
        "PLATFORM_ENCRYPTION_KEY",
        "dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcyExMjM=",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/1")

    # Clear settings cache between overrides
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def feedback_app():
    app = FastAPI()
    app.include_router(feedback_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_redis] = lambda: MagicMock()
    return app


@pytest.fixture
async def feedback_client(feedback_app):
    transport = ASGITransport(app=feedback_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestFeedbackRouterAuth:
    """Route-level tests for require_active_user on PATCH /feedback."""

    @pytest.mark.asyncio
    async def test_stale_session_returns_401(self, feedback_app, feedback_client):
        """Stale/missing DB user returns 401 from require_active_user."""

        async def _raise_401(request: Request, db=None, redis=None):
            raise HTTPException(
                status_code=401,
                detail={"error": "unauthorized", "message_key": "error.unauthorized"},
            )

        feedback_app.dependency_overrides[require_active_user] = _raise_401
        try:
            response = await feedback_client.patch(
                "/api/v1/feedback/550e8400-e29b-41d4-a716-446655440000",
                json={"feedback": 1},
            )
            assert response.status_code == 401
            data = response.json()
            assert data["detail"]["message_key"] == "error.unauthorized"
        finally:
            feedback_app.dependency_overrides.pop(require_active_user, None)

    @pytest.mark.asyncio
    async def test_valid_user_id_passed_to_repo(self, feedback_app, feedback_client):
        """require_active_user user_id is forwarded to repository.update_feedback."""
        mock_repo = MagicMock()
        mock_repo.update_feedback = AsyncMock(
            return_value=MagicMock(
                id=UUID("660e8400-e29b-41d4-a716-446655440000"),
                feedback=1,
                saved=True,
            )
        )
        test_user_id = "550e8400-e29b-41d4-a716-446655440000"

        async def _provide_user(request: Request, db=None, redis=None):
            return test_user_id

        feedback_app.dependency_overrides[require_active_user] = _provide_user
        feedback_app.dependency_overrides[_get_repo] = lambda: mock_repo
        try:
            response = await feedback_client.patch(
                "/api/v1/feedback/550e8400-e29b-41d4-a716-446655440000",
                json={"feedback": 1},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["feedback"] == 1
            assert data["saved"] is True
            mock_repo.update_feedback.assert_awaited_once_with(
                UUID("550e8400-e29b-41d4-a716-446655440000"),
                UUID(test_user_id),
                1,
                saved=None,
            )
        finally:
            feedback_app.dependency_overrides.pop(require_active_user, None)
            feedback_app.dependency_overrides.pop(_get_repo, None)
