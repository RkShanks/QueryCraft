"""CHUNK-12 session-detail pagination regressions."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.dependencies import get_db, require_active_user
from app.main import create_app

_ATTEMPT_COUNT = 10_000
_ATTEMPT_LIMIT = 100


async def _detail_client(
    app: FastAPI,
    db_session: AsyncSession,
    user_id: uuid.UUID,
) -> AsyncGenerator[AsyncClient, None]:
    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_user() -> str:
        return str(user_id)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_active_user] = override_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def _copied_connection_ids(db_session: AsyncSession, count: int) -> list[uuid.UUID]:
    source_id = (await db_session.execute(text("SELECT id FROM source_database_connections LIMIT 1"))).scalar_one()
    connection_ids = [source_id]
    for index in range(count - 1):
        connection_id = uuid.uuid4()
        await db_session.execute(
            text(
                """
                INSERT INTO source_database_connections (
                    id, display_name, database_type, host, port, database_name,
                    username, encrypted_password, ssl_mode, lifecycle_state,
                    health_status, schema_introspection_status
                )
                SELECT :id, display_name || :suffix, database_type, host, port,
                       database_name, username, encrypted_password, ssl_mode,
                       lifecycle_state, health_status, schema_introspection_status
                FROM source_database_connections WHERE id = :source_id
                """
            ),
            {"id": connection_id, "source_id": source_id, "suffix": f"-{index}"},
        )
        connection_ids.append(connection_id)
    return connection_ids


@pytest.mark.asyncio
@pytest.mark.usefixtures("ensure_db_connection")
async def test_attempt_connection_metadata_uses_one_bounded_query(
    db_session: AsyncSession,
    async_engine_fixture: AsyncEngine,
) -> None:
    owner_id = (await db_session.execute(text("SELECT id FROM users WHERE username = 'admin'"))).scalar_one()
    session_id = uuid.uuid4()
    connection_ids = await _copied_connection_ids(db_session, 3)
    await db_session.execute(
        text("INSERT INTO sessions (id, user_id, preview_text) VALUES (:id, :user_id, '')"),
        {"id": session_id, "user_id": owner_id},
    )
    await db_session.execute(
        text(
            """
            INSERT INTO accepted_queries (
                id, user_id, database_connection_id, session_id,
                question_text, generated_sql, llm_provider
            )
            VALUES (:id, :user_id, :connection_id, :session_id, '', '', 'ollama')
            """
        ),
        [
            {
                "id": uuid.uuid4(),
                "user_id": owner_id,
                "connection_id": connection_id,
                "session_id": session_id,
            }
            for connection_id in connection_ids
        ],
    )

    metadata_selects = 0

    def count_metadata_selects(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
        nonlocal metadata_selects
        if statement.lstrip().upper().startswith("SELECT") and "source_database_connections" in statement:
            metadata_selects += 1

    event.listen(async_engine_fixture.sync_engine, "before_cursor_execute", count_metadata_selects)
    try:
        app = create_app()
        async for client in _detail_client(app, db_session, owner_id):
            response = await client.get(f"/api/v1/sessions/{session_id}")
    finally:
        event.remove(async_engine_fixture.sync_engine, "before_cursor_execute", count_metadata_selects)

    assert response.status_code == 200
    assert len(response.json()["attempts"]) == 3
    assert metadata_selects == 1


@pytest.mark.asyncio
@pytest.mark.usefixtures("ensure_db_connection")
async def test_equal_timestamp_attempts_traverse_once_in_stable_owned_order(
    db_session: AsyncSession,
) -> None:
    owner_id = (await db_session.execute(text("SELECT id FROM users WHERE username = 'admin'"))).scalar_one()
    other_id = uuid.uuid4()
    await db_session.execute(
        text(
            """
            INSERT INTO users (id, username, display_name, role, auth_provider)
            VALUES (:id, :username, 'Attempt Other', 'member', 'oidc')
            """
        ),
        {"id": other_id, "username": f"attempt-other-{other_id}"},
    )
    connection_id = (await db_session.execute(text("SELECT id FROM source_database_connections LIMIT 1"))).scalar_one()
    session_id = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO sessions (id, user_id, preview_text) VALUES (:id, :user_id, '')"),
        {"id": session_id, "user_id": owner_id},
    )
    accepted_at = datetime(2026, 8, 12, 11, 0, tzinfo=UTC)
    expected_ids = [uuid.UUID(int=100_000 + index) for index in range(_ATTEMPT_COUNT)]
    await db_session.execute(
        text(
            """
            INSERT INTO accepted_queries (
                id, user_id, database_connection_id, session_id,
                question_text, generated_sql, llm_provider, accepted_at
            )
            VALUES (
                :id, :user_id, :connection_id, :session_id,
                '', '', 'ollama', :accepted_at
            )
            """
        ),
        [
            {
                "id": attempt_id,
                "user_id": owner_id,
                "connection_id": connection_id,
                "session_id": session_id,
                "accepted_at": accepted_at,
            }
            for attempt_id in expected_ids
        ],
    )
    await db_session.execute(
        text(
            """
            INSERT INTO accepted_queries (
                id, user_id, database_connection_id, session_id,
                question_text, generated_sql, llm_provider, accepted_at
            )
            VALUES (
                :id, :user_id, :connection_id, :session_id,
                '', '', 'ollama', :accepted_at
            )
            """
        ),
        {
            "id": uuid.uuid4(),
            "user_id": other_id,
            "connection_id": connection_id,
            "session_id": session_id,
            "accepted_at": accepted_at,
        },
    )

    seen_ids: list[str] = []
    cursor: str | None = None
    app = create_app()
    async for client in _detail_client(app, db_session, owner_id):
        while True:
            response = await client.get(
                f"/api/v1/sessions/{session_id}",
                params={
                    "attempt_limit": _ATTEMPT_LIMIT,
                    **({"attempt_cursor": cursor} if cursor else {}),
                },
            )
            assert response.status_code == 200
            page = response.json()
            assert len(page["attempts"]) <= _ATTEMPT_LIMIT
            assert page["attempts_total"] == _ATTEMPT_COUNT
            seen_ids.extend(attempt["id"] for attempt in page["attempts"])
            cursor = page["attempts_next_cursor"]
            if cursor is None:
                break

    assert seen_ids == [str(attempt_id) for attempt_id in reversed(expected_ids)]
    assert len(seen_ids) == len(set(seen_ids)) == _ATTEMPT_COUNT


@pytest.mark.asyncio
@pytest.mark.usefixtures("ensure_db_connection")
async def test_attempt_page_defaults_to_fifty_and_rejects_malformed_cursor(
    db_session: AsyncSession,
) -> None:
    owner_id = (await db_session.execute(text("SELECT id FROM users WHERE username = 'admin'"))).scalar_one()
    connection_id = (await db_session.execute(text("SELECT id FROM source_database_connections LIMIT 1"))).scalar_one()
    session_id = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO sessions (id, user_id, preview_text) VALUES (:id, :user_id, '')"),
        {"id": session_id, "user_id": owner_id},
    )
    await db_session.execute(
        text(
            """
            INSERT INTO accepted_queries (
                id, user_id, database_connection_id, session_id,
                question_text, generated_sql, llm_provider
            )
            VALUES (:id, :user_id, :connection_id, :session_id, '', '', 'ollama')
            """
        ),
        [
            {
                "id": uuid.uuid4(),
                "user_id": owner_id,
                "connection_id": connection_id,
                "session_id": session_id,
            }
            for _ in range(51)
        ],
    )

    app = create_app()
    async for client in _detail_client(app, db_session, owner_id):
        first_page = await client.get(f"/api/v1/sessions/{session_id}")
        invalid_page = await client.get(
            f"/api/v1/sessions/{session_id}",
            params={"attempt_cursor": "not-a-cursor"},
        )

    assert first_page.status_code == 200
    assert len(first_page.json()["attempts"]) == 50
    assert first_page.json()["attempts_total"] == 51
    assert first_page.json()["attempts_next_cursor"] is not None
    assert invalid_page.status_code == 400
    assert invalid_page.json() == {"error": "invalid_cursor", "message_key": "error.invalidCursor"}
