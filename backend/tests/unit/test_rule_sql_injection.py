"""RED unit tests for SqlInjectionRule (T-828).

Contract tested:
- English SQL injection patterns score >= 0.8
- Arabic SQL injection patterns score >= 0.8
- Benign SQL-adjacent business query scores below block threshold (0.8)
- Returned category is "sql_injection"
- Rule implements DetectionRule protocol
"""

from __future__ import annotations

import pytest

BLOCK_THRESHOLD = 0.8
BENIGN_BLOCK_THRESHOLD = 0.8  # benign must stay below this


@pytest.fixture()
def rule():
    from app.services.detection.rules.sql_injection import SqlInjectionRule

    return SqlInjectionRule()


class TestSqlInjectionRuleProtocol:
    """Rule satisfies DetectionRule protocol."""

    def test_rule_has_name(self, rule):
        assert isinstance(rule.name, str)
        assert rule.name  # non-empty

    def test_rule_name_is_sql_injection(self, rule):
        assert rule.name == "sql_injection"

    def test_detect_returns_detection_result(self, rule):
        from app.services.detection.protocol import DetectionResult

        result = rule.detect("some text")
        assert isinstance(result, DetectionResult)

    def test_category_is_sql_injection(self, rule):
        result = rule.detect("UNION SELECT * FROM users")
        assert result.category == "sql_injection"


class TestSqlInjectionEnglishPatterns:
    """Clear English SQL injection fragments score >= block threshold."""

    def test_union_select_scores_high(self, rule):
        result = rule.detect("UNION SELECT username, password FROM users")
        assert result.confidence >= BLOCK_THRESHOLD, (
            f"Expected >= {BLOCK_THRESHOLD} for UNION SELECT, got {result.confidence}"
        )

    def test_semicolon_delete_scores_high(self, rule):
        result = rule.detect("show me orders; DELETE FROM orders WHERE 1=1")
        assert result.confidence >= BLOCK_THRESHOLD, (
            f"Expected >= {BLOCK_THRESHOLD} for '; DELETE', got {result.confidence}"
        )

    def test_tautology_1_equals_1(self, rule):
        result = rule.detect("show users WHERE id=1 OR 1=1")
        assert result.confidence >= BLOCK_THRESHOLD, f"Expected >= {BLOCK_THRESHOLD} for '1=1', got {result.confidence}"

    def test_or_tautology(self, rule):
        result = rule.detect("login as admin OR 1=1 --")
        assert result.confidence >= BLOCK_THRESHOLD, (
            f"Expected >= {BLOCK_THRESHOLD} for 'OR 1=1', got {result.confidence}"
        )

    def test_drop_table_in_nl_context(self, rule):
        result = rule.detect("DROP TABLE users")
        assert result.confidence >= BLOCK_THRESHOLD, (
            f"Expected >= {BLOCK_THRESHOLD} for DROP TABLE, got {result.confidence}"
        )

    def test_backtick_abuse(self, rule):
        result = rule.detect("SELECT `password` FROM `users` WHERE `id`=1 OR `1`=`1`")
        assert result.confidence >= BLOCK_THRESHOLD, (
            f"Expected >= {BLOCK_THRESHOLD} for backtick abuse, got {result.confidence}"
        )

    @pytest.mark.parametrize(
        "text",
        [
            "UNION SELECT * FROM admin",
            "; DELETE FROM customers",
            "1=1 --",
            "OR 1=1",
            "DROP TABLE orders",
        ],
    )
    def test_parametrized_english_patterns(self, rule, text):
        result = rule.detect(text)
        assert result.confidence >= BLOCK_THRESHOLD, (
            f"Expected >= {BLOCK_THRESHOLD} for: {text!r}, got {result.confidence}"
        )


class TestSqlInjectionArabicPatterns:
    """Clear Arabic SQL injection patterns score >= block threshold."""

    def test_arabic_delete_table(self, rule):
        # احذف الجدول — "delete the table"
        result = rule.detect("احذف الجدول users من قاعدة البيانات")
        assert result.confidence >= BLOCK_THRESHOLD, (
            f"Expected >= {BLOCK_THRESHOLD} for Arabic delete table, got {result.confidence}"
        )

    def test_arabic_select_all(self, rule):
        # اختر كل — "select all"
        result = rule.detect("اختر كل السجلات من جدول المستخدمين")
        assert result.confidence >= BLOCK_THRESHOLD, (
            f"Expected >= {BLOCK_THRESHOLD} for Arabic select all, got {result.confidence}"
        )


class TestSqlInjectionBenignQueries:
    """Benign SQL-adjacent business queries stay below block threshold."""

    def test_union_membership_counts_benign(self, rule):
        # "union" appears but in business context
        result = rule.detect("show me union membership counts by region")
        assert result.confidence < BENIGN_BLOCK_THRESHOLD, (
            f"Expected < {BENIGN_BLOCK_THRESHOLD} for benign union query, got {result.confidence}"
        )

    def test_regular_sales_query_benign(self, rule):
        result = rule.detect("show me the total sales for this quarter")
        assert result.confidence < BENIGN_BLOCK_THRESHOLD

    def test_employee_list_benign(self, rule):
        result = rule.detect("list all employees in the marketing department")
        assert result.confidence < BENIGN_BLOCK_THRESHOLD


class TestSqlInjectionRegistration:
    """SqlInjectionRule is registered in the REGISTRY singleton."""

    def test_sql_injection_rule_registered(self):
        import app.services.detection.rules.sql_injection  # noqa: F401
        from app.services.detection.protocol import REGISTRY

        names = {r.name for r in REGISTRY.list_rules()}
        assert "sql_injection" in names
