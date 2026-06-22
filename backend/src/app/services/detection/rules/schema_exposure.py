"""SchemaExposureRule — detects attempts to expose schema/secrets (T-833).

Covers English and Arabic patterns for probing database schemas,
credentials, configuration, and environment secrets.
Registered into the module-level REGISTRY singleton on import.
"""

from __future__ import annotations

import re

from app.services.detection.protocol import REGISTRY, DetectionResult

# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

_ENGLISH_PATTERNS: list[re.Pattern[str]] = [
    # "show all tables" / "list all tables"
    re.compile(r"\b(?:show|list|get|describe)\b.{0,30}\ball\s+tables\b", re.IGNORECASE),
    re.compile(r"\b(?:show|list|get)\b.{0,30}\btables\b.{0,30}\b(?:database|schema|db)\b", re.IGNORECASE),
    # "list columns / list all columns"
    re.compile(r"\b(?:list|show|get|describe)\b.{0,30}\bcolumns?\b", re.IGNORECASE),
    # "database password" / "db password"
    re.compile(r"\b(?:database|db)\s+password\b", re.IGNORECASE),
    re.compile(r"\bpassword\b.{0,30}\b(?:database|db|connection)\b", re.IGNORECASE),
    # "connection string"
    re.compile(r"\bconnection\s+string\b", re.IGNORECASE),
    # "show config / application config"
    re.compile(r"\bshow\b.{0,30}\bconfig(?:uration)?\b", re.IGNORECASE),
    re.compile(r"\bconfig(?:uration)?\b.{0,30}\bsettings?\b", re.IGNORECASE),
    # "environment variables"
    re.compile(r"\benvironment\s+variables?\b", re.IGNORECASE),
    re.compile(r"\benv\s+vars?\b", re.IGNORECASE),
    # "API key / secret key / access token"
    re.compile(r"\b(?:api|secret|access)\s+(?:key|token)\b", re.IGNORECASE),
    # "show schema"
    re.compile(r"\bshow\b.{0,30}\bschema\b", re.IGNORECASE),
    # "information_schema" (already in SQL injection, but double-coverage acceptable)
    re.compile(r"\binformation_schema\b", re.IGNORECASE),
    # "dump database / dump schema"
    re.compile(r"\bdump\b.{0,30}\b(?:database|schema|db|tables?)\b", re.IGNORECASE),
]

_ARABIC_PATTERNS: list[re.Pattern[str]] = [
    # اعرض الجداول — "show the tables"
    re.compile(r"اعرض\s+الجداول"),
    # كلمة مرور قاعدة البيانات — "database password"
    re.compile(r"كلمة\s+مرور\s+قاعدة\s+البيانات"),
    # سلسلة الاتصال — "connection string"
    re.compile(r"سلسلة\s+الاتصال"),
    # متغيرات البيئة — "environment variables"
    re.compile(r"متغيرات\s+البيئة"),
    # أسماء الأعمدة — "column names"
    re.compile(r"أسماء\s+الأعمدة"),
    # هيكل قاعدة البيانات — "database structure"
    re.compile(r"هيكل\s+قاعدة\s+البيانات"),
]

_ALL_PATTERNS: list[re.Pattern[str]] = _ENGLISH_PATTERNS + _ARABIC_PATTERNS

_PER_PATTERN_CONFIDENCE = 0.85


def _score(text: str) -> tuple[float, str]:
    matched: list[str] = []
    for pattern in _ALL_PATTERNS:
        if pattern.search(text):
            matched.append(pattern.pattern)
    if not matched:
        return 0.0, "no schema exposure patterns detected"
    confidence = min(_PER_PATTERN_CONFIDENCE * len(matched), 1.0)
    return confidence, f"matched {len(matched)} schema exposure pattern(s)"


# ---------------------------------------------------------------------------
# Rule class
# ---------------------------------------------------------------------------


class SchemaExposureRule:
    """Detects attempts to probe or expose schema internals and secrets.

    Scores text against English and Arabic schema/secret exposure patterns.
    Returns confidence >= 0.8 for clear exposure attempts.
    """

    name: str = "schema_exposure"

    def detect(self, text: str) -> DetectionResult:
        confidence, explanation = _score(text)
        return DetectionResult(
            category="schema_exposure",
            confidence=confidence,
            explanation=explanation,
        )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

REGISTRY.register(SchemaExposureRule())
