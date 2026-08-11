"""CHUNK-12 session-detail pagination regressions."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.dependencies import get_db, require_active_user
from app.main import create_app


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
