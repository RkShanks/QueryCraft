"""RED unit tests for DetectionConfigRepository (T-838).

Contract tested:
- get() returns singleton row (creates with defaults block=0.8 / flag=0.5 if missing)
- update() changes block_confidence and flag_confidence
- update() validates block > flag (raises ValueError otherwise)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_session():
    """Build a minimal async SQLAlchemy session mock."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


def _make_threshold_row(block: float = 0.8, flag: float = 0.5):
    """Build a fake DetectionThresholdConfig ORM row."""
    row = MagicMock()
    row.block_confidence = block
    row.flag_confidence = flag
    row.updated_at = __import__("datetime").datetime(2024, 1, 1, tzinfo=__import__("datetime").timezone.utc)
    row.updated_by = None
    return row


class TestDetectionConfigRepositoryGet:
    """get() returns existing row or creates singleton with defaults."""

    @pytest.mark.asyncio
    async def test_get_returns_existing_row(self):
        from app.repositories.detection_config_repository import DetectionConfigRepository

        existing = _make_threshold_row(block=0.9, flag=0.4)
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        session.execute.return_value = result_mock

        repo = DetectionConfigRepository(session)
        row = await repo.get()

        assert row is existing
        assert row.block_confidence == 0.9
        assert row.flag_confidence == 0.4

    @pytest.mark.asyncio
    async def test_get_creates_singleton_with_defaults_when_missing(self):
        from app.repositories.detection_config_repository import DetectionConfigRepository

        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        repo = DetectionConfigRepository(session)
        await repo.get()

        # Should have added a new row
        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert added.block_confidence == pytest.approx(0.8)
        assert added.flag_confidence == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_get_returns_created_row(self):
        from app.repositories.detection_config_repository import DetectionConfigRepository

        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        repo = DetectionConfigRepository(session)
        row = await repo.get()

        # Returned value should be the newly created instance
        assert row is not None
        assert row.block_confidence == pytest.approx(0.8)
        assert row.flag_confidence == pytest.approx(0.5)


class TestDetectionConfigRepositoryUpdate:
    """update() changes values and validates block > flag."""

    @pytest.mark.asyncio
    async def test_update_changes_block_and_flag_confidence(self):
        from app.repositories.detection_config_repository import DetectionConfigRepository

        from app.schemas.detection import DetectionThresholdUpdate  # noqa: I001

        existing = _make_threshold_row(block=0.8, flag=0.5)
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        session.execute.return_value = result_mock

        repo = DetectionConfigRepository(session)
        data = DetectionThresholdUpdate(block_confidence=0.9, flag_confidence=0.4)
        updated = await repo.update(data)

        assert updated.block_confidence == pytest.approx(0.9)
        assert updated.flag_confidence == pytest.approx(0.4)

    @pytest.mark.asyncio
    async def test_update_raises_when_block_less_than_flag(self):
        from pydantic import ValidationError

        from app.schemas.detection import DetectionThresholdUpdate

        with pytest.raises(ValidationError):
            DetectionThresholdUpdate(block_confidence=0.4, flag_confidence=0.8)

    @pytest.mark.asyncio
    async def test_update_raises_when_block_equal_to_flag(self):
        from pydantic import ValidationError

        from app.schemas.detection import DetectionThresholdUpdate

        with pytest.raises(ValidationError):
            DetectionThresholdUpdate(block_confidence=0.5, flag_confidence=0.5)

    @pytest.mark.asyncio
    async def test_update_creates_row_if_missing_then_sets_values(self):
        from app.repositories.detection_config_repository import DetectionConfigRepository

        from app.schemas.detection import DetectionThresholdUpdate  # noqa: I001

        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        repo = DetectionConfigRepository(session)
        data = DetectionThresholdUpdate(block_confidence=0.85, flag_confidence=0.45)
        updated = await repo.update(data)

        assert updated.block_confidence == pytest.approx(0.85)
        assert updated.flag_confidence == pytest.approx(0.45)

    @pytest.mark.asyncio
    async def test_update_calls_flush(self):
        from app.repositories.detection_config_repository import DetectionConfigRepository

        from app.schemas.detection import DetectionThresholdUpdate  # noqa: I001

        existing = _make_threshold_row()
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        session.execute.return_value = result_mock

        repo = DetectionConfigRepository(session)
        data = DetectionThresholdUpdate(block_confidence=0.9, flag_confidence=0.4)
        await repo.update(data)

        session.flush.assert_called()
