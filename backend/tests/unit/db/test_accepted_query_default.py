"""T-191c: accepted_queries.accepted_at must have exactly one default mechanism."""

import pytest
from sqlalchemy import inspect

from app.db.base import Base
from app.db.models.accepted_query import AcceptedQuery


class TestAcceptedQueryDefault:
    """Verify no dual-default drift on accepted_at."""

    def test_accepted_at_has_single_source_of_truth(self):
        """accepted_at must have server_default OR python default, never both."""
        table = AcceptedQuery.__table__
        col = table.c.accepted_at

        has_server_default = col.server_default is not None
        has_python_default = col.default is not None and col.default is not col.server_default

        assert has_server_default, "accepted_at must have a server_default"
        assert not has_python_default, "accepted_at must NOT have a Python-side default (dual-default risk)"
