"""IS-GAP-001 regression coverage for immutable query source continuity."""

from __future__ import annotations

import asyncio
import json
import re
import secrets
from collections.abc import AsyncGenerator, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.api.v1 import query as query_routes
from app.core.credential_provider import FernetCredentialProvider
from app.source_db.adapters import ExecuteResult, MSSQLAdapter, MySQLAdapter, PostgresAdapter


@dataclass(frozen=True)
class SourceSpec:
    connection_id: str
    database_type: str
    dialect: str
    table_name: str
    display_name: str


SOURCE_TYPES = [
    ("postgresql", "postgres"),
    ("mysql", "mysql"),
    ("mssql", "tsql"),
]


class RedactedString(str):
    def __repr__(self) -> str:
        return "<redacted>"


def sensitive_value() -> RedactedString:
    return RedactedString(secrets.token_hex(24))


class SourceCheckingLLM:
    """External LLM boundary that rejects a redirected dialect or schema."""

    def __init__(self, source: SourceSpec, generated_sql: list[str]) -> None:
        self._source = source
        self._generated_sql = iter(generated_sql)
        self.calls = 0

    async def generate_sql(
        self,
        question: str,
        schema_context,
        negative_examples=None,
        conversation_history=None,
        target_dialect=None,
    ) -> str:
        del question, negative_examples, conversation_history
        self.calls += 1
        table_names = {table.name for table in schema_context.tables}
        if table_names != {self._source.table_name}:
            raise AssertionError("query source schema changed after submit")
        if target_dialect != self._source.dialect:
            raise AssertionError("query source dialect changed after submit")
        return next(self._generated_sql)


@pytest_asyncio.fixture
async def continuity_sources(
    async_engine_fixture,
    test_env_vars,
    synced_local_admin,
) -> AsyncGenerator[list[SourceSpec], None]:
    """Create three isolated platform connection records with distinct schemas."""
    del synced_local_admin
    encrypted_password = FernetCredentialProvider(test_env_vars["DB_CREDENTIAL_KEY"]).encrypt("fixture-only")
    sources: list[SourceSpec] = []

    async with async_engine_fixture.begin() as connection:
        admin_role_id = await connection.scalar(
            text("SELECT id FROM roles WHERE name = 'Admin' AND is_builtin = true LIMIT 1")
        )
        for database_type, dialect in SOURCE_TYPES:
            connection_id = uuid4()
            suffix = connection_id.hex[:8]
            table_name = f"continuity_{database_type}_{suffix}"
            display_name = f"Continuity {database_type} {suffix}"
            await connection.execute(
                text(
                    """
                    INSERT INTO source_database_connections (
                        id, display_name, host, port, database_name, username,
                        encrypted_password, ssl_mode, database_type, lifecycle_state,
                        health_status, schema_introspection_status
                    ) VALUES (
                        :id, :display_name, 'source.invalid', 15432, 'continuity',
                        'continuity_user', :encrypted_password, 'disable', :database_type,
                        'active', 'healthy', 'success'
                    )
                    """
                ),
                {
                    "id": connection_id,
                    "display_name": display_name,
                    "encrypted_password": encrypted_password,
                    "database_type": database_type,
                },
            )
            for column_name, column_data_type, is_primary_key in [
                ("probe_id", "integer", True),
                ("probe_value", "text", False),
            ]:
                await connection.execute(
                    text(
                        """
                        INSERT INTO connection_schema_entries (
                            connection_id, table_name, column_name,
                            column_data_type, is_primary_key
                        ) VALUES (
                            :connection_id, :table_name, :column_name,
                            :column_data_type, :is_primary_key
                        )
                        """
                    ),
                    {
                        "connection_id": connection_id,
                        "table_name": table_name,
                        "column_name": column_name,
                        "column_data_type": column_data_type,
                        "is_primary_key": is_primary_key,
                    },
                )
            await connection.execute(
                text(
                    """
                    INSERT INTO role_connection_policies (
                        role_id, connection_id, allowed_tables, row_filters, column_masks
                    ) VALUES (
                        :role_id, :connection_id, CAST(:allowed_tables AS jsonb),
                        '[]'::jsonb, CAST(:column_masks AS jsonb)
                    )
                    """
                ),
                {
                    "role_id": admin_role_id,
                    "connection_id": connection_id,
                    "allowed_tables": json.dumps([{"table": table_name, "columns": ["probe_id", "probe_value"]}]),
                    "column_masks": json.dumps([{"table": table_name, "columns": ["probe_value"]}]),
                },
            )
            sources.append(
                SourceSpec(
                    connection_id=str(connection_id),
                    database_type=database_type,
                    dialect=dialect,
                    table_name=table_name,
                    display_name=display_name,
                )
            )

    yield sources

    async with async_engine_fixture.begin() as connection:
        for source in sources:
            source_uuid = UUID(source.connection_id)
            await connection.execute(
                text("DELETE FROM accepted_queries WHERE database_connection_id = :connection_id"),
                {"connection_id": source_uuid},
            )
            await connection.execute(
                text("UPDATE sessions SET connection_id = NULL WHERE connection_id = :connection_id"),
                {"connection_id": source_uuid},
            )
            await connection.execute(
                text("DELETE FROM role_connection_policies WHERE connection_id = :connection_id"),
                {"connection_id": source_uuid},
            )
            await connection.execute(
                text("DELETE FROM connection_schema_entries WHERE connection_id = :connection_id"),
                {"connection_id": source_uuid},
            )
            await connection.execute(
                text("DELETE FROM source_database_connections WHERE id = :connection_id"),
                {"connection_id": source_uuid},
            )


