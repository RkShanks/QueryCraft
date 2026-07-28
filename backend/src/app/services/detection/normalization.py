"""Bounded text canonicalization for heuristic detection rules."""

from __future__ import annotations

import unicodedata

_ZERO_WIDTH_SEPARATORS = frozenset({"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"})
_ARABIC_TATWEEL = "\u0640"


def _replace_block_comments(text: str) -> str:
    comment_free_parts: list[str] = []
    remaining_start = 0
    while (comment_start := text.find("/*", remaining_start)) >= 0:
        comment_end = text.find("*/", comment_start + 2)
        if comment_end < 0:
            break
        comment_free_parts.extend((text[remaining_start:comment_start], " "))
        remaining_start = comment_end + 2
    comment_free_parts.append(text[remaining_start:])
    return "".join(comment_free_parts)


def normalize_detection_text(text: str) -> str:
    """Canonicalize documented Unicode bypass forms without decoding content."""
    compatibility_text = unicodedata.normalize("NFKC", _replace_block_comments(text))
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
