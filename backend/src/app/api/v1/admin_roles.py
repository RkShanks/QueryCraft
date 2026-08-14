"""Role admin endpoints (T-674).

Protected by ``admin.roles.manage`` permission.
Endpoints:
- GET /admin/roles
- POST /admin/roles
- GET /admin/roles/{id}
- PUT /admin/roles/{id}
- DELETE /admin/roles/{id}
- POST /admin/roles/test-policy  (CHUNK-15 draft preview)
- POST /admin/roles/{id}/test-policy  (T-714)
"""

import uuid
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.permissions import require_permission
from app.core.dependencies import get_db
from app.core.exceptions import BuiltinProtectedError
from app.db.models.database_connection import SourceDatabaseConnection
from app.db.models.enums import AuditActionType, HealthStatus, LifecycleState, Permission, SchemaIntrospectionStatus
from app.db.models.role import Role
from app.db.models.role_connection_policy import RoleConnectionPolicy
from app.db.models.sso_group_mapping import SsoGroupMapping
from app.evaluator.rules.read_only import DIALECT_MAP
from app.evaluator.rules.role_authorization import RoleAuthorizationRule
from app.evaluator.schema_context import Column, SchemaContext, Table
from app.repositories.connection_repository import ConnectionRepository
from app.repositories.role_repository import RoleRepository
from app.schemas.roles import (
    ConnectionPolicyItem,
    DraftPolicyTestRequest,
    PolicyTestRequest,
    PolicyTestResponse,
    RoleCreate,
    RoleUpdate,
)
from app.services.audit_service import AuditService
from app.services.policy_enforcement import PolicyEnforcementService
from app.services.role_service import RoleService

router = APIRouter(prefix="/admin/roles", tags=["Admin Roles"])


@dataclass(frozen=True)
class _PreviewPolicy:
    allowed_tables: list[dict]
    row_filters: list[dict]
    column_masks: list[dict]


@dataclass(frozen=True)
class _ConnectionPolicyValues:
    allowed_tables: list[dict]
    row_filters: list[dict]
    column_masks: list[dict]


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


def _group_mapping_summary(mapping_id: uuid.UUID, group_value: str) -> dict[str, str]:
    return {"id": str(mapping_id), "sso_group_value": group_value}


def _duplicate_group_mapping_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": "conflict",
            "message_key": "error.conflict.duplicateGroupMapping",
        },
    )


async def _create_role_group_mappings(
    db: AsyncSession,
    role_id: uuid.UUID,
    group_values: list[str],
    actor_identity: str | None,
) -> list[dict[str, str]]:
    """Claim requested groups and audit each claim in the caller's transaction."""
    mappings: list[dict[str, str]] = []
    for group_value in group_values:
        mapping_id = await _claim_group_mapping(db, role_id, group_value)
        await _audit_group_mapping_change(db, mapping_id, actor_identity, "create")
        mappings.append(_group_mapping_summary(mapping_id, group_value))
    return mappings


async def _claim_group_mapping(db: AsyncSession, role_id: uuid.UUID, group_value: str) -> uuid.UUID:
    mapping_id = await db.scalar(
        pg_insert(SsoGroupMapping)
        .values(sso_group_value=group_value, role_id=role_id)
        .on_conflict_do_nothing(index_elements=[SsoGroupMapping.sso_group_value])
        .returning(SsoGroupMapping.id)
    )
    if mapping_id is None:
        raise _duplicate_group_mapping_error()
    return mapping_id


async def _audit_group_mapping_change(
    db: AsyncSession,
    mapping_id: uuid.UUID,
    actor_identity: str | None,
    action: str,
) -> None:
    await AuditService.log(
        db,
        action=AuditActionType.ROLE_MAPPING_CHANGE,
        actor_identity=actor_identity,
        resource_type="sso_group_mapping",
        resource_id=str(mapping_id),
        outcome="success",
        context={"action": action},
    )


async def _role_group_mapping_rows(db: AsyncSession, role_id: uuid.UUID) -> list[SsoGroupMapping]:
    result = await db.execute(
        select(SsoGroupMapping)
        .where(SsoGroupMapping.role_id == role_id)
        .order_by(SsoGroupMapping.created_at, SsoGroupMapping.id)
    )
    return list(result.scalars().all())


