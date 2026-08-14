"""Real PostgreSQL coverage for atomic role and group-mapping mutations."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text


async def _role_mutation_audit_count(async_engine_fixture) -> int:
    async with async_engine_fixture.connect() as connection:
        return int(
            await connection.scalar(
                text(
                    """
                    SELECT COUNT(*)
                    FROM audit_log_entries
                    WHERE action_type IN ('role.create', 'role.update', 'role.mapping.change')
                    """
                )
            )
            or 0
        )


async def _audit_action_count(async_engine_fixture, action_type: str) -> int:
    async with async_engine_fixture.connect() as connection:
        return int(
            await connection.scalar(
                text("SELECT COUNT(*) FROM audit_log_entries WHERE action_type = :action_type"),
                {"action_type": action_type},
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

        audit_count_before = await _role_mutation_audit_count(async_engine_fixture)
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
        assert await _role_mutation_audit_count(async_engine_fixture) == audit_count_before
    finally:
        async with async_engine_fixture.begin() as connection:
            await connection.execute(
                text("DELETE FROM roles WHERE name IN (:existing_name, :requested_name)"),
                {
                    "existing_name": existing_name,
                    "requested_name": requested_name,
                },
            )


@pytest.mark.integration
async def test_mapping_conflict_rolls_back_complete_role_update(
    authenticated_client,
    async_engine_fixture,
) -> None:
    """IS-GAP-036: failed mapping diff preserves every previous role value."""
    case_token = uuid4().hex
    target_name = f"chunk16-target-{case_token}"
    conflict_name = f"chunk16-conflict-{case_token}"
    kept_group = f"chunk16-kept-{case_token}"
    removed_group = f"chunk16-removed-{case_token}"
    conflicting_group = f"chunk16-conflicting-{case_token}"
    target_priority = 1_300_000_000 + int(case_token[:7], 16)
    conflict_priority = target_priority + 1

    try:
        async with async_engine_fixture.begin() as connection:
            target_role_id = await connection.scalar(
                text(
                    """
                    INSERT INTO roles (name, description, priority, permissions)
                    VALUES (:name, 'authoritative-before', :priority, '[]'::jsonb)
                    RETURNING id
                    """
                ),
                {"name": target_name, "priority": target_priority},
            )
            conflict_role_id = await connection.scalar(
                text(
                    """
                    INSERT INTO roles (name, priority, permissions)
                    VALUES (:name, :priority, '[]'::jsonb)
                    RETURNING id
                    """
                ),
                {"name": conflict_name, "priority": conflict_priority},
            )
            for group_value, role_id in (
                (kept_group, target_role_id),
                (removed_group, target_role_id),
                (conflicting_group, conflict_role_id),
            ):
                await connection.execute(
                    text(
                        """
                        INSERT INTO sso_group_mappings (sso_group_value, role_id)
                        VALUES (:group_value, :role_id)
                        """
                    ),
                    {"group_value": group_value, "role_id": role_id},
                )
            connection_id = await connection.scalar(
                text("SELECT id FROM source_database_connections ORDER BY created_at LIMIT 1")
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO role_connection_policies (
                        role_id, connection_id, allowed_tables, row_filters, column_masks
                    )
                    VALUES (:role_id, :connection_id, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb)
                    """
                ),
                {"role_id": target_role_id, "connection_id": connection_id},
            )

        async with async_engine_fixture.connect() as connection:
            original_mapping_rows = (
                await connection.execute(
                    text(
                        """
                        SELECT id, sso_group_value
                        FROM sso_group_mappings
                        WHERE role_id = :role_id
                        ORDER BY sso_group_value
                        """
                    ),
                    {"role_id": target_role_id},
                )
            ).all()
        audit_count_before = await _role_mutation_audit_count(async_engine_fixture)

        response = await authenticated_client.put(
            f"/api/v1/admin/roles/{target_role_id}",
            json={
                "description": "attempted-after",
                "group_mappings": [kept_group, conflicting_group],
                "connection_policies": [],
            },
        )

        assert response.status_code == 409
        assert response.json() == {
            "error": "conflict",
            "message_key": "error.conflict.duplicateGroupMapping",
        }
        assert conflicting_group not in response.text

        async with async_engine_fixture.connect() as connection:
            assert (
                await connection.scalar(
                    text("SELECT description FROM roles WHERE id = :role_id"),
                    {"role_id": target_role_id},
                )
                == "authoritative-before"
            )
            persisted_mapping_rows = (
                await connection.execute(
                    text(
                        """
                        SELECT id, sso_group_value
                        FROM sso_group_mappings
                        WHERE role_id = :role_id
                        ORDER BY sso_group_value
                        """
                    ),
                    {"role_id": target_role_id},
                )
            ).all()
            assert persisted_mapping_rows == original_mapping_rows
            assert (
                await connection.scalar(
                    text("SELECT COUNT(*) FROM role_connection_policies WHERE role_id = :role_id"),
                    {"role_id": target_role_id},
                )
                == 1
            )
        assert await _role_mutation_audit_count(async_engine_fixture) == audit_count_before
    finally:
        async with async_engine_fixture.begin() as connection:
            await connection.execute(
                text("DELETE FROM roles WHERE name IN (:target_name, :conflict_name)"),
                {"target_name": target_name, "conflict_name": conflict_name},
            )


