"""T-124 + T-125: Schemathesis contract tests for /query endpoints.

Loads the static OpenAPI 3.0.3 contract. Uses a pre-authenticated session
cookie. Hermetic: StubLLM is already wired in query.py.

Note: schemathesis tests are run on demand (`-m contract`) because they can
be flaky with async SQLAlchemy pools across multiple event loops.
"""

import os
import pathlib

import pytest
import schemathesis

from app.main import create_app

pytestmark = pytest.mark.contract

if not os.environ.get("SCHEMATHESIS_RUN"):
    pytest.skip(
        "Schemathesis tests run on demand: SCHEMATHESIS_RUN=1 pytest -m contract",
        allow_module_level=True,
    )

_schema_path = (
    pathlib.Path(__file__).resolve().parent.parent.parent.parent
    / "specs"
    / "001-core-text-to-sql"
    / "contracts"
    / "openapi.yaml"
)
schema = schemathesis.openapi.from_path(
    str(_schema_path),
    app=create_app(),
)


@schema.parametrize(endpoint="/query/submit")
def test_query_submit_contract(case, contract_session_cookie):
    """Property-based contract test for POST /query/submit."""
    case.call_and_validate(
        cookies={"session_id": contract_session_cookie},
        headers={"origin": "http://test"},
    )


@schema.parametrize(endpoint="/query/reject")
def test_query_reject_contract(case, contract_session_cookie):
    """Property-based contract test for POST /query/reject."""
    case.call_and_validate(
        cookies={"session_id": contract_session_cookie},
        headers={"origin": "http://test"},
    )


@schema.parametrize(endpoint="/query/regenerate")
def test_query_regenerate_contract(case, contract_session_cookie):
    """Property-based contract test for POST /query/regenerate."""
    case.call_and_validate(
        cookies={"session_id": contract_session_cookie},
        headers={"origin": "http://test"},
    )
