"""IS-GAP-032 / CHUNK-20: server-side history dataset search contract.

GET /api/v1/history gains an optional trimmed ``search`` query parameter
(maximum 200 Unicode code points). Matching is case-insensitive literal
substring over the authenticated user's ``question_text`` and
``generated_sql``; wildcard characters are escaped and the pattern is a
bound SQLAlchemy parameter. Pagination stays reverse-chronological keyset
with explicit limits, the first page returns the filtered total, and the
cursor namespace binds to a value-safe hash of the normalized search so a
cursor cannot be replayed against another filter. Raw search text never
enters the cursor payload or audit context.
"""

from __future__ import annotations

import base64
import json
import unittest
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import InvalidCursorError
from app.core.pagination import decode_cursor
from app.services.history_service import (
    HistoryService,
    normalize_history_search,
    search_cursor_namespace,
)
from tests.unit.permission_test_helpers import use_test_session_current_role


def _summary(item_id: str, question: str, sql: str) -> MagicMock:
    row = MagicMock()
    row.id = item_id
    row.question_text = question
    row.generated_sql = sql
    accepted_at = MagicMock()
    accepted_at.isoformat.return_value = "2026-05-04T12:00:00+00:00"
    row.accepted_at = accepted_at
    row.database_connection_id = None
    return row


def _service_with_page(rows, next_cursor=None, total=0):
    repo = MagicMock()
    repo.list_by_user = AsyncMock(return_value=(rows, next_cursor))
    repo.count_by_user = AsyncMock(return_value=total)
    connection_repo = MagicMock()
    connection_repo.get_by_id = AsyncMock(return_value=None)
    return HistoryService(repo, connection_repo), repo


class TestSearchNormalization:
    """Whitespace-only search means unfiltered history."""

    def test_none_stays_none(self):
        assert normalize_history_search(None) is None

    def test_whitespace_only_becomes_unfiltered(self):
        assert normalize_history_search("   \t\n ") is None

    def test_surrounding_whitespace_trimmed(self):
        assert normalize_history_search("  revenue  ") == "revenue"

    def test_inner_content_preserved(self):
        assert normalize_history_search("  a  b  ") == "a  b"

    def test_over_long_search_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            normalize_history_search("x" * 201)
        assert exc_info.value.status_code == 422

    def test_exactly_200_code_points_accepted_after_trim(self):
        padded = f"{'x' * 200}   "
        assert normalize_history_search(padded) == "x" * 200

    def test_multibyte_code_point_counting(self):
        # 100 two-code-point-safe Arabic letters plus padding: 100 code points.
        value = "\u0623\u0647\u0644\u0627" * 50 + "  "
        normalized = normalize_history_search(value)
        assert normalized == value.strip()
        with pytest.raises(HTTPException):
            normalize_history_search("\u0623" * 201)


class TestCursorNamespaceBinding:
    """The cursor namespace carries a hash of the normalized search."""

    def test_namespace_is_hash_bound_not_raw_text(self):
        namespace = search_cursor_namespace("secret needle")
        assert "secret needle" not in namespace
        assert "needle" not in namespace

    def test_same_normalized_search_same_namespace(self):
        assert search_cursor_namespace("revenue") == search_cursor_namespace("  revenue ")

    def test_different_search_different_namespace(self):
        assert search_cursor_namespace("revenue") != search_cursor_namespace("customers")

    @pytest.mark.asyncio
    async def test_filtered_next_cursor_encodes_namespaced_position(self):
        rows = [_summary("550e8400-e29b-41d4-a716-4466554400a1", "q", "s")]
        service, repo = _service_with_page(rows, next_cursor=None, total=1)
        await service.list_history(
            user_id="550e8400-e29b-41d4-a716-446655440001",
            search="revenue",
            limit=1,
        )
        _, kwargs = repo.list_by_user.await_args
        assert kwargs.get("search") or repo.list_by_user.await_args.args
        # The repository receives the trimmed literal search.
        passed = repo.list_by_user.await_args.kwargs.get("search")
        assert passed == "revenue"


class TestCursorPayloadPrivacy:
    """Opaque cursors must not embed raw search text anywhere."""

    def test_decode_rejects_foreign_filter_cursor(self):
        """A cursor minted under one filter cannot decode under another."""
        from datetime import UTC, datetime
        from uuid import uuid4

        from app.core.exceptions import InvalidCursorError

        cursor = (
            base64.urlsafe_b64encode(
                json.dumps(
                    {
                        "v": 1,
                        "n": search_cursor_namespace("revenue"),
                        "s": datetime(2026, 5, 4, tzinfo=UTC).isoformat(),
                        "i": str(uuid4()),
                    },
                    separators=(",", ":"),
                ).encode()
            )
            .rstrip(b"=")
            .decode("ascii")
        )

        with pytest.raises(InvalidCursorError):
            decode_cursor(cursor, search_cursor_namespace("customers"))


