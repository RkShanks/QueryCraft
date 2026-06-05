"""TDD tests for query history scoping (T-715).

GET /history must return only the authenticated user's own accepted
queries. No cross-user leakage. Admins are not exempt unless an
explicit product contract says so; per api-contracts.md line 359-362
the contract is "Filter by user_id = current_user.id. No cross-user
visibility" — admin scope is intentionally identical to non-admin.

Contract per specs/005-sso-rbac-row-column-security/contracts/api-contracts.md
line 359-362 and FR-134 / SC-053::

    GET /history — Returns accepted queries for the authenticated user
    only. Permission: query.history.view. Filter:
    user_id = current_user.id. No cross-user visibility.

Sanitization guarantees (defence in depth):
- No raw UUIDs, DB errors, SQL, stack traces, host/port, usernames,
  credentials, or tokens leak in any response or error path.
- Empty history returns an empty list (not another user's rows).
- Pagination is scoped to the current user (cursor walks the
  caller's own rows only).
- Repository layer always filters by user_id; a regression test
  pins the user_id predicate so a future refactor cannot drop it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException, Request, status
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_db, get_redis, require_active_user

# ── Constants ──────────────────────────────────────────────────────────────

USER_A_ID = "550e8400-e29b-41d4-a716-446655440001"
USER_B_ID = "550e8400-e29b-41d4-a716-446655440002"
ROLE_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

# History items — three for user A, two for user B.
HISTORY_USER_A = [
    {
        "id": "550e8400-e29b-41d4-a716-4466554400a1",
        "question_text": "A question 1",
        "generated_sql": "SELECT 1",
        "accepted_at": "2026-05-04T12:00:00+00:00",
    },
    {
        "id": "550e8400-e29b-41d4-a716-4466554400a2",
        "question_text": "A question 2",
        "generated_sql": "SELECT 2",
        "accepted_at": "2026-05-04T12:00:01+00:00",
    },
    {
        "id": "550e8400-e29b-41d4-a716-4466554400a3",
        "question_text": "A question 3",
        "generated_sql": "SELECT 3",
        "accepted_at": "2026-05-04T12:00:02+00:00",
    },
]

HISTORY_USER_B = [
    {
        "id": "550e8400-e29b-41d4-a716-4466554400b1",
        "question_text": "B question 1",
        "generated_sql": "SELECT 10",
        "accepted_at": "2026-05-04T13:00:00+00:00",
    },
    {
        "id": "550e8400-e29b-41d4-a716-4466554400b2",
        "question_text": "B question 2",
        "generated_sql": "SELECT 20",
        "accepted_at": "2026-05-04T13:00:01+00:00",
    },
]

# Forbidden / sensitive tokens that must never leak through sanitized
# error paths.
SENSITIVE_TOKENS = (
    "Traceback",
    "File ",
    "Error",
    "Exception",
    "asyncpg",
    "asyncio",
    "sqlalchemy",
    "10.0.0.42",
    "5432",
    "svc-prod",
    "***MASKED***",
)


# ── Helpers ───────────────────────────────────────────────────────────────


def _make_accepted_query_mock(
    item_id: str, question_text: str, generated_sql: str, accepted_at: str
):
    """Build an AcceptedQuery-shaped mock with isoformat() on accepted_at."""
    m = MagicMock()
    setattr(m, "id", uuid.UUID(item_id))
    m.question_text = question_text
    m.generated_sql = generated_sql
    m.accepted_at = datetime.fromisoformat(accepted_at)
    m.database_connection_id = None
    m.llm_provider = "ollama"
    m.result_columns = None
    m.result_rows = None
    m.result_row_count = None
    return m


def _history_mock(item: dict):
    """Build a mock from a history-item dict (avoids `id` kwarg collision)."""
    return _make_accepted_query_mock(
        item_id=item["id"],
        question_text=item["question_text"],
        generated_sql=item["generated_sql"],
        accepted_at=item["accepted_at"],
    )


def _make_mock_repo(
    *,
    user_a_items: list | None = None,
    user_b_items: list | None = None,
    user_a_count: int | None = None,
    user_b_count: int | None = None,
    user_a_cursor_items: dict | None = None,
):
    """Build a mock AcceptedQueryRepository keyed by user_id.

    list_by_user returns ``(items, next_cursor)`` for the matching
    user_id. count_by_user returns the per-user total. The mock
    enforces that calls always include a user_id argument; a missing
    user_id would match all users and is a leak vector we want to
    catch in tests.
    """
    repo = MagicMock()
    repo.user_a_items = user_a_items if user_a_items is not None else list(HISTORY_USER_A)
    repo.user_b_items = user_b_items if user_b_items is not None else list(HISTORY_USER_B)
    repo.user_a_count = user_a_count if user_a_count is not None else len(repo.user_a_items)
    repo.user_b_count = user_b_count if user_b_count is not None else len(repo.user_b_items)
    repo.user_a_cursor_items = user_a_cursor_items or {}

    async def _list_by_user(user_id, cursor=None, limit=100):
        key = str(user_id)
        if key == USER_A_ID:
            if cursor is not None and cursor in repo.user_a_cursor_items:
                return repo.user_a_cursor_items[cursor], None
            items = [_history_mock(item) for item in repo.user_a_items[:limit]]
            return items, None
        if key == USER_B_ID:
            items = [_history_mock(item) for item in repo.user_b_items[:limit]]
            return items, None
        return [], None

    async def _count_by_user(user_id):
        key = str(user_id)
        if key == USER_A_ID:
            return repo.user_a_count
        if key == USER_B_ID:
            return repo.user_b_count
        return 0

    repo.list_by_user = AsyncMock(side_effect=_list_by_user)
    repo.count_by_user = AsyncMock(side_effect=_count_by_user)
    return repo


def _make_mock_connection_repo():
    """Connection repo: returns None for any lookup (no metadata)."""
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


def _user_session(user_id: str) -> dict:
    """Build a session dict that the permission middleware will accept."""
    return {
        "user_id": user_id,
        "role_id": ROLE_ID,
        "permissions": ["query.history.view"],
    }


def _admin_session() -> dict:
    """Admin session — admin role is NOT exempt from per-user history
    scoping per api-contracts.md line 362 (no cross-user visibility
    for any caller). The admin's user_id is what the endpoint must
    use, just like a non-admin.
    """
    return {
        "user_id": USER_A_ID,
        "role_id": ROLE_ID,
        "permissions": [
            "query.history.view",
            "admin.connections.manage",
            "admin.roles.manage",
            "admin.sso.manage",
            "admin.audit.verify",
        ],
    }


def _unauthorized_session() -> dict:
    """No permissions -> permission check returns 403."""
    return {
        "user_id": USER_A_ID,
        "role_id": ROLE_ID,
        "permissions": [],
    }


def _unmapped_session(user_id: str) -> dict:
    """Missing role_id -> require_permission denies 403 (FR-126)."""
    return {
        "user_id": user_id,
        "role_id": None,
        "permissions": ["query.history.view"],
    }


# ── App + middleware harness ───────────────────────────────────────────────


def _make_app(
    session_data: dict | None,
    repo: MagicMock | None = None,
    connection_repo: MagicMock | None = None,
):
    """Build a FastAPI app with session injection + mock services.

    The history router is imported lazily so the test harness can
    build a fresh app per test without module-level state.
    """
    from fastapi.responses import JSONResponse
    from starlette.middleware.base import BaseHTTPMiddleware

    from app.api.v1.history import _get_history_service
    from app.api.v1.history import router as history_router

    if repo is None:
        repo = _make_mock_repo()
    if connection_repo is None:
        connection_repo = _make_mock_connection_repo()

    class SessionInjectionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.session = session_data
            return await call_next(request)

    async def _http_exc_handler(request, exc):
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "error", "message_key": str(exc.detail)},
        )

    app = FastAPI()
    app.add_middleware(SessionInjectionMiddleware)
    app.add_exception_handler(HTTPException, _http_exc_handler)
    app.include_router(history_router, prefix="/api/v1")

    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_redis] = lambda: MagicMock()

    # require_active_user normally queries the DB; override it to
    # pull user_id from the session middleware injection.
    async def _provide_user_id(request: Request, db=None, redis=None):
        sess = getattr(request.state, "session", None)
        if sess is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "unauthorized", "message_key": "error.unauthorized"},
            )
        return sess["user_id"]

    app.dependency_overrides[require_active_user] = _provide_user_id

    # Override the history service factory so we inject the mock
    # repository without going through a real DB.
    def _provide_service():
        from app.services.history_service import HistoryService

        return HistoryService(repo, connection_repo)

    app.dependency_overrides[_get_history_service] = _provide_service
    return app


# ── Per-user isolation ─────────────────────────────────────────────────────


class TestPerUserIsolation:
    """FR-134 / SC-053: each user sees only their own history."""

    @pytest.mark.asyncio
    async def test_user_a_sees_only_user_a_history(self):
        app = _make_app(_user_session(USER_A_ID))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/history")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        ids = {item["id"] for item in data["items"]}
        assert ids == {h["id"] for h in HISTORY_USER_A}
        for token in SENSITIVE_TOKENS:
            assert token not in str(data)

    @pytest.mark.asyncio
    async def test_user_b_sees_only_user_b_history(self):
        app = _make_app(_user_session(USER_B_ID))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/history")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        ids = {item["id"] for item in data["items"]}
        assert ids == {h["id"] for h in HISTORY_USER_B}
        for b_item in HISTORY_USER_B:
            assert b_item["id"] in ids
        for a_item in HISTORY_USER_A:
            assert a_item["id"] not in ids

    @pytest.mark.asyncio
    async def test_mixed_history_does_not_leak_across_users(self):
        """Two separate sessions, same /history call, no overlap."""
        app_a = _make_app(_user_session(USER_A_ID))
        app_b = _make_app(_user_session(USER_B_ID))
        transport_a = ASGITransport(app=app_a)
        transport_b = ASGITransport(app=app_b)
        async with AsyncClient(transport=transport_a, base_url="http://test") as ca, AsyncClient(
            transport=transport_b, base_url="http://test"
        ) as cb:
            resp_a = await ca.get("/api/v1/history")
            resp_b = await cb.get("/api/v1/history")
        ids_a = {item["id"] for item in resp_a.json()["items"]}
        ids_b = {item["id"] for item in resp_b.json()["items"]}
        assert ids_a.isdisjoint(ids_b)

    @pytest.mark.asyncio
    async def test_admin_session_scoped_to_own_user_id(self):
        """Per api-contracts.md line 362, admin sessions are not
        exempt from per-user history scoping. The admin's own
        user_id is what the endpoint must use, not a global view.
        """
        app = _make_app(_admin_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/history")
        assert response.status_code == 200
        data = response.json()
        ids = {item["id"] for item in data["items"]}
        assert ids == {h["id"] for h in HISTORY_USER_A}
        for b_item in HISTORY_USER_B:
            assert b_item["id"] not in ids


# ── Empty / pagination scoping ─────────────────────────────────────────────


class TestEmptyAndPagination:
    """Empty history returns an empty list, not other users' rows.
    Pagination cursor walks the caller's own rows only.
    """

    @pytest.mark.asyncio
    async def test_empty_history_returns_empty_list_not_other_users(self):
        repo = _make_mock_repo(
            user_a_items=[],
            user_b_items=list(HISTORY_USER_B),
            user_a_count=0,
            user_b_count=len(HISTORY_USER_B),
        )
        app = _make_app(_user_session(USER_A_ID), repo=repo)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/history")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        ids = {h["id"] for h in HISTORY_USER_B}
        for forbidden in ids:
            assert forbidden not in str(data)
        assert data["next_cursor"] is None

    @pytest.mark.asyncio
    async def test_pagination_limit_scoped_to_caller(self):
        """limit=2 returns 2 of User A's rows (not 2 of any user)."""
        app = _make_app(_user_session(USER_A_ID))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/history?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        for item in data["items"]:
            assert item["id"] in {h["id"] for h in HISTORY_USER_A}


