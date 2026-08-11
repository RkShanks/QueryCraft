"""PostgreSQL proof for revision 010 persisted invariants."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1 import admin_detection
from app.core.dependencies import get_db
from app.repositories.detection_config_repository import DetectionConfigRepository
from tests.migrations.migration_support import (
    current_revision,
    database_snapshot,
    downgrade,
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
def test_revision_010_invariants_survive_upgrade_to_dynamic_head(
    disposable_database_url: str,
) -> None:
    upgrade(disposable_database_url, "head")

    assert revision_ids()[-1] == "011"
    assert current_revision(disposable_database_url) == "011"
    assert_revision_schema(disposable_database_url, "011")


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


@pytest.mark.integration
def test_duplicate_detection_preflight_refusal_is_atomic(disposable_database_url: str) -> None:
    upgrade(disposable_database_url, "009")
    asyncio.run(
        _execute_invalid_write(
            disposable_database_url,
            """
            INSERT INTO detection_threshold_config (block_confidence, flag_confidence)
            VALUES (0.8, 0.5), (0.9, 0.4)
            """,
        )
    )
    before_refusal = database_snapshot(disposable_database_url)

    with pytest.raises(RuntimeError) as refusal:
        upgrade(disposable_database_url, "010")

    assert str(refusal.value) == EXPECTED_REFUSAL
    assert current_revision(disposable_database_url) == "009"
    assert database_snapshot(disposable_database_url) == before_refusal


@pytest.mark.integration
def test_second_detection_row_is_rejected(disposable_database_url: str) -> None:
    upgrade(disposable_database_url, "head")

    with pytest.raises(IntegrityError) as rejected:
        asyncio.run(
            _execute_invalid_write(
                disposable_database_url,
                """
                INSERT INTO detection_threshold_config (block_confidence, flag_confidence)
                VALUES (0.9, 0.4)
                """,
            )
        )

    assert _constraint_name(rejected.value) == "uq_detection_threshold_config_singleton"


async def _initialize_detection_concurrently(database_url: str) -> tuple[set[object], int]:
    engine = create_async_engine(database_url, pool_size=8, max_overflow=0)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    start = asyncio.Event()

    async def initialize() -> object:
        await start.wait()
        async with session_factory() as session:
            row = await DetectionConfigRepository(session).get()
            await session.commit()
            return row.id

    try:
        async with engine.begin() as connection:
            await connection.execute(text("DELETE FROM detection_threshold_config"))
            await connection.execute(
                text(
                    """
                    CREATE FUNCTION chunk10_slow_detection_insert() RETURNS trigger
                    LANGUAGE plpgsql AS $$
                    BEGIN
                        PERFORM pg_sleep(0.1);
                        RETURN NEW;
                    END
                    $$
                    """
                )
            )
            await connection.execute(
                text(
                    """
                    CREATE TRIGGER chunk10_slow_detection_insert
                    BEFORE INSERT ON detection_threshold_config
                    FOR EACH ROW EXECUTE FUNCTION chunk10_slow_detection_insert()
                    """
                )
            )
        tasks = [asyncio.create_task(initialize()) for _ in range(8)]
        start.set()
        row_ids = set(await asyncio.gather(*tasks))
        async with engine.connect() as connection:
            row_count = int(await connection.scalar(text("SELECT count(*) FROM detection_threshold_config")) or 0)
        return row_ids, row_count
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_concurrent_empty_detection_initialization_returns_one_row(
    disposable_database_url: str,
) -> None:
    upgrade(disposable_database_url, "head")

    row_ids, row_count = asyncio.run(_initialize_detection_concurrently(disposable_database_url))

    assert len(row_ids) == 1
    assert row_count == 1


@pytest.mark.integration
def test_010_downgrade_and_reupgrade_preserve_detection_row(disposable_database_url: str) -> None:
    upgrade(disposable_database_url, "009")
    upgrade(disposable_database_url, "010")
    first_head = database_snapshot(disposable_database_url)

    downgrade(disposable_database_url, "009")
    downgraded = database_snapshot(disposable_database_url)

    assert current_revision(disposable_database_url) == "009"
    assert dict(downgraded.row_counts)["detection_threshold_config"] == 1
    assert (
        dict(downgraded.row_fingerprints)["detection_threshold_config"]
        == dict(first_head.row_fingerprints)["detection_threshold_config"]
    )

    upgrade(disposable_database_url, "010")
    second_head = database_snapshot(disposable_database_url)

    assert current_revision(disposable_database_url) == "010"
    assert dict(second_head.row_counts)["detection_threshold_config"] == 1
    assert (
        dict(second_head.row_fingerprints)["detection_threshold_config"]
        == dict(first_head.row_fingerprints)["detection_threshold_config"]
    )


async def _request_admin_detection_config(database_url: str) -> Response:
    app = FastAPI()

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_request, exception):
        return JSONResponse(status_code=exception.status_code, content=exception.detail)

    app.include_router(admin_detection.router, prefix="/api/v1")
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def provide_database_session():
        async with session_factory() as session:
            yield session

    async def provide_admin_session() -> dict[str, str]:
        return {}

    app.dependency_overrides[get_db] = provide_database_session
    for route in admin_detection.router.routes:
        for dependency in route.dependant.dependencies:
            if dependency.name == "_session":
                app.dependency_overrides[dependency.call] = provide_admin_session

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://chunk-10-proof",
        ) as client:
            return await client.get("/api/v1/admin/detection/config")
    finally:
        await engine.dispose()


async def _repair_invalid_detection_thresholds(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE detection_threshold_config
                    SET block_confidence = 0.8, flag_confidence = 0.5
                    """
                )
            )
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_admin_api_is_sanitized_before_explicit_repair_and_migration_retry(
    disposable_database_url: str,
) -> None:
    upgrade(disposable_database_url, "009")
    asyncio.run(
        _execute_invalid_write(
            disposable_database_url,
            """
            INSERT INTO detection_threshold_config (block_confidence, flag_confidence)
            VALUES ('NaN'::double precision, 0.5)
            """,
        )
    )
    before_api_request = database_snapshot(disposable_database_url)

    response = asyncio.run(_request_admin_detection_config(disposable_database_url))

    assert response.status_code == 503
    assert response.json() == {
        "error": "service_unavailable",
        "message_key": "error.service_unavailable",
    }
    assert "nan" not in response.text.lower()
    assert "select" not in response.text.lower()
    assert database_snapshot(disposable_database_url) == before_api_request
    assert current_revision(disposable_database_url) == "009"

    asyncio.run(_repair_invalid_detection_thresholds(disposable_database_url))
    upgrade(disposable_database_url, "010")

    repaired_response = asyncio.run(_request_admin_detection_config(disposable_database_url))
    assert repaired_response.status_code == 200
    assert current_revision(disposable_database_url) == "010"
