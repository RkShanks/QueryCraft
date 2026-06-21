"""PromptInjectionRule — detects prompt injection attempts (T-827).

Covers English and Arabic patterns per research.md R-03 and ADR-23.
Registered into the module-level REGISTRY singleton on import.
"""

from __future__ import annotations

import re

from app.services.detection.protocol import REGISTRY, DetectionResult

# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

# Each entry is a compiled pattern. Ordering does not affect scoring.
_ENGLISH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bignore\b.{0,40}\b(previous|prior|all)\b.{0,40}\b(instructions?|context|prompt)\b", re.IGNORECASE),
    re.compile(r"\bdisregard\b.{0,40}\b(all|prior|previous)\b", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+now\b", re.IGNORECASE),
    re.compile(r"\bpretend\s+you\s+are\b", re.IGNORECASE),
    re.compile(r"\bsystem\s+prompt\b", re.IGNORECASE),
    re.compile(r"\breveal\b.{0,30}\b(prompt|instructions?|config)\b", re.IGNORECASE),
    re.compile(r"\bact\s+as\b.{0,30}\b(if|though|an?)\b", re.IGNORECASE),
    re.compile(r"\bforget\b.{0,40}\b(instructions?|previous|prior|context)\b", re.IGNORECASE),
    re.compile(r"\boverride\b.{0,40}\b(instructions?|restrictions?|rules?)\b", re.IGNORECASE),
    re.compile(r"\bno\s+restrictions?\b", re.IGNORECASE),
    re.compile(r"\bjailbreak\b", re.IGNORECASE),
    re.compile(r"\bDAN\b"),  # "Do Anything Now" jailbreak token
]

# Arabic patterns (right-to-left text; using raw strings for clarity).
# تجاهل التعليمات — ignore the instructions
# تصرف كأنك      — act as if you are
# أنت الآن       — you are now
_ARABIC_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"تجاهل\s+التعليمات"),
    re.compile(r"تجاهل\s+.{0,30}\s*التعليمات"),
    re.compile(r"تصرف\s+كأنك"),
    re.compile(r"أنت\s+الآن"),
    re.compile(r"تظاهر\s+بأنك"),  # pretend you are
    re.compile(r"نسيان\s+التعليمات"),  # forget the instructions
    re.compile(r"تجاوز\s+التعليمات"),  # bypass the instructions
]

_ALL_PATTERNS: list[re.Pattern[str]] = _ENGLISH_PATTERNS + _ARABIC_PATTERNS

# Confidence per matched pattern.  We clamp at 1.0 after scoring.
_PER_PATTERN_CONFIDENCE = 0.85


def _score(text: str) -> tuple[float, str]:
    """Return (confidence, explanation) for *text*."""
    matched: list[str] = []
    for pattern in _ALL_PATTERNS:
        if pattern.search(text):
            matched.append(pattern.pattern)
    if not matched:
        return 0.0, "no prompt injection patterns detected"
    # Each match independently drives confidence to the per-pattern level.
    # Multiple matches don't super-linearly increase confidence beyond 1.0.
    confidence = min(_PER_PATTERN_CONFIDENCE * len(matched), 1.0)
    explanation = f"matched {len(matched)} prompt injection pattern(s)"
    return confidence, explanation


# ---------------------------------------------------------------------------
# Rule class
# ---------------------------------------------------------------------------


class PromptInjectionRule:
    """Detects prompt injection attempts in user-supplied text.

    Scores text against English and Arabic injection patterns.
    Returns confidence >= 0.8 for clear injection attempts.
    """

    name: str = "prompt_injection"

    def detect(self, text: str) -> DetectionResult:
        """Score *text* for prompt injection signals.

        Args:
            text: Raw user input to evaluate.

        Returns:
            DetectionResult with category "prompt_injection".
        """
        confidence, explanation = _score(text)
        return DetectionResult(
            category="prompt_injection",
            confidence=confidence,
            explanation=explanation,
        )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

REGISTRY.register(PromptInjectionRule())
