"""Concurrent Alembic execution safety on disposable PostgreSQL."""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from tests.migrations.migration_support import (
    ALEMBIC_INI,
    BACKEND_ROOT,
    current_revision,
    revision_ids,
    set_database_lock_timeout,
)
from tests.migrations.scenario_support import assert_revision_schema


@pytest.mark.integration
def test_concurrent_upgrades_are_serialized_or_one_is_rejected_safely(
    disposable_database_url: str,
) -> None:
    set_database_lock_timeout(disposable_database_url, 2_000)
    start_barrier = Barrier(2)

    def upgrade_after_barrier(_: int) -> int:
        process_environment = os.environ.copy()
        process_environment["DATABASE_URL"] = disposable_database_url
        start_barrier.wait()
        completed = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), "upgrade", "head"],
            cwd=BACKEND_ROOT,
            env=process_environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
        )
        return completed.returncode

    with ThreadPoolExecutor(max_workers=2) as executor:
        return_codes = list(executor.map(upgrade_after_barrier, range(2)))

    assert 0 in return_codes
    assert current_revision(disposable_database_url) == revision_ids()[-1]
    assert_revision_schema(disposable_database_url, revision_ids()[-1])
