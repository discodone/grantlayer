"""GL-292 — pytest-cov Coverage Baseline scope guard.

Verifies that the coverage infrastructure is correctly wired:
  - pytest-cov is importable (installed in the environment)
  - backend/requirements-dev.txt declares pytest-cov>=4.0.0
  - pytest.ini addopts contains --cov for automatic coverage reporting
  - .github/workflows contains a coverage step with --cov-fail-under=60
"""
import importlib
import pathlib
import re

import pytest


@pytest.mark.scope_guard
class TestCoverageBaseline:
    def test_pytest_cov_importable(self):
        """pytest-cov must be installed."""
        mod = importlib.import_module("pytest_cov")
        assert mod is not None

    def test_requirements_dev_declares_pytest_cov(self):
        """backend/requirements-dev.txt must pin pytest-cov>=4.0.0."""
        req_file = pathlib.Path("backend/requirements-dev.txt")
        assert req_file.exists(), "backend/requirements-dev.txt not found"
        content = req_file.read_text()
        assert "pytest-cov" in content, "pytest-cov missing from requirements-dev.txt"
        match = re.search(r"pytest-cov>=(\d+)", content)
        assert match, "pytest-cov version specifier not found"
        major = int(match.group(1))
        assert major >= 4, f"pytest-cov must be >=4.0.0, found {match.group(0)}"

    def test_pytest_ini_has_cov_addopts(self):
        """pytest.ini addopts must NOT contain --cov (breaks pytest-xdist -n auto).

        GL-291/292: --cov in addopts is incompatible with xdist. Coverage is
        run explicitly: python3 -m pytest --cov=backend/src ...
        """
        ini_file = pathlib.Path("pytest.ini")
        assert ini_file.exists(), "pytest.ini not found"
        content = ini_file.read_text()
        assert "--cov" not in content, (
            "pytest.ini addopts must NOT contain --cov — it breaks pytest-xdist. "
            "Run coverage explicitly: pytest --cov=backend/src ..."
        )

    def test_ci_workflow_has_coverage_with_fail_under(self):
        """CI workflow must reference --cov and --cov-fail-under to enforce threshold."""
        workflow_dir = pathlib.Path(".github/workflows")
        assert workflow_dir.exists(), ".github/workflows directory not found"
        yml_files = list(workflow_dir.glob("*.yml"))
        assert yml_files, "No CI workflow files found"
        has_cov = False
        has_fail_under = False
        for wf in yml_files:
            content = wf.read_text()
            if "--cov" in content:
                has_cov = True
            if "--cov-fail-under" in content:
                has_fail_under = True
        assert has_cov, "No CI workflow references --cov for coverage reporting"
        assert has_fail_under, "No CI workflow enforces --cov-fail-under threshold"
