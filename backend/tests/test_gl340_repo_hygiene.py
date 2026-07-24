"""GL-340 — Repo hygiene and SDK consolidation.

Tests:
- sdk/python/ has been removed (canonical SDK is sdk/grantlayer/).
- sdk/grantlayer/ package exists with pyproject.toml.
- README license badge matches LICENSE file (both Apache 2.0).
- .gitignore covers coverage.json and logs/.
- sdk/grantlayer/ imports cleanly.
"""

from __future__ import annotations

import json
import re
import tomllib
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


class TestApacheLicenseConsistency(unittest.TestCase):
    """The licence is Apache-2.0 everywhere it is stated, not just in
    README + LICENSE.

    The original guard covered only those two files, which let package
    metadata (root + both SDKs) and every site/ page drift to MIT
    unnoticed. This class covers the whole public surface: any location
    that states a licence must state Apache-2.0, and site/ must not name
    any other licence anywhere.
    """

    # Licence names that must never appear as a licence claim on the
    # public surface. Word-bounded, case-sensitive: matches the badge/
    # metadata spellings ("MIT", "GPL-3.0") without tripping on prose
    # like "submit" or "permit".
    _FORBIDDEN_LICENSES = ("MIT", "GPL", "LGPL", "AGPL", "BSD", "MPL", "ISC")
    _FORBIDDEN_RE = re.compile(r"\b(" + "|".join(_FORBIDDEN_LICENSES) + r")\b")
    _LIC_SPAN_RE = re.compile(r'<span class="lic">([^<]*)</span>')

    @staticmethod
    def _pyproject_license_text(path: Path) -> str | None:
        """Return the [project] license as a string, or None if absent.

        Accepts both the table form (license = {text = "..."}) and the
        PEP 639 string form (license = "...")."""
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        lic = data.get("project", {}).get("license")
        if lic is None:
            return None
        if isinstance(lic, dict):
            return lic.get("text")
        return str(lic)

    def test_root_pyproject_license_is_apache(self):
        """Root pyproject.toml package metadata must declare Apache-2.0."""
        lic = self._pyproject_license_text(REPO_ROOT / "pyproject.toml")
        self.assertIsNotNone(lic, "root pyproject.toml must declare a license")
        self.assertIn(
            "Apache", lic,
            f"root pyproject.toml declares {lic!r} but LICENSE is Apache 2.0",
        )

    def test_sdk_pyproject_declares_apache_license(self):
        """sdk/pyproject.toml must declare a licence, and it must be Apache."""
        lic = self._pyproject_license_text(REPO_ROOT / "sdk" / "pyproject.toml")
        self.assertIsNotNone(
            lic,
            "sdk/pyproject.toml declares no license — the SDK package "
            "metadata must state Apache-2.0",
        )
        self.assertIn(
            "Apache", lic,
            f"sdk/pyproject.toml declares {lic!r} but LICENSE is Apache 2.0",
        )

    def test_sdk_js_package_license_is_apache(self):
        """sdk-js/package.json must declare the Apache-2.0 SPDX id."""
        pkg = json.loads((REPO_ROOT / "sdk-js" / "package.json").read_text())
        self.assertEqual(
            pkg.get("license"), "Apache-2.0",
            f"sdk-js/package.json declares {pkg.get('license')!r} but "
            "LICENSE is Apache 2.0",
        )

    def test_site_never_names_another_license(self):
        """No page under site/ may name a non-Apache licence anywhere."""
        offenders = []
        for path in sorted((REPO_ROOT / "site").rglob("*")):
            if path.suffix not in (".html", ".json", ".md", ".txt", ".js", ".css"):
                continue
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                if self._FORBIDDEN_RE.search(line):
                    rel = path.relative_to(REPO_ROOT)
                    offenders.append(f"{rel}:{lineno}: {line.strip()}")
        self.assertEqual(
            offenders, [],
            "site/ names a licence other than Apache-2.0 — the project "
            "is Apache-2.0 everywhere:\n" + "\n".join(offenders),
        )

    def test_site_license_footers_say_apache(self):
        """Every licence footer/badge on the site must say Apache 2.0."""
        spans = []
        for path in sorted((REPO_ROOT / "site").rglob("*.html")):
            for match in self._LIC_SPAN_RE.finditer(path.read_text()):
                spans.append((path.relative_to(REPO_ROOT), match.group(1)))
        self.assertTrue(spans, "expected at least one licence footer in site/")
        wrong = [f"{rel}: {text!r}" for rel, text in spans if "Apache" not in text]
        self.assertEqual(
            wrong, [],
            "site/ licence footers must say Apache 2.0:\n" + "\n".join(wrong),
        )


class TestSdkDistributionNameConsistency(unittest.TestCase):
    """The PyPI distribution name matches the import name and the docs.

    The module has always been `grantlayer` (sdk/grantlayer/), and the
    PyPI trusted publisher is registered for the project `grantlayer`.
    A distribution named anything else would make `pip install X` and
    `import Y` disagree, and the publish workflow would be rejected by
    PyPI. Same spirit as the licence guard above: any place that states
    the install name must state the same name the metadata declares.
    """

    EXPECTED_DIST_NAME = "grantlayer"

    def _sdk_pyproject(self) -> dict:
        with (REPO_ROOT / "sdk" / "pyproject.toml").open("rb") as fh:
            return tomllib.load(fh)

    def test_sdk_distribution_name_matches_import_name(self):
        """sdk/pyproject.toml [project] name must be `grantlayer`."""
        name = self._sdk_pyproject()["project"]["name"]
        self.assertEqual(
            name, self.EXPECTED_DIST_NAME,
            f"sdk/pyproject.toml declares distribution {name!r} but the "
            f"import package is sdk/{self.EXPECTED_DIST_NAME}/ and the PyPI "
            f"trusted publisher is registered for {self.EXPECTED_DIST_NAME!r}",
        )

    def test_import_package_dir_matches_distribution_name(self):
        """The package directory named by the distribution must exist."""
        self.assertTrue(
            (REPO_ROOT / "sdk" / self.EXPECTED_DIST_NAME / "__init__.py").exists(),
            f"sdk/{self.EXPECTED_DIST_NAME}/ must be the import package",
        )

    def test_no_doc_instructs_installing_old_distribution_name(self):
        """No doc may say `pip install grantlayer-sdk` (the pre-rename name).

        `npm install grantlayer-sdk` stays legitimate — that is the JS SDK's
        npm package, a different registry — so this matches pip only.
        """
        old_install = re.compile(r"pip\s+install\s+grantlayer-sdk\b")
        offenders = []
        roots = [REPO_ROOT / "sdk", REPO_ROOT / "docs", REPO_ROOT / "site"]
        candidates = [REPO_ROOT / "README.md"]
        for root in roots:
            candidates.extend(sorted(root.rglob("*")))
        for path in candidates:
            if not path.is_file():
                continue
            if path.suffix not in (".md", ".html", ".txt", ".py", ".toml", ".json"):
                continue
            for lineno, line in enumerate(
                path.read_text(errors="replace").splitlines(), 1
            ):
                if old_install.search(line):
                    rel = path.relative_to(REPO_ROOT)
                    offenders.append(f"{rel}:{lineno}: {line.strip()}")
        self.assertEqual(
            offenders, [],
            "docs instruct installing the retired distribution name "
            "'grantlayer-sdk' — the PyPI distribution is 'grantlayer':\n"
            + "\n".join(offenders),
        )


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
