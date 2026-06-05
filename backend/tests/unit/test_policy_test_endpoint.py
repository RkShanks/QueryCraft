"""TDD tests for role policy test dry-run endpoint (T-713).

POST /admin/roles/{role_id}/test-policy — admin previews what a user
with a given role + connection would be allowed to do. Does NOT call
the LLM and does NOT execute a source DB query. Returns the
accessible/blocked table summary plus row-filter / column-mask
metadata, sanitized.

Contract per specs/005-sso-rbac-row-column-security/contracts/api-contracts.md
line 253-273. Response shape::

    {
      "accessible_tables": ["customers"],
      "accessible_columns": {"customers": ["id", "name"]},
      "blocked_tables": ["orders"],
      "applicable_row_filters": [{"table": "customers", "filter": "region = 'US'"}],
      "masked_columns": {"customers": ["email"]},
      "would_be_allowed": true
    }

Sanitization guarantees:
- No role id / connection id / table / column / SQL / user value /
  DB error / host / port / username / driver / stack / credential /
  token leak in any response or error path.
- Inputs (schema, allowed_tables, etc.) are never mutated.
- Question field is metadata only; the endpoint does not run the LLM
  to convert it to SQL.
- Missing role_connection_policies row -> deny-all result
  (consistent with PR #129 fail-closed provider).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.db.models.enums import DatabaseType
from app.db.models.role import Role
from app.db.models.role_connection_policy import RoleConnectionPolicy
from app.evaluator.schema_context import Column, SchemaContext, Table

# ── Helpers ────────────────────────────────────────────────────────────────


class FakeResult:
    """Mock SQLAlchemy result with scalars().all() / scalar_one_or_none()."""

    def __init__(self, items):
        self._items = items if isinstance(items, list) else [items]

    def scalars(self):
        return self

    def all(self):
        return self._items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def first(self):
        return self._items[0] if self._items else None


def _make_role(
    role_id=None,
    name="Analyst",
    description="Read-only analyst",
    priority=10,
    permissions=None,
    is_builtin=False,
):
    role = MagicMock(spec=Role)
    role.id = role_id or uuid.uuid4()
    role.name = name
    role.description = description
    role.priority = priority
    role.permissions = permissions or ["query.submit", "query.history.view"]
    role.is_builtin = is_builtin
    role.created_at = datetime.now(UTC)
    role.updated_at = datetime.now(UTC)
    return role


def _make_policy(
    role_id,
    connection_id,
    allowed_tables=None,
    row_filters=None,
    column_masks=None,
):
    cp = MagicMock(spec=RoleConnectionPolicy)
    cp.id = uuid.uuid4()
    cp.role_id = role_id
    cp.connection_id = connection_id
    cp.allowed_tables = (
        allowed_tables
        if allowed_tables is not None
        else [
            {"table": "customers", "columns": ["id", "name"]},
        ]
    )
    cp.row_filters = row_filters if row_filters is not None else []
    cp.column_masks = column_masks if column_masks is not None else []
    return cp


def _schema() -> SchemaContext:
    return SchemaContext(
        tables=[
            Table(
                name="customers",
                columns=[
                    Column(name="id", type="integer"),
                    Column(name="name", type="text"),
                    Column(name="email", type="text"),
                    Column(name="region", type="text"),
                ],
            ),
            Table(
                name="orders",
                columns=[
                    Column(name="id", type="integer"),
                    Column(name="customer_id", type="integer"),
                ],
            ),
            Table(
                name="payments",
                columns=[
                    Column(name="id", type="integer"),
                    Column(name="order_id", type="integer"),
                ],
            ),
        ]
    )


def _schema_entries():
    """Build a list of connection_schema entry mocks for the test connection."""
    schema = _schema()
    entries = []
    for table in schema.tables:
        for col in table.columns:
            entry = MagicMock()
            entry.table_name = table.name
            entry.column_name = col.name
            entry.column_data_type = "text" if col.type == "text" else "integer"
            entry.is_primary_key = col.name == "id"
            entries.append(entry)
    return entries


def _admin_session() -> dict:
    return {
        "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "permissions": ["admin.roles.manage"],
    }


def _non_admin_session() -> dict:
    return {
        "role_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "permissions": ["query.submit"],
    }


# ── App + middleware harness ───────────────────────────────────────────────


def _make_app(
    session_data: dict | None,
    role_repo: MagicMock | None = None,
    connection_repo: MagicMock | None = None,
    db: MagicMock | None = None,
):
    """Build a FastAPI app with session injection + optional mock services.

    The admin_roles router is imported lazily so test patches can take
    effect before the module resolves the symbol.
    """
    from fastapi.responses import JSONResponse
    from starlette.middleware.base import BaseHTTPMiddleware

    from app.api.v1.admin_roles import router

    class SessionInjectionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.session = session_data
            request.state.role_repo_override = role_repo
            request.state.connection_repo_override = connection_repo
            request.state.db_override = db
            return await call_next(request)

    async def _http_exc_handler(request, exc):
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"error": "error", "message_key": str(exc.detail)})

    app = FastAPI()
    app.add_middleware(SessionInjectionMiddleware)
    app.add_exception_handler(HTTPException, _http_exc_handler)
    app.include_router(router, prefix="/api/v1")
    return app


# ── Permission Enforcement ─────────────────────────────────────────────────


class TestPermissionEnforcement:
    """POST /admin/roles/{id}/test-policy requires admin.roles.manage."""

    @pytest.mark.asyncio
    async def test_missing_permission_returns_403(self):
        app = _make_app(_non_admin_session())
        transport = ASGITransport(app=app)
        role_id = str(uuid.uuid4())
        conn_id = str(uuid.uuid4())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={"question": "Show customers", "connection_id": conn_id},
            )
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "forbidden"
        assert data["message_key"] == "error.forbidden"


# ── Validation ─────────────────────────────────────────────────────────────


class TestValidation:
    """Path / body validation: sanitized 404 for unknown / malformed ids."""

    @pytest.mark.asyncio
    async def test_invalid_role_id_uuid_returns_404_sanitized(self):
        app = _make_app(_admin_session())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/admin/roles/not-a-uuid/test-policy",
                json={"question": "Show customers", "connection_id": str(uuid.uuid4())},
            )
        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "not_found"
        assert data["message_key"] == "error.notFound"
        body = str(response.json())
        assert "not-a-uuid" not in body
        assert "ValueError" not in body
        assert "stack" not in body.lower()

    @pytest.mark.asyncio
    async def test_unknown_role_returns_404_sanitized(self):
        unknown_role_id = str(uuid.uuid4())
        # role lookup returns None
        role_repo = MagicMock()
        role_repo.get_by_id = AsyncMock(return_value=None)
        db = MagicMock()
        app = _make_app(_admin_session(), role_repo=role_repo, db=db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{unknown_role_id}/test-policy",
                json={"question": "Show customers", "connection_id": str(uuid.uuid4())},
            )
        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "not_found"
        assert data["message_key"] == "error.notFound"
        body = str(response.json())
        assert unknown_role_id not in body
        assert "NoneType" not in body
        assert "Role" not in body or "notFound" in body

    @pytest.mark.asyncio
    async def test_invalid_connection_id_uuid_returns_400_sanitized(self):
        # Mock the role repository to return a valid role
        role_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        role_repo = MagicMock()
        role_repo.get_by_id = AsyncMock(return_value=role)

        app = _make_app(_admin_session(), role_repo=role_repo)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={"question": "Show customers", "connection_id": "not-a-uuid"},
            )
        assert response.status_code == 400
        data = response.json()
        assert data["message_key"] == "error.connection_not_found"
        body = str(response.json())
        assert "not-a-uuid" not in body
        assert "ValueError" not in body

    @pytest.mark.asyncio
    async def test_unknown_connection_returns_400_sanitized(self):
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)

        role_repo = MagicMock()
        role_repo.get_by_id = AsyncMock(return_value=role)
        connection_repo = MagicMock()
        connection_repo.get_by_id = AsyncMock(return_value=None)

        app = _make_app(_admin_session(), role_repo=role_repo, connection_repo=connection_repo)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={"question": "Show customers", "connection_id": str(conn_id)},
            )
        assert response.status_code == 400
        data = response.json()
        assert data["message_key"] == "error.connection_not_found"
        body = str(response.json())
        assert str(conn_id) not in body


# ── Policy evaluation ──────────────────────────────────────────────────────


class TestPolicyEvaluation:
    """Dry-run output for an existing role + connection + policy."""

    @pytest.mark.asyncio
    async def test_existing_policy_returns_accessible_summary(self):
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        policy = _make_policy(
            role_id=role_id,
            connection_id=conn_id,
            allowed_tables=[
                {"table": "customers", "columns": ["id", "name"]},
            ],
            row_filters=[
                {"table": "customers", "filter": "region = 'US'"},
            ],
            column_masks=[
                {"table": "customers", "columns": ["email"]},
            ],
        )

        role_repo = MagicMock()
        role_repo.get_by_id = AsyncMock(return_value=role)

        # Connection: active + healthy + introspected
        conn = MagicMock()
        conn.id = conn_id
        conn.lifecycle_state = MagicMock()
        conn.lifecycle_state.value = "active"
        conn.lifecycle_state.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.health_status = MagicMock()
        conn.health_status.value = "healthy"
        conn.health_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.schema_introspection_status = MagicMock()
        conn.schema_introspection_status.value = "success"
        conn.schema_introspection_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)

        connection_repo = MagicMock()
        connection_repo.get_by_id = AsyncMock(return_value=conn)
        connection_repo.get_schema_entries = AsyncMock(return_value=_schema_entries())

        db = MagicMock()
        # 1st call: role_connection_policies lookup -> single policy
        db.execute = AsyncMock(return_value=FakeResult([policy]))

        app = _make_app(
            _admin_session(),
            role_repo=role_repo,
            connection_repo=connection_repo,
            db=db,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={"question": "Show customers", "connection_id": str(conn_id)},
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "customers" in data["accessible_tables"]
        assert "orders" in data["blocked_tables"]
        assert "payments" in data["blocked_tables"]
        assert "customers" in data["accessible_columns"]
        assert set(data["accessible_columns"]["customers"]) == {"id", "name"}
        assert data["masked_columns"].get("customers") == ["email"]
        assert any(rf.get("table") == "customers" for rf in data["applicable_row_filters"])
        assert data["would_be_allowed"] is True

    @pytest.mark.asyncio
    async def test_missing_policy_row_returns_deny_all(self):
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)

        conn = MagicMock()
        conn.id = conn_id
        conn.lifecycle_state = MagicMock()
        conn.lifecycle_state.value = "active"
        conn.lifecycle_state.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.health_status = MagicMock()
        conn.health_status.value = "healthy"
        conn.health_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.schema_introspection_status = MagicMock()
        conn.schema_introspection_status.value = "success"
        conn.schema_introspection_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)

        role_repo = MagicMock()
        role_repo.get_by_id = AsyncMock(return_value=role)
        connection_repo = MagicMock()
        connection_repo.get_by_id = AsyncMock(return_value=conn)
        connection_repo.get_schema_entries = AsyncMock(return_value=_schema_entries())

        db = MagicMock()
        # No policy row -> deny-all
        db.execute = AsyncMock(return_value=FakeResult([]))

        app = _make_app(
            _admin_session(),
            role_repo=role_repo,
            connection_repo=connection_repo,
            db=db,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={"question": "Show customers", "connection_id": str(conn_id)},
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["accessible_tables"] == []
        assert data["accessible_columns"] == {}
        # Every schema table is blocked
        for tbl in ["customers", "orders", "payments"]:
            assert tbl in data["blocked_tables"]
        assert data["applicable_row_filters"] == []
        assert data["masked_columns"] == {}
        assert data["would_be_allowed"] is False

    @pytest.mark.asyncio
    async def test_empty_allowed_tables_returns_deny_all(self):
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        policy = _make_policy(
            role_id=role_id,
            connection_id=conn_id,
            allowed_tables=[],  # empty list -> deny-all
        )

        conn = MagicMock()
        conn.id = conn_id
        conn.lifecycle_state = MagicMock()
        conn.lifecycle_state.value = "active"
        conn.lifecycle_state.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.health_status = MagicMock()
        conn.health_status.value = "healthy"
        conn.health_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.schema_introspection_status = MagicMock()
        conn.schema_introspection_status.value = "success"
        conn.schema_introspection_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)

        role_repo = MagicMock()
        role_repo.get_by_id = AsyncMock(return_value=role)
        connection_repo = MagicMock()
        connection_repo.get_by_id = AsyncMock(return_value=conn)
        connection_repo.get_schema_entries = AsyncMock(return_value=_schema_entries())

        db = MagicMock()
        db.execute = AsyncMock(return_value=FakeResult([policy]))

        app = _make_app(
            _admin_session(),
            role_repo=role_repo,
            connection_repo=connection_repo,
            db=db,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={"question": "Show customers", "connection_id": str(conn_id)},
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["accessible_tables"] == []
        assert data["would_be_allowed"] is False


# ── Metadata + sanitization ────────────────────────────────────────────────


class TestMetadataAndSanitization:
    """Row filter / mask metadata is echoed verbatim; no secret leak."""

    @pytest.mark.asyncio
    async def test_row_filter_metadata_returned_unbound(self):
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        fragment = "region = {user.subject_id}"
        policy = _make_policy(
            role_id=role_id,
            connection_id=conn_id,
            allowed_tables=[{"table": "customers", "columns": ["id", "region"]}],
            row_filters=[{"table": "customers", "filter": fragment}],
        )

        conn = MagicMock()
        conn.id = conn_id
        conn.lifecycle_state = MagicMock()
        conn.lifecycle_state.value = "active"
        conn.lifecycle_state.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.health_status = MagicMock()
        conn.health_status.value = "healthy"
        conn.health_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.schema_introspection_status = MagicMock()
        conn.schema_introspection_status.value = "success"
        conn.schema_introspection_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)

        role_repo = MagicMock()
        role_repo.get_by_id = AsyncMock(return_value=role)
        connection_repo = MagicMock()
        connection_repo.get_by_id = AsyncMock(return_value=conn)
        connection_repo.get_schema_entries = AsyncMock(return_value=[])

        db = MagicMock()
        db.execute = AsyncMock(return_value=FakeResult([policy]))

        app = _make_app(
            _admin_session(),
            role_repo=role_repo,
            connection_repo=connection_repo,
            db=db,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={"question": "Show customers", "connection_id": str(conn_id)},
            )
        assert response.status_code == 200, response.text
        data = response.json()
        # Filter returned as metadata only — not interpolated, not parsed
        rf = data["applicable_row_filters"]
        assert len(rf) == 1
        assert rf[0]["table"] == "customers"
        assert rf[0]["filter"] == fragment
        # Placeholder syntax preserved
        assert "{user.subject_id}" in rf[0]["filter"]

    @pytest.mark.asyncio
    async def test_column_mask_metadata_returned(self):
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        policy = _make_policy(
            role_id=role_id,
            connection_id=conn_id,
            allowed_tables=[{"table": "customers", "columns": ["id", "name", "email"]}],
            column_masks=[{"table": "customers", "columns": ["email"]}],
        )

        conn = MagicMock()
        conn.id = conn_id
        conn.lifecycle_state = MagicMock()
        conn.lifecycle_state.value = "active"
        conn.lifecycle_state.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.health_status = MagicMock()
        conn.health_status.value = "healthy"
        conn.health_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.schema_introspection_status = MagicMock()
        conn.schema_introspection_status.value = "success"
        conn.schema_introspection_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)

        role_repo = MagicMock()
        role_repo.get_by_id = AsyncMock(return_value=role)
        connection_repo = MagicMock()
        connection_repo.get_by_id = AsyncMock(return_value=conn)
        connection_repo.get_schema_entries = AsyncMock(return_value=[])

        db = MagicMock()
        db.execute = AsyncMock(return_value=FakeResult([policy]))

        app = _make_app(
            _admin_session(),
            role_repo=role_repo,
            connection_repo=connection_repo,
            db=db,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={"question": "Show customers", "connection_id": str(conn_id)},
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["masked_columns"] == {"customers": ["email"]}

    @pytest.mark.asyncio
    async def test_response_does_not_leak_credentials(self):
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        policy = _make_policy(role_id=role_id, connection_id=conn_id)

        conn = MagicMock()
        conn.id = conn_id
        conn.host = "internal-db.example.com"
        conn.port = 5432
        conn.username = "service_account"
        conn.encrypted_password = "gAAAAA-secret-encrypted"
        conn.lifecycle_state = MagicMock()
        conn.lifecycle_state.value = "active"
        conn.lifecycle_state.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.health_status = MagicMock()
        conn.health_status.value = "healthy"
        conn.health_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.schema_introspection_status = MagicMock()
        conn.schema_introspection_status.value = "success"
        conn.schema_introspection_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)

        role_repo = MagicMock()
        role_repo.get_by_id = AsyncMock(return_value=role)
        connection_repo = MagicMock()
        connection_repo.get_by_id = AsyncMock(return_value=conn)
        connection_repo.get_schema_entries = AsyncMock(return_value=[])

        db = MagicMock()
        db.execute = AsyncMock(return_value=FakeResult([policy]))

        app = _make_app(
            _admin_session(),
            role_repo=role_repo,
            connection_repo=connection_repo,
            db=db,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={"question": "Show customers", "connection_id": str(conn_id)},
            )
        assert response.status_code == 200, response.text
        body = response.text
        for secret in [
            "internal-db.example.com",
            "service_account",
            "gAAAAA-secret-encrypted",
            "5432",
        ]:
            assert secret not in body, f"leaked {secret!r} in response body"

    @pytest.mark.asyncio
    async def test_schema_is_not_mutated_by_endpoint(self):
        # The endpoint receives a schema via get_schema_entries and must
        # never mutate the source rows. We assert by passing a sentinel
        # value through the mock and checking it is unchanged.
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        policy = _make_policy(
            role_id=role_id,
            connection_id=conn_id,
            allowed_tables=[{"table": "customers", "columns": ["id", "name"]}],
        )

        conn = MagicMock()
        conn.id = conn_id
        conn.lifecycle_state = MagicMock()
        conn.lifecycle_state.value = "active"
        conn.lifecycle_state.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.health_status = MagicMock()
        conn.health_status.value = "healthy"
        conn.health_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.schema_introspection_status = MagicMock()
        conn.schema_introspection_status.value = "success"
        conn.schema_introspection_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)

        # Build schema entries with sentinel-marker columns. The endpoint
        # must read the rows but not mutate them.
        sentinel_entry = MagicMock()
        sentinel_entry.table_name = "customers"
        sentinel_entry.column_name = "id"
        sentinel_entry.column_data_type = "integer"
        sentinel_entry.is_primary_key = True
        sentinel_entry.__setattr__("sentinel_marker", "untouched")

        role_repo = MagicMock()
        role_repo.get_by_id = AsyncMock(return_value=role)
        connection_repo = MagicMock()
        connection_repo.get_by_id = AsyncMock(return_value=conn)
        connection_repo.get_schema_entries = AsyncMock(return_value=[sentinel_entry])

        db = MagicMock()
        db.execute = AsyncMock(return_value=FakeResult([policy]))

        app = _make_app(
            _admin_session(),
            role_repo=role_repo,
            connection_repo=connection_repo,
            db=db,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={"question": "Show customers", "connection_id": str(conn_id)},
            )
        assert response.status_code == 200, response.text
        # Sentinel preserved on the source row
        assert sentinel_entry.sentinel_marker == "untouched"
        # Accessible summary derived from policy
        data = response.json()
        assert "customers" in data["accessible_tables"]


# ── Connection state ───────────────────────────────────────────────────────


class TestConnectionState:
    """Inaccessible / disabled / no-schema connection returns sanitized 400."""

    @pytest.mark.asyncio
    async def test_inactive_connection_returns_400(self):
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        conn = MagicMock()
        conn.id = conn_id
        conn.lifecycle_state = MagicMock()
        conn.lifecycle_state.value = "disabled"
        conn.lifecycle_state.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.health_status = MagicMock()
        conn.health_status.value = "healthy"
        conn.schema_introspection_status = MagicMock()
        conn.schema_introspection_status.value = "success"

        role_repo = MagicMock()
        role_repo.get_by_id = AsyncMock(return_value=role)
        connection_repo = MagicMock()
        connection_repo.get_by_id = AsyncMock(return_value=conn)

        app = _make_app(
            _admin_session(),
            role_repo=role_repo,
            connection_repo=connection_repo,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={"question": "Show customers", "connection_id": str(conn_id)},
            )
        assert response.status_code == 400
        data = response.json()
        assert data["message_key"] == "error.connection_disabled"
        body = str(response.json())
        assert str(conn_id) not in body
        assert "lifecycle_state" not in body

    @pytest.mark.asyncio
    async def test_no_schema_connection_returns_400(self):
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        conn = MagicMock()
        conn.id = conn_id
        conn.lifecycle_state = MagicMock()
        conn.lifecycle_state.value = "active"
        conn.lifecycle_state.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.health_status = MagicMock()
        conn.health_status.value = "healthy"
        conn.health_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.schema_introspection_status = MagicMock()
        conn.schema_introspection_status.value = "none"
        conn.schema_introspection_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)

        role_repo = MagicMock()
        role_repo.get_by_id = AsyncMock(return_value=role)
        connection_repo = MagicMock()
        connection_repo.get_by_id = AsyncMock(return_value=conn)

        app = _make_app(
            _admin_session(),
            role_repo=role_repo,
            connection_repo=connection_repo,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={"question": "Show customers", "connection_id": str(conn_id)},
            )
        assert response.status_code == 400
        data = response.json()
        assert data["message_key"] == "error.connection_no_schema"


# ── Internal-error sanitization ────────────────────────────────────────────


class TestInternalErrorSanitization:
    """Internal failures are caught and never leak SQL / driver / stack."""

    @pytest.mark.asyncio
    async def test_db_error_returns_sanitized_500(self):
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        conn = MagicMock()
        conn.id = conn_id
        conn.lifecycle_state = MagicMock()
        conn.lifecycle_state.value = "active"
        conn.lifecycle_state.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.health_status = MagicMock()
        conn.health_status.value = "healthy"
        conn.health_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.schema_introspection_status = MagicMock()
        conn.schema_introspection_status.value = "success"
        conn.schema_introspection_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)

        role_repo = MagicMock()
        role_repo.get_by_id = AsyncMock(return_value=role)
        connection_repo = MagicMock()
        connection_repo.get_by_id = AsyncMock(return_value=conn)
        connection_repo.get_schema_entries = AsyncMock(return_value=[])

        db = MagicMock()
        # Driver leak in the raw exception
        db.execute = AsyncMock(
            side_effect=RuntimeError(
                "asyncpg.exceptions.PostgresError: connection refused at 10.0.0.42:5432 (user=svc)"
            )
        )

        app = _make_app(
            _admin_session(),
            role_repo=role_repo,
            connection_repo=connection_repo,
            db=db,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={"question": "Show customers", "connection_id": str(conn_id)},
            )
        assert response.status_code == 500
        data = response.json()
        assert data["message_key"] == "error.internal"
        body = response.text
        for leak in [
            "asyncpg",
            "10.0.0.42",
            "5432",
            "svc",
            "PostgresError",
            "RuntimeError",
            "Traceback",
        ]:
            assert leak not in body, f"leaked {leak!r} in 500 body"


# ── No LLM / no source-DB side effects ─────────────────────────────────────


class TestNoExecution:
    """The dry-run endpoint must not invoke the LLM or source-DB executor."""

    @pytest.mark.asyncio
    async def test_dry_run_does_not_invoke_llm(self):
        # No mock for LLM is wired in the test endpoint by design. We
        # assert the response is computed purely from the policy +
        # schema fixtures, not from any LLM call.
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        policy = _make_policy(role_id=role_id, connection_id=conn_id)

        conn = MagicMock()
        conn.id = conn_id
        conn.lifecycle_state = MagicMock()
        conn.lifecycle_state.value = "active"
        conn.lifecycle_state.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.health_status = MagicMock()
        conn.health_status.value = "healthy"
        conn.health_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
        conn.schema_introspection_status = MagicMock()
        conn.schema_introspection_status.value = "success"
        conn.schema_introspection_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)

        role_repo = MagicMock()
        role_repo.get_by_id = AsyncMock(return_value=role)
        connection_repo = MagicMock()
        connection_repo.get_by_id = AsyncMock(return_value=conn)
        connection_repo.get_schema_entries = AsyncMock(return_value=[])

        db = MagicMock()
        db.execute = AsyncMock(return_value=FakeResult([policy]))

        app = _make_app(
            _admin_session(),
            role_repo=role_repo,
            connection_repo=connection_repo,
            db=db,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={"question": "Show all customer emails", "connection_id": str(conn_id)},
            )
        assert response.status_code == 200, response.text
        data = response.json()
        # Response shape reflects policy state, not LLM-generated SQL
        assert isinstance(data["accessible_tables"], list)
        assert isinstance(data["would_be_allowed"], bool)
        # No SQL or generated question in the response
        assert "sql" not in data
        assert "generated_sql" not in data
        assert "rows" not in data


# ── Sample-SQL evaluation (FR-136 / SC-051 follow-up) ──────────────────────


def _admin_app_with_policy(
    role_id,
    conn_id,
    role,
    policy,
    conn,
    role_repo=None,
    connection_repo=None,
    db=None,
):
    """Build a FastAPI app wired with the given role / connection / policy mocks."""
    if role_repo is None:
        role_repo = MagicMock()
        role_repo.get_by_id = AsyncMock(return_value=role)
    if connection_repo is None:
        connection_repo = MagicMock()
        connection_repo.get_by_id = AsyncMock(return_value=conn)
        connection_repo.get_schema_entries = AsyncMock(return_value=_schema_entries())
    if db is None:
        db = MagicMock()
        db.execute = AsyncMock(return_value=FakeResult([policy]))
    return _make_app(
        _admin_session(),
        role_repo=role_repo,
        connection_repo=connection_repo,
        db=db,
    )


def _active_healthy_conn(conn_id, database_type=DatabaseType.POSTGRESQL):
    """Build a connection mock in active+healthy+introspected state.

    ``database_type`` defaults to POSTGRESQL so existing tests keep
    passing unchanged. The endpoint uses ``conn.database_type`` (a
    ``DatabaseType`` StrEnum) to pick the sqlglot dialect for
    sample-SQL evaluation; supplying a different enum here exercises
    the per-connection dialect resolution.
    """
    conn = MagicMock()
    conn.id = conn_id
    conn.database_type = database_type
    conn.lifecycle_state = MagicMock()
    conn.lifecycle_state.value = "active"
    conn.lifecycle_state.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
    conn.health_status = MagicMock()
    conn.health_status.value = "healthy"
    conn.health_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
    conn.schema_introspection_status = MagicMock()
    conn.schema_introspection_status.value = "success"
    conn.schema_introspection_status.__eq__ = lambda self, other: self.value == getattr(other, "value", other)
    return conn


class TestSampleSqlEvaluation:
    """When the request body includes ``sample_sql``, the endpoint must run
    ``RoleAuthorizationRule`` against the current schema + policy and return
    a SQL-level verdict. The verdict (``would_be_allowed``) is True only when
    every table/column reference in the SQL is in the policy. Blocked SQL
    returns False plus a sanitized ``message_key``. No raw SQL, table,
    column, UUID, driver, or stack text ever appears in the response.
    """

    @pytest.mark.asyncio
    async def test_sample_sql_allowed_returns_true(self):
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        policy = _make_policy(
            role_id=role_id,
            connection_id=conn_id,
            allowed_tables=[
                {"table": "customers", "columns": ["id", "name", "email"]},
            ],
        )
        conn = _active_healthy_conn(conn_id)
        app = _admin_app_with_policy(role_id, conn_id, role, policy, conn)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={
                    "question": "Show customers",
                    "connection_id": str(conn_id),
                    "sample_sql": "SELECT id, name FROM customers",
                },
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["would_be_allowed"] is True
        # No blocking message key when allowed
        assert data.get("message_key") in (None, "")
        # Policy summary is still returned
        assert "customers" in data["accessible_tables"]
        assert "orders" in data["blocked_tables"]

    @pytest.mark.asyncio
    async def test_sample_sql_disallowed_returns_false_with_message_key(self):
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        # Policy allows ONLY customers.orders is NOT allowed.
        policy = _make_policy(
            role_id=role_id,
            connection_id=conn_id,
            allowed_tables=[
                {"table": "customers", "columns": ["id", "name", "email"]},
            ],
        )
        conn = _active_healthy_conn(conn_id)
        app = _admin_app_with_policy(role_id, conn_id, role, policy, conn)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={
                    "question": "Show orders",
                    "connection_id": str(conn_id),
                    "sample_sql": "SELECT * FROM orders",
                },
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["would_be_allowed"] is False
        assert data["message_key"] == "error.queryBlockedPolicy"
        # Policy summary is still returned (admin can see what WOULD be allowed)
        assert "customers" in data["accessible_tables"]
        assert "orders" in data["blocked_tables"]

    @pytest.mark.asyncio
    async def test_sample_sql_blocked_does_not_leak_sql_or_schema(self):
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        policy = _make_policy(
            role_id=role_id,
            connection_id=conn_id,
            allowed_tables=[
                {"table": "customers", "columns": ["id", "name"]},
            ],
        )
        conn = _active_healthy_conn(conn_id)
        app = _admin_app_with_policy(role_id, conn_id, role, policy, conn)
        sample_sql = "SELECT ssn, customer_id FROM orders WHERE region = 'US'"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={
                    "question": "Show me all SSN in orders",
                    "connection_id": str(conn_id),
                    "sample_sql": sample_sql,
                },
            )
        assert response.status_code == 200, response.text
        body = response.text
        # No raw SQL fragment
        for leak in [
            "SELECT ssn",
            "FROM orders",
            "WHERE region",
            "'US'",
            "ssn",
        ]:
            assert leak not in body, f"leaked SQL fragment {leak!r} in response body"
        # No role id, connection id, user, or driver text
        for leak in [
            str(role_id),
            str(conn_id),
            "sqlglot",
            "ParseError",
            "Traceback",
            "evaluator",
            "RoleAuthorization",
        ]:
            assert leak not in body, f"leaked {leak!r} in response body"
        # Sanitized i18n key + the verdict
        data = response.json()
        assert data["would_be_allowed"] is False
        assert data["message_key"] == "error.queryBlockedPolicy"

    @pytest.mark.asyncio
    async def test_sample_sql_absent_keeps_policy_state_verdict(self):
        # Without sample_sql, the endpoint must keep its current
        # policy-state preview behaviour: would_be_allowed reflects
        # bool(accessible_tables) and message_key is absent / null.
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        policy = _make_policy(
            role_id=role_id,
            connection_id=conn_id,
            allowed_tables=[{"table": "customers", "columns": ["id", "name"]}],
        )
        conn = _active_healthy_conn(conn_id)
        app = _admin_app_with_policy(role_id, conn_id, role, policy, conn)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={"question": "Show customers", "connection_id": str(conn_id)},
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["would_be_allowed"] is True
        assert data.get("message_key") in (None, "")

    @pytest.mark.asyncio
    async def test_sample_sql_malformed_returns_blocked_sanitized(self):
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        policy = _make_policy(
            role_id=role_id,
            connection_id=conn_id,
            allowed_tables=[{"table": "customers", "columns": ["id", "name"]}],
        )
        conn = _active_healthy_conn(conn_id)
        app = _admin_app_with_policy(role_id, conn_id, role, policy, conn)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={
                    "question": "Bogus",
                    "connection_id": str(conn_id),
                    "sample_sql": "SELEKT id FORM customers (((",
                },
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["would_be_allowed"] is False
        assert data["message_key"] == "error.queryBlockedPolicy"
        body = response.text
        for leak in [
            "SELEKT",
            "FORM",
            "((( ",
            "ParseError",
            "sqlglot",
            "exceptions",
            "Traceback",
            "tokenizer",
        ]:
            assert leak not in body, f"leaked {leak!r} in malformed-SQL response body"

    @pytest.mark.asyncio
    async def test_sample_sql_non_select_returns_blocked(self):
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        # Policy allows customers. The sample SQL is a DELETE — blocked
        # at the role-auth rule because it is not a SELECT.
        policy = _make_policy(
            role_id=role_id,
            connection_id=conn_id,
            allowed_tables=[{"table": "customers", "columns": ["id", "name"]}],
        )
        conn = _active_healthy_conn(conn_id)
        app = _admin_app_with_policy(role_id, conn_id, role, policy, conn)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={
                    "question": "Wipe",
                    "connection_id": str(conn_id),
                    "sample_sql": "DELETE FROM customers WHERE id = 1",
                },
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["would_be_allowed"] is False
        assert data["message_key"] == "error.queryBlockedPolicy"
        body = response.text
        for leak in [
            "DELETE",
            "WHERE id = 1",
            "ReadOnlyRule",
            "SingleStatement",
            "sqlglot",
        ]:
            assert leak not in body, f"leaked {leak!r} in non-SELECT response body"

    @pytest.mark.asyncio
    async def test_sample_sql_multi_statement_returns_blocked(self):
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        policy = _make_policy(
            role_id=role_id,
            connection_id=conn_id,
            allowed_tables=[{"table": "customers", "columns": ["id", "name"]}],
        )
        conn = _active_healthy_conn(conn_id)
        app = _admin_app_with_policy(role_id, conn_id, role, policy, conn)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={
                    "question": "Sneaky",
                    "connection_id": str(conn_id),
                    "sample_sql": "SELECT id FROM customers; DROP TABLE customers",
                },
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["would_be_allowed"] is False
        assert data["message_key"] == "error.queryBlockedPolicy"
        body = response.text
        for leak in [
            "DROP TABLE",
            "DROP",
            "multi",
            "SingleStatement",
        ]:
            assert leak not in body, f"leaked {leak!r} in multi-statement response body"

    @pytest.mark.asyncio
    async def test_sample_sql_mysql_backtick_allowed(self):
        """MySQL connection + backtick-quoted sample SQL must be parsed with
        the ``mysql`` sqlglot dialect. The previous hard-coded
        ``dialect="postgres"`` caused sqlglot to reject backticks and
        the rule wrongly returned ``query_blocked_policy``."""
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        policy = _make_policy(
            role_id=role_id,
            connection_id=conn_id,
            allowed_tables=[
                {"table": "customers", "columns": ["id", "name", "email"]},
            ],
        )
        conn = _active_healthy_conn(conn_id, database_type=DatabaseType.MYSQL)
        app = _admin_app_with_policy(role_id, conn_id, role, policy, conn)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={
                    "question": "Show customers",
                    "connection_id": str(conn_id),
                    "sample_sql": "SELECT `id`, `name` FROM `customers`",
                },
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["would_be_allowed"] is True, data
        assert data.get("message_key") in (None, "")
        assert "customers" in data["accessible_tables"]

    @pytest.mark.asyncio
    async def test_sample_sql_mssql_bracket_allowed(self):
        """MSSQL connection + bracket-quoted sample SQL must be parsed with
        the ``tsql`` sqlglot dialect. The previous hard-coded
        ``dialect="postgres"`` caused sqlglot to reject brackets and the
        rule wrongly returned ``query_blocked_policy``."""
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        policy = _make_policy(
            role_id=role_id,
            connection_id=conn_id,
            allowed_tables=[
                {"table": "customers", "columns": ["id", "name", "email"]},
            ],
        )
        conn = _active_healthy_conn(conn_id, database_type=DatabaseType.MSSQL)
        app = _admin_app_with_policy(role_id, conn_id, role, policy, conn)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={
                    "question": "Show customers",
                    "connection_id": str(conn_id),
                    "sample_sql": "SELECT [id], [name] FROM [customers]",
                },
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["would_be_allowed"] is True, data
        assert data.get("message_key") in (None, "")
        assert "customers" in data["accessible_tables"]

    @pytest.mark.asyncio
    async def test_sample_sql_wrong_dialect_blocks_sanitized(self):
        """MSSQL connection receiving MySQL-flavoured (backtick) sample SQL
        must block with the sanitized ``error.queryBlockedPolicy`` key
        and never leak the SQL, table, column, role id, connection
        id, sqlglot, or driver text. Guards against a regression where
        a future helper might silently coerce dialects or pass
        through raw parse errors."""
        role_id = uuid.uuid4()
        conn_id = uuid.uuid4()
        role = _make_role(role_id=role_id)
        policy = _make_policy(
            role_id=role_id,
            connection_id=conn_id,
            allowed_tables=[{"table": "customers", "columns": ["id", "name"]}],
        )
        conn = _active_healthy_conn(conn_id, database_type=DatabaseType.MSSQL)
        app = _admin_app_with_policy(role_id, conn_id, role, policy, conn)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/roles/{role_id}/test-policy",
                json={
                    "question": "Show customers",
                    "connection_id": str(conn_id),
                    "sample_sql": "SELECT `id` FROM `customers`",
                },
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["would_be_allowed"] is False
        assert data["message_key"] == "error.queryBlockedPolicy"
        body = response.text
        for leak in [
            "SELECT `id`",
            "FROM `customers`",
            str(role_id),
            str(conn_id),
            "sqlglot",
            "ParseError",
            "Traceback",
            "tsql",
            "mysql",
            "mssql",
            "postgresql",
            "dialect",
            "RoleAuthorization",
        ]:
            assert leak not in body, f"leaked {leak!r} in wrong-dialect response body"