@contextmanager
def source_boundaries(
    source: SourceSpec,
    generated_sql: list[str],
    *,
    columns: list[str] | None = None,
    execution_rows: list[list[tuple]] | None = None,
) -> Iterator[tuple[SourceCheckingLLM, dict[str, AsyncMock]]]:
    """Control only the LLM/source systems while leaving route wiring real."""
    llm = SourceCheckingLLM(source, generated_sql)
    adapter_classes = {
        "postgresql": PostgresAdapter,
        "mysql": MySQLAdapter,
        "mssql": MSSQLAdapter,
    }
    adapter_calls: dict[str, AsyncMock] = {}
    with ExitStack() as stack:
        stack.enter_context(patch("app.api.v1.query.LLMProviderFactory.from_config", return_value=llm))
        for database_type, adapter_class in adapter_classes.items():
            result_columns = columns or ["probe_id", "probe_value"]
            if execution_rows is None:
                execute = AsyncMock(
                    return_value=ExecuteResult(
                        columns=result_columns,
                        rows=[(1, "must-mask")],
                    )
                )
            else:
                execute = AsyncMock(
                    side_effect=[ExecuteResult(columns=result_columns, rows=rows) for rows in execution_rows]
                )
            stack.enter_context(patch.object(adapter_class, "execute", new=execute))
            adapter_calls[database_type] = execute
        yield llm, adapter_calls


async def create_session(authenticated_client, connection_id: str) -> str:
    response = await authenticated_client.post("/api/v1/sessions")
    assert response.status_code == 201
    session_id = response.json()["id"]
    update = await authenticated_client.patch(
        f"/api/v1/sessions/{session_id}/connection",
        json={"connection_id": connection_id},
    )
    assert update.status_code == 200
    return session_id


async def submit_on_source(authenticated_client, source: SourceSpec, session_id: str):
    response = await authenticated_client.post(
        "/api/v1/query/submit",
        json={
            "question": "Continuity check",
            "session_id": session_id,
            "connection_id": source.connection_id,
        },
    )
    assert response.status_code == 200
    assert response.json()["rows"][0][1] == "***"
    return response


async def switch_session(authenticated_client, session_id: str, connection_id: str) -> None:
    response = await authenticated_client.patch(
        f"/api/v1/sessions/{session_id}/connection",
        json={"connection_id": connection_id},
    )
    assert response.status_code == 200


async def persisted_connection(async_engine_fixture, attempt_id: str) -> str | None:
    async with async_engine_fixture.connect() as connection:
        connection_id = await connection.scalar(
            text("SELECT database_connection_id FROM accepted_queries WHERE attempt_id = :attempt_id"),
            {"attempt_id": attempt_id},
        )
    return str(connection_id) if connection_id is not None else None


