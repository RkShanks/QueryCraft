"""Tests for Alembic migration 006 (T-404, FR-091, SC-034).

Verifies migration structure and expected post-migration state.
"""

import importlib.util
from pathlib import Path


def _load_migration_module():
    """Load the migration module directly from file path."""
    migrations_dir = Path(__file__).resolve().parents[3] / "alembic" / "versions"
    migration_file = migrations_dir / "006_phase3_multi_dialect_connections.py"
    spec = importlib.util.spec_from_file_location("migration_006", migration_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestMigration006Structure:
    """Verify migration 006 has correct revision chain and operations."""

    def test_revision_id(self):
        mod = _load_migration_module()
        assert mod.revision == "006"

    def test_down_revision(self):
        mod = _load_migration_module()
        assert mod.down_revision == "005"

    def test_upgrade_function_exists(self):
        mod = _load_migration_module()
        assert callable(mod.upgrade)

    def test_downgrade_function_exists(self):
        mod = _load_migration_module()
        assert callable(mod.downgrade)


class TestMigration006UpgradeOperations:
    """Verify upgrade() performs expected operations by inspecting source."""

    def test_renames_table(self):
        mod = _load_migration_module()
        source = Path(mod.__file__).read_text()
        assert 'rename_table("database_connections", "source_database_connections")' in source

    def test_adds_display_name_column(self):
        mod = _load_migration_module()
        source = Path(mod.__file__).read_text()
        assert '"display_name"' in source

    def test_adds_database_type_column(self):
        mod = _load_migration_module()
        source = Path(mod.__file__).read_text()
        assert '"database_type"' in source

    def test_adds_lifecycle_state_column(self):
        mod = _load_migration_module()
        source = Path(mod.__file__).read_text()
        assert '"lifecycle_state"' in source

    def test_adds_health_status_column(self):
        mod = _load_migration_module()
        source = Path(mod.__file__).read_text()
        assert '"health_status"' in source

    def test_adds_schema_introspection_status_column(self):
        mod = _load_migration_module()
        source = Path(mod.__file__).read_text()
        assert '"schema_introspection_status"' in source

    def test_backfills_postgresql_type(self):
        mod = _load_migration_module()
        source = Path(mod.__file__).read_text()
        assert "database_type = 'postgresql'" in source

    def test_backfills_active_state(self):
        mod = _load_migration_module()
        source = Path(mod.__file__).read_text()
        assert "lifecycle_state = 'active'" in source

    def test_drops_name_column(self):
        mod = _load_migration_module()
        source = Path(mod.__file__).read_text()
        assert 'drop_column("source_database_connections", "name")' in source

    def test_drops_schema_metadata_column(self):
        mod = _load_migration_module()
        source = Path(mod.__file__).read_text()
        assert 'drop_column("source_database_connections", "schema_metadata")' in source

    def test_drops_schema_cached_at_column(self):
        mod = _load_migration_module()
        source = Path(mod.__file__).read_text()
        assert 'drop_column("source_database_connections", "schema_cached_at")' in source

    def test_creates_connection_schema_entries_table(self):
        mod = _load_migration_module()
        source = Path(mod.__file__).read_text()
        assert '"connection_schema_entries"' in source

    def test_adds_connection_id_to_sessions(self):
        mod = _load_migration_module()
        source = Path(mod.__file__).read_text()
        assert '"connection_id"' in source
        assert '"sessions"' in source

    def test_creates_lifecycle_state_index(self):
        mod = _load_migration_module()
        source = Path(mod.__file__).read_text()
        assert "ix_source_db_connections_lifecycle_state" in source
