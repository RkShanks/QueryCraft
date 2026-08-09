"""Revision 007 downgrade safety against populated PostgreSQL."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from argon2 import PasswordHasher
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.migrations.migration_support import (
    current_revision,
    database_snapshot,
    downgrade,
    revision_ids,
    upgrade,
)

EXPECTED_DOWNGRADE_REFUSAL = (
    "Revision 007 downgrade blocked: remove incompatible users or assign valid local authentication "
    "hashes before retrying."
)
PROHIBITED_ERROR_TERMS = (
    "username",
    "email",
    "subject",
    "provider",
    "group",
    "token",
    "certificate",
    "role",
    "connection",
    "password",
)


@pytest.mark.integration
def test_head_to_006_refuses_incompatible_users_atomically_then_allows_explicit_remediation(
    disposable_database_url: str,
) -> None:
    head_revision = revision_ids()[-1]
    upgrade(disposable_database_url, "head")
    asyncio.run(_seed_populated_head(disposable_database_url, incompatible_user_count=2))
    before_refusal = database_snapshot(disposable_database_url)

    with pytest.raises(RuntimeError) as refusal:
        downgrade(disposable_database_url, "006")

    assert str(refusal.value) == EXPECTED_DOWNGRADE_REFUSAL
    assert all(term not in str(refusal.value).casefold() for term in PROHIBITED_ERROR_TERMS)
    assert current_revision(disposable_database_url) == head_revision
    assert database_snapshot(disposable_database_url) == before_refusal

    asyncio.run(_assign_valid_local_hashes(disposable_database_url))
    downgrade(disposable_database_url, "006")
    assert current_revision(disposable_database_url) == "006"
    assert asyncio.run(_pre_revision_007_rows_are_coherent(disposable_database_url))

    upgrade(disposable_database_url, "head")
    assert current_revision(disposable_database_url) == head_revision


async def _seed_populated_head(database_url: str, incompatible_user_count: int) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            admin_user_id = await connection.scalar(text("SELECT id FROM users WHERE is_builtin = true"))
            source_id = uuid4()
            session_id = uuid4()
            role_id = uuid4()
            await _seed_source_history(connection, admin_user_id, source_id, session_id)
            await _seed_rbac_objects(connection, role_id, source_id)
            user_ids = await _seed_incompatible_users(connection, role_id, incompatible_user_count)
            await _seed_security_rows(connection, role_id, user_ids[0])
    finally:
        await engine.dispose()


async def _seed_source_history(connection, admin_user_id, source_id, session_id) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO source_database_connections (
                id, display_name, database_type, host, port, database_name, username,
                encrypted_password, ssl_mode, lifecycle_state, health_status,
                schema_introspection_status
            ) VALUES (
                :id, 'Migration source', 'postgresql', '127.0.0.1', 5432,
                'migration_fixture', 'fixture_reader', 'encrypted-fixture', 'disable',
                'active', 'healthy', 'success'
            )
            """
        ),
        {"id": source_id},
    )
    await connection.execute(
        text(
            """
            INSERT INTO connection_schema_entries (
                connection_id, table_name, column_name, column_data_type, is_primary_key
            ) VALUES (:connection_id, 'orders', 'id', 'integer', true)
            """
        ),
        {"connection_id": source_id},
    )
    await connection.execute(
        text(
            """
            INSERT INTO sessions (id, user_id, connection_id, preview_text)
            VALUES (:id, :user_id, :connection_id, 'Migration session')
            """
        ),
        {"id": session_id, "user_id": admin_user_id, "connection_id": source_id},
    )
    await connection.execute(
        text(
            """
            INSERT INTO accepted_queries (
                user_id, database_connection_id, session_id, question_text, generated_sql,
                llm_provider, attempt_id, saved, feedback, result_columns, result_rows,
                result_row_count
            ) VALUES (
                :user_id, :connection_id, :session_id, 'Migration question', 'SELECT 1',
                'fixture', 'migration-attempt', true, 1, '["id"]'::jsonb,
                '[[1]]'::jsonb, 1
            )
            """
        ),
        {"user_id": admin_user_id, "connection_id": source_id, "session_id": session_id},
    )


