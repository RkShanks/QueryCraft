"""TDD tests for require_permission() FastAPI dependency (T-624).

Tests permission checking against session data, 403 on missing permission,
and sanitized error response with error.forbidden.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Request

from app.api.dependencies.permissions import require_permission
from app.db.models.enums import Permission


class TestRequirePermission:
    """Permission middleware unit tests."""

    @pytest.fixture
    def mock_request_with_permissions(self):
        """Return a mock Request with session data containing permissions."""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        return request

    @pytest.mark.asyncio
    async def test_has_single_permission(self, mock_request_with_permissions):
        """User with exact required permission passes."""
        mock_request_with_permissions.state.session = {
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "permissions": ["query.submit"],
        }
        dep = require_permission(Permission.QUERY_SUBMIT)
        result = await dep(mock_request_with_permissions)
        assert result == mock_request_with_permissions.state.session

    @pytest.mark.asyncio
    async def test_has_one_of_multiple_permissions(self, mock_request_with_permissions):
        """User with one of multiple required permissions passes."""
        mock_request_with_permissions.state.session = {
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "permissions": ["query.submit", "query.history.view"],
        }
        dep = require_permission(Permission.QUERY_SUBMIT, Permission.ADMIN_ROLES_MANAGE)
        result = await dep(mock_request_with_permissions)
        assert result == mock_request_with_permissions.state.session

    @pytest.mark.asyncio
    async def test_missing_permission_raises_403(self, mock_request_with_permissions):
        """User without required permission gets 403 with error.forbidden."""
        mock_request_with_permissions.state.session = {
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "permissions": ["query.submit"],
        }
        dep = require_permission(Permission.ADMIN_ROLES_MANAGE)
        with pytest.raises(HTTPException) as exc_info:
            await dep(mock_request_with_permissions)
        assert exc_info.value.status_code == 403
        detail = exc_info.value.detail
        assert detail["error"] == "forbidden"
        assert detail["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_no_session_raises_401(self, mock_request_with_permissions):
        """No session data raises 401 (handled before permission check)."""
        mock_request_with_permissions.state.session = None
        dep = require_permission(Permission.QUERY_SUBMIT)
        with pytest.raises(HTTPException) as exc_info:
            await dep(mock_request_with_permissions)
        assert exc_info.value.status_code == 401
        detail = exc_info.value.detail
        assert detail["error"] == "unauthorized"
        assert detail["message_key"] == "error.unauthorized"

    @pytest.mark.asyncio
    async def test_empty_permissions_raises_403(self, mock_request_with_permissions):
        """User with empty permissions list gets 403."""
        mock_request_with_permissions.state.session = {
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "permissions": [],
        }
        dep = require_permission(Permission.QUERY_SUBMIT)
        with pytest.raises(HTTPException) as exc_info:
            await dep(mock_request_with_permissions)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_with_all_permissions_passes(self, mock_request_with_permissions):
        """Admin user with all permissions passes any check."""
        mock_request_with_permissions.state.session = {
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "permissions": [
                "query.submit",
                "query.history.view",
                "admin.connections.manage",
                "admin.roles.manage",
                "admin.sso.manage",
                "admin.audit.verify",
            ],
        }
        dep = require_permission(
            Permission.QUERY_SUBMIT,
            Permission.ADMIN_CONNECTIONS_MANAGE,
            Permission.ADMIN_AUDIT_VERIFY,
        )
        result = await dep(mock_request_with_permissions)
        assert result == mock_request_with_permissions.state.session

    @pytest.mark.asyncio
    async def test_permission_values_are_strings(self, mock_request_with_permissions):
        """Permission enum values resolve to string for comparison."""
        mock_request_with_permissions.state.session = {
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "permissions": ["admin.sso.manage"],
        }
        dep = require_permission(Permission.ADMIN_SSO_MANAGE)
        result = await dep(mock_request_with_permissions)
        assert result == mock_request_with_permissions.state.session

    @pytest.mark.asyncio
    async def test_response_does_not_expose_internal_details(self, mock_request_with_permissions):
        """403 response must not leak session internals, UUIDs, or schema details."""
        mock_request_with_permissions.state.session = {
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "permissions": ["query.submit"],
        }
        dep = require_permission(Permission.ADMIN_SSO_MANAGE)
        with pytest.raises(HTTPException) as exc_info:
            await dep(mock_request_with_permissions)
        detail = exc_info.value.detail
        # Must not contain raw UUIDs
        assert "550e8400" not in str(detail)
        # Must not contain internal permission names
        assert "admin.sso.manage" not in str(detail).lower()
        assert "query.submit" not in str(detail).lower()
        # Must only contain sanitized error envelope
        assert set(detail.keys()) == {"error", "message_key"}
