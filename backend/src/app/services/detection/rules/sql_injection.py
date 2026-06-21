"""SqlInjectionRule — detects SQL injection attempts in natural language (T-829).

Covers English and Arabic SQL injection fragments.
Registered into the module-level REGISTRY singleton on import.
"""

from __future__ import annotations

import re

from app.services.detection.protocol import REGISTRY, DetectionResult

# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

_ENGLISH_PATTERNS: list[re.Pattern[str]] = [
    # UNION SELECT — classic injection pivot
    re.compile(r"\bUNION\s+(?:ALL\s+)?SELECT\b", re.IGNORECASE),
    # Semicolon-separated stacked queries with DML
    re.compile(r";\s*(?:DELETE|DROP|UPDATE|INSERT|TRUNCATE|ALTER)\b", re.IGNORECASE),
    # Tautology: 1=1 / '1'='1'
    re.compile(r"\b1\s*=\s*1\b"),
    # OR tautology: OR 'x'='x', OR 1=1
    re.compile(r"\bOR\s+(?:['\"]?\w+['\"]?\s*=\s*['\"]?\w+['\"]?|1\s*=\s*1)\b", re.IGNORECASE),
    # DROP TABLE standalone
    re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE),
    # Backtick identifier abuse with tautology
    re.compile(r"`[^`]+`\s*=\s*`[^`]+`"),
    # SQL comment injection: -- or #
    re.compile(r"\bOR\b.{0,30}(?:--|#)\s*$", re.IGNORECASE | re.MULTILINE),
    # SLEEP / BENCHMARK time-based blind
    re.compile(r"\b(?:SLEEP|BENCHMARK|WAITFOR\s+DELAY)\s*\(", re.IGNORECASE),
    # xp_cmdshell
    re.compile(r"\bxp_cmdshell\b", re.IGNORECASE),
    # Information_schema probing
    re.compile(r"\bINFORMATION_SCHEMA\b", re.IGNORECASE),
]

_ARABIC_PATTERNS: list[re.Pattern[str]] = [
    # احذف الجدول — "delete the table"
    re.compile(r"احذف\s+الجدول"),
    # اختر كل — "select all"
    re.compile(r"اختر\s+كل"),
    # دمج مع اختيار — "union with select"
    re.compile(r"دمج\s+مع\s+اختيار"),
]

_ALL_PATTERNS: list[re.Pattern[str]] = _ENGLISH_PATTERNS + _ARABIC_PATTERNS

_PER_PATTERN_CONFIDENCE = 0.85


def _score(text: str) -> tuple[float, str]:
    matched: list[str] = []
    for pattern in _ALL_PATTERNS:
        if pattern.search(text):
            matched.append(pattern.pattern)
    if not matched:
        return 0.0, "no SQL injection patterns detected"
    confidence = min(_PER_PATTERN_CONFIDENCE * len(matched), 1.0)
    return confidence, f"matched {len(matched)} SQL injection pattern(s)"


# ---------------------------------------------------------------------------
# Rule class
# ---------------------------------------------------------------------------


class SqlInjectionRule:
    """Detects SQL injection fragments embedded in natural language input.

    Scores text against English and Arabic SQL injection patterns.
    Returns confidence >= 0.8 for clear injection attempts.
    """

    name: str = "sql_injection"

    def detect(self, text: str) -> DetectionResult:
        confidence, explanation = _score(text)
        return DetectionResult(
            category="sql_injection",
            confidence=confidence,
            explanation=explanation,
        )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

REGISTRY.register(SqlInjectionRule())