def assert_only_expected_adapter(adapter_calls: dict[str, AsyncMock], database_type: str, count: int) -> None:
    for candidate_type, execute in adapter_calls.items():
        if candidate_type == database_type:
            assert execute.await_count == count
        else:
            execute.assert_not_awaited()


def assert_value_absent(value: str, channel_content: str, channel_name: str) -> None:
    __tracebackhide__ = True
    if value in channel_content:
        raise AssertionError(f"sensitive value reached {channel_name}")


def assert_attempt_payload_minimized(serialized: str, sensitive_values: tuple[str, ...]) -> dict:
    __tracebackhide__ = True
    for sensitive_value in sensitive_values:
        assert_value_absent(sensitive_value, serialized, "Redis attempt state")
    attempt = json.loads(serialized)
    if "executor_result" in attempt:
        raise AssertionError("Redis attempt state retained a result payload")
    return attempt


def assert_masked_api_payload(payload: dict, channel_name: str) -> None:
    if payload.get("rows") != [[1, "***"]]:
        raise AssertionError(f"{channel_name} did not contain only the expected mask")
    columns = payload.get("columns", [])
    if len(columns) != 2 or columns[1].get("masked") is not True:
        raise AssertionError(f"{channel_name} omitted masked-column metadata")


def assert_masked_history_payload(payload: dict) -> None:
    if payload.get("result_rows") != [[1, "***"]]:
        raise AssertionError("accepted history did not contain only the expected mask")
    columns = payload.get("result_columns", [])
    if len(columns) != 2 or columns[1].get("masked") is not True:
        raise AssertionError("accepted history omitted masked-column metadata")


def assert_no_internal_details(response) -> None:
    body = json.dumps(response.json())
    assert re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", body) is None
    for forbidden in [
        "source.invalid",
        "continuity_user",
        "fixture-only",
        "continuity_",
        "SELECT",
        "postgres",
        "mysql",
        "mssql",
        "traceback",
    ]:
        assert forbidden not in body


def assert_sanitized_attempt_error(response) -> None:
    assert response.status_code in {400, 422}
    assert response.json()["message_key"] == "error.attemptInvalid"
    assert_no_internal_details(response)


@pytest.mark.parametrize("source_index", range(3))
@pytest.mark.parametrize("decision", ["accept", "reject", "regenerate"])
async def test_session_switch_cannot_redirect_public_decision(
    authenticated_client,
    async_engine_fixture,
    redis_client,
    continuity_sources,
    source_index,
    decision,
):
    """All public decisions retain source, dialect, schema, policy and adapter."""
    source = continuity_sources[source_index]
    switched_source = continuity_sources[(source_index + 1) % len(continuity_sources)]
    first_sql = f"SELECT probe_id, probe_value FROM {source.table_name}"
    second_sql = f"SELECT probe_id, probe_value FROM {source.table_name} WHERE probe_id >= 0"
    generated_sql = [first_sql] if decision == "accept" else [first_sql, second_sql]

    with source_boundaries(source, generated_sql) as (llm, adapter_calls):
        session_id = await create_session(authenticated_client, source.connection_id)
        submit_response = await submit_on_source(authenticated_client, source, session_id)
        attempt_id = submit_response.json()["attempt_id"]
        await switch_session(authenticated_client, session_id, switched_source.connection_id)

        request_body = {"attempt_id": attempt_id}
        if decision == "accept":
            request_body["session_id"] = session_id
        decision_response = await authenticated_client.post(
            f"/api/v1/query/{decision}",
            json=request_body,
        )

        assert decision_response.status_code in {200, 201}
        expected_attempt_id = attempt_id
        if decision in {"reject", "regenerate"}:
            response_body = decision_response.json()
            assert response_body["kind"] == "result"
            assert response_body["rows"][0][1] == "***"
            expected_attempt_id = response_body["attempt_id"]
            stored_attempt = json.loads(await redis_client.get(f"attempt:{expected_attempt_id}"))
            assert stored_attempt["database_connection_id"] == source.connection_id
        else:
            assert decision_response.json()["database_connection_id"] == source.connection_id

        assert await persisted_connection(async_engine_fixture, expected_attempt_id) == source.connection_id
        session_detail = await authenticated_client.get(f"/api/v1/sessions/{session_id}")
        accepted_query_id = (
            decision_response.json()["id"] if decision == "accept" else decision_response.json()["accepted_query_id"]
        )
        matching_attempt = next(
            attempt for attempt in session_detail.json()["attempts"] if attempt["id"] == accepted_query_id
        )
        assert matching_attempt["database_connection_id"] == source.connection_id
        assert matching_attempt["database_type"] == source.database_type
        assert matching_attempt["database_connection_name"] == source.display_name
        assert not hasattr(query_routes, "_get_query_service")
        assert llm.calls == (1 if decision == "accept" else 2)
        assert_only_expected_adapter(adapter_calls, source.database_type, 1 if decision == "accept" else 2)


