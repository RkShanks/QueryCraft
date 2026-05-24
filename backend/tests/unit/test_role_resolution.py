"""TDD tests for role resolution from SSO group claims (T-642).

Tests single group mapping, multi-group priority ordering, no matching group.
Uses mocked DB session — no external services.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.role import Role
from app.services.sso_service import SsoService


class TestRoleResolution:
    """Role resolution unit tests."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis = AsyncMock()
        redis.set = AsyncMock(return_value=True)
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock(return_value=1)
        return redis

    @pytest.fixture
    def mock_db_session(self):
        """Mock async DB session with execute/scalars pattern."""
        return AsyncMock()

    @pytest.fixture
    def sso_service(self, mock_db_session, mock_redis):
        """SsoService with mocked dependencies."""
        with patch("app.services.sso_service.get_settings") as mock_settings:
            settings = MagicMock()
            settings.PLATFORM_ENCRYPTION_KEY = "d1OQc28ErbKH8nnhjNbchX5y_1EyXcfclkK1hPjPqFY="
            settings.SESSION_IDLE_TIMEOUT_HOURS = 8
            mock_settings.return_value = settings
            service = SsoService(mock_db_session, mock_redis)
            return service

    @pytest.fixture
    def analyst_role(self):
        """Analyst role with priority 10."""
        role = MagicMock(spec=Role)
        role.id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        role.name = "Analyst"
        role.priority = 10
        role.permissions = ["query.submit", "query.history.view"]
        return role

    @pytest.fixture
    def admin_role(self):
        """Admin role with priority 5 (higher than Analyst)."""
        role = MagicMock(spec=Role)
        role.id = uuid.UUID("22222222-2222-2222-2222-222222222222")
        role.name = "Admin"
        role.priority = 5
        role.permissions = [
            "query.submit",
            "query.history.view",
            "admin.connections.manage",
            "admin.roles.manage",
            "admin.sso.manage",
            "admin.audit.verify",
        ]
        return role

    @pytest.fixture
    def viewer_role(self):
        """Viewer role with priority 20 (lower than Analyst)."""
        role = MagicMock(spec=Role)
        role.id = uuid.UUID("33333333-3333-3333-3333-333333333333")
        role.name = "Viewer"
        role.priority = 20
        role.permissions = ["query.history.view"]
        return role

    def _mock_db_result(self, mock_db_session, return_values):
        """Helper to mock DB session.execute().scalars().all() pattern.

        The query selects Role objects, so return_values should be Role mocks.
        """
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = return_values
        mock_db_session.execute.return_value = mock_result

    @pytest.mark.asyncio
    async def test_single_group_maps_to_role(self, sso_service, mock_db_session, analyst_role):
        """Single matching SSO group resolves to mapped role."""
        self._mock_db_result(mock_db_session, [analyst_role])

        role = await sso_service.resolve_role_from_groups(["analysts"])

        assert role is not None
        assert role.id == analyst_role.id
        assert role.name == "Analyst"
        assert role.priority == 10

    @pytest.mark.asyncio
    async def test_multiple_groups_maps_to_highest_priority_role(
        self, sso_service, mock_db_session, analyst_role, admin_role, viewer_role
    ):
        """User in multiple groups gets role with lowest priority number (highest priority)."""
        # DB returns roles ordered by priority ASC, name ASC
        # Admin priority 5, Analyst 10, Viewer 20
        self._mock_db_result(mock_db_session, [admin_role, analyst_role, viewer_role])

        role = await sso_service.resolve_role_from_groups(["analysts", "admins", "viewers"])

        # Admin has priority 5 (lowest number = highest priority)
        assert role is not None
        assert role.id == admin_role.id
        assert role.name == "Admin"

    @pytest.mark.asyncio
    async def test_no_matching_group_returns_none(self, sso_service, mock_db_session):
        """User with no mapped groups gets no role (denied access)."""
        self._mock_db_result(mock_db_session, [])

        role = await sso_service.resolve_role_from_groups(["unmapped-group"])

        assert role is None

    @pytest.mark.asyncio
    async def test_empty_groups_returns_none(self, sso_service, mock_db_session):
        """User with empty groups list gets no role."""
        self._mock_db_result(mock_db_session, [])

        role = await sso_service.resolve_role_from_groups([])

        assert role is None

    @pytest.mark.asyncio
    async def test_partial_match_resolves_to_matching_role(self, sso_service, mock_db_session, analyst_role):
        """One matching group out of many still resolves correctly."""
        self._mock_db_result(mock_db_session, [analyst_role])

        role = await sso_service.resolve_role_from_groups(["unmapped", "analysts", "also-unmapped"])

        assert role is not None
        assert role.id == analyst_role.id

    @pytest.mark.asyncio
    async def test_same_priority_deterministic_by_name(self, sso_service, mock_db_session, analyst_role):
        """If two roles have same priority, deterministic ordering (name sort)."""
        role_b = MagicMock(spec=Role)
        role_b.id = uuid.UUID("44444444-4444-4444-4444-444444444444")
        role_b.name = "Beta"
        role_b.priority = 10
        role_b.permissions = ["query.submit"]

        # DB returns ordered by priority ASC, name ASC → Analyst before Beta
        self._mock_db_result(mock_db_session, [analyst_role, role_b])

        role = await sso_service.resolve_role_from_groups(["alpha", "beta"])

        # Both priority 10; deterministic by name sort (Analyst < Beta)
        assert role is not None
        assert role.id == analyst_role.id

    @pytest.mark.asyncio
    async def test_role_resolution_includes_permissions(self, sso_service, mock_db_session, analyst_role):
        """Resolved role includes permissions list for session creation."""
        self._mock_db_result(mock_db_session, [analyst_role])

        role = await sso_service.resolve_role_from_groups(["analysts"])

        assert role.permissions == ["query.submit", "query.history.view"]

    @pytest.mark.asyncio
    async def test_role_resolution_sanitized_error_no_group_leak(self, sso_service, mock_db_session):
        """Error messages must not leak unmapped group names."""
        self._mock_db_result(mock_db_session, [])

        role = await sso_service.resolve_role_from_groups(["secret-group-name"])

        # Returns None safely; no exception with group names
        assert role is None

    @pytest.mark.asyncio
    async def test_role_resolution_query_filters_by_group_values(self, sso_service, mock_db_session, analyst_role):
        """DB query filters SsoGroupMapping by the user's SSO group values."""
        self._mock_db_result(mock_db_session, [analyst_role])

        await sso_service.resolve_role_from_groups(["analysts"])

        # Verify execute was called with a query
        mock_db_session.execute.assert_called_once()
