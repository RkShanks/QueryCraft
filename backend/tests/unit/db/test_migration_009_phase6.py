"""Regression tests for Phase 6 audit-search index migration 009."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_migration() -> ModuleType:
    migration_path = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "009_phase6_audit_search_indexes.py"
    )
    spec = importlib.util.spec_from_file_location("migration_009", migration_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_downgrade_preserves_indexes_inherited_from_revision_007(monkeypatch):
    """Rolling back 009 must restore the exact audit-index contract of 008."""
    migration = _load_migration()
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.downgrade()

    emitted_ddl = "\n".join(statements)
    assert "ix_audit_log_entries_actor_identity" in emitted_ddl
    assert "ix_audit_log_entries_outcome" in emitted_ddl
    assert "ix_audit_log_entries_context_gin" in emitted_ddl
    assert "ix_audit_log_entries_action_type" not in emitted_ddl
    assert "ix_audit_log_entries_timestamp" not in emitted_ddl
