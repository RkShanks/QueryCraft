"""RED unit tests for DestructiveSqlRule (T-834).

Contract tested:
- English destructive SQL generation patterns score >= 0.8
- Arabic destructive SQL patterns score >= 0.8
- Benign: "delete my saved search" stays below block threshold
- Returned category is "destructive_sql"
- Rule implements DetectionRule protocol
"""

from __future__ import annotations

import pytest

BLOCK_THRESHOLD = 0.8
BENIGN_BLOCK_THRESHOLD = 0.8


@pytest.fixture()
def rule():
    from app.services.detection.rules.destructive_sql import DestructiveSqlRule

    return DestructiveSqlRule()


class TestDestructiveSqlRuleProtocol:
    """Rule satisfies DetectionRule protocol."""

    def test_rule_has_name(self, rule):
        assert isinstance(rule.name, str)
        assert rule.name

    def test_rule_name_is_destructive_sql(self, rule):
        assert rule.name == "destructive_sql"

    def test_detect_returns_detection_result(self, rule):
        from app.services.detection.protocol import DetectionResult

        result = rule.detect("some text")
        assert isinstance(result, DetectionResult)

    def test_category_is_destructive_sql(self, rule):
        result = rule.detect("delete all records from the orders table")
        assert result.category == "destructive_sql"


class TestDestructiveSqlEnglishPatterns:
    """Clear English destructive SQL generation attempts score >= block threshold."""

    def test_delete_all_records(self, rule):
        result = rule.detect("delete all records from the orders table")
        assert result.confidence >= BLOCK_THRESHOLD, (
            f"Expected >= {BLOCK_THRESHOLD} for 'delete all records', got {result.confidence}"
        )

    def test_drop_the_table(self, rule):
        result = rule.detect("drop the users table from the database")
        assert result.confidence >= BLOCK_THRESHOLD, (
            f"Expected >= {BLOCK_THRESHOLD} for 'drop the table', got {result.confidence}"
        )

    def test_truncate_orders(self, rule):
        result = rule.detect("truncate orders table")
        assert result.confidence >= BLOCK_THRESHOLD, (
            f"Expected >= {BLOCK_THRESHOLD} for 'truncate orders', got {result.confidence}"
        )

    def test_alter_table_users(self, rule):
        result = rule.detect("alter table users to drop all columns")
        assert result.confidence >= BLOCK_THRESHOLD, (
            f"Expected >= {BLOCK_THRESHOLD} for 'alter table users', got {result.confidence}"
        )

    def test_update_all_rows(self, rule):
        result = rule.detect("update all rows in the customers table to set active=false")
        assert result.confidence >= BLOCK_THRESHOLD, (
            f"Expected >= {BLOCK_THRESHOLD} for 'update all rows', got {result.confidence}"
        )

    @pytest.mark.parametrize(
        "text",
        [
            "delete all records from the database",
            "drop the orders table",
            "truncate the customers table",
            "alter table users drop column",
            "update all rows set status to deleted",
        ],
    )
    def test_parametrized_english_patterns(self, rule, text):
        result = rule.detect(text)
        assert result.confidence >= BLOCK_THRESHOLD, (
            f"Expected >= {BLOCK_THRESHOLD} for: {text!r}, got {result.confidence}"
        )


class TestDestructiveSqlArabicPatterns:
    """Clear Arabic destructive SQL patterns score >= block threshold."""

    def test_arabic_delete_all_records(self, rule):
        # احذف جميع السجلات — "delete all records"
        result = rule.detect("احذف جميع السجلات من الجدول")
        assert result.confidence >= BLOCK_THRESHOLD, (
            f"Expected >= {BLOCK_THRESHOLD} for Arabic 'delete all records', got {result.confidence}"
        )

    def test_arabic_drop_the_table(self, rule):
        # أسقط الجدول — "drop the table"
        result = rule.detect("أسقط الجدول من قاعدة البيانات")
        assert result.confidence >= BLOCK_THRESHOLD, (
            f"Expected >= {BLOCK_THRESHOLD} for Arabic 'drop the table', got {result.confidence}"
        )


class TestDestructiveSqlBenignQueries:
    """Benign queries stay below block threshold."""

    def test_delete_saved_search_benign(self, rule):
        # "delete my saved search" — user UI action, not DB-level destructive SQL
        result = rule.detect("delete my saved search")
        assert result.confidence < BENIGN_BLOCK_THRESHOLD, (
            f"Expected < {BENIGN_BLOCK_THRESHOLD} for 'delete my saved search', got {result.confidence}"
        )

    def test_remove_inactive_filter_benign(self, rule):
        result = rule.detect("remove the inactive customers filter")
        assert result.confidence < BENIGN_BLOCK_THRESHOLD

    def test_revenue_query_benign(self, rule):
        result = rule.detect("show total revenue for Q4")
        assert result.confidence < BENIGN_BLOCK_THRESHOLD


class TestDestructiveSqlRegistration:
    """DestructiveSqlRule is registered in the REGISTRY singleton."""

    def test_destructive_sql_rule_registered(self):
        import app.services.detection.rules.destructive_sql  # noqa: F401
        from app.services.detection.protocol import REGISTRY

        names = {r.name for r in REGISTRY.list_rules()}
        assert "destructive_sql" in names
