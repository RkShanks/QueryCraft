"""DestructiveSqlRule — detects destructive SQL generation requests (T-835).

Covers English and Arabic patterns for requests to generate DELETE, DROP,
TRUNCATE, ALTER, or mass UPDATE statements.
Registered into the module-level REGISTRY singleton on import.
"""

from __future__ import annotations

import re

from app.services.detection.protocol import REGISTRY, DetectionResult

# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

# Key design choice: detect *destructive intent toward a table/database scope*,
# not individual record deletions in a normal user context.
# "delete all records", "drop the table", "truncate X" → hostile
# "delete my saved search" → benign (no table/database scope)

_ENGLISH_PATTERNS: list[re.Pattern[str]] = [
    # "delete all records/rows" — mass delete
    re.compile(r"\bdelete\s+all\s+(?:records?|rows?|data|entries)\b", re.IGNORECASE),
    # "delete from <table>" — SQL DML in NL context
    re.compile(r"\bdelete\b.{0,20}\bfrom\b.{0,30}\b(?:table|database|db)\b", re.IGNORECASE),
    # "drop the/a table"
    re.compile(r"\bdrop\b.{0,20}\b(?:the\s+)?(?:table|database|db|index)\b", re.IGNORECASE),
    # "truncate <table/orders/customers>"
    re.compile(r"\btruncate\b.{0,40}\b(?:table|the|orders?|customers?|users?|records?)\b", re.IGNORECASE),
    # "alter table <name> drop/modify"
    re.compile(r"\balter\s+table\b", re.IGNORECASE),
    # "update all rows/records"
    re.compile(r"\bupdate\s+all\s+(?:rows?|records?|entries|data)\b", re.IGNORECASE),
    re.compile(r"\bset\b.{0,40}\bwhere\s+1\s*=\s*1\b", re.IGNORECASE),  # mass update tautology
    # "wipe the database / clear the table"
    re.compile(
        r"\b(?:wipe|clear|purge|erase)\b.{0,30}\b(?:table|database|db|all\s+records?|all\s+data)\b",
        re.IGNORECASE,
    ),
    # "remove all data/records from"
    re.compile(r"\bremove\s+all\b.{0,30}\b(?:data|records?|rows?)\b.{0,30}\bfrom\b", re.IGNORECASE),
]

_ARABIC_PATTERNS: list[re.Pattern[str]] = [
    # احذف جميع السجلات — "delete all records"
    re.compile(r"احذف\s+جميع\s+السجلات"),
    # أسقط الجدول — "drop the table"
    re.compile(r"أسقط\s+الجدول"),
    # احذف الجدول — "delete the table" (also used for DROP)
    re.compile(r"احذف\s+الجدول"),
    # امسح جميع البيانات — "erase all data"
    re.compile(r"امسح\s+(?:جميع\s+)?البيانات"),
    # تعديل بنية الجدول — "modify table structure" (ALTER TABLE)
    re.compile(r"تعديل\s+بنية\s+الجدول"),
    # تحديث جميع الصفوف — "update all rows"
    re.compile(r"تحديث\s+جميع\s+الصفوف"),
]

_ALL_PATTERNS: list[re.Pattern[str]] = _ENGLISH_PATTERNS + _ARABIC_PATTERNS

_PER_PATTERN_CONFIDENCE = 0.85


def _score(text: str) -> tuple[float, str]:
    matched: list[str] = []
    for pattern in _ALL_PATTERNS:
        if pattern.search(text):
            matched.append(pattern.pattern)
    if not matched:
        return 0.0, "no destructive SQL patterns detected"
    confidence = min(_PER_PATTERN_CONFIDENCE * len(matched), 1.0)
    return confidence, f"matched {len(matched)} destructive SQL pattern(s)"


# ---------------------------------------------------------------------------
# Rule class
# ---------------------------------------------------------------------------


class DestructiveSqlRule:
    """Detects requests to generate destructive SQL operations.

    Targets requests for DELETE/DROP/TRUNCATE/ALTER/mass UPDATE generation.
    Returns confidence >= 0.8 for clear destructive SQL generation attempts.
    Benign single-record user actions (e.g. "delete my saved search") score low.
    """

    name: str = "destructive_sql"

    def detect(self, text: str) -> DetectionResult:
        confidence, explanation = _score(text)
        return DetectionResult(
            category="destructive_sql",
            confidence=confidence,
            explanation=explanation,
        )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

REGISTRY.register(DestructiveSqlRule())