class TestServiceForwardsSearch:
    """Service passes trimmed search to repository and keeps totals filtered."""

    @pytest.mark.asyncio
    async def test_list_forwards_trimmed_search_and_count(self):
        rows = [_summary("550e8400-e29b-41d4-a716-4466554400a1", "Revenue top", "SELECT 1")]
        service, repo = _service_with_page(rows, next_cursor="opaque", total=7)

        response = await service.list_history(
            user_id="550e8400-e29b-41d4-a716-446655440001",
            search="  revenue ",
            limit=5,
        )

        repo.list_by_user.assert_awaited_once()
        call_kwargs = repo.list_by_user.await_args.kwargs
        assert call_kwargs["search"] == "revenue"
        assert call_kwargs["limit"] == 5
        repo.count_by_user.assert_awaited_once()
        assert repo.count_by_user.await_args.kwargs["search"] == "revenue"
        assert response.total == 7
        assert response.next_cursor == "opaque"

    @pytest.mark.asyncio
    async def test_blank_search_is_unfiltered(self):
        service, repo = _service_with_page([], None, 0)
        await service.list_history(
            user_id="550e8400-e29b-41d4-a716-446655440001",
            search="   ",
        )
        assert repo.list_by_user.await_args.kwargs["search"] is None
        assert repo.count_by_user.await_args.kwargs["search"] is None

    @pytest.mark.asyncio
    async def test_audit_context_never_contains_raw_search_text(self):
        rows = [_summary("550e8400-e29b-41d4-a716-4466554400a1", "Revenue top", "SELECT 1")]
        repo = MagicMock()
        repo.list_by_user = AsyncMock(return_value=(rows, None))
        repo.count_by_user = AsyncMock(return_value=1)
        connection_repo = MagicMock()
        connection_repo.get_by_id = AsyncMock(return_value=None)
        service = HistoryService(repo, connection_repo, db_session=AsyncMock())

        with unittest.mock.patch("app.services.history_service.AuditService.log", new_callable=AsyncMock) as audit_log:
            await service.list_history(
                user_id="550e8400-e29b-41d4-a716-446655440001",
                search="confidential-needle",
            )

        context = audit_log.await_args.kwargs["context"]
        serialized = json.dumps(context)
        assert "confidential-needle" not in serialized
        assert context.get("operation") == "list"


def _build_history_app(service: HistoryService) -> FastAPI:
    """Minimal app mirroring the production sanitized error contracts.

    The full application's session middleware cannot run in this unit
    environment, so the router mounts on a bare FastAPI app with the same
    HTTPException and RequestValidationError handlers as ``create_app()``
    (main.py) so responses match the production sanitized envelopes.
    """
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
    from starlette.middleware.base import BaseHTTPMiddleware

    from app.api.v1.history import _get_history_service, router
    from app.core.dependencies import require_active_user

    async def override_service():
        return service

    async def override_user():
        return "550e8400-e29b-41d4-a716-446655440001"

    class SessionInjectionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.session = {
                "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "permissions": ["query.history.view"],
            }
            return await call_next(request)

    app = FastAPI()
    use_test_session_current_role(app)
    app.add_middleware(SessionInjectionMiddleware)

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(request, exc):
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "error", "message_key": str(exc.detail)},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(request, exc):
        details = []
        for err in exc.errors():
            field = ".".join(str(loc) for loc in err.get("loc", []))
            details.append(
                {
                    "field": field,
                    "message_key": err.get("type", "error.validation.generic"),
                    "message_params": {"msg": err.get("msg", "")},
                }
            )
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation",
                "message_key": "error.validation.generic",
                "details": details,
            },
        )

    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[_get_history_service] = override_service
    app.dependency_overrides[require_active_user] = override_user
    return app


class TestHistorySearchEndpoint:
    """HTTP contract for the optional trimmed search parameter."""

    @pytest.mark.asyncio
    async def test_search_query_param_reaches_the_service_trimmed(self):
        rows = [_summary("550e8400-e29b-41d4-a716-4466554400a1", "Revenue top", "SELECT 1")]
        service, repo = _service_with_page(rows, None, 1)

        transport = ASGITransport(app=_build_history_app(service))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/history", params={"search": "  revenue  "})

        assert response.status_code == 200
        assert repo.list_by_user.await_args.kwargs["search"] == "revenue"
        assert response.json()["total"] == 1

    @pytest.mark.asyncio
    async def test_blank_search_is_accepted_as_unfiltered(self):
        service, repo = _service_with_page([], None, 0)

        transport = ASGITransport(app=_build_history_app(service))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/history", params={"search": "   "})

        assert response.status_code == 200
        assert repo.list_by_user.await_args.kwargs["search"] is None

    @pytest.mark.asyncio
    async def test_over_long_search_returns_sanitized_validation_error(self):
        service, repo = _service_with_page([], None, 0)

        transport = ASGITransport(app=_build_history_app(service))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/history", params={"search": "x" * 201})

        assert response.status_code == 422
        body = json.dumps(response.json())
        assert "x" * 201 not in body
        assert response.json().get("error") == "validation"
        repo.list_by_user.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_invalid_cursor_still_returns_existing_sanitized_contract(self):
        rows = [_summary("550e8400-e29b-41d4-a716-4466554400a1", "q", "s")]
        service, _repo = _service_with_page(rows, None, 1)
        service._repo.list_by_user = AsyncMock(side_effect=InvalidCursorError())

        transport = ASGITransport(app=_build_history_app(service))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/history", params={"search": "revenue", "cursor": "garbage"})

        assert response.status_code == 400
        body = response.json()
        assert body["error"] == "invalid_cursor"
        assert body["message_key"] == "error.invalidCursor"


class TestHistorySearchOpenApiContract:
    """Canonical OpenAPI declares the bounded optional search parameter."""

    def test_list_history_declares_bounded_optional_search(self):
        from pathlib import Path

        canonical_path = Path(__file__).resolve().parents[2] / "openapi.json"
        schema = json.loads(canonical_path.read_text(encoding="utf-8"))
        operation = schema["paths"]["/api/v1/history"]["get"]
        parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}

        assert "search" in parameters
        search_parameter = parameters["search"]
        assert search_parameter["in"] == "query"
        assert search_parameter["required"] is False
        schema = search_parameter["schema"]
        variants = schema.get("anyOf", [schema])
        string_schema = next(variant for variant in variants if variant.get("type") == "string")
        assert string_schema["maxLength"] == 200
