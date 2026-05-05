"""LLM exception shim — re-exports from core.exceptions (T-128 consolidation).

New code should import directly from ``app.core.exceptions``. This module is
kept for one chunk to avoid breaking existing adapter imports.
"""

from app.core.exceptions import (
    LLMConfigurationError,
    LLMTimeout,
    LLMUnavailable,
)

__all__ = ["LLMUnavailable", "LLMTimeout", "LLMConfigurationError"]
