"""Role admin endpoints (T-674).

Protected by ``admin.roles.manage`` permission.
Endpoints:
- GET /admin/roles
- POST /admin/roles
- GET /admin/roles/{id}
- PUT /admin/roles/{id}
- DELETE /admin/roles/{id}
- POST /admin/roles/{id}/test-policy  (T-714)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.permissions import require_permission
from app.core.dependencies import get_db
from app.core.exceptions import BuiltinProtectedError
from app.db.models.enums import HealthStatus, LifecycleState, Permission, SchemaIntrospectionStatus
from app.db.models.role import Role
from app.db.models.role_connection_policy import RoleConnectionPolicy
from app.db.models.sso_group_mapping import SsoGroupMapping
from app.evaluator.rules.role_authorization import RoleAuthorizationRule
from app.evaluator.schema_context import Column, SchemaContext, Table
from app.repositories.connection_repository import ConnectionRepository
from app.repositories.role_repository import RoleRepository
from app.schemas.roles import PolicyTestRequest, RoleCreate, RoleUpdate
from app.services.policy_enforcement import PolicyEnforcementService
from app.services.role_service import RoleService

router = APIRouter(prefix="/admin/roles", tags=["Admin Roles"])


def _role_to_list_response(role: Role, group_mappings: list, connection_policy_count: int) -> dict:
    return {
        "id": str(role.id),
        "name": role.name,
        "description": role.description,
        "priority": role.priority,
        "permissions": role.permissions or [],
        "is_builtin": getattr(role, "is_builtin", False),
        "group_mappings": group_mappings,
        "connection_policy_count": connection_policy_count,
        "created_at": role.created_at.isoformat() if role.created_at else None,
        "updated_at": role.updated_at.isoformat() if role.updated_at else None,
    }


def _role_to_detail_response(role: Role, group_mappings: list, connection_policies: list) -> dict:
    return {
        "id": str(role.id),
        "name": role.name,
        "description": role.description,
        "priority": role.priority,
        "permissions": role.permissions or [],
        "is_builtin": getattr(role, "is_builtin", False),
        "group_mappings": group_mappings,
        "connection_policies": connection_policies,
        "created_at": role.created_at.isoformat() if role.created_at else None,
        "updated_at": role.updated_at.isoformat() if role.updated_at else None,
    }


def _validate_permissions(permissions: list[str] | None) -> None:
    """Validate permission values against the fixed allowed set."""
    allowed = {p.value for p in Permission}
    if permissions is None:
        return
    invalid = [p for p in permissions if p not in allowed]
    if invalid:
        raise ValueError(f"Invalid permissions: {', '.join(invalid)}")


@router.get("")
async def list_roles(
    _session: dict = Depends(require_permission(Permission.ADMIN_ROLES_MANAGE)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """GET /admin/roles — list all roles."""

    try:
        repo = RoleRepository(db)
        service = RoleService(repo)
        roles = await service.list_roles()

        # Fetch all group mappings
        gm_result = await db.execute(select(SsoGroupMapping))
        gm_rows = gm_result.scalars().all()
        gm_by_role: dict = {}
        for gm in gm_rows:
            gm_by_role.setdefault(str(gm.role_id), []).append(
                {
                    "id": str(gm.id),
                    "sso_group_value": gm.sso_group_value,
                }
            )

        # Fetch connection policy counts
        cp_result = await db.execute(
            select(RoleConnectionPolicy.role_id, func.count(RoleConnectionPolicy.id)).group_by(
                RoleConnectionPolicy.role_id
            )
        )
        cp_counts = {str(row[0]): row[1] for row in cp_result.all()}

        return {
            "roles": [
                _role_to_list_response(
                    role,
                    gm_by_role.get(str(role.id), []),
                    cp_counts.get(str(role.id), 0),
                )
                for role in roles
            ]
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal", "message_key": "error.internal"},
        ) from None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_role(
    request: Request,
    body: RoleCreate,
    _session: dict = Depends(require_permission(Permission.ADMIN_ROLES_MANAGE)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """POST /admin/roles — create a new role."""

    try:
        _validate_permissions(body.permissions)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "message_key": "error.validation.invalidPermissions"},
        ) from None

    try:
        repo = RoleRepository(db)
        service = RoleService(repo)

        session = getattr(request.state, "session", {}) or {}
        role = await service.create_role(
            name=body.name,
            description=body.description,
            priority=body.priority,
            permissions=body.permissions,
            actor_identity=session.get("username"),
            db_session=db,
        )

        await db.commit()
        await db.refresh(role)

        return _role_to_detail_response(role, [], [])
    except BuiltinProtectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message_key": exc.message_key},
        ) from None
    except ValueError as exc:
        msg = str(exc)
        if "duplicate_name" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "conflict", "message_key": "error.conflict.duplicateName"},
            ) from None
        if "duplicate_priority" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "conflict", "message_key": "error.conflict.duplicatePriority"},
            ) from None
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound"},
        ) from None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal", "message_key": "error.internal"},
        ) from None


@router.get("/{role_id}")
async def get_role(
    role_id: str,
    _session: dict = Depends(require_permission(Permission.ADMIN_ROLES_MANAGE)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """GET /admin/roles/{id} — get role detail."""

    try:
        role_uuid = uuid.UUID(role_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound"},
        ) from None

    try:
        repo = RoleRepository(db)
        service = RoleService(repo)
        role = await service.get_role(role_uuid)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message_key": "error.notFound"},
            )

        gm_result = await db.execute(select(SsoGroupMapping).where(SsoGroupMapping.role_id == role_id))
        gm_rows = gm_result.scalars().all()
        group_mappings = [{"id": str(gm.id), "sso_group_value": gm.sso_group_value} for gm in gm_rows]

        cp_result = await db.execute(select(RoleConnectionPolicy).where(RoleConnectionPolicy.role_id == role_id))
        cp_rows = cp_result.scalars().all()
        connection_policies = []
        for cp in cp_rows:
            connection_policies.append(
                {
                    "id": str(cp.id),
                    "connection_id": str(cp.connection_id),
                    "allowed_tables": cp.allowed_tables or [],
                    "row_filters": cp.row_filters or [],
                    "column_masks": cp.column_masks or [],
                }
            )

        return _role_to_detail_response(role, group_mappings, connection_policies)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal", "message_key": "error.internal"},
        ) from None


@router.put("/{role_id}")
async def update_role(
    request: Request,
    role_id: str,
    body: RoleUpdate,
    _session: dict = Depends(require_permission(Permission.ADMIN_ROLES_MANAGE)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """PUT /admin/roles/{id} — update a role."""

    try:
        _validate_permissions(body.permissions)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "message_key": "error.validation.invalidPermissions"},
        ) from None

    fields = {}
    if body.name is not None:
        fields["name"] = body.name
    if body.description is not None:
        fields["description"] = body.description
    if body.priority is not None:
        fields["priority"] = body.priority
    if body.permissions is not None:
        fields["permissions"] = body.permissions

    try:
        role_uuid = uuid.UUID(role_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound"},
        ) from None

    try:
        repo = RoleRepository(db)
        service = RoleService(repo)

        session = getattr(request.state, "session", {}) or {}
        role = await service.update_role(
            role_id=role_uuid,
            fields=fields,
            actor_identity=session.get("username"),
            db_session=db,
        )

        await db.commit()
        await db.refresh(role)

        return _role_to_detail_response(role, [], [])
    except BuiltinProtectedError as exc:
        # Commit the audit log (access.denied was written inside service)
        # before returning 403. If AuditService.log had raised, we would not
        # reach this block; the outer Exception handler returns 500.
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message_key": exc.message_key},
        ) from None
    except ValueError as exc:
        msg = str(exc)
        if "duplicate_name" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "conflict", "message_key": "error.conflict.duplicateName"},
            ) from None
        if "duplicate_priority" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "conflict", "message_key": "error.conflict.duplicatePriority"},
            ) from None
        if "not_found" in msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message_key": "error.notFound"},
            ) from None
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "message_key": "error.validation.generic"},
        ) from None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal", "message_key": "error.internal"},
        ) from None


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    request: Request,
    role_id: str,
    _session: dict = Depends(require_permission(Permission.ADMIN_ROLES_MANAGE)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """DELETE /admin/roles/{id} — remove a role."""

    try:
        role_uuid = uuid.UUID(role_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound"},
        ) from None

    try:
        repo = RoleRepository(db)
        service = RoleService(repo)

        session = getattr(request.state, "session", {}) or {}
        await service.delete_role(
            role_id=role_uuid,
            actor_identity=session.get("username"),
            db_session=db,
        )

        await db.commit()
        return None
    except BuiltinProtectedError as exc:
        # Commit the audit log (access.denied was written inside service)
        # before returning 403. If AuditService.log had raised, we would not
        # reach this block; the outer Exception handler returns 500.
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message_key": exc.message_key},
        ) from None
    except ValueError as exc:
        if "not_found" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message_key": "error.notFound"},
            ) from None
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "message_key": "error.validation.generic"},
        ) from None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal", "message_key": "error.internal"},
        ) from None


# ─────────────────────────────────────────────────────────────────────────
# T-714: POST /admin/roles/{role_id}/test-policy
#
# Dry-run a sample question against a role's policy. Returns the
# accessible/blocked table summary, applicable row filter + column
# mask metadata, and a verdict. Does NOT call the LLM and does NOT
# execute a source-DB query (FR-136).
# ─────────────────────────────────────────────────────────────────────────


def _policy_test_connection_state_error(
    state,
    health,
    introspect,
):
    """Map connection lifecycle / health / introspection state to a sanitized 400.

    Returns ``None`` when the connection is in a usable state. Order
    matters: disabled takes precedence over unhealthy, which takes
    precedence over no-schema (mirrors the query flow pre-flight).

    Uses ``not (a == b)`` (not ``a != b``) so MagicMock test fakes that
    override ``__eq__`` are honored — ``unittest.mock.MagicMock`` keeps
    a separate auto-generated ``__ne__`` that does not delegate.
    """
    if not (state == LifecycleState.ACTIVE):  # noqa: SIM201
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "connection_disabled", "message_key": "error.connection_disabled"},
        )
    if not (health == HealthStatus.HEALTHY):  # noqa: SIM201
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "connection_unhealthy", "message_key": "error.connection_unhealthy"},
        )
    if not (introspect == SchemaIntrospectionStatus.SUCCESS):  # noqa: SIM201
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "connection_no_schema", "message_key": "error.connection_no_schema"},
        )
    return None


def _build_schema_from_entries(entries):
    """Group connection_schema entries into a SchemaContext.

    Inputs are read but never mutated. The endpoint never inspects or
    echoes the column data type beyond the schema filter pass.
    """
    tables = {}
    for entry in entries:
        table = tables.get(entry.table_name)
        if table is None:
            table = Table(name=entry.table_name, columns=[])
            tables[entry.table_name] = table
        table.columns.append(
            Column(
                name=entry.column_name,
                data_type=entry.column_data_type,
                is_primary_key=entry.is_primary_key,
            )
        )
    return SchemaContext(tables=list(tables.values()))


@router.post("/{role_id}/test-policy")
async def test_role_policy(
    request: Request,
    role_id: str,
    body: PolicyTestRequest,
    _session: dict = Depends(require_permission(Permission.ADMIN_ROLES_MANAGE)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """POST /admin/roles/{id}/test-policy — dry-run a question against role policy.

    Request body: ``{"question": str, "connection_id": uuid}``.

    Response 200::

        {
          "accessible_tables": [...],
          "accessible_columns": {"table": [cols]},
          "blocked_tables": [...],
          "applicable_row_filters": [{"table": ..., "filter": ...}],
          "masked_columns": {"table": [cols]},
          "would_be_allowed": bool
        }

    Behaviour:
    - Loads the role by id. Unknown / malformed role id -> sanitized
      404 with ``error.notFound``. The id is never echoed.
    - Loads the connection by id. Unknown / malformed connection id,
      or inactive / unhealthy / no-schema connection -> sanitized 400
      with the matching connection_* message key. Credentials, host,
      port, username, and the raw id are never echoed.
    - Loads the ``role_connection_policies`` row for
      ``(role_id, connection_id)``. Missing row -> deny-all result
      (consistent with PR #129 fail-closed provider; a role with no
      policy for the connection sees nothing).
    - Applies ``PolicyEnforcementService.filter_schema`` to the
      connection's introspected schema with the policy's
      ``allowed_tables``. The result drives
      ``accessible_tables`` / ``accessible_columns``.
    - ``blocked_tables`` = every schema table not in accessible.
    - ``applicable_row_filters`` is the policy's row-filter list
      echoed verbatim — never interpolated, never bound. Placeholder
      syntax (``{user.*}``) is preserved as metadata.
    - ``masked_columns`` is derived from the policy's ``column_masks``
      and includes only columns that also appear in
      ``accessible_columns`` (a mask on a non-accessible column is
      not a leak risk but is omitted for clarity).
    - ``would_be_allowed`` is True iff the policy grants at least one
      table. The endpoint does NOT evaluate generated SQL — that is
      the role of the live ``/query/submit`` evaluator; this dry-run
      is a policy-state preview, not a query simulation.
    - Internal failures (driver errors, missing tables, etc.) are
      caught and returned as sanitized 500 with constant
      ``error.internal``. No host / port / username / SQL / stack
      trace / driver class leaks in any error path.
    - Inputs (schema entries, allowed_tables, row_filters,
      column_masks) are never mutated.
    - The question field is accepted for context but is not used to
      drive any LLM call or SQL generation.
    """
    # Path / body UUID parsing — sanitized 404/400 (never echo the input).
    try:
        role_uuid = uuid.UUID(role_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound"},
        ) from None

    try:
        conn_uuid = uuid.UUID(body.connection_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "connection_not_found", "message_key": "error.connection_not_found"},
        ) from None

    # Test seam: tests may inject mock repos on request.state. In
    # production the attributes are absent and the real db / repos
    # are used.
    role_repo_override = getattr(request.state, "role_repo_override", None)
    conn_repo_override = getattr(request.state, "connection_repo_override", None)
    db_override = getattr(request.state, "db_override", None)
    db_to_use = db_override if db_override is not None else db

    try:
        if role_repo_override is not None:
            role = await role_repo_override.get_by_id(role_uuid)
        else:
            role_repo = RoleRepository(db_to_use)
            role = await role_repo.get_by_id(role_uuid)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message_key": "error.notFound"},
            )

        if conn_repo_override is not None:
            conn = await conn_repo_override.get_by_id(conn_uuid)
        else:
            conn_repo = ConnectionRepository(db_to_use)
            conn = await conn_repo.get_by_id(conn_uuid)
        if conn is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "connection_not_found", "message_key": "error.connection_not_found"},
            )

        state_err = _policy_test_connection_state_error(
            getattr(conn, "lifecycle_state", None),
            getattr(conn, "health_status", None),
            getattr(conn, "schema_introspection_status", None),
        )
        if state_err is not None:
            raise state_err

        if conn_repo_override is not None:
            schema_entries = await conn_repo_override.get_schema_entries(conn.id)
        else:
            schema_entries = await ConnectionRepository(db_to_use).get_schema_entries(conn.id)
        schema_context = _build_schema_from_entries(schema_entries)

        # Load the role_connection_policies row for (role_id, conn_id).
        # Missing row -> deny-all (fail-closed, matches PR #129 provider).
        result = await db_to_use.execute(
            select(RoleConnectionPolicy).where(
                RoleConnectionPolicy.role_id == role_uuid,
                RoleConnectionPolicy.connection_id == conn_uuid,
            )
        )
        policy_row = result.scalars().first()

        if policy_row is None:
            allowed_tables: list[dict] = []
            row_filters_list: list[dict] = []
            column_masks_list: list[dict] = []
        else:
            allowed_tables = policy_row.allowed_tables or []
            row_filters_list = policy_row.row_filters or []
            column_masks_list = policy_row.column_masks or []

        # Apply the role policy to the connection schema. The
        # policy_enforcement service never mutates its inputs.
        filtered_schema = PolicyEnforcementService.filter_schema(schema_context, allowed_tables)
        accessible_tables = [t.name for t in filtered_schema.tables]
        accessible_columns = {t.name: [c.name for c in t.columns] for t in filtered_schema.tables}

        # Blocked = every schema table not in accessible. Preserve the
        # original schema order via a set difference.
        all_tables = [t.name for t in schema_context.tables]
        blocked_tables = [name for name in all_tables if name not in accessible_tables]

        # Row filters / masks returned as metadata only. The endpoint
        # does NOT bind placeholders, does NOT inject the filter into
        # any SQL, and does NOT transform masked values. Placeholder
        # syntax is preserved verbatim.
        applicable_row_filters = [
            {"table": rf.get("table"), "filter": rf.get("filter")} for rf in row_filters_list if isinstance(rf, dict)
        ]
        masked_columns = {}
        for entry in column_masks_list:
            if not isinstance(entry, dict):
                continue
            table_name = entry.get("table")
            cols = entry.get("columns")
            if not isinstance(table_name, str) or not isinstance(cols, list):
                continue
            masked_columns[table_name] = [c for c in cols if isinstance(c, str)]

        # Verdict + message_key. Default to the policy-state preview
        # (bool(accessible_tables)). When the request carries a
        # non-empty sample_sql, run RoleAuthorizationRule against the
        # full schema + policy and override the verdict with the
        # SQL-level result. The rule's `evaluate` is fail-closed: it
        # returns the constant "query_blocked_policy" reason for every
        # failure mode (disallowed reference, malformed SQL, multi-
        # statement, non-SELECT, empty) and never echoes the raw SQL,
        # table, column, schema, or driver text. The i18n message key
        # we surface is the constant "error.queryBlockedPolicy" per
        # api-contracts.md line 385.
        would_be_allowed = bool(accessible_tables)
        message_key: str | None = None
        sample_sql = body.sample_sql if isinstance(body.sample_sql, str) else None
        if sample_sql and sample_sql.strip():
            rule = RoleAuthorizationRule(
                allowed_tables=allowed_tables if allowed_tables else None,
                column_masks=column_masks_list if column_masks_list else None,
                dialect="postgres",
            )
            allowed, _reason = await rule.evaluate(sample_sql, schema_context)
            would_be_allowed = bool(allowed)
            if not allowed:
                message_key = "error.queryBlockedPolicy"

        return {
            "accessible_tables": accessible_tables,
            "accessible_columns": accessible_columns,
            "blocked_tables": blocked_tables,
            "applicable_row_filters": applicable_row_filters,
            "masked_columns": masked_columns,
            "would_be_allowed": would_be_allowed,
            "message_key": message_key,
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal", "message_key": "error.internal"},
        ) from None