async def _sync_role_group_mappings(
    db: AsyncSession,
    role_id: uuid.UUID,
    requested_values: list[str],
    actor_identity: str | None,
) -> list[dict[str, str]]:
    current_rows = await _role_group_mapping_rows(db, role_id)
    current_by_value = {row.sso_group_value: row for row in current_rows}
    requested_set = set(requested_values)

    for mapping in current_rows:
        if mapping.sso_group_value not in requested_set:
            await db.delete(mapping)
            await _audit_group_mapping_change(db, mapping.id, actor_identity, "delete")

    persisted_ids = {group_value: mapping.id for group_value, mapping in current_by_value.items()}
    for group_value in requested_values:
        if group_value not in persisted_ids:
            mapping_id = await _claim_group_mapping(db, role_id, group_value)
            await _audit_group_mapping_change(db, mapping_id, actor_identity, "create")
            persisted_ids[group_value] = mapping_id

    return [_group_mapping_summary(persisted_ids[value], value) for value in requested_values]


def _validate_permissions(permissions: list[str] | None) -> None:
    """Validate permission values against the fixed allowed set."""
    allowed = {p.value for p in Permission}
    if permissions is None:
        return
    invalid = [p for p in permissions if p not in allowed]
    if invalid:
        raise ValueError(f"Invalid permissions: {', '.join(invalid)}")


def _parse_policy_connection_ids(policies) -> list[uuid.UUID]:
    """Parse and validate `connection_id` UUIDs in a connection_policies list.

    Raises sanitized 422 on bad UUID format. Returns the parsed UUIDs in
    input order. Duplicates are detected in `_validate_policy_input`.
    """
    parsed: list[uuid.UUID] = []
    for policy in policies:
        raw = getattr(policy, "connection_id", None)
        if not isinstance(raw, str) or not raw:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "message_key": "error.validation.invalidConnection",
                },
            )
        try:
            parsed.append(uuid.UUID(raw))
        except (ValueError, AttributeError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "message_key": "error.validation.invalidConnection",
                },
            ) from None
    return parsed


async def _validate_policy_input(db: AsyncSession, parsed_conn_ids: list[uuid.UUID]) -> None:
    """Validate a parsed policy input: duplicate detection + connection existence.

    - Duplicate `connection_id` in the body -> sanitized 422.
    - Unknown `connection_id` (not in `source_database_connections`) ->
      sanitized 404. The bad uuid is never echoed.
    """
    seen: set[uuid.UUID] = set()
    for conn_uuid in parsed_conn_ids:
        if conn_uuid in seen:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "message_key": "error.validation.duplicateConnectionPolicy",
                },
            )
        seen.add(conn_uuid)

    if not seen:
        return

    result = await db.execute(select(SourceDatabaseConnection.id).where(SourceDatabaseConnection.id.in_(seen)))
    existing = {row for row in result.scalars().all()}
    missing = seen - existing
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message_key": "error.notFound.connection"},
        )


def _row_filter_validation_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error": "filter_validation_failed",
            "message_key": "error.filterValidationFailed",
        },
    )


async def _validate_policy_row_filters(
    db: AsyncSession,
    policies,
    parsed_conn_ids: list[uuid.UUID],
) -> None:
    """Validate every configured row filter against its connection schema."""
    connection_repo = ConnectionRepository(db)
    for policy, connection_id in zip(policies, parsed_conn_ids, strict=True):
        if not policy.row_filters:
            continue

        connection = await connection_repo.get_by_id(connection_id)
        if connection is None:
            raise _row_filter_validation_error()
        schema_entries = await connection_repo.get_schema_entries(connection_id)
        schema = _build_schema_from_entries(schema_entries)
        dialect = _resolve_dialect(connection.database_type)

        _validate_preview_row_filters(policy.row_filters, schema, dialect)


def _validate_preview_row_filters(
    row_filters: list[dict],
    schema: SchemaContext,
    dialect: str,
) -> None:
    for row_filter in row_filters:
        table_name = row_filter.get("table")
        filter_sql = row_filter.get("filter")
        if not isinstance(table_name, str) or not isinstance(filter_sql, str):
            raise _row_filter_validation_error()
        try:
            PolicyEnforcementService.validate_row_filter(
                filter_sql,
                schema,
                table_name,
                dialect=dialect,
            )
        except ValueError:
            raise _row_filter_validation_error() from None