@pytest.mark.parametrize("source_index", range(3))
async def test_fresh_accept_persists_attempt_connection(
    authenticated_client,
    async_engine_fixture,
    continuity_sources,
    source_index,
):
    """Fresh accept uses attempt context when the auto-saved row is absent."""
    source = continuity_sources[source_index]
    switched_source = continuity_sources[(source_index + 1) % len(continuity_sources)]
    sql = f"SELECT probe_id, probe_value FROM {source.table_name}"
    with source_boundaries(source, [sql]) as (_llm, adapter_calls):
        session_id = await create_session(authenticated_client, source.connection_id)
        submit_response = await submit_on_source(authenticated_client, source, session_id)
        attempt_id = submit_response.json()["attempt_id"]
        await switch_session(authenticated_client, session_id, switched_source.connection_id)
        async with async_engine_fixture.begin() as connection:
            await connection.execute(
                text("DELETE FROM accepted_queries WHERE attempt_id = :attempt_id"),
                {"attempt_id": attempt_id},
            )

        response = await authenticated_client.post(
            "/api/v1/query/accept",
            json={"attempt_id": attempt_id, "session_id": session_id},
        )

        assert response.status_code == 201
        assert response.json()["database_connection_id"] == source.connection_id
        assert await persisted_connection(async_engine_fixture, attempt_id) == source.connection_id
        assert_only_expected_adapter(adapter_calls, source.database_type, 1)


@pytest.mark.parametrize(
    ("source_index", "revocation", "expected_status"),
    [
        (0, "deleted", 400),
        (1, "disabled", 400),
        (2, "unauthorized", 422),
    ],
)
async def test_accept_fails_closed_when_original_source_is_revoked(
    authenticated_client,
    async_engine_fixture,
    continuity_sources,
    source_index,
    revocation,
    expected_status,
):
    """Deleted, disabled and unauthorized submit-time sources never fall back."""
    source = continuity_sources[source_index]
    switched_source = continuity_sources[(source_index + 1) % len(continuity_sources)]
    sql = f"SELECT probe_id, probe_value FROM {source.table_name}"
    with source_boundaries(source, [sql]) as (llm, adapter_calls):
        session_id = await create_session(authenticated_client, source.connection_id)
        submit_response = await submit_on_source(authenticated_client, source, session_id)
        attempt_id = submit_response.json()["attempt_id"]
        await switch_session(authenticated_client, session_id, switched_source.connection_id)

        async with async_engine_fixture.begin() as connection:
            if revocation == "deleted":
                await connection.execute(
                    text("DELETE FROM accepted_queries WHERE attempt_id = :attempt_id"),
                    {"attempt_id": attempt_id},
                )
                await connection.execute(
                    text("DELETE FROM role_connection_policies WHERE connection_id = :connection_id"),
                    {"connection_id": UUID(source.connection_id)},
                )
                await connection.execute(
                    text("DELETE FROM connection_schema_entries WHERE connection_id = :connection_id"),
                    {"connection_id": UUID(source.connection_id)},
                )
                await connection.execute(
                    text("DELETE FROM source_database_connections WHERE id = :connection_id"),
                    {"connection_id": UUID(source.connection_id)},
                )
            elif revocation == "disabled":
                await connection.execute(
                    text("UPDATE source_database_connections SET lifecycle_state = 'disabled' WHERE id = :id"),
                    {"id": UUID(source.connection_id)},
                )
            else:
                await connection.execute(
                    text("DELETE FROM role_connection_policies WHERE connection_id = :connection_id"),
                    {"connection_id": UUID(source.connection_id)},
                )

        response = await authenticated_client.post(
            "/api/v1/query/accept",
            json={"attempt_id": attempt_id, "session_id": session_id},
        )

        assert response.status_code == expected_status
        assert_no_internal_details(response)
        assert llm.calls == 1
        assert_only_expected_adapter(adapter_calls, source.database_type, 1)


