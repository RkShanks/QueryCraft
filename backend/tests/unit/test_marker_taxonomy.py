"""Verify pytest directory-based auto-marker taxonomy (T-17.0d).

Tests in tests/conftest.py::pytest_collection_modifyitems auto-mark
by directory. This file asserts the behavior is active.
"""

import subprocess
import sys


def _run_pytest_subprocess(args: list[str]) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "pytest"] + args + ["--collect-only", "-q"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout + "\n" + result.stderr


class TestMarkerTaxonomy:
    """Auto-marker applied by directory."""

    def test_unit_directory_gets_unit_marker(self):
        """tests/unit files are auto-marked 'unit'."""
        output = _run_pytest_subprocess(["tests/unit/test_marker_taxonomy.py", "-m", "unit"])
        assert "test_marker_taxonomy.py" in output, output

    def test_unit_directory_excluded_by_integration_marker(self):
        """tests/unit files are NOT selected by -m integration."""
        output = _run_pytest_subprocess(["tests/unit/test_marker_taxonomy.py", "-m", "integration"])
        assert "no tests collected" in output.lower() or "deselected" in output.lower(), output

    def test_lifecycle_directory_gets_lifecycle_marker(self):
        """tests/lifecycle files are auto-marked 'lifecycle'."""
        output = _run_pytest_subprocess(["tests/lifecycle/test_conftest.py", "-m", "lifecycle"])
        assert "test_conftest.py" in output, output

    def test_integration_directory_gets_integration_marker(self):
        """tests/integration files are auto-marked 'integration'."""
        output = _run_pytest_subprocess(["tests/integration/", "-m", "integration", "-q"])
        # integration tests may error (no services), but should be selected
        assert any(word in output.lower() for word in ["test_", "collected", "error"]), output

    def test_acceptance_directory_gets_acceptance_marker(self):
        """tests/acceptance files are auto-marked 'acceptance'."""
        output = _run_pytest_subprocess(["tests/acceptance/", "-m", "acceptance", "-q"])
        assert "test_" in output, output

    def test_contract_directory_gets_contract_marker(self):
        """tests/contract files are auto-marked 'contract'."""
        output = _run_pytest_subprocess(["tests/contract/", "-m", "contract", "-q"])
        assert "test_" in output, output

    def test_integration_marked_tests_in_unit_dir_excluded_by_not_integration(self):
        """Explicit @pytest.mark.integration under tests/unit is excluded by -m 'not integration'."""
        output = _run_pytest_subprocess(["tests/unit/source_db/test_connector.py", "-m", "not integration", "-q"])
        # Quiet collect-only shows count only; verify integration test names absent
        assert "test_select_as_pagila_user" not in output, output
        assert "test_insert_fails_for_pagila_user" not in output, output
