"""Opaque keyset cursor encoding shared by bounded collections."""

import base64
import binascii
import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from app.core.exceptions import InvalidCursorError

_CURSOR_VERSION = 1
_MAX_CURSOR_LENGTH = 512


@dataclass(frozen=True)
class CursorPosition:
    """Validated sort position carried between keyset pages."""

    sort_value: str
    item_id: uuid.UUID


def encode_cursor(namespace: str, sort_value: str, item_id: uuid.UUID) -> str:
    """Encode only the collection namespace and keyset position."""
    payload = json.dumps(
        {"v": _CURSOR_VERSION, "n": namespace, "s": sort_value, "i": str(item_id)},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def decode_cursor(cursor: str, namespace: str) -> CursorPosition:
    """Decode a cursor only when its version, namespace, and value types match."""
    try:
        if not cursor or len(cursor) > _MAX_CURSOR_LENGTH:
            raise ValueError
        padding = b"=" * (-len(cursor) % 4)
        raw = base64.b64decode(cursor.encode("ascii") + padding, altchars=b"-_", validate=True)
        payload = json.loads(raw)
        if set(payload) != {"v", "n", "s", "i"}:
            raise ValueError
        if (
            payload["v"] != _CURSOR_VERSION
            or payload["n"] != namespace
            or not isinstance(payload["s"], str)
            or not isinstance(payload["i"], str)
        ):
            raise ValueError
        return CursorPosition(sort_value=payload["s"], item_id=uuid.UUID(payload["i"]))
    except (UnicodeError, binascii.Error, json.JSONDecodeError, TypeError, ValueError):
        raise InvalidCursorError() from None


def decode_datetime_cursor(cursor: str, namespace: str) -> tuple[datetime, uuid.UUID]:
    """Decode a cursor whose primary sort value is a timezone-aware datetime."""
    position = decode_cursor(cursor, namespace)
    try:
        sort_time = datetime.fromisoformat(position.sort_value)
        if sort_time.tzinfo is None:
            raise ValueError
    except ValueError:
        raise InvalidCursorError() from None
    return sort_time, position.item_id
