"""CHUNK-12 session-list pagination regressions."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_active_user
from app.main import create_app

_SESSION_COUNT = 10_000
_PAGE_LIMIT = 100


async def _session_client(
    app: FastAPI, db_session: AsyncSession, user_id: uuid.UUID
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


@pytest.fixture
async def collection_user_ids(db_session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    owner_id = (await db_session.execute(text("SELECT id FROM users WHERE username = 'admin'"))).scalar_one()
    other_id = uuid.uuid4()
    await db_session.execute(
        text(
            """
            INSERT INTO users (id, username, display_name, role, auth_provider)
            VALUES (:id, :username, 'Pagination Other', 'member', 'oidc')
            """
        ),
        {"id": other_id, "username": f"pagination-other-{other_id}"},
    )
    return owner_id, other_id


@pytest.mark.asyncio
async def test_equal_timestamp_sessions_traverse_once_in_stable_owned_order(
    db_session: AsyncSession,
    collection_user_ids: tuple[uuid.UUID, uuid.UUID],
) -> None:
    owner_id, other_id = collection_user_ids
    shared_time = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)
    expected_ids = [uuid.UUID(int=index + 1) for index in range(_SESSION_COUNT)]
    await db_session.execute(
        text(
            """
            INSERT INTO sessions (id, user_id, preview_text, created_at, last_activity_at)
            VALUES (:id, :user_id, '', :timestamp, :timestamp)
            """
        ),
        [{"id": session_id, "user_id": owner_id, "timestamp": shared_time} for session_id in expected_ids],
    )
    await db_session.execute(
        text(
            """
            INSERT INTO sessions (id, user_id, preview_text, created_at, last_activity_at)
            VALUES (:id, :user_id, '', :timestamp, :timestamp)
            """
        ),
        [
            {"id": uuid.UUID(int=_SESSION_COUNT + index + 1), "user_id": other_id, "timestamp": shared_time}
            for index in range(5)
        ],
    )

    seen_ids: list[str] = []
    cursor: str | None = None
    app = create_app()
    async for client in _session_client(app, db_session, owner_id):
        while True:
            response = await client.get(
                "/api/v1/sessions",
                params={"limit": _PAGE_LIMIT, **({"cursor": cursor} if cursor else {})},
            )
            assert response.status_code == 200
            page = response.json()
            assert len(page["items"]) <= _PAGE_LIMIT
            assert page["total"] == _SESSION_COUNT
            seen_ids.extend(item["id"] for item in page["items"])
            cursor = page["next_cursor"]
            if cursor is None:
                break

    assert seen_ids == [str(session_id) for session_id in reversed(expected_ids)]
    assert len(seen_ids) == len(set(seen_ids)) == _SESSION_COUNT


@pytest.mark.asyncio
async def test_session_list_defaults_to_fifty_and_rejects_malformed_cursor(
    db_session: AsyncSession,
    collection_user_ids: tuple[uuid.UUID, uuid.UUID],
) -> None:
    owner_id, _ = collection_user_ids
    await db_session.execute(
        text(
            """
            INSERT INTO sessions (id, user_id, preview_text)
            SELECT gen_random_uuid(), :user_id, '' FROM generate_series(1, 51)
            """
        ),
        {"user_id": owner_id},
    )

    app = create_app()
    async for client in _session_client(app, db_session, owner_id):
        first_page = await client.get("/api/v1/sessions")
        invalid_page = await client.get("/api/v1/sessions", params={"cursor": "not-a-cursor"})

    assert first_page.status_code == 200
    assert len(first_page.json()["items"]) == 50
    assert first_page.json()["next_cursor"] is not None
    assert invalid_page.status_code == 400
    assert invalid_page.json() == {"error": "invalid_cursor", "message_key": "error.invalidCursor"}


@pytest.mark.asyncio
async def test_session_list_refreshes_after_changes_without_snapshot_claim(
    db_session: AsyncSession,
    collection_user_ids: tuple[uuid.UUID, uuid.UUID],
) -> None:
    owner_id, _ = collection_user_ids
    base_time = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)
    original_ids = [uuid.uuid4() for _ in range(4)]
    await db_session.execute(
        text(
            """
            INSERT INTO sessions (id, user_id, preview_text, created_at, last_activity_at)
            VALUES (:id, :user_id, '', :timestamp, :timestamp)
            """
        ),
        [
            {"id": session_id, "user_id": owner_id, "timestamp": base_time - timedelta(minutes=index)}
            for index, session_id in enumerate(original_ids)
        ],
    )

    app = create_app()
    async for client in _session_client(app, db_session, owner_id):
        first_page = (await client.get("/api/v1/sessions", params={"limit": 2})).json()
        created_id = uuid.uuid4()
        await db_session.execute(
            text(
                """
                INSERT INTO sessions (id, user_id, preview_text, created_at, last_activity_at)
                VALUES (:id, :user_id, '', :timestamp, :timestamp)
                """
            ),
            {"id": created_id, "user_id": owner_id, "timestamp": base_time + timedelta(minutes=1)},
        )
        await db_session.execute(
            text("DELETE FROM sessions WHERE id = :id"),
            {"id": original_ids[2]},
        )
        await db_session.execute(
            text("UPDATE sessions SET last_activity_at = :timestamp WHERE id = :id"),
            {"id": original_ids[3], "timestamp": base_time + timedelta(minutes=2)},
        )

        continuation = (
            await client.get(
                "/api/v1/sessions",
                params={"limit": 2, "cursor": first_page["next_cursor"]},
            )
        ).json()
        refreshed = (await client.get("/api/v1/sessions", params={"limit": 2})).json()

    assert continuation["items"] == []
    assert continuation["total"] == 4
    assert [item["id"] for item in refreshed["items"]] == [str(original_ids[3]), str(created_id)]
    assert refreshed["total"] == 4