@pytest.mark.parametrize("source_index", range(3))
async def test_regenerate_applies_policy_revocation_before_provider_or_source_work(
    authenticated_client,
    async_engine_fixture,
    continuity_sources,
    source_index,
):
    source = continuity_sources[source_index]
    sql = f"SELECT probe_id, probe_value FROM {source.table_name}"
    with source_boundaries(source, [sql]) as (llm, adapter_calls):
        session_id = await create_session(authenticated_client, source.connection_id)
        submit_response = await submit_on_source(authenticated_client, source, session_id)
        async with async_engine_fixture.begin() as connection:
            await connection.execute(
                text("DELETE FROM role_connection_policies WHERE connection_id = :connection_id"),
                {"connection_id": UUID(source.connection_id)},
            )

        response = await authenticated_client.post(
            "/api/v1/query/regenerate",
            json={"attempt_id": submit_response.json()["attempt_id"]},
        )

        assert response.status_code == 422
        assert response.json()["message_key"] == "error.queryBlockedPolicy"
        assert llm.calls == 1
        assert_only_expected_adapter(adapter_calls, source.database_type, 1)


@pytest.mark.parametrize("context_change", ["missing", "malformed", "forged_connection", "forged_user"])
async def test_forged_attempt_context_fails_before_retry_work(
    authenticated_client,
    redis_client,
    continuity_sources,
    context_change,
):
    source = continuity_sources[1]
    sql = f"SELECT probe_id, probe_value FROM {source.table_name}"
    with source_boundaries(source, [sql]) as (llm, adapter_calls):
        session_id = await create_session(authenticated_client, source.connection_id)
        submit_response = await submit_on_source(authenticated_client, source, session_id)
        attempt_id = submit_response.json()["attempt_id"]
        attempt_key = f"attempt:{attempt_id}"
        stored_attempt = json.loads(await redis_client.get(attempt_key))
        if context_change == "missing":
            stored_attempt.pop("database_connection_id", None)
        elif context_change == "malformed":
            stored_attempt["database_connection_id"] = "not-a-uuid"
        elif context_change == "forged_connection":
            stored_attempt["database_connection_id"] = continuity_sources[2].connection_id
        else:
            stored_attempt["user_id"] = str(uuid4())
        await redis_client.set(attempt_key, json.dumps(stored_attempt), ex=900)

        response = await authenticated_client.post(
            "/api/v1/query/regenerate",
            json={"attempt_id": attempt_id},
        )

        assert_sanitized_attempt_error(response)
        assert llm.calls == 1
        assert_only_expected_adapter(adapter_calls, source.database_type, 1)


@pytest.mark.parametrize("source_index", range(3))
@pytest.mark.parametrize("decision", ["reject", "regenerate"])
async def test_refine_terminal_path_preserves_persisted_source_label(
    authenticated_client,
    async_engine_fixture,
    continuity_sources,
    source_index,
    decision,
):
    source = continuity_sources[source_index]
    switched_source = continuity_sources[(source_index + 1) % len(continuity_sources)]
    sql = f"SELECT probe_id, probe_value FROM {source.table_name}"
    with source_boundaries(source, [sql, sql]) as (_llm, adapter_calls):
        session_id = await create_session(authenticated_client, source.connection_id)
        submit_response = await submit_on_source(authenticated_client, source, session_id)
        attempt_id = submit_response.json()["attempt_id"]
        await switch_session(authenticated_client, session_id, switched_source.connection_id)

        response = await authenticated_client.post(
            f"/api/v1/query/{decision}",
            json={"attempt_id": attempt_id},
        )

        assert response.status_code == 200
        assert response.json()["kind"] == "refine"
        assert await persisted_connection(async_engine_fixture, attempt_id) == source.connection_id
        detail = await authenticated_client.get(f"/api/v1/sessions/{session_id}")
        assert detail.json()["attempts"][0]["database_connection_id"] == source.connection_id
        assert detail.json()["attempts"][0]["database_type"] == source.database_type
        assert_only_expected_adapter(adapter_calls, source.database_type, 1)


