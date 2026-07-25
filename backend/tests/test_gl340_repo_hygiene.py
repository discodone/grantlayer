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

        This matches pip only; the JS SDK's npm package name is guarded
        separately by TestSdkInstallabilityClaims.
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


class TestSdkInstallabilityClaims(unittest.TestCase):
    """Public claims must match what is actually installable.

    Actual state: the Python SDK is published on PyPI (`pip install
    grantlayer` works for anyone); the TypeScript SDK is NOT published to
    npm and is built from source. Same spirit as the licence guard: any
    doc or site page that states how to obtain an SDK must state something
    that is literally true today.

    When the TS SDK is really published to npm, delete
    NPM_PACKAGE_PUBLISHED = False below (flip it to True) and the
    npm-instruction ban lifts itself.
    """

    NPM_PACKAGE_PUBLISHED = False

    _DOC_SUFFIXES = (".md", ".html", ".txt")

    def _doc_files(self):
        roots = [REPO_ROOT / "sdk", REPO_ROOT / "sdk-js",
                 REPO_ROOT / "docs", REPO_ROOT / "site"]
        files = [REPO_ROOT / "README.md"]
        for root in roots:
            files.extend(p for p in sorted(root.rglob("*"))
                         if p.is_file() and p.suffix in self._DOC_SUFFIXES)
        return files

    def _offending_lines(self, pattern: re.Pattern) -> list[str]:
        offenders = []
        for path in self._doc_files():
            for lineno, line in enumerate(
                path.read_text(errors="replace").splitlines(), 1
            ):
                if pattern.search(line):
                    rel = path.relative_to(REPO_ROOT)
                    offenders.append(f"{rel}:{lineno}: {line.strip()}")
        return offenders

    def test_no_npm_registry_install_instruction_while_unpublished(self):
        """`npm install grantlayer-sdk` (registry form) is banned while the
        package is not on npm. Tarball installs (`npm install
        ./grantlayer-sdk-<version>.tgz`) do not match and stay legal."""
        if self.NPM_PACKAGE_PUBLISHED:
            self.skipTest("TS SDK is published to npm; instruction is legal")
        pattern = re.compile(r"npm\s+install\s+grantlayer-sdk\s*$")
        offenders = self._offending_lines(pattern)
        self.assertEqual(
            offenders, [],
            "docs instruct `npm install grantlayer-sdk` but the package is "
            "not published to npm — build-from-source is the only true "
            "install path:\n" + "\n".join(offenders),
        )

    def test_no_fictional_scoped_npm_package_name(self):
        """Nothing may reference \"@grantlayer/sdk\" — that package name
        never existed on npm or in this repo (the real name is
        grantlayer-sdk)."""
        offenders = self._offending_lines(re.compile(r"@grantlayer/sdk\b"))
        self.assertEqual(
            offenders, [],
            "found references to the fictional npm package "
            "'@grantlayer/sdk':\n" + "\n".join(offenders),
        )

    def test_python_install_instruction_present_and_correct(self):
        """The Python SDK is genuinely on PyPI; sdk/README.md must carry the
        real install command."""
        readme = (REPO_ROOT / "sdk" / "README.md").read_text()
        self.assertIn(
            "pip install grantlayer", readme,
            "sdk/README.md must document `pip install grantlayer` — the "
            "package is published on PyPI under that name",
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


class TestVersionDeclarationConsistency(unittest.TestCase):
    """GL-394 — user-visible backend version declarations must agree.

    ``/health``'s ``_VERSION`` is the anchor (it matches the CHANGELOG's
    authoritative 0.x line). The FastAPI/OpenAPI metadata in ``app.py`` and the
    hand-maintained ``docs/openapi.yaml`` contract are user-visible surfaces of
    the same backend and must declare the same version, so the three cannot
    drift apart again (gl-391 bumped ``/health`` to 0.19.0 but left ``app.py``
    at 0.1.0 and ``docs/openapi.yaml`` at 0.203b.0-developer-preview).
    """

    def _health_version(self) -> str:
        src = (REPO_ROOT / "backend" / "src" / "api" / "routers" / "health.py").read_text()
        m = re.search(r'^_VERSION\s*=\s*"([^"]+)"', src, re.M)
        assert m is not None, "health.py must declare _VERSION"
        return m.group(1)

    def test_app_metadata_version_matches_health(self):
        """FastAPI(version=...) in app.py must equal health._VERSION."""
        src = (REPO_ROOT / "backend" / "src" / "api" / "app.py").read_text()
        found = re.findall(r'version="([^"]+)"', src)
        self.assertEqual(
            len(found), 1,
            "expected exactly one version=\"...\" declaration in app.py",
        )
        self.assertEqual(
            found[0], self._health_version(),
            "app.py FastAPI metadata version must match health._VERSION — "
            "these are two user-visible declarations of the same backend",
        )

    def test_openapi_contract_version_matches_health(self):
        """docs/openapi.yaml info.version must equal health._VERSION."""
        # Regex on the info block instead of a yaml parse: pyyaml is not
        # installed in every CI job (see test_gl230 ignore note).
        text = (REPO_ROOT / "docs" / "openapi.yaml").read_text()
        info_block = text.split("\npaths:")[0]
        m = re.search(r'^  version:\s*"([^"]+)"', info_block, re.M)
        self.assertIsNotNone(m, "docs/openapi.yaml must declare info.version")
        self.assertEqual(
            m.group(1), self._health_version(),
            "docs/openapi.yaml info.version must match health._VERSION — the "
            "contract file is hand-maintained and drifts silently otherwise",
        )

    def test_root_pyproject_version_matches_health(self):
        """Root pyproject.toml [project].version must equal health._VERSION.

        The CHANGELOG pins the 0.x line as authoritative and calls the v1.x
        artifacts historical; the root package (never published — the PyPI
        'grantlayer' dist builds from sdk/, which versions independently)
        must not keep a contradicting 1.x declaration alive.
        """
        with (REPO_ROOT / "pyproject.toml").open("rb") as fh:
            data = tomllib.load(fh)
        self.assertEqual(
            data["project"]["version"], self._health_version(),
            "root pyproject.toml version must match health._VERSION — the "
            "CHANGELOG's 0.x scheme is authoritative repo-wide",
        )
