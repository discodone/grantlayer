"""GL-340 — Repo hygiene and SDK consolidation.

Tests:
- sdk/python/ has been removed (canonical SDK is sdk/grantlayer/).
- sdk/grantlayer/ package exists with pyproject.toml.
- README license badge matches LICENSE file (both Apache 2.0).
- .gitignore covers coverage.json and logs/.
- sdk/grantlayer/ imports cleanly.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestSdkConsolidation(unittest.TestCase):
    def test_sdk_python_removed(self):
        """sdk/python/ must be deleted — canonical SDK is sdk/grantlayer/."""
        self.assertFalse(
            (REPO_ROOT / "sdk" / "python").exists(),
            "sdk/python/ must be removed; use sdk/grantlayer/ as the canonical SDK",
        )

    def test_canonical_sdk_package_exists(self):
        """sdk/grantlayer/ must exist as the canonical Python SDK package."""
        self.assertTrue(
            (REPO_ROOT / "sdk" / "grantlayer" / "client.py").exists(),
            "sdk/grantlayer/client.py must exist",
        )

    def test_canonical_sdk_has_pyproject(self):
        """sdk/pyproject.toml must exist so the package is pip-installable."""
        self.assertTrue(
            (REPO_ROOT / "sdk" / "pyproject.toml").exists(),
            "sdk/pyproject.toml must exist",
        )

    def test_canonical_sdk_importable(self):
        """sdk.grantlayer package must import without errors."""
        import sys
        sdk_parent = str(REPO_ROOT / "sdk")
        sys.path.insert(0, sdk_parent)
        try:
            import importlib
            mod = importlib.import_module("grantlayer")
            self.assertIsNotNone(mod)
        finally:
            sys.path.remove(sdk_parent)


class TestLicenseBadge(unittest.TestCase):
    def test_readme_license_badge_is_apache(self):
        """README.md license badge must say Apache 2.0 (not MIT)."""
        readme = (REPO_ROOT / "README.md").read_text()
        self.assertNotIn(
            "license-MIT", readme,
            "README badge says MIT but LICENSE is Apache 2.0 — badge must match",
        )
        self.assertIn("Apache", readme, "README must reference Apache license")

    def test_license_file_is_apache(self):
        """LICENSE file must contain Apache License text."""
        lic = (REPO_ROOT / "LICENSE").read_text()
        self.assertIn("Apache License", lic)
        self.assertIn("Version 2.0", lic)


class TestGitignoreCoverage(unittest.TestCase):
    def test_gitignore_covers_coverage_json(self):
        """.gitignore must exclude coverage.json."""
        gi = (REPO_ROOT / ".gitignore").read_text()
        self.assertIn("coverage.json", gi)

    def test_gitignore_covers_logs(self):
        """.gitignore must exclude logs/ directory."""
        gi = (REPO_ROOT / ".gitignore").read_text()
        self.assertIn("logs/", gi)

    def test_gitignore_covers_stray_pip_file(self):
        """.gitignore must exclude the =0.19.0 pip-redirect artifact."""
        gi = (REPO_ROOT / ".gitignore").read_text()
        self.assertIn("=0.19.0", gi)