async def test_concurrent_selector_update_cannot_redirect_retry_and_only_affects_new_submit(
    authenticated_client,
    async_engine_fixture,
    continuity_sources,
):
    original = continuity_sources[1]
    later = continuity_sources[2]
    first_sql = f"SELECT probe_id, probe_value FROM {original.table_name}"
    retry_sql = f"SELECT probe_id, probe_value FROM {original.table_name} WHERE probe_id >= 0"
    with source_boundaries(original, [first_sql, retry_sql]) as (_llm, adapter_calls):
        session_id = await create_session(authenticated_client, original.connection_id)
        submit_response = await submit_on_source(authenticated_client, original, session_id)
        attempt_id = submit_response.json()["attempt_id"]

        switch_response, retry_response = await asyncio.gather(
            authenticated_client.patch(
                f"/api/v1/sessions/{session_id}/connection",
                json={"connection_id": later.connection_id},
            ),
            authenticated_client.post(
                "/api/v1/query/regenerate",
                json={"attempt_id": attempt_id},
            ),
        )

        assert switch_response.status_code == 200
        assert retry_response.status_code == 200
        assert (
            await persisted_connection(async_engine_fixture, retry_response.json()["attempt_id"])
            == original.connection_id
        )
        assert_only_expected_adapter(adapter_calls, original.database_type, 2)

    later_sql = f"SELECT probe_id, probe_value FROM {later.table_name}"
    with source_boundaries(later, [later_sql]) as (_llm, adapter_calls):
        later_submit = await submit_on_source(authenticated_client, later, session_id)
        assert (
            await persisted_connection(async_engine_fixture, later_submit.json()["attempt_id"]) == later.connection_id
        )
        assert_only_expected_adapter(adapter_calls, later.database_type, 1)


MASKED_PROJECTION_CASES = [
    pytest.param(
        "SELECT probe_id, probe_value FROM {table}",
        "SELECT probe_id, probe_value FROM {table} WHERE probe_id >= 0",
        ["probe_id", "probe_value"],
        False,
        id="direct",
    ),
    pytest.param(
        "SELECT probe_id, probe_value AS protected_value FROM {table}",
        "SELECT probe_id, probe_value AS protected_value FROM {table} WHERE probe_id >= 0",
        ["probe_id", "protected_value"],
        False,
        id="alias",
    ),
    pytest.param(
        "WITH nested AS (SELECT probe_id, probe_value AS protected_value FROM {table}) "
        "SELECT probe_id, protected_value FROM nested",
        "WITH nested AS (SELECT probe_id, probe_value AS protected_value FROM {table}) "
        "SELECT probe_id, protected_value FROM nested ORDER BY probe_id",
        ["probe_id", "protected_value"],
        False,
        id="nested",
    ),
    pytest.param(
        "SELECT probe_id, probe_value FROM {table}",
        "SELECT probe_id, probe_value FROM {table} ORDER BY probe_id",
        ["probe_id", "probe_value"],
        True,
        id="row-filter-and-mask",
    ),
]


