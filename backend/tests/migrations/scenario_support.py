"""Populated-state builders and assertions for the 001-009 migration chain."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models.database_connection import SourceDatabaseConnection
from app.db.models.enums import DatabaseType, HealthStatus, LifecycleState, SchemaIntrospectionStatus
from app.db.models.sso_provider import SsoProvider
from app.db.models.user import User
from app.db.models.user_identity import UserIdentity
from app.repositories.connection_repository import ConnectionRepository
from app.repositories.detection_config_repository import DetectionConfigRepository
from app.repositories.quota_repository import QuotaRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.quota import RoleQuotaUpsert
from app.services.audit_service import AuditService
from tests.migrations.migration_support import SchemaInventory, schema_inventory

_PASSWORD_HASHER = PasswordHasher()


def seed_revision_state(database_url: str, revision: str, incompatible_user_count: int = 0) -> None:
    asyncio.run(_seed_revision_state(database_url, revision, incompatible_user_count))


def seed_local_only_revision_007_state(database_url: str) -> None:
    asyncio.run(_seed_local_only_revision_007_state(database_url))


def assign_valid_local_hashes(database_url: str) -> None:
    asyncio.run(_assign_valid_local_hashes(database_url))


def pre_revision_007_rows_are_coherent(database_url: str) -> bool:
    return asyncio.run(_pre_revision_007_rows_are_coherent(database_url))


def assert_genesis_chain(database_url: str) -> None:
    asyncio.run(_assert_genesis_chain(database_url))


def run_head_model_repository_smoke(database_url: str) -> None:
    asyncio.run(_run_head_model_repository_smoke(database_url))


def admin_seed_count(database_url: str) -> int:
    return asyncio.run(_admin_seed_count(database_url))


def assert_phase6_permissions_unique(database_url: str) -> None:
    asyncio.run(_assert_phase6_permissions_unique(database_url))


def assert_revision_schema(database_url: str, revision: str | None) -> None:
    inventory = schema_inventory(database_url)
    if revision is None:
        assert inventory.table_names == {"alembic_version"}
        return

    revision_number = int(revision)
    assert inventory.table_names == _expected_tables(revision_number)
    _assert_expected_columns(inventory, revision_number)
    _assert_expected_constraints(inventory, revision_number)
    _assert_expected_indexes(inventory, revision_number)
    _assert_expected_nullability_and_defaults(inventory, revision_number)


def schema_evidence(database_url: str, revision: str) -> dict[str, int | str]:
    inventory = schema_inventory(database_url)
    return {
        "revision": revision,
        "table_count": len(inventory.tables),
        "column_count": sum(len(table.columns) for table in inventory.tables),
        "constraint_count": sum(
            1 + len(table.foreign_keys) + len(table.unique_constraints) for table in inventory.tables
        ),
        "index_count": sum(len(table.indexes) for table in inventory.tables),
    }


async def _seed_revision_state(database_url: str, revision: str, incompatible_user_count: int) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            revision_number = int(revision)
            local_user_id = await _seed_local_user(connection, revision_number)
            source_id = await _seed_source(connection, revision_number)
            await _seed_history(connection, revision_number, local_user_id, source_id)
            if revision_number >= 7:
                await _seed_rbac_security(connection, source_id, incompatible_user_count)
            if revision_number >= 8:
                await _seed_phase6_security(connection)
    finally:
        await engine.dispose()


async def _seed_local_only_revision_007_state(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            local_user_id = await _seed_local_user(connection, 7)
            source_id = await _seed_source(connection, 7)
            await _seed_history(connection, 7, local_user_id, source_id)
    finally:
        await engine.dispose()


async def _seed_local_user(connection, revision_number: int) -> UUID:
    user_id = uuid4()
    local_hash = _PASSWORD_HASHER.hash("migration-local-fixture")
    if revision_number >= 7:
        admin_role_id = await connection.scalar(text("SELECT id FROM roles WHERE name = 'Admin'"))
        statement = text(
            """
            INSERT INTO users (
                id, username, display_name, password_hash, role, role_id,
                is_builtin, auth_provider
            ) VALUES (
                :id, 'migration-local', 'Migration Local', :password_hash,
                'admin', :role_id, false, 'local'
            )
            """
        )
        parameters = {"id": user_id, "password_hash": local_hash, "role_id": admin_role_id}
    else:
        statement = text(
            """
            INSERT INTO users (id, username, display_name, password_hash, role)
            VALUES (:id, 'migration-local', 'Migration Local', :password_hash, 'admin')
            """
        )
        parameters = {"id": user_id, "password_hash": local_hash}
    await connection.execute(statement, parameters)
    return user_id


async def _seed_source(connection, revision_number: int) -> UUID:
    source_id = uuid4()
    if revision_number < 6:
        await connection.execute(
            text(
                """
                INSERT INTO database_connections (
                    id, name, host, port, database_name, username,
                    encrypted_password, ssl_mode, schema_metadata, schema_cached_at
                ) VALUES (
                    :id, 'Migration source', '127.0.0.1', 5432, 'migration_fixture',
                    'fixture_reader', 'encrypted-fixture', 'disable',
                    '{"orders":{"id":"integer"}}'::jsonb, now()
                )
                """
            ),
            {"id": source_id},
        )
        return source_id

    await connection.execute(
        text(
            """
            INSERT INTO source_database_connections (
                id, display_name, database_type, host, port, database_name, username,
                encrypted_password, ssl_mode, lifecycle_state, health_status,
                schema_introspection_status, schema_last_refreshed_at
            ) VALUES (
                :id, 'Migration source', 'postgresql', '127.0.0.1', 5432,
                'migration_fixture', 'fixture_reader', 'encrypted-fixture', 'disable',
                'active', 'healthy', 'success', now()
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
    return source_id


async def _seed_history(connection, revision_number: int, user_id: UUID, source_id: UUID) -> None:
    session_id = None
    if revision_number >= 4:
        session_id = uuid4()
        if revision_number >= 6:
            await connection.execute(
                text(
                    """
                    INSERT INTO sessions (id, user_id, connection_id, preview_text)
                    VALUES (:id, :user_id, :connection_id, 'Migration session')
                    """
                ),
                {"id": session_id, "user_id": user_id, "connection_id": source_id},
            )
        else:
            await connection.execute(
                text(
                    """
                    INSERT INTO sessions (id, user_id, preview_text)
                    VALUES (:id, :user_id, 'Migration session')
                    """
                ),
                {"id": session_id, "user_id": user_id},
            )

    columns = ["user_id", "database_connection_id", "question_text", "generated_sql", "llm_provider"]
    values = [":user_id", ":source_id", "'Migration question'", "'SELECT 1'", "'fixture'"]
    if revision_number >= 3:
        columns.append("attempt_id")
        values.append("'migration-attempt'")
    if revision_number >= 4:
        columns.extend(("session_id", "saved", "feedback"))
        values.extend((":session_id", "true", "1"))
    if revision_number >= 5:
        columns.extend(("result_columns", "result_rows", "result_row_count"))
        values.extend(("'[\"id\"]'::jsonb", "'[[1]]'::jsonb", "1"))
    await connection.execute(
        text(f"INSERT INTO accepted_queries ({', '.join(columns)}) VALUES ({', '.join(values)})"),
        {"user_id": user_id, "source_id": source_id, "session_id": session_id},
    )


async def _seed_rbac_security(connection, source_id: UUID, incompatible_user_count: int) -> None:
    role_id = uuid4()
    await _seed_role_provider_policy(connection, role_id, source_id)
    compatible_user_id = await _seed_sso_user(connection, role_id, 0, has_local_hash=True)
    for ordinal in range(1, incompatible_user_count + 1):
        await _seed_sso_user(connection, role_id, ordinal, has_local_hash=False)
    await _seed_audit_entry(connection, compatible_user_id)


async def _seed_role_provider_policy(connection, role_id: UUID, source_id: UUID) -> None:
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
        text("INSERT INTO sso_group_mappings (sso_group_value, role_id) VALUES ('migration-analysts', :role_id)"),
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


async def _seed_sso_user(connection, role_id: UUID, ordinal: int, has_local_hash: bool) -> UUID:
    user_id = uuid4()
    local_hash = _PASSWORD_HASHER.hash("migration-sso-compatible") if has_local_hash else None
    await connection.execute(
        text(
            """
            INSERT INTO users (
                id, username, display_name, password_hash, role, role_id, auth_provider
            ) VALUES (
                :id, :username, :display_name, :password_hash, 'user', :role_id, 'oidc'
            )
            """
        ),
        {
            "id": user_id,
            "username": f"migration-sso-{ordinal}",
            "display_name": f"Migration SSO {ordinal}",
            "password_hash": local_hash,
            "role_id": role_id,
        },
    )
    await connection.execute(
        text(
            """
            INSERT INTO user_identities (user_id, provider, subject_id, email, sso_groups)
            VALUES (:user_id, 'oidc', :subject_id, :email, '["migration-analysts"]'::jsonb)
            """
        ),
        {
            "user_id": user_id,
            "subject_id": f"migration-subject-{ordinal}",
            "email": f"migration-{ordinal}@invalid.example",
        },
    )
    return user_id


async def _seed_audit_entry(connection, actor_id: UUID) -> None:
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
        {"timestamp": timestamp, "actor_id": actor_id, "prev_hash": genesis_hash, "row_hash": row_hash},
    )