@pytest.mark.integration
async def test_duplicate_groups_return_sanitized_422_without_mutation(
    authenticated_client,
    async_engine_fixture,
) -> None:
    case_token = uuid4().hex
    requested_name = f"chunk16-duplicate-{case_token}"
    duplicate_group = f"chunk16-duplicate-group-{case_token}"
    requested_priority = 1_500_000_000 + int(case_token[:7], 16)

    try:
        audit_count_before = await _role_mutation_audit_count(async_engine_fixture)
        response = await authenticated_client.post(
            "/api/v1/admin/roles",
            json={
                "name": requested_name,
                "priority": requested_priority,
                "permissions": [],
                "group_mappings": [duplicate_group, duplicate_group],
                "connection_policies": [],
            },
        )

        assert response.status_code == 422
        assert response.json()["error"] == "validation"
        assert response.json()["message_key"] == "error.validation.generic"
        assert duplicate_group not in response.text
        async with async_engine_fixture.connect() as connection:
            assert (
                await connection.scalar(
                    text("SELECT COUNT(*) FROM roles WHERE name = :name"),
                    {"name": requested_name},
                )
                == 0
            )
        assert await _role_mutation_audit_count(async_engine_fixture) == audit_count_before
    finally:
        async with async_engine_fixture.begin() as connection:
            await connection.execute(
                text("DELETE FROM roles WHERE name = :name"),
                {"name": requested_name},
            )


@pytest.mark.integration
async def test_noop_mapping_update_preserves_identity_without_audit(
    authenticated_client,
    async_engine_fixture,
) -> None:
    case_token = uuid4().hex
    role_name = f"chunk16-noop-{case_token}"
    group_values = [f"chunk16-noop-a-{case_token}", f"chunk16-noop-b-{case_token}"]
    role_priority = 1_700_000_000 + int(case_token[:7], 16)

    try:
        async with async_engine_fixture.begin() as connection:
            role_id = await connection.scalar(
                text(
                    """
                    INSERT INTO roles (name, priority, permissions)
                    VALUES (:name, :priority, '[]'::jsonb)
                    RETURNING id
                    """
                ),
                {"name": role_name, "priority": role_priority},
            )
            original_ids = []
            for group_value in group_values:
                original_ids.append(
                    await connection.scalar(
                        text(
                            """
                            INSERT INTO sso_group_mappings (sso_group_value, role_id)
                            VALUES (:group_value, :role_id)
                            RETURNING id
                            """
                        ),
                        {"group_value": group_value, "role_id": role_id},
                    )
                )

        role_updates_before = await _audit_action_count(async_engine_fixture, "role.update")
        mapping_updates_before = await _audit_action_count(async_engine_fixture, "role.mapping.change")
        response = await authenticated_client.put(
            f"/api/v1/admin/roles/{role_id}",
            json={"group_mappings": group_values},
        )

        assert response.status_code == 200
        assert response.json()["group_mappings"] == [
            {"id": str(mapping_id), "sso_group_value": group_value}
            for mapping_id, group_value in zip(original_ids, group_values, strict=True)
        ]
        assert await _audit_action_count(async_engine_fixture, "role.update") == role_updates_before
        assert await _audit_action_count(async_engine_fixture, "role.mapping.change") == mapping_updates_before
    finally:
        async with async_engine_fixture.begin() as connection:
            await connection.execute(text("DELETE FROM roles WHERE name = :name"), {"name": role_name})


