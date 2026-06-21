"""RbacBypassRule — detects RBAC/policy bypass attempts (T-831).

Covers English and Arabic patterns for bypassing row-level security,
access controls, and policy restrictions.
Registered into the module-level REGISTRY singleton on import.
"""

from __future__ import annotations

import re

from app.services.detection.protocol import REGISTRY, DetectionResult

# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

_ENGLISH_PATTERNS: list[re.Pattern[str]] = [
    # "show me all users" — broad data dump bypassing row filters
    re.compile(r"\bshow\s+(?:me\s+)?all\s+(?:users?|data|records?|rows?|entries)\b", re.IGNORECASE),
    # "bypass filter/restriction/policy"
    re.compile(r"\bbypass\b.{0,40}\b(?:filter|restriction|policy|access|control|limit)\b", re.IGNORECASE),
    # "ignore row restrictions / ignore access controls"
    re.compile(r"\bignore\b.{0,40}\b(?:row|access|column|permission|restriction|filter|policy)\b", re.IGNORECASE),
    # "show all data (without restrictions)"
    re.compile(r"\bshow\s+all\s+data\b", re.IGNORECASE),
    # "override policy/access/restriction"
    re.compile(r"\boverride\b.{0,40}\b(?:policy|access|permission|restriction|filter|control)\b", re.IGNORECASE),
    # "without any restrictions/filters"
    re.compile(r"\bwithout\b.{0,30}\b(?:restrictions?|filters?|permissions?|limits?)\b", re.IGNORECASE),
    # "full access / unrestricted access"
    re.compile(r"\b(?:full|unrestricted|complete)\s+access\b", re.IGNORECASE),
    # "list everything / list all records"
    re.compile(r"\blist\s+(?:everything|all\s+(?:records?|users?|data))\b", re.IGNORECASE),
]

_ARABIC_PATTERNS: list[re.Pattern[str]] = [
    # تجاوز القيود — "bypass restrictions"
    re.compile(r"تجاوز\s+القيود"),
    # أظهر كل البيانات — "show all the data"
    re.compile(r"أظهر\s+كل\s+البيانات"),
    # تجاوز الصلاحيات — "bypass permissions"
    re.compile(r"تجاوز\s+الصلاحيات"),
    # تجاهل فلاتر الوصول — "ignore access filters"
    re.compile(r"تجاهل\s+(?:فلاتر|قواعد)\s+الوصول"),
    # عرض كل المستخدمين — "show all users"
    re.compile(r"عرض\s+كل\s+المستخدمين"),
]

_ALL_PATTERNS: list[re.Pattern[str]] = _ENGLISH_PATTERNS + _ARABIC_PATTERNS

_PER_PATTERN_CONFIDENCE = 0.85


def _score(text: str) -> tuple[float, str]:
    matched: list[str] = []
    for pattern in _ALL_PATTERNS:
        if pattern.search(text):
            matched.append(pattern.pattern)
    if not matched:
        return 0.0, "no RBAC bypass patterns detected"
    confidence = min(_PER_PATTERN_CONFIDENCE * len(matched), 1.0)
    return confidence, f"matched {len(matched)} RBAC bypass pattern(s)"


# ---------------------------------------------------------------------------
# Rule class
# ---------------------------------------------------------------------------


class RbacBypassRule:
    """Detects attempts to bypass row/column-level security and access controls.

    Scores text against English and Arabic RBAC bypass patterns.
    Returns confidence >= 0.8 for clear bypass attempts.
    """

    name: str = "rbac_bypass"

    def detect(self, text: str) -> DetectionResult:
        confidence, explanation = _score(text)
        return DetectionResult(
            category="rbac_bypass",
            confidence=confidence,
            explanation=explanation,
        )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

REGISTRY.register(RbacBypassRule())