async def _sync_role_connection_policies(
    db: AsyncSession,
    role_id: uuid.UUID,
    policies: list[ConnectionPolicyItem],
) -> tuple[list[dict], bool]:
    """Apply an empty/unchanged/added/updated/removed policy set without committing."""
    parsed_conn_ids = _parse_policy_connection_ids(policies)
    await _validate_policy_input(db, parsed_conn_ids)
    await _validate_policy_row_filters(db, policies, parsed_conn_ids)

    current_rows = await _role_connection_policy_rows(db, role_id)
    current_by_connection = {row.connection_id: row for row in current_rows}
    requested_connections = set(parsed_conn_ids)
    removed = await _remove_obsolete_connection_policies(db, current_rows, requested_connections)
    updated = _apply_requested_connection_policies(
        db,
        role_id,
        current_by_connection,
        list(zip(policies, parsed_conn_ids, strict=True)),
    )
    changed = removed or updated

    if changed:
        await db.flush()
    return await _role_connection_policy_responses(db, role_id), changed


async def _remove_obsolete_connection_policies(
    db: AsyncSession,
    current_rows: list[RoleConnectionPolicy],
    requested_connections: set[uuid.UUID],
) -> bool:
    removed = False
    for current_row in current_rows:
        if current_row.connection_id not in requested_connections:
            await db.delete(current_row)
            removed = True
    return removed


def _apply_requested_connection_policies(
    db: AsyncSession,
    role_id: uuid.UUID,
    current_by_connection: dict[uuid.UUID, RoleConnectionPolicy],
    requested_policies: list[tuple[ConnectionPolicyItem, uuid.UUID]],
) -> bool:
    changed = False
    for policy, connection_id in requested_policies:
        values = _connection_policy_values(policy)
        current_row = current_by_connection.get(connection_id)
        if current_row is None:
            db.add(_new_connection_policy(role_id, connection_id, values))
            changed = True
        elif _connection_policy_values_changed(current_row, values):
            _apply_connection_policy_values(current_row, values)
            changed = True
    return changed


def _connection_policy_values(
    policy: ConnectionPolicyItem | RoleConnectionPolicy,
) -> _ConnectionPolicyValues:
    return _ConnectionPolicyValues(
        allowed_tables=policy.allowed_tables or [],
        row_filters=policy.row_filters or [],
        column_masks=policy.column_masks or [],
    )


def _new_connection_policy(
    role_id: uuid.UUID,
    connection_id: uuid.UUID,
    values: _ConnectionPolicyValues,
) -> RoleConnectionPolicy:
    return RoleConnectionPolicy(
        role_id=role_id,
        connection_id=connection_id,
        allowed_tables=values.allowed_tables,
        row_filters=values.row_filters,
        column_masks=values.column_masks,
    )


def _connection_policy_values_changed(
    current: RoleConnectionPolicy,
    requested: _ConnectionPolicyValues,
) -> bool:
    return (
        current.allowed_tables != requested.allowed_tables
        or current.row_filters != requested.row_filters
        or current.column_masks != requested.column_masks
    )


def _apply_connection_policy_values(
    current: RoleConnectionPolicy,
    requested: _ConnectionPolicyValues,
) -> None:
    current.allowed_tables = requested.allowed_tables
    current.row_filters = requested.row_filters
    current.column_masks = requested.column_masks


async def _role_connection_policy_rows(db: AsyncSession, role_id: uuid.UUID) -> list[RoleConnectionPolicy]:
    result = await db.execute(
        select(RoleConnectionPolicy)
        .where(RoleConnectionPolicy.role_id == role_id)
        .order_by(RoleConnectionPolicy.created_at, RoleConnectionPolicy.id)
    )
    return list(result.scalars().all())


async def _role_connection_policy_responses(db: AsyncSession, role_id: uuid.UUID) -> list[dict]:
    """Return authoritative persisted policies for one role."""

    rows = await _role_connection_policy_rows(db, role_id)
    return [
        {
            "id": str(cp.id),
            "connection_id": str(cp.connection_id),
            "allowed_tables": cp.allowed_tables or [],
            "row_filters": cp.row_filters or [],
            "column_masks": cp.column_masks or [],
        }
        for cp in rows
    ]


