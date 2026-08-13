"""Regression tests for collection-pagination index migration 011."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_migration() -> ModuleType:
    migration_path = (
        Path(__file__).resolve().parents[3] / "alembic" / "versions" / "011_collection_pagination_indexes.py"
    )
    spec = importlib.util.spec_from_file_location("migration_011", migration_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_creates_indexes_for_each_keyset_traversal(monkeypatch) -> None:
    migration = _load_migration()
    created: list[tuple[str, str, tuple[str, ...]]] = []

    def capture(name: str, table: str, columns: list[object]) -> None:
        created.append((name, table, tuple(str(column) for column in columns)))

    monkeypatch.setattr(migration.op, "create_index", capture)

    migration.upgrade()

    assert created == [
        (
            "ix_sessions_user_activity_page",
            "sessions",
            ("user_id", "last_activity_at DESC", "id DESC"),
        ),
        (
            "ix_accepted_queries_session_user_accepted_page",
            "accepted_queries",
            ("session_id", "user_id", "accepted_at DESC", "id DESC"),
        ),
        ("ix_users_role_id_page", "users", ("role_id", "id")),
    ]


def test_downgrade_removes_only_revision_011_indexes(monkeypatch) -> None:
    migration = _load_migration()
    dropped: list[tuple[str, str]] = []
    monkeypatch.setattr(
        migration.op,
        "drop_index",
        lambda name, *, table_name: dropped.append((name, table_name)),
    )

    migration.downgrade()

    assert dropped == [
        ("ix_users_role_id_page", "users"),
        (
            "ix_accepted_queries_session_user_accepted_page",
            "accepted_queries",
        ),
        ("ix_sessions_user_activity_page", "sessions"),
    ]
