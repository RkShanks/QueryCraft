"""Detection audit representation helpers (T-843).

Functions:
- build_redacted_summary(text): first 100 chars with hostile patterns replaced.
- compute_input_hash(text): SHA-256 hex of raw text.
- build_detection_audit_context(outcome, results, text): safe audit context dict.

Raw hostile text MUST NEVER appear in the output of any function here.
"""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.detection.protocol import DetectionResult

# ---------------------------------------------------------------------------
# Hostile pattern catalogue for redaction
# Mirrors the patterns from built-in rules — we re-define a lightweight set
# here so audit_representation has no circular import on the rule modules.
# ---------------------------------------------------------------------------

_REDACT_PATTERNS: list[re.Pattern[str]] = [
    # Prompt injection
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
    re.compile(r"\bDAN\b"),
    # SQL injection
    re.compile(r"\bUNION\s+(?:ALL\s+)?SELECT\b", re.IGNORECASE),
    re.compile(r";\s*(?:DELETE|DROP|UPDATE|INSERT|TRUNCATE|ALTER)\b", re.IGNORECASE),
    re.compile(r"\b1\s*=\s*1\b"),
    re.compile(r"\bOR\s+(?:['\"]?\w+['\"]?\s*=\s*['\"]?\w+['\"]?|1\s*=\s*1)\b", re.IGNORECASE),
    re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bDROP\s+DATABASE\b", re.IGNORECASE),
    re.compile(r"\b(?:SLEEP|BENCHMARK|WAITFOR\s+DELAY)\s*\(", re.IGNORECASE),
    re.compile(r"\bxp_cmdshell\b", re.IGNORECASE),
    re.compile(r"\bINFORMATION_SCHEMA\b", re.IGNORECASE),
    # RBAC bypass
    re.compile(r"\bbypass\b.{0,30}\b(role|permission|access|security)\b", re.IGNORECASE),
    re.compile(r"\bescalate\b.{0,30}\b(privilege|permission|access|role)\b", re.IGNORECASE),
    re.compile(r"\bgrant\b.{0,30}\b(admin|superuser|root|privilege)\b", re.IGNORECASE),
    re.compile(r"\bimpersonat\w*\b.{0,30}\b(user|admin|role)\b", re.IGNORECASE),
    re.compile(r"\bsudo\b", re.IGNORECASE),
    # Schema exposure
    re.compile(r"\blist\b.{0,30}\b(all\s+)?tables?\b", re.IGNORECASE),
    re.compile(r"\bshow\b.{0,30}\btables?\b", re.IGNORECASE),
    re.compile(r"\bdump\b.{0,30}\b(schema|database|table)\b", re.IGNORECASE),
    # Destructive SQL
    re.compile(r"\bTRUNCATE\b.{0,30}\b(TABLE|DATABASE)?\b", re.IGNORECASE),
    re.compile(r"\bDELETE\b.{0,30}\bFROM\b", re.IGNORECASE),
    re.compile(r"\bALTER\b.{0,30}\b(TABLE|DATABASE|USER)\b", re.IGNORECASE),
    # Shell command injection (content of xp_cmdshell or similar)
    re.compile(r"\brm\s+-[rfR]+\b", re.IGNORECASE),
    re.compile(r"\bexec\s*\(", re.IGNORECASE),
    re.compile(r"\bshell\s*\(", re.IGNORECASE),
    re.compile(r"\bos\.system\b", re.IGNORECASE),
    re.compile(r"\bsubprocess\b", re.IGNORECASE),
    # Arabic hostile
    re.compile(r"تجاهل\s+التعليمات"),
    re.compile(r"احذف\s+الجدول"),
    re.compile(r"تصرف\s+كأنك"),
]

_REDACT_PLACEHOLDER = "[REDACTED_PATTERN]"
_MAX_SUMMARY_LEN = 100


def build_redacted_summary(text: str) -> str:
    """Return a redacted summary of *text*, at most 100 characters.

    Hostile pattern matches are replaced with ``[REDACTED_PATTERN]``.
    The result is then truncated to 100 characters.  Raw hostile text
    MUST NOT appear in the output.

    Args:
        text: Raw user input.

    Returns:
        Redacted + truncated string, at most 100 characters.
    """
    if not text:
        return ""
    redacted = text
    for pattern in _REDACT_PATTERNS:
        redacted = pattern.sub(_REDACT_PLACEHOLDER, redacted)
    return redacted[:_MAX_SUMMARY_LEN]


def compute_input_hash(text: str) -> str:
    """Return the SHA-256 hex digest of *text* (UTF-8 encoded).

    Args:
        text: Raw user input.

    Returns:
        64-character lowercase hexadecimal string.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_detection_audit_context(
    outcome: str,
    results: list[DetectionResult],
    text: str,
) -> dict[str, Any]:
    """Build a safe audit context dict for a detection event.

    The returned dict contains ONLY safe fields:
    - ``category``: category label of the highest-confidence result
    - ``confidence``: max confidence across all results
    - ``rules_triggered``: list of rule names (strings only; no patterns)
    - ``outcome``: "blocked" | "flagged" | "allowed"
    - ``input_summary``: redacted, max-100-char summary
    - ``input_hash``: SHA-256 hex of the raw input

    Raw hostile text MUST NEVER appear in the output.

    Args:
        outcome: Detection outcome string.
        results: List of DetectionResult from all rules.
        text: Raw user input (used for hashing + summary; never stored raw).

    Returns:
        Safe context dict for ``AuditService.log``.
    """
    # Find highest-confidence result to pick category
    best = max(results, key=lambda r: r.confidence, default=None)
    category = best.category if best is not None else "unknown"
    max_confidence = best.confidence if best is not None else 0.0

    # Collect rule names only — never patterns, explanations, or raw text
    rules_triggered: list[str] = []
    for r in results:
        if r.confidence > 0.0:
            # Prefer rule_name if present (set by rules that expose it)
            name = getattr(r, "rule_name", None) or r.category
            rules_triggered.append(name)

    return {
        "category": category,
        "confidence": round(max_confidence, 4),
        "rules_triggered": rules_triggered,
        "outcome": outcome,
        "input_summary": build_redacted_summary(text),
        "input_hash": compute_input_hash(text),
    }