async def _audit_role_update(
    db: AsyncSession,
    role_id: uuid.UUID,
    actor_identity: str | None,
    updated_fields: list[str],
) -> None:
    await AuditService.log(
        db,
        action=AuditActionType.ROLE_UPDATE,
        actor_identity=actor_identity,
        resource_type="role",
        resource_id=str(role_id),
        outcome="success",
        context={"updated_fields": updated_fields},
    )


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


@router.post("/test-policy")
async def test_draft_role_policy(
    request: Request,
    body: DraftPolicyTestRequest,
    _session: dict = Depends(require_permission(Permission.ADMIN_ROLES_MANAGE)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PolicyTestResponse:
    """Validate and evaluate one supplied policy without persistence or execution."""
    connection_id = _parse_preview_connection_id(body.connection_policy.connection_id)
    try:
        connection, schema = await _load_preview_connection(request, connection_id, db)
        draft = body.connection_policy
        policy = _PreviewPolicy(
            allowed_tables=[entry.model_dump() for entry in draft.allowed_tables],
            row_filters=[entry.model_dump() for entry in draft.row_filters],
            column_masks=[entry.model_dump() for entry in draft.column_masks],
        )
        dialect = _resolve_dialect(connection.database_type)
        _validate_preview_row_filters(policy.row_filters, schema, dialect)
        return await _evaluate_policy_preview(schema, policy, body.sample_sql, dialect)
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

        # role.id is set by repo.create's internal flush. All response
        # preparation remains inside the transaction so a flush/refresh fault
        # cannot produce a declared 500 after the mutation has committed.
        persisted_policies, _policy_changed = await _sync_role_connection_policies(
            db,
            role.id,
            body.connection_policies,
        )
        persisted_mappings = await _create_role_group_mappings(
            db,
            role.id,
            body.group_mappings,
            session.get("username"),
        )

        await db.flush()
        await db.refresh(role)
        response_body = _role_to_detail_response(role, persisted_mappings, persisted_policies)
        await db.commit()

        return response_body
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
        update_outcome = await service.update_role(
            role_id=role_uuid,
            fields=fields,
            actor_identity=session.get("username"),
            db_session=None,
        )
        role = update_outcome.role
        changed_role_fields = list(update_outcome.updated_fields)

        if body.connection_policies is None:
            persisted_policies = await _role_connection_policy_responses(db, role.id)
            policy_changed = False
        else:
            persisted_policies, policy_changed = await _sync_role_connection_policies(
                db,
                role.id,
                body.connection_policies,
            )
        updated_fields = [*changed_role_fields]
        if policy_changed:
            updated_fields.append("connection_policies")
        if updated_fields:
            await _audit_role_update(db, role.id, session.get("username"), updated_fields)

        if body.group_mappings is None:
            mapping_rows = await _role_group_mapping_rows(db, role.id)
            persisted_mappings = [
                _group_mapping_summary(mapping.id, mapping.sso_group_value) for mapping in mapping_rows
            ]
        else:
            persisted_mappings = await _sync_role_group_mappings(
                db,
                role.id,
                body.group_mappings,
                session.get("username"),
            )

        await db.flush()
        await db.refresh(role)
        response_body = _role_to_detail_response(role, persisted_mappings, persisted_policies)
        await db.commit()

        return response_body
    except BuiltinProtectedError as exc:
        try:
            await AuditService.log(
                db,
                action=AuditActionType.ACCESS_DENIED,
                actor_identity=session.get("username"),
                resource_type="role",
                resource_id=role_id,
                outcome="denied",
                context={"reason": "builtin_protected"},
            )
            await db.commit()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "internal", "message_key": "error.internal"},
            ) from None
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


def _resolve_dialect(database_type) -> str:
    """Map a ``DatabaseType`` (or any value) to a sqlglot read dialect.

    Uses the canonical ``DIALECT_MAP`` from ``app.evaluator.rules.read_only``
    (T-429 / FR-071) so PostgreSQL / MySQL / MSSQL get the dialect they
    actually need. Falls back to ``"postgres"`` (the conservative
    default used by ``read_only`` and ``role_authorization``) when the
    value is missing, ``None``, an unexpected type, or an unknown enum
    member. The fallback is never surfaced to the client — the endpoint
    uses the dialect only inside the role-auth rule, which already
    returns the constant ``"query_blocked_policy"`` for every parse
    failure (no dialect name is ever echoed in the response).
    """
    try:
        return DIALECT_MAP[database_type]
    except (KeyError, TypeError):
        return "postgres"