@pytest.mark.integration
async def test_empty_mapping_update_clears_with_exact_delete_audits(
    authenticated_client,
    async_engine_fixture,
) -> None:
    case_token = uuid4().hex
    role_name = f"chunk16-clear-{case_token}"
    group_values = [f"chunk16-clear-a-{case_token}", f"chunk16-clear-b-{case_token}"]
    role_priority = 1_800_000_000 + int(case_token[:7], 16)

    try:
        async with async_engine_fixture.begin() as connection:
            role_id = await connection.scalar(
                text(
                    """
                    INSERT INTO roles (name, priority, permissions)
                    VALUES (:name, :priority, '[]'::jsonb)
                    RETURNING id
                    """
                ),
                {"name": role_name, "priority": role_priority},
            )
            for group_value in group_values:
                await connection.execute(
                    text(
                        """
                        INSERT INTO sso_group_mappings (sso_group_value, role_id)
                        VALUES (:group_value, :role_id)
                        """
                    ),
                    {"group_value": group_value, "role_id": role_id},
                )

        role_updates_before = await _audit_action_count(async_engine_fixture, "role.update")
        mapping_updates_before = await _audit_action_count(async_engine_fixture, "role.mapping.change")
        response = await authenticated_client.put(
            f"/api/v1/admin/roles/{role_id}",
            json={"group_mappings": []},
        )

        assert response.status_code == 200
        assert response.json()["group_mappings"] == []
        assert await _audit_action_count(async_engine_fixture, "role.update") == role_updates_before
        assert await _audit_action_count(async_engine_fixture, "role.mapping.change") == mapping_updates_before + 2
    finally:
        async with async_engine_fixture.begin() as connection:
            await connection.execute(text("DELETE FROM roles WHERE name = :name"), {"name": role_name})


