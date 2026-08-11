"""PostgreSQL proof for revision 010 persisted invariants."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from tests.migrations.migration_support import (
    current_revision,
    database_snapshot,
    revision_ids,
    upgrade,
)
from tests.migrations.scenario_support import assert_revision_schema

EXPECTED_REFUSAL = "Revision 010 preflight refused: persisted invariant repair is required before retry."


def _constraint_name(error: IntegrityError) -> str | None:
    driver_error = getattr(error.orig, "__cause__", None)
    return getattr(driver_error, "constraint_name", None)


async def _execute_invalid_write(
    database_url: str,
    statement: str,
    parameters: Mapping[str, Any] | None = None,
) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(statement), parameters or {})
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_revision_010_is_dynamic_head(disposable_database_url: str) -> None:
    upgrade(disposable_database_url, "head")

    assert revision_ids()[-1] == "010"
    assert current_revision(disposable_database_url) == "010"
    assert_revision_schema(disposable_database_url, "010")


@pytest.mark.integration
@pytest.mark.parametrize(
    ("column_name", "constraint_name"),
    [
        ("daily_query_limit", "ck_role_quotas_daily_query_limit_nonnegative"),
        ("daily_execution_limit", "ck_role_quotas_daily_execution_limit_nonnegative"),
        ("daily_export_limit", "ck_role_quotas_daily_export_limit_nonnegative"),
    ],
)
def test_negative_nullable_role_quota_is_rejected(
    disposable_database_url: str,
    column_name: str,
    constraint_name: str,
) -> None:
    upgrade(disposable_database_url, "head")
    statement = f"""
        INSERT INTO role_quotas (role_id, {column_name})
        SELECT id, -1 FROM roles WHERE name = 'Admin'
    """

    with pytest.raises(IntegrityError) as rejected:
        asyncio.run(_execute_invalid_write(disposable_database_url, statement))

    assert _constraint_name(rejected.value) == constraint_name


@pytest.mark.integration
@pytest.mark.parametrize(
    ("block_confidence", "flag_confidence"),
    [
        (0.8, -0.1),
        (1.1, 0.5),
        (0.5, 0.5),
        (0.4, 0.5),
        (float("nan"), 0.5),
        (0.8, float("nan")),
        (float("inf"), 0.5),
        (float("-inf"), 0.5),
        (0.8, float("inf")),
        (0.8, float("-inf")),
    ],
    ids=[
        "negative",
        "above-one",
        "equal",
        "reversed",
        "nan-block",
        "nan-flag",
        "positive-infinity-block",
        "negative-infinity-block",
        "positive-infinity-flag",
        "negative-infinity-flag",
    ],
)
def test_invalid_detection_thresholds_are_rejected(
    disposable_database_url: str,
    block_confidence: float,
    flag_confidence: float,
) -> None:
    upgrade(disposable_database_url, "head")

    with pytest.raises(IntegrityError) as rejected:
        asyncio.run(
            _execute_invalid_write(
                disposable_database_url,
                """
                UPDATE detection_threshold_config
                SET block_confidence = :block_confidence,
                    flag_confidence = :flag_confidence
                """,
                {
                    "block_confidence": block_confidence,
                    "flag_confidence": flag_confidence,
                },
            )
        )

    assert _constraint_name(rejected.value) == "ck_detection_thresholds_ordered_range"


@pytest.mark.integration
@pytest.mark.parametrize(
    ("column_name", "constraint_name"),
    [
        ("database_type", "ck_source_db_connections_database_type_valid"),
        ("lifecycle_state", "ck_source_db_connections_lifecycle_state_valid"),
        ("health_status", "ck_source_db_connections_health_status_valid"),
        ("schema_introspection_status", "ck_source_db_connections_schema_status_valid"),
    ],
)
def test_invalid_source_connection_enum_is_rejected(
    disposable_database_url: str,
    column_name: str,
    constraint_name: str,
) -> None:
    upgrade(disposable_database_url, "head")
    statement = """
        INSERT INTO source_database_connections (
            display_name, database_type, host, port, database_name, username,
            encrypted_password, ssl_mode, lifecycle_state, health_status,
            schema_introspection_status
        ) VALUES (
            'Constraint proof', 'postgresql', 'example.invalid', 5432,
            'constraint_proof', 'constraint_reader', 'encrypted', 'disable',
            'active', 'untested', 'none'
        )
        RETURNING id
    """

    async def insert_then_corrupt() -> None:
        engine = create_async_engine(disposable_database_url)
        try:
            async with engine.begin() as connection:
                connection_id = await connection.scalar(text(statement))
                await connection.execute(
                    text(f"UPDATE source_database_connections SET {column_name} = 'invalid' WHERE id = :id"),
                    {"id": connection_id},
                )
        finally:
            await engine.dispose()

    with pytest.raises(IntegrityError) as rejected:
        asyncio.run(insert_then_corrupt())

    assert _constraint_name(rejected.value) == constraint_name


@pytest.mark.integration
@pytest.mark.parametrize(
    ("statement", "constraint_name"),
    [
        (
            """
            INSERT INTO users (username, display_name, password_hash, role, auth_provider)
            VALUES ('invalid-auth-provider', 'Invalid auth provider', NULL, 'user', 'invalid')
            """,
            "ck_users_auth_provider_valid",
        ),
        (
            """
            INSERT INTO sso_providers (protocol, display_name)
            VALUES ('invalid', 'Invalid protocol')
            """,
            "ck_sso_providers_protocol_valid",
        ),
    ],
    ids=["user-auth-provider", "sso-protocol"],
)
def test_invalid_identity_provider_enum_is_rejected(
    disposable_database_url: str,
    statement: str,
    constraint_name: str,
) -> None:
    upgrade(disposable_database_url, "head")

    with pytest.raises(IntegrityError) as rejected:
        asyncio.run(_execute_invalid_write(disposable_database_url, statement))

    assert _constraint_name(rejected.value) == constraint_name


PREFLIGHT_CORRUPTIONS = [
    pytest.param(
        """
        INSERT INTO role_quotas (role_id, daily_query_limit)
        SELECT id, -1 FROM roles WHERE name = 'Admin'
        """,
        id="quota",
    ),
    pytest.param(
        """
        INSERT INTO detection_threshold_config (block_confidence, flag_confidence)
        VALUES ('NaN'::double precision, 0.5)
        """,
        id="threshold",
    ),
    pytest.param(
        """
        INSERT INTO source_database_connections (
            display_name, database_type, host, port, database_name, username,
            encrypted_password, ssl_mode, lifecycle_state, health_status,
            schema_introspection_status
        ) VALUES (
            'Preflight proof', 'invalid', 'example.invalid', 5432,
            'preflight_proof', 'preflight_reader', 'encrypted', 'disable',
            'active', 'untested', 'none'
        )
        """,
        id="source-enum",
    ),
    pytest.param(
        """
        INSERT INTO users (username, display_name, password_hash, role, auth_provider)
        VALUES ('preflight-invalid-auth', 'Preflight invalid auth', NULL, 'user', 'invalid')
        """,
        id="auth-provider",
    ),
    pytest.param(
        """
        INSERT INTO sso_providers (protocol, display_name)
        VALUES ('invalid', 'Preflight invalid protocol')
        """,
        id="sso-protocol",
    ),
]


@pytest.mark.integration
@pytest.mark.parametrize("corruption_statement", PREFLIGHT_CORRUPTIONS)
def test_populated_preflight_refusal_is_atomic(
    disposable_database_url: str,
    corruption_statement: str,
) -> None:
    upgrade(disposable_database_url, "009")
    asyncio.run(_execute_invalid_write(disposable_database_url, corruption_statement))
    before_refusal = database_snapshot(disposable_database_url)

    with pytest.raises(RuntimeError) as refusal:
        upgrade(disposable_database_url, "010")

    assert str(refusal.value) == EXPECTED_REFUSAL
    assert current_revision(disposable_database_url) == "009"
    assert database_snapshot(disposable_database_url) == before_refusal
