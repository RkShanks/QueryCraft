"""Complete populated Alembic 001-009 transition matrix on PostgreSQL."""

from __future__ import annotations

import json

import pytest

from tests.migrations.migration_support import (
    DatabaseSnapshot,
    current_revision,
    database_snapshot,
    downgrade,
    revision_ids,
    upgrade,
)
from tests.migrations.scenario_support import (
    admin_seed_count,
    assert_genesis_chain,
    assert_phase6_permissions_unique,
    assert_revision_schema,
    run_head_model_repository_smoke,
    schema_evidence,
    seed_revision_state,
)

REVISIONS = revision_ids()
HISTORICAL_REVISIONS = REVISIONS[:-1]


@pytest.mark.integration
def test_empty_database_upgrades_one_revision_at_a_time(disposable_database_url: str) -> None:
    evidence_ledger: list[dict[str, int | str]] = []
    for revision in REVISIONS:
        upgrade(disposable_database_url, revision)
        assert current_revision(disposable_database_url) == revision
        assert_revision_schema(disposable_database_url, revision)
        snapshot = database_snapshot(disposable_database_url)
        evidence_entry = schema_evidence(disposable_database_url, revision)
        evidence_entry["schema_fingerprint"] = snapshot.schema_fingerprint
        evidence_ledger.append(evidence_entry)

    print(f"CHUNK06_SCHEMA_LEDGER={json.dumps(evidence_ledger, sort_keys=True)}")


@pytest.mark.integration
def test_fresh_database_upgrades_from_base_to_dynamic_head(disposable_database_url: str) -> None:
    upgrade(disposable_database_url, "head")

    assert current_revision(disposable_database_url) == REVISIONS[-1]
    assert_revision_schema(disposable_database_url, REVISIONS[-1])
    assert_genesis_chain(disposable_database_url)


@pytest.mark.integration
def test_populated_head_cycles_stepwise_to_base_and_back(disposable_database_url: str) -> None:
    upgrade(disposable_database_url, "head")
    seed_revision_state(disposable_database_url, REVISIONS[-1])

    for revision_index in range(len(REVISIONS) - 1, -1, -1):
        target = REVISIONS[revision_index - 1] if revision_index else "base"
        downgrade(disposable_database_url, target)
        expected_revision = None if target == "base" else target
        assert current_revision(disposable_database_url) == expected_revision
        assert_revision_schema(disposable_database_url, expected_revision)

    for revision in REVISIONS:
        upgrade(disposable_database_url, revision)
        assert current_revision(disposable_database_url) == revision
        assert_revision_schema(disposable_database_url, revision)

    assert_genesis_chain(disposable_database_url)
    run_head_model_repository_smoke(disposable_database_url)


@pytest.mark.integration
@pytest.mark.parametrize("revision", REVISIONS)
def test_each_revision_cycles_populated_state(disposable_database_url: str, revision: str) -> None:
    revision_index = REVISIONS.index(revision)
    parent = REVISIONS[revision_index - 1] if revision_index else "base"
    upgrade(disposable_database_url, revision)
    assert_revision_schema(disposable_database_url, revision)
    seed_revision_state(disposable_database_url, revision)
    before_downgrade = database_snapshot(disposable_database_url)

    downgrade(disposable_database_url, parent)

    expected_parent = None if parent == "base" else parent
    assert current_revision(disposable_database_url) == expected_parent
    assert_revision_schema(disposable_database_url, expected_parent)
    _assert_documented_downgrade_behavior(disposable_database_url, revision, before_downgrade)

    upgrade(disposable_database_url, revision)
    assert current_revision(disposable_database_url) == revision
    assert_revision_schema(disposable_database_url, revision)
    _assert_revision_seed_idempotency(disposable_database_url, revision)


@pytest.mark.integration
@pytest.mark.parametrize("historical_revision", HISTORICAL_REVISIONS)
def test_each_historical_revision_upgrades_directly_to_dynamic_head(
    disposable_database_url: str,
    historical_revision: str,
) -> None:
    upgrade(disposable_database_url, historical_revision)
    seed_revision_state(disposable_database_url, historical_revision)

    upgrade(disposable_database_url, "head")

    assert current_revision(disposable_database_url) == REVISIONS[-1]
    assert_revision_schema(disposable_database_url, REVISIONS[-1])
    assert_genesis_chain(disposable_database_url)


@pytest.mark.integration
@pytest.mark.parametrize("historical_target", HISTORICAL_REVISIONS)
def test_populated_head_downgrades_to_each_historical_target(
    disposable_database_url: str,
    historical_target: str,
) -> None:
    upgrade(disposable_database_url, "head")
    seed_revision_state(disposable_database_url, REVISIONS[-1])

    downgrade(disposable_database_url, historical_target)

    assert current_revision(disposable_database_url) == historical_target
    assert_revision_schema(disposable_database_url, historical_target)


def _assert_documented_downgrade_behavior(
    database_url: str,
    revision: str,
    before_downgrade: DatabaseSnapshot,
) -> None:
    after_downgrade = database_snapshot(database_url)
    before_counts = dict(before_downgrade.row_counts)
    after_counts = dict(after_downgrade.row_counts)
    if revision == "001":
        assert set(after_counts) == {"alembic_version"}
        return
    if revision == "002":
        assert after_counts["users"] == before_counts["users"] - 1
    if int(revision) >= 3:
        assert after_counts["accepted_queries"] == before_counts["accepted_queries"]
    if revision == "004":
        assert "sessions" not in after_counts
    if revision == "006":
        assert "connection_schema_entries" not in after_counts
        assert after_counts["database_connections"] == before_counts["source_database_connections"]
    if revision == "007":
        assert "roles" not in after_counts
        assert after_counts["users"] == before_counts["users"]
    if revision == "008":
        assert {"role_quotas", "detection_threshold_config"}.isdisjoint(after_counts)
        assert after_counts["roles"] == before_counts["roles"]
    if revision == "009":
        before_rows = dict(before_downgrade.row_fingerprints)
        after_rows = dict(after_downgrade.row_fingerprints)
        before_rows.pop("alembic_version")
        after_rows.pop("alembic_version")
        assert after_rows == before_rows


def _assert_revision_seed_idempotency(database_url: str, revision: str) -> None:
    if revision == "002":
        assert admin_seed_count(database_url) == 1
    if revision == "007":
        assert_genesis_chain(database_url)
    if revision == "008":
        assert_phase6_permissions_unique(database_url)
