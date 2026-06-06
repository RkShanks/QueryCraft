"""TDD tests for audit verification endpoints (T-737).

POST /admin/audit/verify and GET /admin/audit/status per
specs/005-sso-rbac-row-column-security/contracts/api-contracts.md
lines 310-345 and plan.md S-008.

Contract::

    POST /admin/audit/verify
        Permission: admin.audit.verify
        Response 200: {verified, entries_checked, first_break_at, verified_at}

    GET /admin/audit/status
        Permission: admin.audit.verify
        Response 200: {total_entries, last_verification: {verified, verified_at, entries_checked} | None}

S-008 chain recovery behavior (T-740):
- Verification walks the chain from genesis, reports ``sequence_number``
  of first mismatch (``first_break_at``).
- No auto-repair. The endpoint does NOT mutate or rewrite any chain row.
- After a broken chain, the next ``AuditService.log`` call appends
  with ``next_seq = (last_seq or 0) + 1`` and ``prev_hash = the actual
  previous row's row_hash`` regardless of break. The chain is allowed
  to continue from whatever the last entry's row_hash was.
- The verification result itself is recorded as an ``audit.verify``
  audit event after the chain is walked.

AUDIT_VERIFY emission recursion-safety contract (per user input):
- ``AuditService.log()`` does NOT internally call ``AuditService.verify_chain()``.
  No loop, no recursion.
- The verify endpoint calls ``verify_chain()`` first, captures the result,
  then calls ``AuditService.log(..., action=AUDIT_VERIFY)`` ONCE.
- The new ``audit.verify`` entry is appended to the chain AFTER the
  verification was performed. The response ``entries_checked`` reflects
  the chain size AT THE TIME of verification (pre-log). The audit.verify
  row itself is NOT counted in the same response.

Sanitization guarantees (defence in depth):
- 403 / 401 responses carry constant i18n keys; no role_id, user_id,
  username, UUID, host, port, credential, token, SAML/XML/cert,
  SQL fragment, driver name, or stack trace in any response or
  error path.
- ``resource_id`` on the ``audit.verify`` audit event is the stable
  constant ``"audit_chain"`` (no internal row UUIDs are exposed to
  end users; the audit model contract does not define a per-verification
  row UUID, so a constant sentinel is used per the user input contract).
- Audit context is key-based redacted by ``AuditService.log`` per
  ``_SENSITIVE_TOKENS`` in ``audit_service.py``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text as sql_text

from app.db.models.audit_log_entry import AuditLogEntry
from app.db.models.enums import AuditActionType
from app.services.audit_service import AuditService, VerificationResult

# ---------------------------------------------------------------------------
# Test fixtures and helpers
# ---------------------------------------------------------------------------


_AUDIT_PATCH = "app.services.audit_service.AuditService.log"

# Stable, contractually-defined resource_id for AUDIT_VERIFY events.
# No audit verification model exists in the audit model contract, so a
# sentinel constant is used per the user input contract. This avoids
# exposing internal row UUIDs to end users.
_AUDIT_VERIFY_RESOURCE_ID = "audit_chain"


def _admin_session() -> dict:
    """Session with admin.audit.verify permission."""
    return {
        "user_id": str(uuid.uuid4()),
        "role_id": str(uuid.uuid4()),
        "permissions": ["admin.audit.verify"],
        "username": "admin@example.com",
    }


def _non_admin_session() -> dict:
    """Session without admin.audit.verify permission."""
    return {
        "user_id": str(uuid.uuid4()),
        "role_id": str(uuid.uuid4()),
        "permissions": ["query.submit"],
        "username": "user@example.com",
    }


def _unmapped_session() -> dict:
    """Session with valid permissions but empty role_id (unmapped)."""
    return {
        "user_id": str(uuid.uuid4()),
        "role_id": "",
        "permissions": ["admin.audit.verify"],
        "username": "admin@example.com",
    }


def _make_app(session_data: dict | None) -> FastAPI:
    """Build a FastAPI app with session injection for the admin_audit router.

    The ``get_db`` dependency is overridden to yield a no-op ``AsyncMock``
    session so HTTP-level tests do not require a live database. The
    mocked session's ``commit`` is an ``AsyncMock`` coroutine; nothing
    else is exercised by these tests because ``AuditService.verify_chain``
    and ``AuditService.log`` are patched at the endpoint level.
    """
    from fastapi.responses import JSONResponse
    from starlette.middleware.base import BaseHTTPMiddleware

    from app.api.v1.admin_audit import router as admin_audit_router
    from app.core.dependencies import get_db

    class SessionInjectionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.session = session_data
            return await call_next(request)

    async def _http_exc_handler(request, exc):
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"error": "error", "message_key": str(exc.detail)})

    async def _mock_get_db():
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()
        yield mock_session

    app = FastAPI()
    app.add_middleware(SessionInjectionMiddleware)
    app.add_exception_handler(HTTPException, _http_exc_handler)
    app.dependency_overrides[get_db] = _mock_get_db
    app.include_router(admin_audit_router, prefix="/api/v1")
    return app


@pytest.fixture(autouse=True)
def _reset_audit_state():
    """Reset any in-memory last-verification state before each test.

    Historical: the admin_audit module used to keep a module-level
    ``_last_verification`` singleton. That was removed in the
    status-contract fix — the endpoint now derives both
    ``total_entries`` and ``last_verification`` from the durable
    ``audit_log_entries`` table on every request. This fixture is
    kept as a no-op so any future module-level state has a single
    reset point. Tests that mutate in-process state should do so
    explicitly via ``import app.api.v1.admin_audit as m; m.X = ...``.
    """
    yield


# ---------------------------------------------------------------------------
# Forbidden token sweep (defence in depth)
# ---------------------------------------------------------------------------


_AUDIT_FORBIDDEN_TOKENS: tuple[str, ...] = (
    "SELECT password FROM users",
    "admin_pw",
    "secret-token",
    "sk-12345",
    "-----BEGIN CERT-----",
    "PHNhbWw+",
    "asyncpg",
    "psycopg2",
    "pymysql",
    "pyodbc",
    "10.0.0.42",
    "5432",
    "Traceback",
)


def _assert_no_forbidden_in_response(body: dict | str) -> None:
    """Assert no forbidden token appears anywhere in the response body."""
    body_text = str(body)
    for token in _AUDIT_FORBIDDEN_TOKENS:
        assert token not in body_text, f"Forbidden token {token!r} in response: {body}"


def _assert_no_session_internal_leak(body: dict | str, session: dict | None) -> None:
    """Assert no internal session detail (UUID, username) leaks into the response."""
    body_text = str(body)
    if session is not None:
        for key in ("user_id", "role_id", "username"):
            val = session.get(key)
            if isinstance(val, str) and val:
                assert val not in body_text, f"Session field {key}={val!r} leaked into response: {body}"


# ---------------------------------------------------------------------------
# Permission enforcement
# ---------------------------------------------------------------------------


class TestPermissionEnforcement:
    """Both endpoints require admin.audit.verify permission."""

    @pytest.mark.asyncio
    async def test_verify_without_admin_audit_verify_permission_returns_403(self):
        app = _make_app(_non_admin_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/admin/audit/verify")
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "forbidden"
        assert data["message_key"] == "error.forbidden"
        _assert_no_forbidden_in_response(data)
        _assert_no_session_internal_leak(data, _non_admin_session())

    @pytest.mark.asyncio
    async def test_status_without_admin_audit_verify_permission_returns_403(self):
        app = _make_app(_non_admin_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/admin/audit/status")
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "forbidden"
        assert data["message_key"] == "error.forbidden"
        _assert_no_forbidden_in_response(data)

    @pytest.mark.asyncio
    async def test_verify_with_unmapped_user_returns_403(self):
        app = _make_app(_unmapped_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/admin/audit/verify")
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "forbidden"
        assert data["message_key"] == "error.forbidden"

    @pytest.mark.asyncio
    async def test_status_with_unmapped_user_returns_403(self):
        app = _make_app(_unmapped_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/admin/audit/status")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_verify_without_session_returns_401(self):
        app = _make_app(None)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/admin/audit/verify")
        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "unauthorized"
        assert data["message_key"] == "error.unauthorized"


# ---------------------------------------------------------------------------
# POST /admin/audit/verify — response shape (mocked verify_chain)
# ---------------------------------------------------------------------------


class TestVerifyResponseShape:
    """POST /admin/audit/verify returns the VerificationResult shape."""

    @pytest.mark.asyncio
    async def test_verify_intact_chain_returns_verified_true(self):
        mock_result = VerificationResult(
            verified=True,
            entries_checked=10,
            first_break_at=None,
            verified_at=datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC),
        )
        app = _make_app(_admin_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.api.v1.admin_audit.AuditService.verify_chain", new_callable=AsyncMock) as mock_vc:
                mock_vc.return_value = mock_result
                with patch(_AUDIT_PATCH, new_callable=AsyncMock) as _mock_log:  # noqa: F841
                    response = await client.post("/api/v1/admin/audit/verify")
        assert response.status_code == 200
        data = response.json()
        assert data["verified"] is True
        assert data["entries_checked"] == 10
        assert data["first_break_at"] is None
        assert data["verified_at"] == "2026-06-06T12:00:00+00:00"
        _assert_no_forbidden_in_response(data)

    @pytest.mark.asyncio
    async def test_verify_broken_chain_returns_first_break_at(self):
        mock_result = VerificationResult(
            verified=False,
            entries_checked=100,
            first_break_at=42,
            verified_at=datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC),
        )
        app = _make_app(_admin_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.api.v1.admin_audit.AuditService.verify_chain", new_callable=AsyncMock) as mock_vc:
                mock_vc.return_value = mock_result
                with patch(_AUDIT_PATCH, new_callable=AsyncMock) as _mock_log:  # noqa: F841
                    response = await client.post("/api/v1/admin/audit/verify")
        assert response.status_code == 200
        data = response.json()
        assert data["verified"] is False
        assert data["entries_checked"] == 100
        assert data["first_break_at"] == 42
        _assert_no_forbidden_in_response(data)

    @pytest.mark.asyncio
    async def test_verify_empty_chain_returns_zero_entries(self):
        mock_result = VerificationResult(
            verified=True,
            entries_checked=0,
            first_break_at=None,
            verified_at=datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC),
        )
        app = _make_app(_admin_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.api.v1.admin_audit.AuditService.verify_chain", new_callable=AsyncMock) as mock_vc:
                mock_vc.return_value = mock_result
                with patch(_AUDIT_PATCH, new_callable=AsyncMock) as _mock_log:  # noqa: F841
                    response = await client.post("/api/v1/admin/audit/verify")
        assert response.status_code == 200
        data = response.json()
        assert data["verified"] is True
        assert data["entries_checked"] == 0


# ---------------------------------------------------------------------------
# POST /admin/audit/verify — AUDIT_VERIFY emission (T-740 / S-008)
# ---------------------------------------------------------------------------


class TestVerifyEmitsAuditEvent:
    """Verify endpoint must emit a single AUDIT_VERIFY audit event (T-740)."""

    @pytest.mark.asyncio
    async def test_verify_emits_audit_verify_action(self):
        mock_result = VerificationResult(
            verified=True,
            entries_checked=5,
            first_break_at=None,
            verified_at=datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC),
        )
        app = _make_app(_admin_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.api.v1.admin_audit.AuditService.verify_chain", new_callable=AsyncMock) as mock_vc:
                mock_vc.return_value = mock_result
                with patch(_AUDIT_PATCH, new_callable=AsyncMock) as mock_log:
                    response = await client.post("/api/v1/admin/audit/verify")
        assert response.status_code == 200

        # Audit must have been called exactly once
        assert mock_log.await_count == 1
        kwargs = mock_log.await_args.kwargs
        assert kwargs["action"] == AuditActionType.AUDIT_VERIFY

    @pytest.mark.asyncio
    async def test_verify_emits_audit_verify_on_broken_chain(self):
        """Broken chain → endpoint still emits AUDIT_VERIFY so tampering is recorded."""
        mock_result = VerificationResult(
            verified=False,
            entries_checked=10,
            first_break_at=7,
            verified_at=datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC),
        )
        app = _make_app(_admin_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.api.v1.admin_audit.AuditService.verify_chain", new_callable=AsyncMock) as mock_vc:
                mock_vc.return_value = mock_result
                with patch(_AUDIT_PATCH, new_callable=AsyncMock) as mock_log:
                    response = await client.post("/api/v1/admin/audit/verify")
        assert response.status_code == 200
        assert mock_log.await_count == 1
        kwargs = mock_log.await_args.kwargs
        assert kwargs["action"] == AuditActionType.AUDIT_VERIFY
        # Outcome reflects verification result
        assert kwargs["outcome"] == "broken"

    @pytest.mark.asyncio
    async def test_verify_emits_audit_verify_with_stable_resource_id(self):
        """resource_id must be the stable constant ``audit_chain``; never a row UUID."""
        mock_result = VerificationResult(
            verified=True,
            entries_checked=2,
            first_break_at=None,
            verified_at=datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC),
        )
        app = _make_app(_admin_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.api.v1.admin_audit.AuditService.verify_chain", new_callable=AsyncMock) as mock_vc:
                mock_vc.return_value = mock_result
                with patch(_AUDIT_PATCH, new_callable=AsyncMock) as mock_log:
                    response = await client.post("/api/v1/admin/audit/verify")
        assert response.status_code == 200
        kwargs = mock_log.await_args.kwargs
        assert kwargs["resource_id"] == _AUDIT_VERIFY_RESOURCE_ID
        assert kwargs["resource_type"] == "audit_chain"

    @pytest.mark.asyncio
    async def test_verify_audit_context_does_not_leak_secrets(self):
        """Audit context for AUDIT_VERIFY must be free of forbidden tokens."""
        mock_result = VerificationResult(
            verified=True,
            entries_checked=3,
            first_break_at=None,
            verified_at=datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC),
        )
        app = _make_app(_admin_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.api.v1.admin_audit.AuditService.verify_chain", new_callable=AsyncMock) as mock_vc:
                mock_vc.return_value = mock_result
                with patch(_AUDIT_PATCH, new_callable=AsyncMock) as mock_log:
                    response = await client.post("/api/v1/admin/audit/verify")
        assert response.status_code == 200
        kwargs = mock_log.await_args.kwargs
        context = kwargs.get("context") or {}
        context_str = str(context)
        for token in _AUDIT_FORBIDDEN_TOKENS:
            assert token not in context_str, f"Forbidden token {token!r} in audit context: {context}"


# ---------------------------------------------------------------------------
# POST /admin/audit/verify — recursion-safety contract
# ---------------------------------------------------------------------------


class TestVerifyNoInfiniteRecursion:
    """``AuditService.log`` does NOT internally call ``AuditService.verify_chain``.

    This is the recursion-safety contract. The verify endpoint explicitly
    calls ``verify_chain`` once, captures the result, then logs a single
    ``AUDIT_VERIFY`` event. The audit log call never re-invokes
    ``verify_chain`` — proving this requires the source code to not have
    any internal call to ``verify_chain`` from inside ``log``.
    """

    def test_audit_service_log_does_not_call_verify_chain(self):
        """Static check: ``AuditService.log`` source must not call ``verify_chain``."""
        import inspect

        from app.services import audit_service

        source = inspect.getsource(audit_service.AuditService.log)
        assert "verify_chain" not in source, (
            "AuditService.log must not call AuditService.verify_chain internally; "
            "this would cause infinite recursion when the verify endpoint logs AUDIT_VERIFY."
        )

    @pytest.mark.asyncio
    async def test_verify_chain_called_exactly_once_per_request(self):
        """verify_chain must be called once; the audit log does not invoke it again."""
        mock_result = VerificationResult(
            verified=True,
            entries_checked=0,
            first_break_at=None,
            verified_at=datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC),
        )
        app = _make_app(_admin_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.api.v1.admin_audit.AuditService.verify_chain", new_callable=AsyncMock) as mock_vc:
                mock_vc.return_value = mock_result
                with patch(_AUDIT_PATCH, new_callable=AsyncMock) as _mock_log:  # noqa: F841
                    response = await client.post("/api/v1/admin/audit/verify")
        assert response.status_code == 200
        assert mock_vc.await_count == 1
        # log must not have triggered a second verify_chain call
        assert mock_vc.await_count == 1


class TestVerifyResponsePreLogCount:
    """The response ``entries_checked`` reflects the chain size at the moment of
    verification — i.e. BEFORE the audit.verify row is appended.

    Rationale: the endpoint runs ``verify_chain()`` first, captures the
    result, then calls ``AuditService.log(...)`` to record the
    AUDIT_VERIFY event. The newly-appended audit.verify row is NOT
    included in the same response's ``entries_checked``.

    This contract is observable by:
    1. Inspecting the mock call ordering: verify_chain is awaited
       BEFORE log.
    2. Asserting that the returned ``entries_checked`` matches the
       VerificationResult that verify_chain returned, not the
       post-log count.
    """

    @pytest.mark.asyncio
    async def test_verify_chain_called_before_audit_log(self):
        """verify_chain must complete before AuditService.log is called."""
        call_order: list[str] = []

        async def _verify_chain(*args, **kwargs):
            call_order.append("verify_chain")
            return VerificationResult(
                verified=True,
                entries_checked=2,
                first_break_at=None,
                verified_at=datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC),
            )

        async def _log(*args, **kwargs):
            call_order.append("log")
            return MagicMock()

        app = _make_app(_admin_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.api.v1.admin_audit.AuditService.verify_chain", side_effect=_verify_chain):
                with patch(_AUDIT_PATCH, side_effect=_log):
                    response = await client.post("/api/v1/admin/audit/verify")
        assert response.status_code == 200
        assert call_order == ["verify_chain", "log"], f"verify_chain must run before log; got {call_order!r}"

    @pytest.mark.asyncio
    async def test_response_entries_checked_does_not_include_audit_verify_row(self):
        """entries_checked in the response is the pre-log count, not post-log."""
        # Pre-log count: 5. The endpoint should log AFTER capturing
        # this 5 and return entries_checked=5 in the response.
        pre_log_count = 5
        mock_result = VerificationResult(
            verified=True,
            entries_checked=pre_log_count,
            first_break_at=None,
            verified_at=datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC),
        )
        app = _make_app(_admin_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.api.v1.admin_audit.AuditService.verify_chain", new_callable=AsyncMock) as mock_vc:
                mock_vc.return_value = mock_result
                with patch(_AUDIT_PATCH, new_callable=AsyncMock) as _mock_log:  # noqa: F841
                    response = await client.post("/api/v1/admin/audit/verify")
        assert response.status_code == 200
        data = response.json()
        # Response reflects PRE-log count. If the endpoint mistakenly
        # added the audit.verify row, this would be pre_log_count + 1.
        assert data["entries_checked"] == pre_log_count, (
            f"Response entries_checked={data['entries_checked']} should equal pre-log "
            f"count {pre_log_count}. The audit.verify row should not be counted in the same response."
        )


# ---------------------------------------------------------------------------
# GET /admin/audit/status — response shape (DB-derived)
# ---------------------------------------------------------------------------


class TestStatusResponseShape:
    """GET /admin/audit/status returns ``total_entries`` from the DB and
    reconstructs ``last_verification`` from the most recent
    ``audit.verify`` row in ``audit_log_entries``.

    These tests exercise the real DB (via ``db_session`` +
    ``clean_audit_table``) because the contract is the durable row
    count, not an in-process counter. They are unit tests in the
    taxonomy sense (no full app stack) and they auto-skip if the
    testcontainer Postgres is unavailable — they do NOT carry the
    ``integration`` marker.
    """

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("clean_audit_table")
    async def test_status_empty_db_returns_zero_and_null(self, db_session):
        from app.api.v1.admin_audit import get_audit_status

        result = await get_audit_status(db=db_session, _session=_admin_session())
        assert result["total_entries"] == 0
        assert result["last_verification"] is None
        _assert_no_forbidden_in_response(result)

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("clean_audit_table")
    async def test_status_before_verify_returns_actual_db_count(self, db_session):
        """When the DB has rows but no verify has run, total_entries reflects
        the real row count (not zero, not an in-process value)."""
        # Pre-populate audit log with three non-verify rows
        for _ in range(3):
            await AuditService.log(db_session, action=AuditActionType.QUERY_SUBMIT)
        await db_session.commit()

        from app.api.v1.admin_audit import get_audit_status

        result = await get_audit_status(db=db_session, _session=_admin_session())
        # total_entries is the ACTUAL count from the DB, not 0.
        assert result["total_entries"] == 3, (
            f"status must return real DB count; got {result['total_entries']!r}, expected 3"
        )
        # No audit.verify has been logged yet, so last_verification is None.
        assert result["last_verification"] is None
        _assert_no_forbidden_in_response(result)

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("clean_audit_table")
    async def test_status_after_verify_returns_actual_count_including_audit_verify_row(
        self,
        db_session,
    ):
        """After a verify call, total_entries reflects the actual DB count
        which INCLUDES the appended audit.verify row (one higher than the
        pre-log entries_checked returned by the verify endpoint itself)."""
        # Two rows before verify
        await AuditService.log(db_session, action=AuditActionType.QUERY_SUBMIT)
        await AuditService.log(db_session, action=AuditActionType.QUERY_ACCEPT)
        await db_session.commit()

        from app.api.v1.admin_audit import verify_audit_chain

        fake_request = MagicMock()
        fake_request.state.session = _admin_session()
        with patch(
            "app.api.v1.admin_audit.AuditService.verify_chain",
            new_callable=AsyncMock,
        ) as mock_vc:
            mock_vc.return_value = VerificationResult(
                verified=True,
                entries_checked=2,
                first_break_at=None,
                verified_at=datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC),
            )
            v_response = await verify_audit_chain(
                request=fake_request,
                db=db_session,
                _session=_admin_session(),
            )
        assert v_response["entries_checked"] == 2  # pre-log count

        from app.api.v1.admin_audit import get_audit_status

        result = await get_audit_status(db=db_session, _session=_admin_session())
        # total_entries is the ACTUAL DB count: 2 originals + 1 audit.verify = 3
        assert result["total_entries"] == 3, (
            f"status must return real DB count including the appended audit.verify "
            f"row; got {result['total_entries']!r}, expected 3"
        )
        # last_verification is reconstructed from the persisted audit.verify row
        assert result["last_verification"] is not None
        assert result["last_verification"]["verified"] is True
        assert result["last_verification"]["entries_checked"] == 2
        assert result["last_verification"]["first_break_at"] is None
        # verified_at is the row's persisted timestamp (ISO 8601 with +00:00).
        assert isinstance(result["last_verification"]["verified_at"], str)
        assert result["last_verification"]["verified_at"].endswith("+00:00")
        _assert_no_forbidden_in_response(result)

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("clean_audit_table")
    async def test_status_persisted_broken_chain_includes_first_break_at(self, db_session):
        """A broken-chain verify is still recorded as an audit.verify row;
        status returns that row's first_break_at."""
        from app.api.v1.admin_audit import verify_audit_chain

        fake_request = MagicMock()
        fake_request.state.session = _admin_session()
        with patch(
            "app.api.v1.admin_audit.AuditService.verify_chain",
            new_callable=AsyncMock,
        ) as mock_vc:
            mock_vc.return_value = VerificationResult(
                verified=False,
                entries_checked=10,
                first_break_at=7,
                verified_at=datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC),
            )
            await verify_audit_chain(
                request=fake_request,
                db=db_session,
                _session=_admin_session(),
            )

        from app.api.v1.admin_audit import get_audit_status

        result = await get_audit_status(db=db_session, _session=_admin_session())
        assert result["last_verification"] is not None
        assert result["last_verification"]["verified"] is False
        assert result["last_verification"]["first_break_at"] == 7
        assert result["last_verification"]["entries_checked"] == 10
        _assert_no_forbidden_in_response(result)

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("clean_audit_table")
    async def test_status_survives_in_process_state_reset(self, db_session):
        """The status endpoint is DB-derived; clearing any in-process state
        (simulating a process restart) must not affect the response."""
        # Pre-populate with one row and one audit.verify row
        await AuditService.log(db_session, action=AuditActionType.QUERY_SUBMIT)

        from app.api.v1.admin_audit import verify_audit_chain

        fake_request = MagicMock()
        fake_request.state.session = _admin_session()
        with patch(
            "app.api.v1.admin_audit.AuditService.verify_chain",
            new_callable=AsyncMock,
        ) as mock_vc:
            mock_vc.return_value = VerificationResult(
                verified=True,
                entries_checked=1,
                first_break_at=None,
                verified_at=datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC),
            )
            await verify_audit_chain(
                request=fake_request,
                db=db_session,
                _session=_admin_session(),
            )

        # Simulate process restart by wiping any module-level state.
        import app.api.v1.admin_audit as admin_audit_module

        for attr in ("_last_verification",):
            if hasattr(admin_audit_module, attr):
                setattr(admin_audit_module, attr, None)

        from app.api.v1.admin_audit import get_audit_status

        result = await get_audit_status(db=db_session, _session=_admin_session())
        # Both total_entries and last_verification are DB-derived
        # and must survive the in-process state wipe.
        assert result["total_entries"] == 2  # 1 original + 1 audit.verify
        assert result["last_verification"] is not None
        assert result["last_verification"]["verified"] is True
        assert result["last_verification"]["entries_checked"] == 1

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("clean_audit_table")
    async def test_status_sanitized_no_session_internal_leak(self, db_session):
        from app.api.v1.admin_audit import get_audit_status

        result = await get_audit_status(db=db_session, _session=_admin_session())
        _assert_no_session_internal_leak(result, _admin_session())
        _assert_no_forbidden_in_response(result)

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("clean_audit_table")
    async def test_status_uses_most_recent_audit_verify_row(self, db_session):
        """When multiple audit.verify rows exist, status returns the most
        recent one (highest sequence_number) — not the first one ever."""
        from app.api.v1.admin_audit import verify_audit_chain

        fake_request = MagicMock()
        fake_request.state.session = _admin_session()

        # First verify
        with patch(
            "app.api.v1.admin_audit.AuditService.verify_chain",
            new_callable=AsyncMock,
        ) as mock_vc:
            mock_vc.return_value = VerificationResult(
                verified=True,
                entries_checked=1,
                first_break_at=None,
                verified_at=datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC),
            )
            await verify_audit_chain(
                request=fake_request,
                db=db_session,
                _session=_admin_session(),
            )

        # Second verify (broken chain)
        with patch(
            "app.api.v1.admin_audit.AuditService.verify_chain",
            new_callable=AsyncMock,
        ) as mock_vc:
            mock_vc.return_value = VerificationResult(
                verified=False,
                entries_checked=5,
                first_break_at=3,
                verified_at=datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC),
            )
            await verify_audit_chain(
                request=fake_request,
                db=db_session,
                _session=_admin_session(),
            )

        from app.api.v1.admin_audit import get_audit_status

        result = await get_audit_status(db=db_session, _session=_admin_session())
        # The most recent verify is the broken-chain one
        assert result["last_verification"]["verified"] is False
        assert result["last_verification"]["first_break_at"] == 3
        assert result["last_verification"]["entries_checked"] == 5
        # verified_at is the persisted row's timestamp; for the most
        # recent (broken-chain) verify, it must be >= the first verify's.
        assert isinstance(result["last_verification"]["verified_at"], str)
        assert result["last_verification"]["verified_at"].endswith("+00:00")


