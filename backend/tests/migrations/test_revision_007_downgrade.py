"""Revision 007 downgrade safety against populated PostgreSQL."""

from __future__ import annotations

import pytest

from tests.migrations.migration_support import current_revision, database_snapshot, downgrade, revision_ids, upgrade
from tests.migrations.scenario_support import (
    assert_revision_schema,
    assign_valid_local_hashes,
    pre_revision_007_rows_are_coherent,
    seed_local_only_revision_007_state,
    seed_revision_state,
)

EXPECTED_DOWNGRADE_REFUSAL = (
    "Revision 007 downgrade blocked: remove incompatible users or assign valid local authentication "
    "hashes before retrying."
)
PROHIBITED_ERROR_TERMS = (
    "username",
    "email",
    "subject",
    "provider",
    "group",
    "token",
    "certificate",
    "role",
    "connection",
    "password",
)


@pytest.mark.integration
def test_head_to_006_refuses_incompatible_users_atomically_then_allows_explicit_remediation(
    disposable_database_url: str,
) -> None:
    head_revision = revision_ids()[-1]
    upgrade(disposable_database_url, "head")
    assert current_revision(disposable_database_url) == head_revision
    seed_revision_state(disposable_database_url, head_revision, incompatible_user_count=2)
    before_refusal = database_snapshot(disposable_database_url)

    _assert_downgrade_refusal(disposable_database_url, "006")
    assert current_revision(disposable_database_url) == head_revision
    assert database_snapshot(disposable_database_url) == before_refusal

    assign_valid_local_hashes(disposable_database_url)
    downgrade(disposable_database_url, "006")
    assert current_revision(disposable_database_url) == "006"
    assert_revision_schema(disposable_database_url, "006")
    assert pre_revision_007_rows_are_coherent(disposable_database_url)

    upgrade(disposable_database_url, "head")
    assert current_revision(disposable_database_url) == head_revision


@pytest.mark.integration
def test_direct_007_to_006_refuses_one_incompatible_user_without_mutation(
    disposable_database_url: str,
) -> None:
    upgrade(disposable_database_url, "007")
    assert current_revision(disposable_database_url) == "007"
    seed_revision_state(disposable_database_url, "007", incompatible_user_count=1)
    before_refusal = database_snapshot(disposable_database_url)

    _assert_downgrade_refusal(disposable_database_url, "006")

    assert current_revision(disposable_database_url) == "007"
    assert database_snapshot(disposable_database_url) == before_refusal


@pytest.mark.integration
def test_populated_local_only_007_downgrades_to_006(disposable_database_url: str) -> None:
    upgrade(disposable_database_url, "007")
    assert current_revision(disposable_database_url) == "007"
    seed_local_only_revision_007_state(disposable_database_url)

    downgrade(disposable_database_url, "006")

    assert current_revision(disposable_database_url) == "006"
    assert_revision_schema(disposable_database_url, "006")
    assert pre_revision_007_rows_are_coherent(disposable_database_url)


def _assert_downgrade_refusal(database_url: str, target: str) -> None:
    with pytest.raises(RuntimeError) as refusal:
        downgrade(database_url, target)
    refusal_message = str(refusal.value)
    assert refusal_message == EXPECTED_DOWNGRADE_REFUSAL
    assert all(term not in refusal_message.casefold() for term in PROHIBITED_ERROR_TERMS)
