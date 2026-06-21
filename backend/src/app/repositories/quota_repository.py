"""QuotaRepository — data access for role_quotas table."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.role_quota import RoleQuota
from app.schemas.quota import RoleQuotaUpsert


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
