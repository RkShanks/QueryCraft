"""Per-scenario disposable PostgreSQL database fixtures."""

from __future__ import annotations

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest

from tests.migrations.migration_support import (
    DISPOSABLE_DATABASE_PREFIX,
    create_disposable_database,
    drop_disposable_database,
)


@pytest.fixture
def disposable_database_url(monkeypatch, set_test_env) -> Iterator[str]:
    """Create and always destroy one isolated database for a migration scenario."""
    admin_url = os.environ.get("QUERYCRAFT_MIGRATION_ADMIN_URL")
    if admin_url is None:
        pytest.skip("QUERYCRAFT_MIGRATION_ADMIN_URL is required for isolated migration tests")

    database_name = f"{DISPOSABLE_DATABASE_PREFIX}{uuid4().hex}"
    database_url = create_disposable_database(admin_url, database_name)
    monkeypatch.setenv("DATABASE_URL", database_url)
    try:
        yield database_url
    finally:
        drop_disposable_database(database_url)
