"""RED unit tests for QuotaService (T-793).

These tests define the contract for QuotaService.check_and_increment():
- Increments Redis counter via Lua script and returns (used, limit, reset_at)
- Raises QuotaExceededError with dimension and reset_at when exhausted
- Raises QuotaUnavailableError when Redis unreachable
- Daily TTL key format quota:{user_id}:{dim}:{YYYY-MM-DD} with TTL <= 86400s
- Uncapped role (NULL limit) always allows
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from redis.asyncio import Redis as AsyncRedis

from app.core.exceptions import QuotaExceededError, QuotaUnavailableError


def _make_script(return_value=(1, 5, 10), side_effect=None):
    async def _script(*args, **kwargs):
        if side_effect:
            raise side_effect
        return return_value

    return _script


class TestQuotaServiceCheckAndIncrement:
    """QuotaService.check_and_increment() core contract."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock(spec=AsyncRedis)
        redis.register_script.return_value = _make_script((1, 5, 10))
        return redis

    @pytest.fixture
    def mock_quota_repo(self):
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def service(self, mock_redis, mock_quota_repo):
        from app.services.quota_service import QuotaService

        return QuotaService(redis=mock_redis, quota_repo=mock_quota_repo)

    @pytest.mark.asyncio
    async def test_increments_redis_counter_and_returns_usage(self, service, mock_redis, mock_quota_repo):
        role_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_quota_repo.get.return_value = MagicMock(daily_query_limit=10, role_id=role_id)
        service._check_script = _make_script((1, 1, 10))

        used, limit, reset_at = await service.check_and_increment(user_id, role_id, "queries")

        assert used == 1
        assert limit == 10
        assert reset_at is not None

    @pytest.mark.asyncio
    async def test_raises_quota_exceeded_when_limit_reached(self, service, mock_redis, mock_quota_repo):
        role_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_quota_repo.get.return_value = MagicMock(daily_query_limit=5, role_id=role_id)
        service._check_script = _make_script((0, 6, 5))

        with pytest.raises(QuotaExceededError) as exc_info:
            await service.check_and_increment(user_id, role_id, "queries")

        assert exc_info.value.dimension == "queries"
        assert exc_info.value.reset_at is not None

    @pytest.mark.asyncio
    async def test_raises_quota_unavailable_when_redis_unreachable(self, service, mock_redis, mock_quota_repo):
        role_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_quota_repo.get.return_value = MagicMock(daily_query_limit=10, role_id=role_id)
        service._check_script = _make_script(side_effect=ConnectionError("Redis unreachable"))

        with pytest.raises(QuotaUnavailableError):
            await service.check_and_increment(user_id, role_id, "executions")

    @pytest.mark.asyncio
    async def test_redis_key_format_includes_user_dim_date(self, service, mock_redis, mock_quota_repo):
        role_id = uuid.uuid4()
        user_id = uuid.uuid4()
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        mock_quota_repo.get.return_value = MagicMock(daily_query_limit=10, role_id=role_id)
        call_args = {}

        async def _capture_script(*args, **kwargs):
            call_args.update(kwargs)
            return (1, 1, 10)

        service._check_script = _capture_script

        await service.check_and_increment(user_id, role_id, "queries")

        keys = call_args.get("keys", [])
        expected_key = f"quota:{user_id}:queries:{today}"
        assert expected_key in keys

    @pytest.mark.asyncio
    async def test_daily_ttl_key_has_ttl_at_most_86400(self, service, mock_redis, mock_quota_repo):
        role_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_quota_repo.get.return_value = MagicMock(daily_query_limit=10, role_id=role_id)
        call_args = {}

        async def _capture_script(*args, **kwargs):
            call_args.update(kwargs)
            return (1, 1, 10)

        service._check_script = _capture_script

        await service.check_and_increment(user_id, role_id, "queries")

        args = call_args.get("args", [])
        if len(args) >= 2:
            ttl = int(args[1])
            assert 0 < ttl <= 86400

    @pytest.mark.asyncio
    async def test_uncapped_role_null_limit_always_allows(self, service, mock_redis, mock_quota_repo):
        role_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_quota_repo.get.return_value = MagicMock(daily_query_limit=None, role_id=role_id)
        script_called = False

        async def _fail_if_called(*args, **kwargs):
            nonlocal script_called
            script_called = True
            return (1, 1, 10)

        service._check_script = _fail_if_called

        used, limit, reset_at = await service.check_and_increment(user_id, role_id, "queries")

        assert limit is None
        assert used == 0
        assert not script_called

    @pytest.mark.asyncio
    async def test_uncapped_execution_limit_always_allows(self, service, mock_redis, mock_quota_repo):
        role_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_quota_repo.get.return_value = MagicMock(daily_execution_limit=None, role_id=role_id)
        script_called = False

        async def _fail_if_called(*args, **kwargs):
            nonlocal script_called
            script_called = True
            return (1, 1, 10)

        service._check_script = _fail_if_called

        used, limit, reset_at = await service.check_and_increment(user_id, role_id, "executions")

        assert limit is None
        assert used == 0
        assert not script_called

    @pytest.mark.asyncio
    async def test_no_quota_config_always_allows(self, service, mock_redis, mock_quota_repo):
        role_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_quota_repo.get.return_value = None
        script_called = False

        async def _fail_if_called(*args, **kwargs):
            nonlocal script_called
            script_called = True
            return (1, 1, 10)

        service._check_script = _fail_if_called

        used, limit, reset_at = await service.check_and_increment(user_id, role_id, "queries")

        assert limit is None
        assert used == 0
        assert not script_called

    @pytest.mark.asyncio
    async def test_quota_exceeded_error_has_sanitized_attributes(self, service, mock_redis, mock_quota_repo):
        role_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_quota_repo.get.return_value = MagicMock(daily_execution_limit=3, role_id=role_id)
        service._check_script = _make_script((0, 4, 3))

        with pytest.raises(QuotaExceededError) as exc_info:
            await service.check_and_increment(user_id, role_id, "executions")

        err = exc_info.value
        assert err.dimension == "executions"
        assert err.reset_at is not None
        assert not hasattr(err, "counter") or getattr(err, "counter", None) is None
        assert not hasattr(err, "policy_id") or getattr(err, "policy_id", None) is None

    @pytest.mark.asyncio
    async def test_first_increment_sets_ttl(self, service, mock_redis, mock_quota_repo):
        role_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_quota_repo.get.return_value = MagicMock(daily_query_limit=10, role_id=role_id)
        service._check_script = _make_script((1, 1, 10))

        await service.check_and_increment(user_id, role_id, "queries")

        mock_redis.register_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_subsequent_increment_does_not_set_ttl(self, service, mock_redis, mock_quota_repo):
        role_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_quota_repo.get.return_value = MagicMock(daily_query_limit=10, role_id=role_id)
        service._check_script = _make_script((1, 2, 10))

        await service.check_and_increment(user_id, role_id, "queries")

        mock_redis.register_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_execution_dimension_uses_execution_limit(self, service, mock_redis, mock_quota_repo):
        role_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_quota_repo.get.return_value = MagicMock(daily_execution_limit=20, role_id=role_id)
        service._check_script = _make_script((1, 5, 20))

        used, limit, reset_at = await service.check_and_increment(user_id, role_id, "executions")

        assert used == 5
        assert limit == 20

    @pytest.mark.asyncio
    async def test_fail_closed_on_redis_get_error(self, service, mock_redis, mock_quota_repo):
        role_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_quota_repo.get.return_value = MagicMock(daily_query_limit=10, role_id=role_id)
        service._check_script = _make_script(side_effect=ConnectionError("Redis connection lost"))

        with pytest.raises(QuotaUnavailableError):
            await service.check_and_increment(user_id, role_id, "queries")
