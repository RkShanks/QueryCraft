"""RED integration test for 95% pass-through of normal business queries (T-836).

Runs ≥20 curated normal business queries (English + Arabic) through
HostileInputDetector with default thresholds.

Assertions:
- At least 95% return outcome="allowed"
- 0 normal queries trigger outcome="blocked"
"""

from __future__ import annotations

import pytest

# Default thresholds (match DetectionConfigRepository defaults)
_BLOCK_CONFIDENCE = 0.8
_FLAG_CONFIDENCE = 0.5

# ≥20 normal business queries in English and Arabic.
# These must NOT trigger hostile patterns.
NORMAL_QUERIES: list[str] = [
    # English business queries
    "Show me total sales for Q3 2024",
    "What is the revenue breakdown by region?",
    "List all customers who ordered last month",
    "How many employees are in each department?",
    "Show me the average order value by product category",
    "What are the top 10 products by revenue this year?",
    "How many new users registered in the last 7 days?",
    "Show me open support tickets grouped by priority",
    "What is the churn rate for enterprise customers?",
    "List all invoices overdue by more than 30 days",
    "Show me monthly recurring revenue trend for 2024",
    "What is the conversion rate from trial to paid?",
    "How many active sessions are there right now?",
    "Show me the distribution of order sizes",
    "What percentage of customers are in each plan tier?",
    "List all projects that are behind schedule",
    "Show me the average response time for support tickets",
    "What are the most common reasons for refund requests?",
    "How many queries did each user run this week?",
    "Show me the database connection pool usage over time",
    # Arabic business queries
    "أظهر لي إجمالي المبيعات للربع الثالث",
    "ما هو توزيع الإيرادات حسب المنطقة؟",
    "قائمة بجميع العملاء الذين طلبوا الشهر الماضي",
    "كم عدد الموظفين في كل قسم؟",
    "أظهر متوسط قيمة الطلب حسب فئة المنتج",
]

# Thresholds
_MIN_PASS_RATE = 0.95
_MAX_BLOCKED = 0


def _make_config(block: float = _BLOCK_CONFIDENCE, flag: float = _FLAG_CONFIDENCE):
    """Build a fake DetectionThresholdConfig with given thresholds."""
    from unittest.mock import MagicMock

    cfg = MagicMock()
    cfg.block_confidence = block
    cfg.flag_confidence = flag
    return cfg


class TestDetectionPassthrough:
    """≥20 normal queries → ≥95% allowed, 0 blocked."""

    @pytest.mark.asyncio
    async def test_normal_queries_pass_through(self):
        """All normal queries: ≥95% allowed, 0 blocked."""
        # Import detection package — this populates all 5 rules via REGISTRY
        import app.services.detection  # noqa: F401
        from app.services.detection.detector import HostileInputDetector
        from app.services.detection.protocol import REGISTRY

        detector = HostileInputDetector(registry=REGISTRY)
        config = _make_config()

        outcomes = []
        for query in NORMAL_QUERIES:
            outcome = await detector.detect(query, config)
            outcomes.append((query, outcome.outcome, outcome.max_confidence))

        blocked = [(q, o, c) for q, o, c in outcomes if o == "blocked"]
        allowed = [(q, o, c) for q, o, c in outcomes if o == "allowed"]

        total = len(outcomes)
        pass_rate = len(allowed) / total

        # 0 blocked
        assert len(blocked) == _MAX_BLOCKED, f"Expected 0 blocked queries but got {len(blocked)}: " + ", ".join(
            f"{q!r} (conf={c:.2f})" for q, _, c in blocked
        )

        # ≥95% allowed
        assert pass_rate >= _MIN_PASS_RATE, (
            f"Expected ≥{_MIN_PASS_RATE:.0%} allowed, got {pass_rate:.1%} "
            f"({len(allowed)}/{total}). "
            "Non-allowed: " + ", ".join(f"{q!r}={o}" for q, o, _ in outcomes if o != "allowed")
        )

    @pytest.mark.asyncio
    async def test_at_least_20_queries_in_corpus(self):
        """Sanity check: corpus has ≥20 entries."""
        assert len(NORMAL_QUERIES) >= 20

    @pytest.mark.asyncio
    async def test_corpus_has_english_and_arabic(self):
        """Corpus must contain both English and Arabic queries."""
        # Arabic queries contain Arabic script characters (U+0600–U+06FF range)
        has_arabic = any(any("\u0600" <= ch <= "\u06ff" for ch in q) for q in NORMAL_QUERIES)
        has_english = any(
            all(ord(ch) < 0x0600 or ch.isspace() or ch in ".,;:?!'\"" for ch in q) for q in NORMAL_QUERIES
        )
        assert has_arabic, "Corpus must include Arabic queries"
        assert has_english, "Corpus must include English queries"