@pytest.mark.integration
async def test_omitted_mappings_and_policies_preserve_authoritative_detail(
    authenticated_client,
    async_engine_fixture,
) -> None:
    case_token = uuid4().hex
    role_name = f"chunk16-omitted-{case_token}"
    group_value = f"chunk16-omitted-group-{case_token}"
    role_priority = 1_600_000_000 + int(case_token[:7], 16)

    try:
        async with async_engine_fixture.begin() as connection:
            role_id = await connection.scalar(
                text(
                    """
                    INSERT INTO roles (name, description, priority, permissions)
                    VALUES (:name, 'before', :priority, '[]'::jsonb)
                    RETURNING id
                    """
                ),
                {"name": role_name, "priority": role_priority},
            )
            mapping_id = await connection.scalar(
                text(
                    """
                    INSERT INTO sso_group_mappings (sso_group_value, role_id)
                    VALUES (:group_value, :role_id)
                    RETURNING id
                    """
                ),
                {"group_value": group_value, "role_id": role_id},
            )
            connection_id = await connection.scalar(
                text("SELECT id FROM source_database_connections ORDER BY created_at LIMIT 1")
            )
            policy_id = await connection.scalar(
                text(
                    """
                    INSERT INTO role_connection_policies (
                        role_id, connection_id, allowed_tables, row_filters, column_masks
                    )
                    VALUES (:role_id, :connection_id, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb)
                    RETURNING id
                    """
                ),
                {"role_id": role_id, "connection_id": connection_id},
            )

        role_updates_before = await _audit_action_count(async_engine_fixture, "role.update")
        mapping_updates_before = await _audit_action_count(async_engine_fixture, "role.mapping.change")
        response = await authenticated_client.put(
            f"/api/v1/admin/roles/{role_id}",
            json={"description": "after"},
        )

        assert response.status_code == 200
        assert response.json()["group_mappings"] == [
            {"id": str(mapping_id), "sso_group_value": group_value}
        ]
        assert response.json()["connection_policies"] == [
            {
                "id": str(policy_id),
                "connection_id": str(connection_id),
                "allowed_tables": [],
                "row_filters": [],
                "column_masks": [],
            }
        ]
        assert await _audit_action_count(async_engine_fixture, "role.update") == role_updates_before + 1
        assert await _audit_action_count(async_engine_fixture, "role.mapping.change") == mapping_updates_before
    finally:
        async with async_engine_fixture.begin() as connection:
            await connection.execute(text("DELETE FROM roles WHERE name = :name"), {"name": role_name})


@pytest.mark.integration
async def test_policy_only_change_emits_one_truthful_role_audit(
    authenticated_client,
    async_engine_fixture,
) -> None:
    case_token = uuid4().hex
    role_name = f"chunk16-policy-{case_token}"
    group_value = f"chunk16-policy-group-{case_token}"
    role_priority = 1_550_000_000 + int(case_token[:7], 16)

    try:
        async with async_engine_fixture.begin() as connection:
            role_id = await connection.scalar(
                text(
                    """
                    INSERT INTO roles (name, priority, permissions)
                    VALUES (:name, :priority, '[]'::jsonb)
                    RETURNING id
                    """
                ),
                {"name": role_name, "priority": role_priority},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO sso_group_mappings (sso_group_value, role_id)
                    VALUES (:group_value, :role_id)
                    """
                ),
                {"group_value": group_value, "role_id": role_id},
            )
            connection_id = await connection.scalar(
                text("SELECT id FROM source_database_connections ORDER BY created_at LIMIT 1")
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO role_connection_policies (
                        role_id, connection_id, allowed_tables, row_filters, column_masks
                    )
                    VALUES (:role_id, :connection_id, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb)
                    """
                ),
                {"role_id": role_id, "connection_id": connection_id},
            )

        role_updates_before = await _audit_action_count(async_engine_fixture, "role.update")
        mapping_updates_before = await _audit_action_count(async_engine_fixture, "role.mapping.change")
        response = await authenticated_client.put(
            f"/api/v1/admin/roles/{role_id}",
            json={
                "connection_policies": [
                    {
                        "connection_id": str(connection_id),
                        "allowed_tables": [{"table": "customer", "columns": ["customer_id"]}],
                        "row_filters": [],
                        "column_masks": [],
                    }
                ]
            },
        )

        assert response.status_code == 200
        assert await _audit_action_count(async_engine_fixture, "role.update") == role_updates_before + 1
        assert await _audit_action_count(async_engine_fixture, "role.mapping.change") == mapping_updates_before
        async with async_engine_fixture.connect() as connection:
            audit_context = await connection.scalar(
                text(
                    """
                    SELECT context
                    FROM audit_log_entries
                    WHERE action_type = 'role.update' AND resource_id = :resource_id
                    ORDER BY sequence_number DESC
                    LIMIT 1
                    """
                ),
                {"resource_id": str(role_id)},
            )
        assert audit_context == {"updated_fields": ["connection_policies"]}
    finally:
        async with async_engine_fixture.begin() as connection:
            await connection.execute(text("DELETE FROM roles WHERE name = :name"), {"name": role_name})