async def _seed_phase6_security(connection) -> None:
    role_id = await connection.scalar(text("SELECT id FROM roles WHERE name = 'Migration analyst'"))
    user_id = await connection.scalar(text("SELECT id FROM users WHERE username = 'migration-local'"))
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
        {"updated_by": user_id},
    )


async def _assign_valid_local_hashes(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            local_hash = _PASSWORD_HASHER.hash("migration-fixture-remediation")
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
            tables = (
                "users",
                "source_database_connections",
                "connection_schema_entries",
                "sessions",
                "accepted_queries",
            )
            counts = [
                int(await connection.scalar(text(f"SELECT count(*) FROM {table_name}")) or 0) for table_name in tables
            ]
            missing_hashes = int(
                await connection.scalar(text("SELECT count(*) FROM users WHERE password_hash IS NULL")) or 0
            )
            return all(counts) and missing_hashes == 0
    finally:
        await engine.dispose()


async def _assert_genesis_chain(database_url: str) -> None:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_factory() as session:
            verification = await AuditService.verify_chain(session)
            genesis_count = await session.scalar(
                text("SELECT count(*) FROM audit_log_entries WHERE sequence_number = 1 AND prev_hash = 'GENESIS'")
            )
            assert verification.verified
            assert genesis_count == 1
    finally:
        await engine.dispose()


async def _admin_seed_count(database_url: str) -> int:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            return int(await connection.scalar(text("SELECT count(*) FROM users WHERE username = 'admin'")) or 0)
    finally:
        await engine.dispose()


async def _assert_phase6_permissions_unique(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            permissions = await connection.scalar(text("SELECT permissions FROM roles WHERE name = 'Admin'"))
            assert len(permissions) == len(set(permissions))
            assert {"admin.quotas.manage", "admin.security.manage"}.issubset(permissions)
    finally:
        await engine.dispose()


async def _run_head_model_repository_smoke(database_url: str) -> None:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_factory.begin() as session:
            role = await RoleRepository(session).create(
                name="Repository smoke", priority=75, permissions=["query.submit"], is_builtin=False
            )
            user = User(
                username="repository-smoke",
                display_name="Repository Smoke",
                password_hash=_PASSWORD_HASHER.hash("repository-smoke"),
                role="user",
                role_id=role.id,
                auth_provider="local",
            )
            session.add(user)
            await session.flush()
            session.add(UserIdentity(user_id=user.id, provider="oidc", subject_id="repository-smoke"))
            session.add(SsoProvider(protocol="saml", display_name="Repository smoke IdP"))
            connection = await ConnectionRepository(session).create(_smoke_connection())
            await QuotaRepository(session).upsert(role.id, RoleQuotaUpsert(daily_query_limit=10))
            detection = await DetectionConfigRepository(session).get()
            assert await UserRepository(session).get_by_username(user.username) is not None
            assert await RoleRepository(session).get_by_id(role.id) is not None
            assert await ConnectionRepository(session).get_by_id(connection.id) is not None
            assert await session.scalar(select(UserIdentity.id).where(UserIdentity.user_id == user.id)) is not None
            assert detection.block_confidence > detection.flag_confidence
            assert (await AuditService.verify_chain(session)).verified
    finally:
        await engine.dispose()


def _smoke_connection() -> SourceDatabaseConnection:
    return SourceDatabaseConnection(
        display_name="Repository smoke source",
        database_type=DatabaseType.POSTGRESQL,
        host="127.0.0.1",
        port=5432,
        database_name="repository_smoke",
        username="repository_reader",
        encrypted_password="encrypted-fixture",
        ssl_mode="disable",
        lifecycle_state=LifecycleState.ACTIVE,
        health_status=HealthStatus.HEALTHY,
        schema_introspection_status=SchemaIntrospectionStatus.SUCCESS,
    )


def _expected_tables(revision_number: int) -> frozenset[str]:
    tables = {"alembic_version", "accepted_queries", "app_config", "users"}
    tables.add("database_connections" if revision_number < 6 else "source_database_connections")
    if revision_number >= 4:
        tables.add("sessions")
    if revision_number >= 6:
        tables.add("connection_schema_entries")
    if revision_number >= 7:
        tables.update(
            {
                "audit_log_entries",
                "role_connection_policies",
                "roles",
                "sso_group_mappings",
                "sso_providers",
                "user_identities",
            }
        )
    if revision_number >= 8:
        tables.update({"detection_threshold_config", "role_quotas"})
    return frozenset(tables)


def _assert_expected_columns(inventory: SchemaInventory, revision_number: int) -> None:
    accepted_columns = {
        "id",
        "user_id",
        "database_connection_id",
        "question_text",
        "generated_sql",
        "llm_provider",
        "accepted_at",
    }
    if revision_number >= 3:
        accepted_columns.add("attempt_id")
    if revision_number >= 4:
        accepted_columns.update({"session_id", "saved", "feedback"})
    if revision_number >= 5:
        accepted_columns.update({"result_columns", "result_rows", "result_row_count"})
    assert _column_names(inventory, "accepted_queries") == accepted_columns

    user_columns = {"id", "username", "display_name", "password_hash", "role", "created_at", "updated_at"}
    if revision_number >= 7:
        user_columns.update({"role_id", "is_builtin", "auth_provider"})
    assert _column_names(inventory, "users") == user_columns

    if revision_number >= 6:
        assert {"display_name", "database_type", "lifecycle_state", "health_status"}.issubset(
            _column_names(inventory, "source_database_connections")
        )
        assert {"connection_id", "table_name", "column_name", "column_data_type"}.issubset(
            _column_names(inventory, "connection_schema_entries")
        )
    else:
        assert {"name", "schema_metadata", "schema_cached_at"}.issubset(
            _column_names(inventory, "database_connections")
        )


def _assert_expected_constraints(inventory: SchemaInventory, revision_number: int) -> None:
    for table in inventory.tables:
        if table.name != "alembic_version":
            assert table.primary_key[1]
    assert ("username",) in _unique_column_sets(inventory, "users")
    expected_source = "database_connections" if revision_number < 6 else "source_database_connections"
    assert expected_source in _foreign_key_targets(inventory, "accepted_queries")
    assert "users" in _foreign_key_targets(inventory, "accepted_queries")
    if revision_number < 6:
        assert ("name",) in _unique_column_sets(inventory, "database_connections")
    if revision_number >= 4:
        assert "users" in _foreign_key_targets(inventory, "sessions")
        assert "sessions" in _foreign_key_targets(inventory, "accepted_queries")
    if revision_number >= 6:
        assert ("connection_id", "table_name", "column_name") in _unique_column_sets(
            inventory, "connection_schema_entries"
        )
    if revision_number >= 7:
        assert {("name",), ("priority",)}.issubset(_unique_column_sets(inventory, "roles"))
        assert ("protocol",) in _unique_column_sets(inventory, "sso_providers")
        assert ("provider", "subject_id") in _unique_column_sets(inventory, "user_identities")
        assert ("role_id", "connection_id") in _unique_column_sets(inventory, "role_connection_policies")
    if revision_number >= 8:
        assert ("role_id",) in _unique_column_sets(inventory, "role_quotas")


def _assert_expected_indexes(inventory: SchemaInventory, revision_number: int) -> None:
    assert "idx_accepted_queries_user_id_accepted_at" in _index_names(inventory, "accepted_queries")
    if revision_number >= 4:
        assert {"ix_sessions_user_id_last_activity", "ix_accepted_queries_session_id"}.issubset(
            _all_index_names(inventory)
        )
    if revision_number >= 6:
        assert {"ix_schema_entries_connection_id", "ix_source_db_connections_lifecycle_state"}.issubset(
            _all_index_names(inventory)
        )
    if revision_number >= 7:
        assert {
            "ix_audit_log_entries_action_type",
            "ix_audit_log_entries_timestamp",
            "ix_audit_log_entries_actor_id",
        }.issubset(_all_index_names(inventory))
    if revision_number >= 9:
        assert {
            "ix_audit_log_entries_actor_identity",
            "ix_audit_log_entries_outcome",
            "ix_audit_log_entries_context_gin",
        }.issubset(_all_index_names(inventory))
    elif revision_number >= 7:
        assert {
            "ix_audit_log_entries_actor_identity",
            "ix_audit_log_entries_outcome",
            "ix_audit_log_entries_context_gin",
        }.isdisjoint(_all_index_names(inventory))


def _assert_expected_nullability_and_defaults(inventory: SchemaInventory, revision_number: int) -> None:
    assert _column(inventory, "users", "username")[2] is False
    assert _column(inventory, "users", "password_hash")[2] is (revision_number >= 7)
    assert _column(inventory, "users", "created_at")[3] is not None
    source_table = "database_connections" if revision_number < 6 else "source_database_connections"
    assert _column(inventory, source_table, "port")[3] is not None
    if revision_number >= 4:
        assert _column(inventory, "accepted_queries", "saved")[2] is False
        assert _column(inventory, "accepted_queries", "saved")[3] is not None
    if revision_number >= 6:
        assert _column(inventory, source_table, "database_type")[3] is not None
    if revision_number >= 7:
        assert _column(inventory, "roles", "permissions")[3] is not None
        assert _column(inventory, "users", "auth_provider")[2] is False
    if revision_number >= 8:
        assert _column(inventory, "detection_threshold_config", "block_confidence")[3] is not None


def _column_names(inventory: SchemaInventory, table_name: str) -> set[str]:
    return {column[0] for column in inventory.table(table_name).columns}


def _column(inventory: SchemaInventory, table_name: str, column_name: str) -> tuple[str, str, bool, str | None]:
    return next(column for column in inventory.table(table_name).columns if column[0] == column_name)


def _unique_column_sets(inventory: SchemaInventory, table_name: str) -> set[tuple[str, ...]]:
    return {columns for _, columns in inventory.table(table_name).unique_constraints}


def _foreign_key_targets(inventory: SchemaInventory, table_name: str) -> set[str]:
    return {str(foreign_key[2]) for foreign_key in inventory.table(table_name).foreign_keys}


def _index_names(inventory: SchemaInventory, table_name: str) -> set[str]:
    return {str(index[0]) for index in inventory.table(table_name).indexes}


def _all_index_names(inventory: SchemaInventory) -> set[str]:
    return {str(index[0]) for table in inventory.tables for index in table.indexes}
