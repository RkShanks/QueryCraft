"""Shared frontend/backend row-filter validation contract for CHUNK-15."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.evaluator.schema_context import Column, SchemaContext, Table
from app.services.policy_enforcement import PolicyEnforcementService

CORPUS_PATH = Path(__file__).resolve().parents[3] / "contracts" / "row-filter-validation-corpus.json"
CORPUS = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def _schema_context() -> SchemaContext:
    return SchemaContext(
        tables=[
            Table(
                name=table["name"],
                columns=[Column(name=column, type="text") for column in table["columns"]],
            )
            for table in CORPUS["schema"]["tables"]
        ]
    )


@pytest.mark.parametrize("case", CORPUS["cases"], ids=lambda case: case["id"])
def test_shared_row_filter_corpus_matches_backend_authority(case: dict[str, object]) -> None:
    def validate() -> None:
        PolicyEnforcementService.validate_row_filter(
            str(case["filter"]),
            _schema_context(),
            str(case["table"]),
            dialect=str(case["dialect"]),
        )

    if case["valid"]:
        validate()
        return

    with pytest.raises(ValueError, match="^filter_validation_failed$"):
        validate()
