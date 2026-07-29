"""XP-012 append-time audit context redaction regressions."""

from __future__ import annotations

import json
import secrets
from unittest.mock import AsyncMock

import pytest

from app.db.models.enums import AuditActionType
from app.services.audit_service import AuditService


@pytest.mark.asyncio
async def test_mock_log_redacts_secret_shaped_values_under_safe_nested_keys():
    runtime_probe = secrets.token_urlsafe(24)
    entry = await AuditService.log(
        AsyncMock(),
        action=AuditActionType.QUERY_SUBMIT,
        context={"details": [{"value": f"Bearer {runtime_probe}"}]},
    )

    probe_leaked = runtime_probe in json.dumps(entry.context)
    value_redacted = entry.context["details"][0]["value"] == "[REDACTED]"
    assert probe_leaked is False
    assert value_redacted is True
