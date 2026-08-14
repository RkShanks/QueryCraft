"""Real PostgreSQL coverage for atomic role and group-mapping mutations."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text


async def _role_audit_count(async_engine_fixture) -> int:
    async with async_engine_fixture.connect() as connection:
        return int(
            await connection.scalar(
                text(
                    """
                    SELECT COUNT(*)
                    FROM audit_log_entries
                    WHERE action_type IN ('role.create', 'role.mapping.change')
                    """
                )
            )
            or 0
        )


@pytest.mark.integration
async def test_conflicting_group_rejects_complete_role_create(
    authenticated_client,
    async_engine_fixture,
) -> None:
    """IS-GAP-036: a mapping conflict cannot leave an already-created role."""
    case_token = uuid4().hex
    existing_name = f"chunk16-existing-{case_token}"
    requested_name = f"chunk16-requested-{case_token}"
    group_value = f"chunk16-group-{case_token}"
    existing_priority = 1_000_000_000 + int(case_token[:7], 16)
    requested_priority = existing_priority + 1

    try:
        async with async_engine_fixture.begin() as connection:
            existing_role_id = await connection.scalar(
                text(
                    """
                    INSERT INTO roles (name, priority, permissions)
                    VALUES (:name, :priority, '[]'::jsonb)
                    RETURNING id
                    """
                ),
                {"name": existing_name, "priority": existing_priority},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO sso_group_mappings (sso_group_value, role_id)
                    VALUES (:group_value, :role_id)
                    """
                ),
                {"group_value": group_value, "role_id": existing_role_id},
            )

        audit_count_before = await _role_audit_count(async_engine_fixture)
        response = await authenticated_client.post(
            "/api/v1/admin/roles",
            json={
                "name": requested_name,
                "priority": requested_priority,
                "permissions": ["query.submit"],
                "group_mappings": [group_value],
                "connection_policies": [],
            },
        )

        assert response.status_code == 409
        assert response.json() == {
            "error": "conflict",
            "message_key": "error.conflict.duplicateGroupMapping",
        }
        assert group_value not in response.text

        async with async_engine_fixture.connect() as connection:
            assert (
                await connection.scalar(
                    text("SELECT COUNT(*) FROM roles WHERE name = :name"),
                    {"name": requested_name},
                )
                == 0
            )
            assert (
                await connection.scalar(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM sso_group_mappings
                        WHERE sso_group_value = :group_value
                        """
                    ),
                    {"group_value": group_value},
                )
                == 1
            )
        assert await _role_audit_count(async_engine_fixture) == audit_count_before
    finally:
        async with async_engine_fixture.begin() as connection:
            await connection.execute(
                text("DELETE FROM roles WHERE name IN (:existing_name, :requested_name)"),
                {
                    "existing_name": existing_name,
                    "requested_name": requested_name,
                },
            )
