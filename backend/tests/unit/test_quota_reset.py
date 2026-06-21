"""RED unit tests for quota daily reset (T-808).

Tests:
- Counter key includes date suffix
- TTL is <= 86400 and > 0
- New day generates new key (old key irrelevant)
"""

from datetime import UTC, datetime

from app.services.quota_service import _seconds_until_midnight_utc, _today_key_suffix


class TestQuotaDailyReset:
    def test_key_suffix_includes_date(self):
        now = datetime(2026, 6, 12, 15, 30, 0, tzinfo=UTC)
        suffix = _today_key_suffix(now)
        assert suffix == "2026-06-12"

    def test_key_suffix_changes_at_midnight(self):
        before_midnight = datetime(2026, 6, 12, 23, 59, 59, tzinfo=UTC)
        after_midnight = datetime(2026, 6, 13, 0, 0, 1, tzinfo=UTC)

        assert _today_key_suffix(before_midnight) == "2026-06-12"
        assert _today_key_suffix(after_midnight) == "2026-06-13"

    def test_ttl_is_positive_and_at_most_86400(self):
        for hour in range(0, 24, 3):
            now = datetime(2026, 6, 12, hour, 30, 0, tzinfo=UTC)
            ttl = _seconds_until_midnight_utc(now)
            assert 0 < ttl <= 86400, f"TTL at hour {hour}: {ttl}"

    def test_ttl_at_midnight_is_86400(self):
        now = datetime(2026, 6, 12, 0, 0, 0, tzinfo=UTC)
        ttl = _seconds_until_midnight_utc(now)
        assert ttl == 86400

    def test_ttl_just_before_midnight_is_small(self):
        now = datetime(2026, 6, 12, 23, 59, 59, tzinfo=UTC)
        ttl = _seconds_until_midnight_utc(now)
        assert 0 < ttl <= 2

    def test_new_day_generates_new_key(self):
        day1 = datetime(2026, 6, 12, 15, 0, 0, tzinfo=UTC)
        day2 = datetime(2026, 6, 13, 10, 0, 0, tzinfo=UTC)

        key1 = f"quota:user1:queries:{_today_key_suffix(day1)}"
        key2 = f"quota:user1:queries:{_today_key_suffix(day2)}"

        assert key1 != key2
        assert "2026-06-12" in key1
        assert "2026-06-13" in key2
