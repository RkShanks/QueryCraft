"""RED integration tests for detection admin API (T-840).

Tests:
- GET /admin/detection/config returns 200 with thresholds for admin with admin.security.manage
- GET /admin/detection/config returns 403 for user without permission
- PUT /admin/detection/config updates thresholds and returns updated object
- PUT with block <= flag returns 422
- PUT emits detection.config.change audit event
"""

import pytest


async def _sign_in_admin_without_security_permission(
    app_client,
    async_engine_fixture,
    *,
    username: str,
    password: str,
    priority: int,
) -> None:
    from argon2 import PasswordHasher
    from sqlalchemy import text

    role_name = f"{username}_role"
    async with async_engine_fixture.connect() as conn:
        password_hash = PasswordHasher().hash(password)
        await conn.execute(
            text(
                """
                INSERT INTO roles (name, description, priority, permissions, is_builtin)
                VALUES (:role_name, 'Detection admin test role without security permission', :priority,
                        '["query.submit"]'::jsonb, false)
                ON CONFLICT (name) DO UPDATE SET
                    permissions = EXCLUDED.permissions,
                    updated_at = now()
                """
            ),
            {"role_name": role_name, "priority": priority},
        )
        await conn.execute(
            text(
                """
                INSERT INTO users (username, display_name, password_hash, role, role_id, auth_provider)
                SELECT :username, 'No Security Permission', :pwd, 'admin', id, 'local'
                FROM roles
                WHERE name = :role_name
                ON CONFLICT (username) DO UPDATE SET
                    password_hash = EXCLUDED.password_hash,
                    role = EXCLUDED.role,
                    role_id = EXCLUDED.role_id,
                    auth_provider = EXCLUDED.auth_provider,
                    updated_at = now()
                """
            ),
            {"username": username, "pwd": password_hash, "role_name": role_name},
        )
        await conn.commit()

    response = await app_client.post(
        "/api/v1/auth/sign-in",
        json={"username": username, "password": password},
        headers={"origin": "http://test"},
    )
    assert response.status_code == 200


def _assert_detection_validation_response_is_sanitized(response) -> None:
    data = response.json()
    assert data["error"] == "validation"
    assert data["message_key"] == "error.validation.generic"
    body = response.text
    assert "input" not in body
    assert "stack" not in body
    assert "0.3" not in body
    assert "0.8" not in body


class TestDetectionAdminGetConfig:
    """GET /admin/detection/config — permission-gated config retrieval."""

    @pytest.mark.asyncio
    async def test_get_config_returns_200_for_admin(self, authenticated_client):
        response = await authenticated_client.get("/api/v1/admin/detection/config")
        assert response.status_code == 200
        data = response.json()
        assert "block_confidence" in data
        assert "flag_confidence" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_get_config_default_thresholds(self, authenticated_client):
        response = await authenticated_client.get("/api/v1/admin/detection/config")
        assert response.status_code == 200
        data = response.json()
        # Default: block=0.8, flag=0.5
        assert 0.0 <= data["block_confidence"] <= 1.0
        assert 0.0 <= data["flag_confidence"] <= 1.0
        assert data["block_confidence"] > data["flag_confidence"]

    @pytest.mark.asyncio
    async def test_get_config_403_for_non_admin(self, app_client, async_engine_fixture):
        await _sign_in_admin_without_security_permission(
            app_client,
            async_engine_fixture,
            username="detection_no_security_get",
            password="detectionpass",
            priority=9201,
        )
        response = await app_client.get("/api/v1/admin/detection/config")
        assert response.status_code == 403


class TestDetectionAdminPutConfig:
    """PUT /admin/detection/config — threshold update."""

    @pytest.mark.asyncio
    async def test_put_config_updates_thresholds(self, authenticated_client):
        response = await authenticated_client.put(
            "/api/v1/admin/detection/config",
            json={"block_confidence": 0.9, "flag_confidence": 0.4},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["block_confidence"] == pytest.approx(0.9)
        assert data["flag_confidence"] == pytest.approx(0.4)

    @pytest.mark.asyncio
    async def test_put_config_returns_updated_values(self, authenticated_client):
        await authenticated_client.put(
            "/api/v1/admin/detection/config",
            json={"block_confidence": 0.85, "flag_confidence": 0.45},
        )
        # Fetch again to confirm persistence
        response = await authenticated_client.get("/api/v1/admin/detection/config")
        assert response.status_code == 200
        data = response.json()
        assert data["block_confidence"] == pytest.approx(0.85)
        assert data["flag_confidence"] == pytest.approx(0.45)

    @pytest.mark.asyncio
    async def test_put_config_block_less_than_flag_returns_422(self, authenticated_client):
        response = await authenticated_client.put(
            "/api/v1/admin/detection/config",
            json={"block_confidence": 0.3, "flag_confidence": 0.8},
        )
        assert response.status_code == 422
        _assert_detection_validation_response_is_sanitized(response)

    @pytest.mark.asyncio
    async def test_put_config_block_equal_to_flag_returns_422(self, authenticated_client):
        response = await authenticated_client.put(
            "/api/v1/admin/detection/config",
            json={"block_confidence": 0.5, "flag_confidence": 0.5},
        )
        assert response.status_code == 422
        _assert_detection_validation_response_is_sanitized(response)

    @pytest.mark.asyncio
    async def test_put_config_403_for_non_admin(self, app_client, async_engine_fixture):
        await _sign_in_admin_without_security_permission(
            app_client,
            async_engine_fixture,
            username="detection_no_security_put",
            password="detectionpass2",
            priority=9202,
        )
        response = await app_client.put(
            "/api/v1/admin/detection/config",
            json={"block_confidence": 0.9, "flag_confidence": 0.4},
        )
        assert response.status_code == 403


class TestDetectionAdminAuditEvent:
    """PUT emits detection.config.change audit event."""

    @pytest.mark.asyncio
    async def test_put_emits_detection_config_change_audit(self, authenticated_client, async_engine_fixture):
        from sqlalchemy import text

        await authenticated_client.put(
            "/api/v1/admin/detection/config",
            json={"block_confidence": 0.75, "flag_confidence": 0.35},
        )

        async with async_engine_fixture.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT context FROM audit_log_entries "
                    "WHERE action_type = 'detection.config.change' "
                    "ORDER BY sequence_number DESC LIMIT 1"
                )
            )
            entry = result.fetchone()
            assert entry is not None, "detection.config.change audit event not found"
            context = entry[0] if isinstance(entry[0], dict) else __import__("json").loads(entry[0])
            # Context must not expose raw values or secrets — just confirm event was logged
            assert isinstance(context, dict)
