"""Bounded text canonicalization for heuristic detection rules."""

from __future__ import annotations

import unicodedata

_ZERO_WIDTH_SEPARATORS = frozenset({"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"})
_ARABIC_TATWEEL = "\u0640"


def normalize_detection_text(text: str) -> str:
    """Canonicalize documented Unicode bypass forms without decoding content."""
    compatibility_text = unicodedata.normalize("NFKC", text)
    normalized_characters: list[str] = []
    for character in compatibility_text:
        if character in _ZERO_WIDTH_SEPARATORS:
            normalized_characters.append(" ")
        elif character == _ARABIC_TATWEEL or unicodedata.combining(character):
            continue
        elif unicodedata.category(character) == "Cf":
            continue
        else:
            normalized_characters.append(character)
    return " ".join("".join(normalized_characters).split())