# ── Permission / session requirements ──────────────────────────────────────


class TestPermissionAndSession:
    """Permission and session requirements are still enforced."""

    @pytest.mark.asyncio
    async def test_missing_query_history_view_returns_403(self):
        app = _make_app(_unauthorized_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/history")
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "forbidden"
        assert data["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_unmapped_user_returns_403(self):
        app = _make_app(_unmapped_session(USER_A_ID))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/history")
        assert response.status_code == 403
        data = response.json()
        assert data["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_no_session_returns_401(self):
        app = _make_app(None)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/history")
        assert response.status_code == 401
        data = response.json()
        assert data["message_key"] == "error.unauthorized"


# ── Regression: repository receives the right user_id ─────────────────────


class TestRepositoryUserIdPredicate:
    """Regression tests: the repository must be called with the
    authenticated user's id at every layer (list + count). Future
    refactors cannot drop the user_id filter without breaking
    these tests.
    """

    @pytest.mark.asyncio
    async def test_list_by_user_called_with_user_a_id(self):
        repo = _make_mock_repo()
        app = _make_app(_user_session(USER_A_ID), repo=repo)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get("/api/v1/history")
        assert repo.list_by_user.await_count == 1
        call = repo.list_by_user.await_args
        # The first positional/keyword argument is the user_id.
        first_arg = call.args[0] if call.args else call.kwargs.get("user_id")
        assert str(first_arg) == USER_A_ID
        assert str(first_arg) != USER_B_ID

    @pytest.mark.asyncio
    async def test_list_by_user_called_with_user_b_id(self):
        repo = _make_mock_repo()
        app = _make_app(_user_session(USER_B_ID), repo=repo)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get("/api/v1/history")
        assert repo.list_by_user.await_count == 1
        call = repo.list_by_user.await_args
        first_arg = call.args[0] if call.args else call.kwargs.get("user_id")
        assert str(first_arg) == USER_B_ID
        assert str(first_arg) != USER_A_ID

    @pytest.mark.asyncio
    async def test_count_by_user_called_with_current_user_id(self):
        repo = _make_mock_repo()
        app = _make_app(_user_session(USER_A_ID), repo=repo)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get("/api/v1/history")
        assert repo.count_by_user.await_count == 1
        call = repo.count_by_user.await_args
        first_arg = call.args[0] if call.args else call.kwargs.get("user_id")
        assert str(first_arg) == USER_A_ID

    @pytest.mark.asyncio
    async def test_user_a_and_user_b_invoke_different_user_ids_at_repo(self):
        repo = _make_mock_repo()
        app_a = _make_app(_user_session(USER_A_ID), repo=repo)
        app_b = _makeApp = _make_app(_user_session(USER_B_ID), repo=repo)
        transport_a = ASGITransport(app=app_a)
        transport_b = ASGITransport(app=app_b)
        async with AsyncClient(transport=transport_a, base_url="http://test") as ca, AsyncClient(
            transport=transport_b, base_url="http://test"
        ) as cb:
            await ca.get("/api/v1/history")
            await cb.get("/api/v1/history")
        assert repo.list_by_user.await_count == 2
        user_ids = [
            (call.args[0] if call.args else call.kwargs.get("user_id"))
            for call in repo.list_by_user.await_args_list
        ]
        assert str(user_ids[0]) == USER_A_ID
        assert str(user_ids[1]) == USER_B_ID


# ── Response shape and sanitization ────────────────────────────────────────


class TestResponseShapeAndSanitization:
    """Response shape preserved (backward compat). No leak of other
    users' rows in any field of the response.
    """

    @pytest.mark.asyncio
    async def test_response_shape_preserved(self):
        app = _make_app(_user_session(USER_A_ID))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/history")
        data = response.json()
        assert set(data.keys()) >= {"items", "total", "next_cursor"}
        for item in data["items"]:
            assert "id" in item
            assert "question_text" in item
            assert "generated_sql" in item
            assert "accepted_at" in item

    @pytest.mark.asyncio
    async def test_response_items_do_not_leak_other_users_question_or_sql(self):
        """User A's response body must not contain User B's question
        text or generated SQL anywhere in the items.
        """
        app = _make_app(_user_session(USER_A_ID))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/history")
        body = str(response.json())
        for b_item in HISTORY_USER_B:
            assert b_item["question_text"] not in body
            assert b_item["generated_sql"] not in body


# ── Detail endpoint scoping (defence in depth) ─────────────────────────────


class TestDetailScoping:
    """GET /history/{id} also passes user_id to the repo. A detail
    lookup for User B's row from User A's session returns 404 (not
    200 with another user's row).
    """

    @pytest.mark.asyncio
    async def test_user_a_cannot_fetch_user_b_detail(self):
        """The repo.get_by_id mock returns None for mismatched user_id
        because the production repo WHERE-clause includes user_id.
        Here we model that: if repo.get_by_id is called with
        user_a_id, it returns a User A row; with user_b_id, it
        returns a User B row. Mismatched call -> 404.
        """
        repo = MagicMock()
        a_id = uuid.UUID(HISTORY_USER_A[0]["id"])
        b_id = uuid.UUID(HISTORY_USER_B[0]["id"])

        async def _get_by_id(query_id, user_id):
            if query_id == a_id and str(user_id) == USER_A_ID:
                return _history_mock(HISTORY_USER_A[0])
            if query_id == b_id and str(user_id) == USER_B_ID:
                return _history_mock(HISTORY_USER_B[0])
            return None

        repo.get_by_id = AsyncMock(side_effect=_get_by_id)
        app = _make_app(_user_session(USER_A_ID), repo=repo)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/history/{b_id}")
        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "not_found"
        assert data["message_key"] == "error.notFound"
        # The other user's id / SQL / question text must not leak.
        body = str(data)
        assert HISTORY_USER_B[0]["question_text"] not in body
        assert HISTORY_USER_B[0]["generated_sql"] not in body

    @pytest.mark.asyncio
    async def test_user_a_can_fetch_own_detail(self):
        repo = MagicMock()
        a_id = uuid.UUID(HISTORY_USER_A[0]["id"])

        async def _get_by_id(query_id, user_id):
            if query_id == a_id and str(user_id) == USER_A_ID:
                return _history_mock(HISTORY_USER_A[0])
            return None

        repo.get_by_id = AsyncMock(side_effect=_get_by_id)
        app = _make_app(_user_session(USER_A_ID), repo=repo)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/history/{a_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == HISTORY_USER_A[0]["id"]