# ---------------------------------------------------------------------------
# T-740: Chain recovery behavior on broken chain
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
class TestChainRecoveryBehavior:
    """S-008: broken chain does not auto-repair, appending continues.

    - Verification reports ``sequence_number`` of first mismatch.
    - No auto-repair. The endpoint never mutates or rewrites chain rows.
    - After a broken chain, ``AuditService.log`` continues appending
      (sequence_number = last_seq + 1).
    - The verification result itself is recorded as an ``audit.verify``
      audit event.
    """

    async def test_broken_chain_reports_sequence_number_of_first_mismatch(self, db_session):
        # Insert one valid entry
        await AuditService.log(db_session, action=AuditActionType.QUERY_SUBMIT)
        # Insert tampered entry at sequence 2
        bad = AuditLogEntry(
            sequence_number=2,
            timestamp=datetime.now(UTC),
            action_type="query.execute",
            outcome="success",
            prev_hash="GENESIS",
            row_hash="0" * 64,
            context={},
        )
        db_session.add(bad)
        await db_session.flush()

        result = await AuditService.verify_chain(db_session)
        assert result.verified is False
        assert result.first_break_at == 2  # sequence_number of first mismatch

    async def test_broken_chain_no_auto_repair(self, db_session):
        """verify_chain must not mutate the chain or rewrite any row hash."""
        await AuditService.log(db_session, action=AuditActionType.QUERY_SUBMIT)

        original_bad_hash = "0" * 64
        bad = AuditLogEntry(
            sequence_number=2,
            timestamp=datetime.now(UTC),
            action_type="query.execute",
            outcome="success",
            prev_hash="GENESIS",
            row_hash=original_bad_hash,
            context={},
        )
        db_session.add(bad)
        await db_session.flush()

        await AuditService.verify_chain(db_session)

        # Reload and confirm the tampered row was NOT rewritten
        result = await db_session.execute(sql_text("SELECT row_hash FROM audit_log_entries WHERE sequence_number = 2"))
        row_hash_after = result.scalar_one()
        assert row_hash_after == original_bad_hash, (
            f"verify_chain must not auto-repair; tampered row hash changed from "
            f"{original_bad_hash!r} to {row_hash_after!r}"
        )

    async def test_appending_continues_after_broken_chain(self, db_session):
        """After a broken chain, AuditService.log continues appending (chain restarts)."""
        # Insert tampered entry at sequence 1
        bad = AuditLogEntry(
            sequence_number=1,
            timestamp=datetime.now(UTC),
            action_type="query.execute",
            outcome="success",
            prev_hash="GENESIS",
            row_hash="deadbeef" * 8,
            context={},
        )
        db_session.add(bad)
        await db_session.flush()

        # New valid entry after break — must succeed without raising
        e2 = await AuditService.log(db_session, action=AuditActionType.QUERY_ACCEPT)
        assert e2.sequence_number == 2

        # The chain walk now reports break at 1 and stops (no auto-repair)
        result = await AuditService.verify_chain(db_session)
        assert result.first_break_at == 1
        # But the second entry IS in the table (append continued)
        assert result.entries_checked == 2

    async def test_verify_endpoint_logs_audit_verify_on_broken_chain(self, db_session):
        """T-740: verification result itself is recorded as audit event."""
        # Pre-populate with a broken chain
        bad = AuditLogEntry(
            sequence_number=1,
            timestamp=datetime.now(UTC),
            action_type="query.execute",
            outcome="success",
            prev_hash="GENESIS",
            row_hash="deadbeef" * 8,
            context={},
        )
        db_session.add(bad)
        await db_session.flush()

        # Hit the verify endpoint via an in-process call (bypass HTTP for test speed)
        from app.api.v1.admin_audit import verify_audit_chain

        with patch(
            "app.api.v1.admin_audit.AuditService.verify_chain",
            new_callable=AsyncMock,
        ) as mock_vc:
            mock_vc.return_value = VerificationResult(
                verified=False,
                entries_checked=1,
                first_break_at=1,
                verified_at=datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC),
            )
            with patch(_AUDIT_PATCH, new_callable=AsyncMock) as mock_log:
                # Build a fake request with admin session
                fake_request = MagicMock()
                fake_request.state.session = _admin_session()
                await verify_audit_chain(
                    request=fake_request,
                    db=db_session,
                    _session=_admin_session(),
                )

        # Audit was logged once
        assert mock_log.await_count == 1
        kwargs = mock_log.await_args.kwargs
        assert kwargs["action"] == AuditActionType.AUDIT_VERIFY
        assert kwargs["outcome"] == "broken"
        assert kwargs["resource_id"] == _AUDIT_VERIFY_RESOURCE_ID

    async def test_verify_endpoint_does_not_recurse_into_itself(self, db_session):
        """Calling verify must not recurse: the log call does not trigger another verify."""
        from app.api.v1.admin_audit import verify_audit_chain

        call_count = {"verify": 0}

        async def _fake_verify(*args, **kwargs):
            call_count["verify"] += 1
            return VerificationResult(
                verified=True,
                entries_checked=0,
                first_break_at=None,
                verified_at=datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC),
            )

        fake_request = MagicMock()
        fake_request.state.session = _admin_session()
        with patch(
            "app.api.v1.admin_audit.AuditService.verify_chain",
            side_effect=_fake_verify,
        ):
            with patch(_AUDIT_PATCH, new_callable=AsyncMock) as _mock_log:  # noqa: F841
                await verify_audit_chain(
                    request=fake_request,
                    db=db_session,
                    _session=_admin_session(),
                )

        # Exactly one verify_chain call per request, no recursion
        assert call_count["verify"] == 1


