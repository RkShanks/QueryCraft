"""T-126: Schemathesis contract test for /admin/refresh-schema.

Loads the static OpenAPI 3.0.3 contract. Uses session cookie for admin auth.

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
    / "specs" / "001-core-text-to-sql" / "contracts" / "openapi.yaml"
)
schema = schemathesis.openapi.from_path(
    str(_schema_path),
    app=create_app(),
)


@schema.parametrize(endpoint="/admin/refresh-schema")
def test_admin_contract(case, contract_session_cookie):
    """Property-based contract test for Admin endpoints."""
    case.call_and_validate(
        cookies={"session_id": contract_session_cookie},
        headers={"origin": "http://test"},
    )
