"""Regression coverage for current-role Phase 6 authorization."""

import uuid

import pytest
from sqlalchemy import text

from app.core.security import SessionMiddleware


@pytest.mark.asyncio
async def test_revoked_quota_permission_denies_the_next_api_request(
    app_client,
    async_engine_fixture,
    redis_client,
):
    role_id = uuid.uuid4()
    user_id = uuid.uuid4()
    role_name = f"Phase6Revocation-{role_id.hex}"
    username = f"phase6-revocation-{user_id.hex}"

    async with async_engine_fixture.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO roles (id, name, description, priority, permissions, is_builtin)
                VALUES (
                    :role_id, :role_name, 'Phase 6 revocation regression',
                    :priority, '["admin.quotas.manage"]'::jsonb, false
                )
                """
            ),
            {
                "role_id": role_id,
                "role_name": role_name,
                "priority": 200000 + user_id.int % 100000000,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO users (
                    id, username, display_name, role, role_id, is_builtin, auth_provider
                )
                VALUES (
                    :user_id, :username, 'Phase 6 revocation user',
                    'admin', :role_id, false, 'local'
                )
                """
            ),
            {"user_id": user_id, "username": username, "role_id": role_id},
        )

    session_id = await SessionMiddleware.create_session(
        redis_client,
        {
            "user_id": str(user_id),
            "username": username,
            "display_name": "Phase 6 revocation user",
            "role": "admin",
            "role_id": str(role_id),
            "role_name": role_name,
            "permissions": ["admin.quotas.manage"],
            "auth_provider": "local",
            "subject_id": username,
        },
    )
    app_client.cookies.set(SessionMiddleware.COOKIE_NAME, session_id)

    try:
        allowed = await app_client.get("/api/v1/admin/quotas")
        assert allowed.status_code == 200

        async with async_engine_fixture.begin() as connection:
            await connection.execute(
                text("UPDATE roles SET permissions = '[]'::jsonb WHERE id = :role_id"),
                {"role_id": role_id},
            )

        revoked = await app_client.get("/api/v1/admin/quotas")

        assert revoked.status_code == 403
        assert revoked.json() == {
            "error": "forbidden",
            "message_key": "error.forbidden",
        }
    finally:
        await redis_client.delete(f"session:{session_id}")
        async with async_engine_fixture.begin() as connection:
            await connection.execute(
                text("DELETE FROM users WHERE id = :user_id"),
                {"user_id": user_id},
            )
            await connection.execute(
                text("DELETE FROM roles WHERE id = :role_id"),
                {"role_id": role_id},
            )


@pytest.mark.asyncio
async def test_auth_profile_refreshes_revoked_permissions(
    app_client,
    async_engine_fixture,
    redis_client,
):
    role_id = uuid.uuid4()
    user_id = uuid.uuid4()
    role_name = f"Phase6Profile-{role_id.hex}"
    username = f"phase6-profile-{user_id.hex}"

    async with async_engine_fixture.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO roles (id, name, description, priority, permissions, is_builtin)
                VALUES (
                    :role_id, :role_name, 'Phase 6 profile regression',
                    :priority, '["admin.quotas.manage"]'::jsonb, false
                )
                """
            ),
            {
                "role_id": role_id,
                "role_name": role_name,
                "priority": 200000 + user_id.int % 100000000,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO users (
                    id, username, display_name, role, role_id, is_builtin, auth_provider
                )
                VALUES (
                    :user_id, :username, 'Phase 6 profile user',
                    'admin', :role_id, false, 'local'
                )
                """
            ),
            {"user_id": user_id, "username": username, "role_id": role_id},
        )

    session_id = await SessionMiddleware.create_session(
        redis_client,
        {
            "user_id": str(user_id),
            "username": username,
            "display_name": "Phase 6 profile user",
            "role": "admin",
            "role_id": str(role_id),
            "role_name": role_name,
            "permissions": ["admin.quotas.manage"],
            "auth_provider": "local",
            "subject_id": username,
        },
    )
    app_client.cookies.set(SessionMiddleware.COOKIE_NAME, session_id)

    try:
        initial_profile = await app_client.get("/api/v1/auth/me")
        assert initial_profile.status_code == 200
        assert initial_profile.json()["permissions"] == ["admin.quotas.manage"]

        async with async_engine_fixture.begin() as connection:
            await connection.execute(
                text("UPDATE roles SET permissions = '[]'::jsonb WHERE id = :role_id"),
                {"role_id": role_id},
            )

        refreshed_profile = await app_client.get("/api/v1/auth/me")

        assert refreshed_profile.status_code == 200
        assert refreshed_profile.json()["permissions"] == []
    finally:
        await redis_client.delete(f"session:{session_id}")
        async with async_engine_fixture.begin() as connection:
            await connection.execute(
                text("DELETE FROM users WHERE id = :user_id"),
                {"user_id": user_id},
            )
            await connection.execute(
                text("DELETE FROM roles WHERE id = :role_id"),
                {"role_id": role_id},
            )
