"""QuotaRepository — data access for role_quotas table."""

import uuid
from collections.abc import AsyncIterator

from sqlalchemy import and_, asc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.core.pagination import decode_cursor, encode_cursor
from app.db.models.role import Role
from app.db.models.role_quota import RoleQuota
from app.db.models.user import User
from app.schemas.quota import RoleQuotaUpsert

_QUOTA_STATUS_CURSOR_NAMESPACE = "quota_status"


class QuotaRepository:
    """Repository for role quota CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, role_id: uuid.UUID) -> RoleQuota | None:
        result = await self._session.execute(select(RoleQuota).where(RoleQuota.role_id == role_id))
        return result.scalar_one_or_none()

    async def upsert(self, role_id: uuid.UUID, data: RoleQuotaUpsert, fields_set: set[str] | None = None) -> RoleQuota:
        existing = await self.get(role_id)
        if existing is not None:
            update_fields = fields_set if fields_set is not None else data.model_fields_set
            if "daily_query_limit" in update_fields:
                existing.daily_query_limit = data.daily_query_limit
            if "daily_execution_limit" in update_fields:
                existing.daily_execution_limit = data.daily_execution_limit
            if "daily_export_limit" in update_fields:
                existing.daily_export_limit = data.daily_export_limit
            from datetime import UTC, datetime

            existing.updated_at = datetime.now(UTC)
            await self._session.flush()
            return existing

        quota = RoleQuota(
            role_id=role_id,
            daily_query_limit=data.daily_query_limit,
            daily_execution_limit=data.daily_execution_limit,
            daily_export_limit=data.daily_export_limit,
        )
        self._session.add(quota)
        await self._session.flush()
        return quota

    async def delete(self, role_id: uuid.UUID) -> bool:
        result = await self._session.execute(select(RoleQuota).where(RoleQuota.role_id == role_id))
        quota = result.scalar_one_or_none()
        if quota is None:
            return False
        await self._session.delete(quota)
        await self._session.flush()
        return True

    async def list_all(self) -> list[RoleQuota]:
        result = await self._session.execute(select(RoleQuota))
        return list(result.scalars().all())

    async def status_page(
        self,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[RoleQuota], str | None]:
        """Return one quota-status page in stable role-name order."""
        statement = (
            select(RoleQuota)
            .join(Role, Role.id == RoleQuota.role_id)
            .options(contains_eager(RoleQuota.role))
            .order_by(asc(Role.name), asc(Role.id))
            .limit(limit + 1)
        )
        if cursor is not None:
            position = decode_cursor(cursor, _QUOTA_STATUS_CURSOR_NAMESPACE)
            statement = statement.where(
                or_(Role.name > position.sort_value, and_(Role.name == position.sort_value, Role.id > position.item_id))
            )

        rows = list((await self._session.execute(statement)).scalars().all())
        if len(rows) <= limit:
            return rows, None
        page = rows[:limit]
        last = page[-1]
        return page, encode_cursor(_QUOTA_STATUS_CURSOR_NAMESPACE, last.role.name, last.role_id)

    async def count_status_roles(self) -> int:
        """Return the exact number of configured quota roles."""
        statement = select(func.count()).select_from(RoleQuota)
        return int((await self._session.execute(statement)).scalar_one())

    async def user_id_batches(
        self,
        role_ids: set[uuid.UUID],
        batch_size: int = 500,
    ) -> AsyncIterator[list[tuple[uuid.UUID, uuid.UUID]]]:
        """Keyset user IDs for the current role page in bounded batches."""
        if not role_ids:
            return
        last_position: tuple[uuid.UUID, uuid.UUID] | None = None
        while True:
            statement = select(User.role_id, User.id).where(User.role_id.in_(role_ids))
            if last_position:
                last_role_id, last_user_id = last_position
                statement = statement.where(
                    or_(User.role_id > last_role_id, and_(User.role_id == last_role_id, User.id > last_user_id))
                )
            statement = statement.order_by(asc(User.role_id), asc(User.id)).limit(batch_size)
            rows = [(row.role_id, row.id) for row in (await self._session.execute(statement)).all()]
            if not rows:
                return
            yield rows
            if len(rows) < batch_size:
                return
            last_position = rows[-1]
