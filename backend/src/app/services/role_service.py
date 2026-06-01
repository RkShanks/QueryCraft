"""RoleService — business logic for role CRUD with validation and audit.

T-673: Role CRUD with validation, built-in role guard, and audit logging.
"""

from __future__ import annotations

import uuid

from app.core.exceptions import BuiltinProtectedError
from app.db.models.enums import AuditActionType, Permission
from app.db.models.role import Role
from app.repositories.role_repository import RoleRepository
from app.services.audit_service import AuditService

_ALLOWED_PERMISSIONS: set[str] = {p.value for p in Permission}


def validate_permissions(permissions: list[str] | None) -> None:
    """Validate permission values against the fixed allowed set.

    Raises:
        ValueError: If any permission is not in the allowed set.
    """
    if permissions is None:
        return
    invalid = [p for p in permissions if p not in _ALLOWED_PERMISSIONS]
    if invalid:
        raise ValueError(f"Invalid permissions: {', '.join(invalid)}")


class RoleService:
    """Business logic for role management."""

    def __init__(self, repository: RoleRepository):
        self._repo = repository

    async def list_roles(self) -> list[Role]:
        """Return all roles ordered by priority."""
        return await self._repo.list_all()

    async def get_role(self, role_id: uuid.UUID) -> Role | None:
        """Fetch a single role by ID."""
        return await self._repo.get_by_id(role_id)

    async def create_role(
        self,
        name: str,
        description: str | None,
        priority: int,
        permissions: list[str] | None,
        actor_identity: str | None = None,
        db_session=None,
    ) -> Role:
        """Create a new role with validation.

        Raises:
            ValueError: duplicate name, duplicate priority, or invalid permissions.
        """
        if await self._repo.get_by_name(name):
            raise ValueError("duplicate_name")
        if await self._repo.get_by_priority(priority):
            raise ValueError("duplicate_priority")
        validate_permissions(permissions)

        role = await self._repo.create(
            name=name,
            description=description,
            priority=priority,
            permissions=permissions or [],
        )

        if db_session is not None:
            await AuditService.log(
                db_session,
                action=AuditActionType.ROLE_CREATE,
                actor_identity=actor_identity,
                resource_type="role",
                resource_id=str(role.id),
                outcome="success",
                context={"name": name, "priority": priority},
            )

        return role

    async def update_role(
        self,
        role_id: uuid.UUID,
        fields: dict,
        actor_identity: str | None = None,
        db_session=None,
    ) -> Role:
        """Update a role with validation and built-in protection.

        Raises:
            BuiltinProtectedError: if modifying core fields of a built-in role.
            ValueError: duplicate name, duplicate priority, or invalid permissions.
        """
        existing = await self._repo.get_by_id(role_id)
        if existing is None:
            raise ValueError("not_found")

        # Built-in protection is handled in repository; re-raise with clear semantics
        if getattr(existing, "is_builtin", False):
            protected_fields = {"name", "permissions", "is_builtin", "priority"}
            attempted_protected = protected_fields.intersection(fields.keys())
            if attempted_protected:
                raise BuiltinProtectedError(resource_type="role", resource_id=str(role_id))

        if "name" in fields and fields["name"] is not None:
            name_conflict = await self._repo.get_by_name(fields["name"])
            if name_conflict is not None and name_conflict.id != role_id:
                raise ValueError("duplicate_name")

        if "priority" in fields and fields["priority"] is not None:
            priority_conflict = await self._repo.get_by_priority(fields["priority"])
            if priority_conflict is not None and priority_conflict.id != role_id:
                raise ValueError("duplicate_priority")

        if "permissions" in fields:
            validate_permissions(fields["permissions"])

        role = await self._repo.update(role_id, fields)
        if role is None:
            raise ValueError("not_found")

        if db_session is not None:
            await AuditService.log(
                db_session,
                action=AuditActionType.ROLE_UPDATE,
                actor_identity=actor_identity,
                resource_type="role",
                resource_id=str(role.id),
                outcome="success",
                context={"updated_fields": list(fields.keys())},
            )

        return role

    async def delete_role(
        self,
        role_id: uuid.UUID,
        actor_identity: str | None = None,
        db_session=None,
    ) -> bool:
        """Delete a role.

        Raises:
            BuiltinProtectedError: if the role is built-in.
            ValueError: if role not found.
        """
        existing = await self._repo.get_by_id(role_id)
        if existing is None:
            raise ValueError("not_found")

        result = await self._repo.delete(role_id)
        if not result:
            raise ValueError("not_found")

        if db_session is not None:
            await AuditService.log(
                db_session,
                action=AuditActionType.ROLE_DELETE,
                actor_identity=actor_identity,
                resource_type="role",
                resource_id=str(role_id),
                outcome="success",
                context={},
            )

        return True
