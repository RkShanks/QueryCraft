"""RED unit tests for DetectionConfigRepository (T-838).

Contract tested:
- get() returns singleton row (creates with defaults block=0.8 / flag=0.5 if missing)
- update() changes block_confidence and flag_confidence
- update() validates block > flag (raises ValueError otherwise)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import MultipleResultsFound


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
        missing_result = MagicMock()
        missing_result.scalar_one_or_none.return_value = None
        inserted = _make_threshold_row()
        inserted_result = MagicMock()
        inserted_result.scalar_one_or_none.return_value = inserted
        session.execute.side_effect = [missing_result, MagicMock(), inserted_result]

        repo = DetectionConfigRepository(session)
        row = await repo.get()

        assert row is inserted
        assert row.block_confidence == pytest.approx(0.8)
        assert row.flag_confidence == pytest.approx(0.5)
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_returns_created_row(self):
        from app.repositories.detection_config_repository import DetectionConfigRepository

        session = _make_session()
        missing_result = MagicMock()
        missing_result.scalar_one_or_none.return_value = None
        inserted = _make_threshold_row()
        inserted_result = MagicMock()
        inserted_result.scalar_one_or_none.return_value = inserted
        session.execute.side_effect = [missing_result, MagicMock(), inserted_result]

        repo = DetectionConfigRepository(session)
        row = await repo.get()

        # Returned value should be the newly created instance
        assert row is inserted
        assert row.block_confidence == pytest.approx(0.8)
        assert row.flag_confidence == pytest.approx(0.5)


class TestDetectionConfigRepositoryForDetection:
    """Runtime detection reads require one finite, ordered singleton."""

    @pytest.mark.asyncio
    async def test_missing_runtime_config_fails_closed(self):
        from app.core.exceptions import DetectionUnavailableError
        from app.repositories.detection_config_repository import DetectionConfigRepository

        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        with pytest.raises(DetectionUnavailableError):
            await DetectionConfigRepository(session).get_for_detection()

        session.add.assert_not_called()
        session.flush.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("block", "flag"),
        [
            (float("nan"), 0.5),
            (0.8, float("nan")),
            (float("inf"), 0.5),
            (0.8, float("-inf")),
            (0.5, 0.5),
            (0.4, 0.5),
            (1.1, 0.5),
            (0.8, -0.1),
        ],
    )
    async def test_broken_runtime_config_fails_closed(self, block: float, flag: float):
        from app.core.exceptions import DetectionUnavailableError
        from app.repositories.detection_config_repository import DetectionConfigRepository

        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = _make_threshold_row(block=block, flag=flag)
        session.execute.return_value = result_mock

        with pytest.raises(DetectionUnavailableError):
            await DetectionConfigRepository(session).get_for_detection()

    @pytest.mark.asyncio
    async def test_multiple_runtime_configs_fail_closed(self):
        from app.core.exceptions import DetectionUnavailableError
        from app.repositories.detection_config_repository import DetectionConfigRepository

        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.side_effect = MultipleResultsFound()
        session.execute.return_value = result_mock

        with pytest.raises(DetectionUnavailableError):
            await DetectionConfigRepository(session).get_for_detection()


class TestDetectionConfigRepositoryUpdate:
    """update() changes values and validates block > flag."""

    @pytest.mark.asyncio
    async def test_update_changes_block_and_flag_confidence(self):
        from app.repositories.detection_config_repository import DetectionConfigRepository
        from app.schemas.detection import DetectionThresholdUpdate

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
        from app.core.exceptions import DetectionUnavailableError
        from app.repositories.detection_config_repository import DetectionConfigRepository
        from app.schemas.detection import DetectionThresholdUpdate

        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        repo = DetectionConfigRepository(session)
        data = DetectionThresholdUpdate(block_confidence=0.85, flag_confidence=0.45)
        with pytest.raises(DetectionUnavailableError):
            await repo.update(data)

        session.add.assert_not_called()
        session.flush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_calls_flush(self):
        from app.repositories.detection_config_repository import DetectionConfigRepository
        from app.schemas.detection import DetectionThresholdUpdate

        existing = _make_threshold_row()
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        session.execute.return_value = result_mock

        repo = DetectionConfigRepository(session)
        data = DetectionThresholdUpdate(block_confidence=0.9, flag_confidence=0.4)
        await repo.update(data)

        session.flush.assert_called()
