"""Durable audit coverage for the local administrator sign-in endpoint."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models.audit_log_entry import AuditLogEntry
from app.db.models.enums import AuditActionType


async def _audit_entries(async_engine_fixture) -> list[AuditLogEntry]:
    session_factory = async_sessionmaker(async_engine_fixture, expire_on_commit=False)
    async with session_factory() as session:
        result = await session.execute(select(AuditLogEntry).order_by(AuditLogEntry.sequence_number))
        return list(result.scalars().all())


@pytest.mark.integration
@pytest.mark.usefixtures("clean_audit_table", "redis_client", "synced_local_admin")
class TestLocalLoginAudit:
    async def test_success_is_durably_audited(self, app_client, async_engine_fixture):
        response = await app_client.post(
            "/api/v1/auth/sign-in",
            json={"username": "admin", "password": "admin123"},
            headers={"origin": "http://test"},
        )

        assert response.status_code == 200
        entries = await _audit_entries(async_engine_fixture)
        assert len(entries) == 1
        entry = entries[0]
        assert entry.action_type == AuditActionType.AUTH_LOGIN_SUCCESS.value
        assert entry.actor_identity == "admin"
        assert entry.resource_type == "user"
        assert entry.outcome == "success"
        assert entry.context == {"auth_provider": "local", "role_name": "Admin"}

    async def test_failure_is_durably_audited_without_attempted_identity(
        self,
        app_client,
        async_engine_fixture,
    ):
        attempted_username = "unknown-user"
        response = await app_client.post(
            "/api/v1/auth/sign-in",
            json={"username": attempted_username, "password": "wrong-password"},
            headers={"origin": "http://test"},
        )

        assert response.status_code == 401
        assert response.json() == {
            "error": "unauthorized",
            "message_key": "error.unauthorized",
        }
        entries = await _audit_entries(async_engine_fixture)
        assert len(entries) == 1
        entry = entries[0]
        assert entry.action_type == AuditActionType.AUTH_LOGIN_FAILURE.value
        assert entry.actor_identity is None
        assert entry.resource_type == "session"
        assert entry.resource_id is None
        assert entry.outcome == "failure"
        assert entry.context == {
            "auth_provider": "local",
            "error_code": "unauthorized",
        }
        assert attempted_username not in str(entry.context)