async def _seed_rbac_objects(connection, role_id, source_id) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO roles (id, name, description, priority, permissions)
            VALUES (:id, 'Migration analyst', 'Migration fixture', 50, '["query.submit"]'::jsonb)
            """
        ),
        {"id": role_id},
    )
    await connection.execute(
        text(
            """
            INSERT INTO sso_providers (protocol, display_name, issuer_url, client_id)
            VALUES ('oidc', 'Migration IdP', 'https://idp.invalid', 'migration-client')
            """
        )
    )
    await connection.execute(
        text(
            """
            INSERT INTO sso_group_mappings (sso_group_value, role_id)
            VALUES ('migration-analysts', :role_id)
            """
        ),
        {"role_id": role_id},
    )
    await connection.execute(
        text(
            """
            INSERT INTO role_connection_policies (
                role_id, connection_id, allowed_tables, row_filters, column_masks
            ) VALUES (
                :role_id, :connection_id, '[{"table":"orders"}]'::jsonb,
                '[]'::jsonb, '[]'::jsonb
            )
            """
        ),
        {"role_id": role_id, "connection_id": source_id},
    )


async def _seed_incompatible_users(connection, role_id, incompatible_user_count: int) -> list:
    user_ids = [uuid4() for _ in range(incompatible_user_count)]
    for ordinal, user_id in enumerate(user_ids):
        await connection.execute(
            text(
                """
                INSERT INTO users (
                    id, username, display_name, password_hash, role, role_id, auth_provider
                ) VALUES (
                    :id, :username, :display_name, NULL, 'user', :role_id, 'oidc'
                )
                """
            ),
            {
                "id": user_id,
                "username": f"migration-sso-{ordinal}",
                "display_name": f"Migration SSO {ordinal}",
                "role_id": role_id,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO user_identities (
                    user_id, provider, subject_id, email, sso_groups
                ) VALUES (
                    :user_id, 'oidc', :subject_id, :email, '["migration-analysts"]'::jsonb
                )
                """
            ),
            {
                "user_id": user_id,
                "subject_id": f"migration-subject-{ordinal}",
                "email": f"migration-{ordinal}@invalid.example",
            },
        )
    return user_ids


async def _seed_security_rows(connection, role_id, actor_id) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO role_quotas (
                role_id, daily_query_limit, daily_execution_limit, daily_export_limit
            ) VALUES (:role_id, 20, 10, 5)
            """
        ),
        {"role_id": role_id},
    )
    await connection.execute(
        text(
            """
            INSERT INTO detection_threshold_config (block_confidence, flag_confidence, updated_by)
            VALUES (0.8, 0.5, :updated_by)
            """
        ),
        {"updated_by": actor_id},
    )
    genesis_hash = await connection.scalar(text("SELECT row_hash FROM audit_log_entries WHERE sequence_number = 1"))
    timestamp = datetime.now(UTC)
    payload = {
        "sequence_number": 2,
        "timestamp": timestamp.isoformat(),
        "actor_id": str(actor_id),
        "actor_identity": "migration-fixture",
        "action_type": "auth.login.success",
        "resource_type": "session",
        "resource_id": None,
        "outcome": "success",
        "context": {"classification": "migration-fixture"},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    row_hash = hashlib.sha256(f"{canonical}{genesis_hash}".encode()).hexdigest()
    await connection.execute(
        text(
            """
            INSERT INTO audit_log_entries (
                sequence_number, timestamp, actor_id, actor_identity, action_type,
                resource_type, resource_id, outcome, context, prev_hash, row_hash
            ) VALUES (
                2, :timestamp, :actor_id, 'migration-fixture', 'auth.login.success',
                'session', NULL, 'success', '{"classification":"migration-fixture"}'::jsonb,
                :prev_hash, :row_hash
            )
            """
        ),
        {
            "timestamp": timestamp,
            "actor_id": actor_id,
            "prev_hash": genesis_hash,
            "row_hash": row_hash,
        },
    )


async def _assign_valid_local_hashes(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            local_hash = PasswordHasher().hash("migration-fixture-remediation")
            await connection.execute(
                text("UPDATE users SET password_hash = :local_hash WHERE password_hash IS NULL"),
                {"local_hash": local_hash},
            )
    finally:
        await engine.dispose()


async def _pre_revision_007_rows_are_coherent(database_url: str) -> bool:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            counts = {
                table_name: int(await connection.scalar(text(f"SELECT count(*) FROM {table_name}")) or 0)
                for table_name in (
                    "users",
                    "source_database_connections",
                    "connection_schema_entries",
                    "sessions",
                    "accepted_queries",
                )
            }
            missing_hashes = int(
                await connection.scalar(text("SELECT count(*) FROM users WHERE password_hash IS NULL")) or 0
            )
            return all(counts.values()) and missing_hashes == 0
    finally:
        await engine.dispose()
