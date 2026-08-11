"""DetectionConfigRepository — singleton get/update for detection threshold config (T-839)."""

from __future__ import annotations

from datetime import UTC, datetime
from math import isfinite

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DetectionUnavailableError
from app.db.models.detection_config import DetectionThresholdConfig
from app.schemas.detection import DetectionThresholdUpdate

# Default thresholds for singleton creation
_DEFAULT_BLOCK = 0.8
_DEFAULT_FLAG = 0.5


class DetectionConfigRepository:
    """Repository for the singleton DetectionThresholdConfig row.

    There is exactly one row in the detection_threshold_config table.
    ``get()`` creates it with defaults if the table is empty.
    ``update()`` requires one valid existing row before persisting.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self) -> DetectionThresholdConfig:
        """Return the singleton, initializing an empty table atomically."""
        row = await self._valid_singleton_or_none()
        if row is not None:
            return row
        statement = (
            insert(DetectionThresholdConfig)
            .values(
                block_confidence=_DEFAULT_BLOCK,
                flag_confidence=_DEFAULT_FLAG,
                updated_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing()
        )
        await self._session.execute(statement)
        row = await self._valid_singleton_or_none()
        if row is None:
            raise DetectionUnavailableError()
        return row

    async def _valid_singleton_or_none(self) -> DetectionThresholdConfig | None:
        result = await self._session.execute(select(DetectionThresholdConfig))
        try:
            row = result.scalar_one_or_none()
        except MultipleResultsFound:
            raise DetectionUnavailableError() from None
        if row is not None and not self._has_valid_thresholds(row):
            raise DetectionUnavailableError()
        return row

    async def get_for_detection(self) -> DetectionThresholdConfig:
        """Return one valid runtime config or fail closed.

        The query path never repairs missing or corrupt security configuration
        as a side effect of processing user input.
        """
        row = await self._valid_singleton_or_none()
        if row is None:
            raise DetectionUnavailableError()
        return row

    async def get_for_admin(self) -> DetectionThresholdConfig:
        """Return one valid administrative config without repairing state."""
        row = await self._valid_singleton_or_none()
        if row is None:
            raise DetectionUnavailableError()
        return row

    @staticmethod
    def _has_valid_thresholds(row: DetectionThresholdConfig) -> bool:
        block = row.block_confidence
        flag = row.flag_confidence
        values_are_finite_numbers = all(
            isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)
            for value in (block, flag)
        )
        return values_are_finite_numbers and 0.0 <= flag < block <= 1.0

    async def update(self, data: DetectionThresholdUpdate) -> DetectionThresholdConfig:
        """Update block/flag confidence on the singleton row.

        ``data`` is already validated by Pydantic (block > flag).
        Missing or corrupt singleton state fails closed without mutation.
        """
        row = await self.get_for_admin()
        row.block_confidence = data.block_confidence
        row.flag_confidence = data.flag_confidence
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        return row
