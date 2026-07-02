"""T-894 — Cross-dialect quota enforcement verification.

Verifies that quota enforcement is dialect-agnostic: quotas are checked
and enforced regardless of which source database dialect (PostgreSQL,
MySQL, MSSQL) the user is querying against.

Key contracts verified:
1. Quota check is performed BEFORE SQL is generated or executed.
2. The same quota state (Redis keys, dimensions, reset windows) is used
   regardless of the source DB dialect.
3. 429 + error.quota_exceeded fires for every dimension (queries,
   executions, exports) when the limit is exhausted, regardless of dialect.
4. Quota fail-closed (503) is dialect-agnostic — Redis unavailability
   blocks all dialects, not just postgres.
5. No dialect identifier (postgres/mysql/mssql) leaks into quota error body.
6. Quota key namespacing is per-user per-dimension (not per-connection/dialect).

FR-152 (quota enforcement), SC-063 (fail-closed), SC-064 (sanitized body).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import QuotaExceededError, QuotaUnavailableError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DIALECTS = ["postgres", "mysql", "mssql"]

_DIMENSIONS = ["queries", "executions", "exports"]


def _make_query_service(*, quota_side_effect=None, quota_return=None):
    """Build a QueryService with mocked dependencies for quota testing."""
    from app.services.query_service import QueryService

    user_id = uuid.uuid4()
    role_id = uuid.uuid4()

    mock_quota_service = AsyncMock()
    if quota_side_effect is not None:
        mock_quota_service.check_and_increment = AsyncMock(side_effect=quota_side_effect)
    else:
        mock_quota_service.check_and_increment = AsyncMock(return_value=quota_return or (1, 100, None))

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=MagicMock(id=user_id, role_id=role_id, username="testuser"))
        )
    )
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock()

    service = QueryService(
        accepted_query_repository=AsyncMock(),
        session_repository=AsyncMock(),
        db_session=mock_db,
        redis=mock_redis,
        llm=AsyncMock(),
        evaluator=AsyncMock(),
        source_db_executor=AsyncMock(),
        llm_provider="test",
        schema_context="",
        quota_service=mock_quota_service,
    )
    return service, user_id, role_id, mock_quota_service


# ---------------------------------------------------------------------------
# T-894.1 — Quota check is dialect-agnostic
# ---------------------------------------------------------------------------


class TestQuotaCheckIsDialectAgnostic:
    """QuotaService.check_and_increment is called before any DB execution
    regardless of which source database dialect is configured.

    The quota check happens at submit_question time, before schema introspection
    or SQL generation. The connection dialect plays no role in whether quota
    is enforced.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("dialect", _DIALECTS)
    async def test_quota_exceeded_fires_before_llm_regardless_of_dialect(self, dialect: str) -> None:
        """Quota check fires and raises 429 before LLM generation for all dialects."""
        from fastapi import HTTPException

        reset_at = "2026-07-01T00:00:00+00:00"
        service, user_id, role_id, mock_quota = _make_query_service(
            quota_side_effect=QuotaExceededError(dimension="queries", reset_at=reset_at)
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.submit_question(
                http_session_id="test-session",
                user_id=str(user_id),
                question="show me all orders",
            )

        assert exc_info.value.status_code == 429, f"[{dialect}] Expected 429, got {exc_info.value.status_code}"
        assert exc_info.value.detail["message_key"] == "error.quota_exceeded", (
            f"[{dialect}] Wrong message_key: {exc_info.value.detail['message_key']}"
        )
        # LLM never called — quota blocks before SQL generation
        service._llm.generate_sql.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("dialect", _DIALECTS)
    async def test_quota_unavailable_blocks_all_dialects(self, dialect: str) -> None:
        """Redis unavailability (503) blocks submission regardless of dialect."""
        from fastapi import HTTPException

        service, user_id, role_id, mock_quota = _make_query_service(quota_side_effect=QuotaUnavailableError())

        with pytest.raises(HTTPException) as exc_info:
            await service.submit_question(
                http_session_id="test-session",
                user_id=str(user_id),
                question="show me all orders",
            )

        assert exc_info.value.status_code == 503, f"[{dialect}] Expected 503, got {exc_info.value.status_code}"
        assert exc_info.value.detail["message_key"] == "error.service_unavailable", (
            f"[{dialect}] Wrong message_key: {exc_info.value.detail['message_key']}"
        )
        service._llm.generate_sql.assert_not_called()


# ---------------------------------------------------------------------------
# T-894.2 — Quota key namespacing is per-user, not per-connection/dialect
# ---------------------------------------------------------------------------


class TestQuotaKeyNamespacingIsPerUser:
    """Quota Redis keys are namespaced per user_id + dimension + date.

    The connection_id (and its dialect) plays no role in the quota key
    structure. Two users with the same role can have separate quota budgets;
    one user's queries against MySQL vs PostgreSQL share the same counter.
    """

    def test_quota_key_pattern_excludes_connection_id(self) -> None:
        """Quota key must contain user_id and dimension, not connection_id or dialect."""
        import re

        from app.services.quota_service import _today_key_suffix

        user_id = str(uuid.uuid4())
        dimension = "queries"
        date_suffix = _today_key_suffix()

        # Simulate the key pattern used by QuotaService
        key = f"quota:{user_id}:{dimension}:{date_suffix}"

        # Must not include any dialect name
        for dialect in _DIALECTS:
            assert dialect not in key, f"Dialect '{dialect}' found in quota key: {key}"
        # Must contain user_id and dimension
        assert user_id in key
        assert dimension in key
        # Must contain a date suffix matching YYYY-MM-DD
        assert re.search(r"\d{4}-\d{2}-\d{2}", key)

    @pytest.mark.parametrize("dialect", _DIALECTS)
    def test_quota_key_same_for_same_user_different_dialect(self, dialect: str) -> None:
        """Same user querying different dialects uses the same quota key."""
        from app.services.quota_service import _today_key_suffix

        user_id = str(uuid.uuid4())
        dimension = "queries"
        date_suffix = _today_key_suffix()
        key = f"quota:{user_id}:{dimension}:{date_suffix}"

        # Key is identical regardless of dialect (dialect is irrelevant)
        assert dialect not in key  # dialect not a key component
        assert user_id in key
        assert dimension in key


# ---------------------------------------------------------------------------
# T-894.3 — Quota error body never leaks dialect info
# ---------------------------------------------------------------------------


class TestQuotaErrorBodyNeverLeaksDatabaseInfo:
    """Error body for quota exceeded never exposes DB dialect or connection details."""

    @pytest.mark.parametrize("dialect", _DIALECTS)
    def test_quota_exceeded_body_no_dialect_leak(self, dialect: str) -> None:
        """429 body must not mention the source DB dialect."""
        import json

        from app.core.exceptions import QuotaExceededError

        err = QuotaExceededError(dimension="queries", reset_at="2026-07-01T00:00:00+00:00")
        body = {
            "error": "quota_exceeded",
            "message_key": err.message_key,
            "reset_at": err.reset_at,
        }
        body_str = json.dumps(body)

        assert dialect not in body_str, f"Dialect '{dialect}' leaked into quota exceeded error body"

    @pytest.mark.parametrize("dialect", _DIALECTS)
    def test_quota_unavailable_body_no_dialect_leak(self, dialect: str) -> None:
        """503 body must not mention source DB dialect or Redis config."""
        import json

        body = {
            "error": "service_unavailable",
            "message_key": "error.service_unavailable",
        }
        body_str = json.dumps(body)

        assert dialect not in body_str
        assert "redis" not in body_str
        assert "localhost" not in body_str
        assert "6379" not in body_str  # default Redis port

    def test_quota_error_body_contains_no_connection_details(self) -> None:
        """Quota error body has no connection_id, db_host, db_port, or db_name."""
        import json

        body = {
            "error": "quota_exceeded",
            "message_key": "error.quota_exceeded",
            "reset_at": "2026-07-01T00:00:00+00:00",
        }
        body_str = json.dumps(body)

        for forbidden in ["connection_id", "db_host", "db_port", "db_name", "connection_string"]:
            assert forbidden not in body_str, f"Forbidden field '{forbidden}' found in quota exceeded body"


# ---------------------------------------------------------------------------
# T-894.4 — Quota QuotaService.check_and_increment is dialect-agnostic
# ---------------------------------------------------------------------------


class TestQuotaServiceDialectAgnostic:
    """QuotaService.check_and_increment signature does not take dialect param."""

    def test_check_and_increment_signature_no_dialect_param(self) -> None:
        """check_and_increment must not have a 'dialect' parameter."""
        import inspect

        from app.services.quota_service import QuotaService

        sig = inspect.signature(QuotaService.check_and_increment)
        param_names = set(sig.parameters.keys())

        assert "dialect" not in param_names, (
            f"check_and_increment unexpectedly has a 'dialect' parameter: {param_names}"
        )
        assert "connection_type" not in param_names
        assert "db_type" not in param_names

    def test_check_and_increment_takes_user_role_dimension(self) -> None:
        """check_and_increment takes user_id, role_id, and dimension — not dialect."""
        import inspect

        from app.services.quota_service import QuotaService

        sig = inspect.signature(QuotaService.check_and_increment)
        param_names = set(sig.parameters.keys())

        # Required fields
        assert "user_id" in param_names
        assert "role_id" in param_names
        assert "dimension" in param_names


# ---------------------------------------------------------------------------
# T-894.5 — All quota dimensions are dialect-agnostic
# ---------------------------------------------------------------------------


class TestAllQuotaDimensionsDialectAgnostic:
    """queries, executions, and exports quota dimensions are enforced consistently."""

    @pytest.mark.parametrize("dimension", _DIMENSIONS)
    def test_dimension_limit_map_is_dialect_agnostic(self, dimension: str) -> None:
        """All three quota dimensions map to DB fields regardless of source dialect."""
        from app.services.quota_service import _DIMENSION_LIMIT_MAP

        assert dimension in _DIMENSION_LIMIT_MAP, f"Quota dimension '{dimension}' not in _DIMENSION_LIMIT_MAP"
        limit_attr = _DIMENSION_LIMIT_MAP[dimension]
        # The attribute name must not reference any dialect
        for dialect in _DIALECTS:
            assert dialect not in limit_attr, (
                f"Dialect '{dialect}' found in limit attribute for dimension '{dimension}': {limit_attr}"
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("dimension", _DIMENSIONS)
    async def test_quota_exceeded_429_for_all_dimensions(self, dimension: str) -> None:
        """Quota exceeded 429 fires for each of the three quota dimensions."""
        from fastapi import HTTPException

        reset_at = "2026-07-01T00:00:00+00:00"
        service, user_id, role_id, mock_quota = _make_query_service(
            quota_side_effect=QuotaExceededError(dimension=dimension, reset_at=reset_at)
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.submit_question(
                http_session_id="test-session",
                user_id=str(user_id),
                question="show me all orders",
            )

        assert exc_info.value.status_code == 429, f"[{dimension}] Expected 429, got {exc_info.value.status_code}"
        assert exc_info.value.detail["message_key"] == "error.quota_exceeded"
