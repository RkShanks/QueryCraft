"""Unit tests for admin settings endpoint SQL binding."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from app.api.v1.admin import update_settings_admin
from app.schemas.admin_settings import UpdateAdminSettingsRequest


@pytest.mark.asyncio
async def test_patch_settings_binds_both_params():
    """PATCH /admin/settings must bind both :cap and :max_regen as CAST params."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()

    req = MagicMock(spec=UpdateAdminSettingsRequest)
    req.llm_context_cap = 5
    req.max_regenerate_attempts = 3

    request = MagicMock(spec=Request)
    request.state.session = {
        "user_id": "admin",
        "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    }

    captured_params = []

    async def _capture_execute(stmt, *args, **kwargs):
        if args:
            captured_params.append(args[0])

    db.execute = _capture_execute

    mock_checker = AsyncMock(return_value={})
    with patch("app.api.v1.admin.require_permission", return_value=mock_checker):
        await update_settings_admin(
            req=req,
            _session={"permissions": ["admin.connections.manage"]},
            db=db,
        )

    assert len(captured_params) == 2
    cap_param = captured_params[0]
    regen_param = captured_params[1]

    assert "cap" in cap_param
    assert cap_param["cap"] == "5"
    assert "max_regen" in regen_param
    assert regen_param["max_regen"] == "3"