async def _evaluate_policy_preview(
    schema: SchemaContext,
    policy: _PreviewPolicy,
    sample_sql: str | None,
    dialect: str,
) -> PolicyTestResponse:
    accessible_tables, accessible_columns, blocked_tables = _policy_access_summary(schema, policy)
    would_be_allowed, message_key = await _preview_verdict(schema, policy, sample_sql, dialect)
    return PolicyTestResponse(
        accessible_tables=accessible_tables,
        accessible_columns=accessible_columns,
        blocked_tables=blocked_tables,
        applicable_row_filters=[
            {"table": row_filter.get("table"), "filter": row_filter.get("filter")}
            for row_filter in policy.row_filters
            if isinstance(row_filter, dict)
        ],
        masked_columns=_preview_masks(policy.column_masks),
        would_be_allowed=would_be_allowed,
        message_key=message_key,
    )


def _policy_access_summary(
    schema: SchemaContext,
    policy: _PreviewPolicy,
) -> tuple[list[str], dict[str, list[str]], list[str]]:
    filtered_schema = PolicyEnforcementService.filter_schema(schema, policy.allowed_tables)
    accessible_tables = [table.name for table in filtered_schema.tables]
    accessible_columns = {table.name: [column.name for column in table.columns] for table in filtered_schema.tables}
    blocked_tables = [table.name for table in schema.tables if table.name not in accessible_tables]
    return accessible_tables, accessible_columns, blocked_tables


def _preview_masks(column_masks: list[dict]) -> dict[str, list[str]]:
    return {
        mask["table"]: [column for column in mask["columns"] if isinstance(column, str)]
        for mask in column_masks
        if isinstance(mask, dict) and isinstance(mask.get("table"), str) and isinstance(mask.get("columns"), list)
    }


async def _preview_verdict(
    schema: SchemaContext,
    policy: _PreviewPolicy,
    sample_sql: str | None,
    dialect: str,
) -> tuple[bool, str | None]:
    if not sample_sql or not sample_sql.strip():
        return bool(PolicyEnforcementService.filter_schema(schema, policy.allowed_tables).tables), None
    rule = RoleAuthorizationRule(
        allowed_tables=policy.allowed_tables or None,
        column_masks=policy.column_masks or None,
        dialect=dialect,
    )
    allowed, _reason = await rule.evaluate(sample_sql, schema)
    return bool(allowed), None if allowed else "error.queryBlockedPolicy"


def _parse_preview_connection_id(connection_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(connection_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "connection_not_found", "message_key": "error.connection_not_found"},
        ) from None


async def _load_preview_connection(
    request: Request,
    connection_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[SourceDatabaseConnection, SchemaContext]:
    db_override = getattr(request.state, "db_override", None)
    db_to_use = db_override if db_override is not None else db
    repo_override = getattr(request.state, "connection_repo_override", None)
    repo = repo_override if repo_override is not None else ConnectionRepository(db_to_use)
    connection = await repo.get_by_id(connection_id)
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "connection_not_found", "message_key": "error.connection_not_found"},
        )
    state_error = _policy_test_connection_state_error(
        connection.lifecycle_state,
        connection.health_status,
        connection.schema_introspection_status,
    )
    if state_error is not None:
        raise state_error
    schema_entries = await repo.get_schema_entries(connection.id)
    return connection, _build_schema_from_entries(schema_entries)


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

    conn_uuid = _parse_preview_connection_id(body.connection_id)

    # Test seam: tests may inject mock repos on request.state. In
    # production the attributes are absent and the real db / repos
    # are used.
    role_repo_override = getattr(request.state, "role_repo_override", None)
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

        conn, schema_context = await _load_preview_connection(request, conn_uuid, db)

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

        policy = _PreviewPolicy(
            allowed_tables=allowed_tables,
            row_filters=row_filters_list,
            column_masks=column_masks_list,
        )
        return await _evaluate_policy_preview(
            schema_context,
            policy,
            body.sample_sql,
            _resolve_dialect(getattr(conn, "database_type", None)),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal", "message_key": "error.internal"},
        ) from None