@pytest.mark.parametrize("source_index", range(3), ids=["postgresql", "mysql", "mssql"])
@pytest.mark.parametrize(
    ("initial_sql_template", "retry_sql_template", "result_columns", "with_row_filter"),
    MASKED_PROJECTION_CASES,
)
async def test_masked_submit_and_regenerate_never_serialize_result_payload(
    authenticated_client,
    async_engine_fixture,
    redis_client,
    continuity_sources,
    source_index,
    initial_sql_template,
    retry_sql_template,
    result_columns,
    with_row_filter,
):
    """IS-GAP-002: API/history stay masked while Redis retains metadata only."""
    source = continuity_sources[source_index]
    if with_row_filter:
        async with async_engine_fixture.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE role_connection_policies "
                    "SET row_filters = CAST(:row_filters AS jsonb) "
                    "WHERE connection_id = :connection_id"
                ),
                {
                    "connection_id": UUID(source.connection_id),
                    "row_filters": json.dumps([{"table": source.table_name, "filter": "probe_id >= 0"}]),
                },
            )

    initial_sql = initial_sql_template.format(table=source.table_name)
    retry_sql = retry_sql_template.format(table=source.table_name)
    initial_sensitive_value = sensitive_value()
    retry_sensitive_value = sensitive_value()
    sensitive_values = (initial_sensitive_value, retry_sensitive_value)

    with source_boundaries(
        source,
        [initial_sql, retry_sql],
        columns=result_columns,
        execution_rows=[
            [(1, initial_sensitive_value)],
            [(1, retry_sensitive_value)],
        ],
    ) as (_llm, adapter_calls):
        session_id = await create_session(authenticated_client, source.connection_id)
        submit_response = await authenticated_client.post(
            "/api/v1/query/submit",
            json={
                "question": "Masked attempt check",
                "session_id": session_id,
                "connection_id": source.connection_id,
            },
        )
        if submit_response.status_code != 200:
            raise AssertionError("masked submit did not succeed")
        submit_payload = submit_response.json()
        assert_masked_api_payload(submit_payload, "submit response")
        submit_attempt_id = submit_payload["attempt_id"]
        submit_serialized = RedactedString(await redis_client.get(f"attempt:{submit_attempt_id}"))
        submit_attempt = assert_attempt_payload_minimized(submit_serialized, sensitive_values)
        assert submit_attempt["database_connection_id"] == source.connection_id

        submit_history = await authenticated_client.get(f"/api/v1/history/{submit_payload['accepted_query_id']}")
        if submit_history.status_code != 200:
            raise AssertionError("accepted submit history was unavailable")
        assert_masked_history_payload(submit_history.json())

        regenerate_response = await authenticated_client.post(
            "/api/v1/query/regenerate",
            json={"attempt_id": submit_attempt_id},
        )
        if regenerate_response.status_code != 200:
            raise AssertionError("masked regenerate did not succeed")
        regenerate_payload = regenerate_response.json()
        assert_masked_api_payload(regenerate_payload, "regenerate response")
        regenerate_attempt_id = regenerate_payload["attempt_id"]
        regenerate_serialized = RedactedString(await redis_client.get(f"attempt:{regenerate_attempt_id}"))
        regenerate_attempt = assert_attempt_payload_minimized(regenerate_serialized, sensitive_values)
        assert regenerate_attempt["database_connection_id"] == source.connection_id
        assert await redis_client.get(f"attempt:{submit_attempt_id}") is None

        regenerate_history = await authenticated_client.get(
            f"/api/v1/history/{regenerate_payload['accepted_query_id']}"
        )
        if regenerate_history.status_code != 200:
            raise AssertionError("accepted regenerate history was unavailable")
        assert_masked_history_payload(regenerate_history.json())
        assert_only_expected_adapter(adapter_calls, source.database_type, 2)


async def test_masked_source_value_absent_from_audit_search_export_and_logs(
    authenticated_client,
    redis_client,
    continuity_sources,
    caplog,
):
    """IS-GAP-002: query rows never enter audit, export, or application logs."""
    source = continuity_sources[0]
    source_value = sensitive_value()
    sql = f"SELECT probe_id, probe_value FROM {source.table_name}"

    with source_boundaries(
        source,
        [sql],
        execution_rows=[[(1, source_value)]],
    ):
        session_id = await create_session(authenticated_client, source.connection_id)
        response = await authenticated_client.post(
            "/api/v1/query/submit",
            json={
                "question": "Audit leakage check",
                "session_id": session_id,
                "connection_id": source.connection_id,
            },
        )

    if response.status_code != 200:
        raise AssertionError("masked submit did not succeed")
    response_body = response.json()
    assert_masked_api_payload(response_body, "submit response")
    serialized = RedactedString(await redis_client.get(f"attempt:{response_body['attempt_id']}"))
    assert_attempt_payload_minimized(serialized, (source_value,))

    search_response = await authenticated_client.get("/api/v1/admin/audit/entries?page_size=100")
    if search_response.status_code != 200:
        raise AssertionError("audit search did not succeed")
    export_response = await authenticated_client.post(
        "/api/v1/admin/audit/export",
        json={"format": "json"},
    )
    if export_response.status_code != 200:
        raise AssertionError("audit export did not succeed")

    assert_value_absent(source_value, RedactedString(search_response.text), "audit search")
    assert_value_absent(source_value, RedactedString(export_response.text), "audit export")
    assert_value_absent(source_value, RedactedString(caplog.text), "application logs")
