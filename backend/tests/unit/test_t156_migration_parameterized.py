"""T-156 regression test — Alembic migration must not use raw f-string SQL.

Migration 002_seed_admin_user.py interpolates env vars directly into SQL
via f-strings, creating a SQL injection vector if display_name contains
single quotes (e.g. "O'Brien").
"""

import re
from pathlib import Path

MIGRATION_PATH = Path(__file__).parents[3] / "backend" / "alembic" / "versions" / "002_seed_admin_user.py"


def test_migration_has_no_f_string_sql():
    """The migration file must not contain f-string interpolation in SQL."""
    assert MIGRATION_PATH.exists(), f"Migration file not found: {MIGRATION_PATH}"
    content = MIGRATION_PATH.read_text()

    # Reject op.execute(f"...") or op.execute(f'...')
    f_string_pattern = re.compile(r"op\.execute\s*\(\s*f[\"']")
    matches = f_string_pattern.findall(content)
    assert len(matches) == 0, f"Found f-string SQL interpolation in migration: {matches}"


def test_migration_uses_parameterized_execute():
    """The migration should use sa.text() with bind parameters."""
    content = MIGRATION_PATH.read_text()
    assert "sa.text" in content or "text(" in content, "Migration should use sa.text() for parameterization"
    assert ":username" in content, "Migration should use named parameter :username"
    assert ":display_name" in content, "Migration should use named parameter :display_name"
