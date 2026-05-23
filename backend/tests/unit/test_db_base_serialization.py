"""T-XXX: Verify custom JSON serializer in db.base handles Decimal/datetime."""

import json
from datetime import date, datetime, time
from decimal import Decimal

from app.db.base import custom_json_dumps


def test_custom_json_serializes_decimal():
    """Decimal is serialized as float."""
    payload = {"amount": Decimal("99.99")}
    result = json.loads(custom_json_dumps(payload))
    assert result["amount"] == 99.99


def test_custom_json_serializes_datetime():
    """datetime, date, time are serialized as ISO strings."""
    payload = {
        "created": datetime(2026, 5, 23, 12, 0, 0),
        "birthday": date(2026, 5, 23),
        "start": time(9, 30, 0),
    }
    result = json.loads(custom_json_dumps(payload))
    assert result["created"] == "2026-05-23T12:00:00"
    assert result["birthday"] == "2026-05-23"
    assert result["start"] == "09:30:00"
