"""Query-pipeline fail-closed regressions for hostile-input detection."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.services.query_service import QueryService
from tests.lifecycle.helpers import FakeRedis


def _service_with_spies(db_session: AsyncMock, redis: FakeRedis) -> tuple[QueryService, dict[str, AsyncMock]]:
    spies = {
        "history": AsyncMock(),
        "sessions": AsyncMock(),
        "llm": AsyncMock(),
        "evaluator": AsyncMock(),
        "executor": AsyncMock(),
        "quota": AsyncMock(),
    }
    service = QueryService(
        accepted_query_repository=spies["history"],
        session_repository=spies["sessions"],
        db_session=db_session,
        redis=redis,
        llm=spies["llm"],
        evaluator=spies["evaluator"],
        source_db_executor=spies["executor"],
        quota_service=spies["quota"],
    )
    return service, spies


def _user_result(user_id: uuid.UUID) -> MagicMock:
    return MagicMock(
        scalar_one_or_none=MagicMock(
            return_value=MagicMock(
                id=user_id,
                role_id=uuid.uuid4(),
                username="detection-test-user",
            )
        )
    )


def _missing_config_result() -> MagicMock:
    return MagicMock(scalar_one_or_none=MagicMock(return_value=None))


def _assert_no_downstream_side_effects(spies: dict[str, AsyncMock], redis: FakeRedis) -> None:
    spies["quota"].check_and_increment.assert_not_awaited()
    spies["sessions"].create.assert_not_awaited()
    spies["sessions"].get_by_id.assert_not_awaited()
    spies["history"].create.assert_not_awaited()
    spies["llm"].generate_sql.assert_not_awaited()
    spies["evaluator"].evaluate.assert_not_awaited()
    spies["executor"].execute.assert_not_awaited()
    assert not any(key.startswith(("attempt:", "active_attempt:")) for key in redis._data)


@pytest.mark.asyncio
async def test_missing_detection_config_returns_sanitized_503_before_downstream_work():
    user_id = uuid.uuid4()
    db_session = AsyncMock()
    db_session.execute = AsyncMock(side_effect=[_user_result(user_id), _missing_config_result()])
    redis = FakeRedis()
    service, spies = _service_with_spies(db_session, redis)

    with pytest.raises(HTTPException) as exc_info:
        await service.submit_question(
            http_session_id="missing-config",
            user_id=str(user_id),
            question="ordinary request",
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == {
        "error": "service_unavailable",
        "message_key": "error.service_unavailable",
    }
    _assert_no_downstream_side_effects(spies, redis)


@pytest.mark.asyncio
async def test_rule_failure_returns_sanitized_503_before_downstream_work(monkeypatch):
    from app.core.exceptions import DetectionUnavailableError

    user_id = uuid.uuid4()
    thresholds = MagicMock(block_confidence=0.8, flag_confidence=0.5)
    db_session = AsyncMock()
    db_session.execute = AsyncMock(
        side_effect=[
            _user_result(user_id),
            MagicMock(scalar_one_or_none=MagicMock(return_value=thresholds)),
        ]
    )
    redis = FakeRedis()
    service, spies = _service_with_spies(db_session, redis)
    monkeypatch.setattr(
        "app.services.query_service.HostileInputDetector.detect",
        AsyncMock(side_effect=DetectionUnavailableError()),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.submit_question(
            http_session_id="broken-rule",
            user_id=str(user_id),
            question="ordinary request",
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == {
        "error": "service_unavailable",
        "message_key": "error.service_unavailable",
    }
    _assert_no_downstream_side_effects(spies, redis)