# ---------------------------------------------------------------------------
# Source code contract: AUDIT_VERIFY emit exists in shipped code
# ---------------------------------------------------------------------------


class TestAuditVerifyHasShippedCaller:
    """The Wave 17.4a structural backstop is updated: AUDIT_VERIFY has a shipped caller now."""

    def test_audit_verify_is_referenced_in_shipped_code(self):
        """Once T-738 lands, ``AuditActionType.AUDIT_VERIFY`` is referenced by
        ``src/app/api/v1/admin_audit.py``. The previous deferral
        (``KNOWN_DEFERRED`` in test_audit_event_coverage.py) is cleared."""
        from pathlib import Path

        app_root = Path(__file__).resolve().parents[2] / "src" / "app"
        needle = "AuditActionType.AUDIT_VERIFY"
        hits: list[str] = []
        for py in app_root.rglob("*.py"):
            if needle in py.read_text(encoding="utf-8", errors="replace"):
                hits.append(str(py.relative_to(app_root)))
        assert hits, (
            "AuditActionType.AUDIT_VERIFY has no shipped caller in src/app/. "
            "After T-738 the /admin/audit/verify endpoint must reference the enum."
        )
        # Must be in the admin_audit module specifically
        assert any("admin_audit" in h for h in hits), f"AUDIT_VERIFY emit should live in admin_audit.py; found: {hits}"
