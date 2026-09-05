"""IS-GAP-032 / CHUNK-20: real-PostgreSQL history search behavior.

Covers literal wildcard matching, multi-page filtered traversal,
cross-user isolation, cursor/filter binding and filtered totals against
live PostgreSQL through AcceptedQueryRepository.
"""

from __future__ import annotations

import base64
import json

import pytest
from sqlalchemy import event, text

from app.core.exceptions import InvalidCursorError
from app.core.pagination import decode_cursor, decode_datetime_cursor
from app.db.base import get_async_engine
from app.repositories.accepted_query_repository import (
    HISTORY_CURSOR_NAMESPACE,
    AcceptedQueryRepository,
    search_cursor_namespace,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("search", ["\x00", "before\x00after", " \x00trimmed "])
async def test_nul_search_returns_sanitized_422_before_search_sql(authenticated_client, search):
    """Freeze contract blocker: invalid text must not reach PostgreSQL search."""
    search_statements = 0

    def observe_search_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        nonlocal search_statements
        if "accepted_queries" in statement:
            search_statements += 1

    engine = get_async_engine().sync_engine
    event.listen(engine, "before_cursor_execute", observe_search_sql)
    try:
        response = await authenticated_client.get("/api/v1/history", params={"search": search})
    finally:
        event.remove(engine, "before_cursor_execute", observe_search_sql)

    assert response.status_code == 422
    assert response.json() == {"error": "invalid_search", "message_key": "error.invalidSearch"}
    assert search_statements == 0


async def _connection_id(db_session) -> object:
    result = await db_session.execute(
        text(
            """
            INSERT INTO source_database_connections (
                display_name, host, port, database_name, username,
                encrypted_password, database_type, lifecycle_state,
                health_status, schema_introspection_status
            )
            VALUES ('qc20_conn', 'localhost', 5432, 'qc20', 'user', 'enc',
                    'postgresql', 'active', 'healthy', 'success')
            RETURNING id
            """
        )
    )
    return result.fetchone()[0]


async def _seed_rows(db_session, repo, user_id, connection_id, rows):
    for question, sql in rows:
        await repo.create(
            user_id=user_id,
            database_connection_id=connection_id,
            question_text=question,
            generated_sql=sql,
            llm_provider="ollama",
        )


@pytest.fixture
async def qc20_admin_user_id(db_session):
    """Fetch the seeded admin user's UUID."""
    result = await db_session.execute(text("SELECT id FROM users WHERE username = 'admin'"))
    row = result.fetchone()
    assert row is not None
    return row[0]


@pytest.fixture
async def qc20_second_user_id(db_session):
    """Create a disposable second user and return its UUID."""
    result = await db_session.execute(
        text(
            """
            INSERT INTO users (username, display_name, role)
            VALUES ('qc20_other_user', 'QC20 Other', 'admin')
            RETURNING id
            """
        )
    )
    return result.fetchone()[0]


@pytest.mark.integration
@pytest.mark.asyncio
class TestHistorySearchRepository:
    async def test_search_matches_question_and_sql_case_insensitively(self, db_session, qc20_admin_user_id):
        connection_id = await _connection_id(db_session)
        repo = AcceptedQueryRepository(db_session)
        await _seed_rows(
            db_session,
            repo,
            qc20_admin_user_id,
            connection_id,
            [
                ("Show REVENUE by month", "SELECT month FROM revenue"),
                ("Customer count", "select count(*) from CUSTOMER"),
                ("Unrelated", "SELECT 1"),
            ],
        )

        items, _cursor = await repo.list_by_user(qc20_admin_user_id, limit=10, search="revenue")
        assert {item.question_text for item in items} == {"Show REVENUE by month"}

        items, _cursor = await repo.list_by_user(qc20_admin_user_id, limit=10, search="COUNT")
        assert [item.question_text for item in items] == ["Customer count"]

    async def test_count_by_user_reflects_search_filter(self, db_session, qc20_admin_user_id):
        connection_id = await _connection_id(db_session)
        repo = AcceptedQueryRepository(db_session)
        await _seed_rows(
            db_session,
            repo,
            qc20_admin_user_id,
            connection_id,
            [("revenue one", "SELECT 1"), ("REVENUE two", "SELECT 2"), ("unrelated", "SELECT 3")],
        )

        unfiltered_total = await repo.count_by_user(qc20_admin_user_id)
        filtered_total = await repo.count_by_user(qc20_admin_user_id, search="revenue")
        other_total = await repo.count_by_user(qc20_admin_user_id, search="nomatch-xyz")

        assert (unfiltered_total, filtered_total, other_total) == (3, 2, 0)

    async def test_search_wildcards_are_literal(self, db_session, qc20_admin_user_id):
        connection_id = await _connection_id(db_session)
        repo = AcceptedQueryRepository(db_session)
        await _seed_rows(
            db_session,
            repo,
            qc20_admin_user_id,
            connection_id,
            [
                ("Percent literal", "SELECT 100%_done"),
                ("Wildcard bait a", "SELECT 1"),
                ("Wildcard bait b", "SELECT 2"),
            ],
        )

        items, _cursor = await repo.list_by_user(qc20_admin_user_id, limit=10, search="100%_done")
        assert len(items) == 1
        assert items[0].question_text == "Percent literal"

        # A lone % or _ matches only rows containing that literal character —
        # if wildcards were active, every row would match instead.
        items, _cursor = await repo.list_by_user(qc20_admin_user_id, limit=10, search="%")
        assert [item.question_text for item in items] == ["Percent literal"]
        items, _cursor = await repo.list_by_user(qc20_admin_user_id, limit=10, search="_")
        assert [item.question_text for item in items] == ["Percent literal"]

        # Backslash is also matched literally (no row contains one).
        items, _cursor = await repo.list_by_user(qc20_admin_user_id, limit=10, search="\\")
        assert items == []

    async def test_search_is_user_scoped(self, db_session, qc20_admin_user_id, qc20_second_user_id):
        connection_id = await _connection_id(db_session)
        repo = AcceptedQueryRepository(db_session)
        await _seed_rows(db_session, repo, qc20_admin_user_id, connection_id, [("Admin revenue note", "SELECT 9")])
        await _seed_rows(db_session, repo, qc20_second_user_id, connection_id, [("Other revenue note", "SELECT 8")])

        items, _cursor = await repo.list_by_user(qc20_admin_user_id, limit=50, search="revenue")
        count = await repo.count_by_user(qc20_admin_user_id, search="revenue")

        assert [item.question_text for item in items] == ["Admin revenue note"]
        assert count == 1

    async def test_filtered_pagination_walks_all_matches_across_pages(self, db_session, qc20_admin_user_id):
        connection_id = await _connection_id(db_session)
        repo = AcceptedQueryRepository(db_session)
        rows = [(f"needle row {i}", f"SELECT {i}") for i in range(7)]
        rows += [("filler", "SELECT 0") for _ in range(4)]
        await _seed_rows(db_session, repo, qc20_admin_user_id, connection_id, rows)

        expected_total = await repo.count_by_user(qc20_admin_user_id, search="NEEDLE")
        assert expected_total == 7

        seen: list[str] = []
        cursor = None
        pages = 0
        while True:
            items, next_cursor = await repo.list_by_user(qc20_admin_user_id, cursor=cursor, limit=3, search="needle")
            pages += 1
            seen.extend(item.question_text for item in items)
            if not next_cursor or pages > 10:
                break
            cursor = next_cursor

        assert sorted(seen) == sorted(f"needle row {i}" for i in range(7))
        assert pages == 3

    async def test_search_cursor_rejected_under_different_filter(self, db_session, qc20_admin_user_id):
        connection_id = await _connection_id(db_session)
        repo = AcceptedQueryRepository(db_session)
        await _seed_rows(
            db_session,
            repo,
            qc20_admin_user_id,
            connection_id,
            [("alpha match one", "SELECT 1"), ("alpha match two", "SELECT 2"), ("beta other", "SELECT 3")],
        )

        page1, cursor = await repo.list_by_user(qc20_admin_user_id, limit=1, search="alpha")
        assert len(page1) == 1
        assert cursor is not None

        # Same filter: cursor continues.
        page2, exhausted = await repo.list_by_user(qc20_admin_user_id, cursor=cursor, limit=5, search="alpha")
        assert [item.question_text for item in page1 + page2] == [
            "alpha match two",
            "alpha match one",
        ]
        assert exhausted is None

        # Different filter namespace: decode must refuse.
        position = decode_cursor(cursor, search_cursor_namespace("alpha"))
        assert position.item_id == page1[-1].id
        with pytest.raises(InvalidCursorError):
            decode_cursor(cursor, search_cursor_namespace("beta"))
        with pytest.raises(InvalidCursorError):
            decode_cursor(cursor, HISTORY_CURSOR_NAMESPACE)

        with pytest.raises(InvalidCursorError):
            decode_datetime_cursor(cursor, search_cursor_namespace("beta"))

    async def test_legacy_unfiltered_cursor_still_paginates(self, db_session, qc20_admin_user_id):
        connection_id = await _connection_id(db_session)
        repo = AcceptedQueryRepository(db_session)
        rows = [("r1", "SELECT 1"), ("r2", "SELECT 2"), ("r3", "SELECT 3")]
        await _seed_rows(db_session, repo, qc20_admin_user_id, connection_id, rows)

        # Canonical order for these three rows (reverse-chronological, id tiebreak).
        everything, _none = await repo.list_by_user(qc20_admin_user_id, limit=10)
        expected_order = [item.question_text for item in everything]
        assert sorted(expected_order) == ["r1", "r2", "r3"]

        # New cursors are opaque under the history namespace...
        items, opaque_cursor = await repo.list_by_user(qc20_admin_user_id, limit=1)
        assert len(items) == 1
        position = decode_cursor(opaque_cursor, HISTORY_CURSOR_NAMESPACE)
        assert position.item_id == items[-1].id

        page2, _cursor2 = await repo.list_by_user(qc20_admin_user_id, cursor=opaque_cursor, limit=5)
        assert [item.question_text for item in items + page2] == expected_order

        # ...while pre-existing legacy "accepted_at|id" cursors keep working
        # for the unfiltered listing (compatibility), but never when filtered.
        last_accepted_at = items[-1].accepted_at.isoformat()
        legacy_cursor = f"{last_accepted_at}|{items[-1].id}"
        legacy_page, legacy_next = await repo.list_by_user(qc20_admin_user_id, cursor=legacy_cursor, limit=5)
        assert [item.question_text for item in legacy_page] == expected_order[1:]
        assert legacy_next is None

        with pytest.raises(InvalidCursorError):
            await repo.list_by_user(qc20_admin_user_id, cursor=legacy_cursor, limit=5, search="r")

    async def test_opaque_cursor_payload_never_contains_raw_search(self, db_session, qc20_admin_user_id):
        connection_id = await _connection_id(db_session)
        repo = AcceptedQueryRepository(db_session)
        await _seed_rows(
            db_session,
            repo,
            qc20_admin_user_id,
            connection_id,
            [("secretive one", "SELECT 1"), ("secretive two", "SELECT 2"), ("secretive three", "SELECT 3")],
        )

        _items, cursor = await repo.list_by_user(qc20_admin_user_id, limit=2, search="secretive")
        padding = b"=" * (-len(cursor) % 4)
        payload = json.loads(base64.b64decode(cursor.encode("ascii") + padding, altchars=b"-_"))
        assert set(payload) == {"v", "n", "s", "i"}
        assert "secretive" not in json.dumps(payload)
