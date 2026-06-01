"""RoleRepository — data access for roles table."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BuiltinProtectedError
from app.db.models.role import Role


class RoleRepository:
    """Repository for role CRUD with built-in protection."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_all(self) -> list[Role]:
        """Fetch all roles ordered by priority."""
        result = await self._session.execute(select(Role).order_by(Role.priority))
        return result.scalars().all()

    async def get_by_id(self, role_id: uuid.UUID) -> Role | None:
        """Fetch a role by primary key UUID."""
        result = await self._session.execute(select(Role).where(Role.id == role_id))
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Role | None:
        """Fetch a role by exact name match."""
        result = await self._session.execute(select(Role).where(Role.name == name))
        return result.scalar_one_or_none()

    async def get_by_priority(self, priority: int) -> Role | None:
        """Fetch a role by exact priority match."""
        result = await self._session.execute(select(Role).where(Role.priority == priority))
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> Role:
        """Create a new role and flush to generate defaults."""
        role = Role(**kwargs)
        self._session.add(role)
        await self._session.flush()
        return role

    async def delete(self, role_id: uuid.UUID) -> bool:
        """Delete a role by ID.

        Raises:
            BuiltinProtectedError: if the role has is_builtin=true.
        """
        result = await self._session.execute(select(Role).where(Role.id == role_id))
        role = result.scalar_one_or_none()
        if role is None:
            return False
        if getattr(role, "is_builtin", False):
            raise BuiltinProtectedError(resource_type="role", resource_id=str(role_id))
        await self._session.delete(role)
        await self._session.flush()
        return True

    async def update(self, role_id: uuid.UUID, fields: dict) -> Role | None:
        """Update a role by ID.

        Core properties (name, permissions, is_builtin, priority) of built-in roles
        are protected. Description updates are allowed.

        Raises:
            BuiltinProtectedError: if attempting to modify protected fields
                                   on a built-in role.
        """
        result = await self._session.execute(select(Role).where(Role.id == role_id))
        role = result.scalar_one_or_none()
        if role is None:
            return None

        if getattr(role, "is_builtin", False):
            # Core properties that cannot be modified on built-in roles
            protected_fields = {"name", "permissions", "is_builtin", "priority"}
            attempted_protected = protected_fields.intersection(fields.keys())
            if attempted_protected:
                raise BuiltinProtectedError(
                    resource_type="role",
                    resource_id=str(role_id),
                )

        for key, value in fields.items():
            if hasattr(role, key):
                setattr(role, key, value)

        await self._session.flush()
        return role
