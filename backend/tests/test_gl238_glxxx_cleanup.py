"""GL-238: GL-XXX reference cleanup — validation tests.

Verifies that public-facing Python source files (backend/src/) and
key config files no longer contain GL-NNN references in comments or
docstrings. Internal paths (docs/internal/, backend/tests/) are excluded.
"""

from __future__ import annotations

import re
import pathlib
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

_GL_RE = re.compile(r"GL-\d+")

_AUTHORIZED_SOURCE_DIRS = [
    _REPO_ROOT / "backend" / "src",
]

_AUTHORIZED_CONFIG_FILES = [
    _REPO_ROOT / "CHANGELOG.md",
    _REPO_ROOT / "requirements.txt",
    _REPO_ROOT / "docker-compose.postgres.yml",
    _REPO_ROOT / ".github" / "workflows" / "postgres-ci.yml",
]

_EXCLUDED_DIRS = {
    _REPO_ROOT / "docs" / "internal",
    _REPO_ROOT / "backend" / "tests",
    _REPO_ROOT / "docs" / "examples",
}


def _collect_py_files():
    files = []
    for src_dir in _AUTHORIZED_SOURCE_DIRS:
        for p in sorted(src_dir.rglob("*.py")):
            files.append(p)
    return files


def _find_gl_in_comments_and_docstrings(path: pathlib.Path) -> list[tuple[int, str]]:
    """Return (lineno, line) pairs where GL-NNN appears in a comment or docstring."""
    hits = []
    in_multiline = False
    quote_char = None
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            stripped = line.strip()

            # Detect entering/leaving multiline string
            for q in ('"""', "'''"):
                count = stripped.count(q)
                if count >= 2:
                    # Opens and closes on same line — treat as string literal, skip
                    pass
                elif count == 1:
                    if not in_multiline:
                        in_multiline = True
                        quote_char = q
                    elif quote_char == q:
                        in_multiline = False
                        quote_char = None

            # Check comments (#...)
            if "#" in line:
                comment_part = line[line.index("#"):]
                if _GL_RE.search(comment_part):
                    hits.append((lineno, line.rstrip()))

            # Check docstring lines
            elif in_multiline:
                if _GL_RE.search(stripped):
                    hits.append((lineno, line.rstrip()))

            # Check module docstring on first few lines (line 1 typically)
            elif lineno <= 3 and '"""' in line and _GL_RE.search(line):
                hits.append((lineno, line.rstrip()))

    return hits


class TestGl238GlxxxCleanupPySources(unittest.TestCase):
    """Python source files in backend/src/ must not have GL-NNN in comments/docstrings."""

    def _check_file(self, path):
        hits = _find_gl_in_comments_and_docstrings(path)
        rel = path.relative_to(_REPO_ROOT)
        self.assertEqual(
            hits,
            [],
            f"{rel} still contains GL-NNN references in comments/docstrings:\n"
            + "\n".join(f"  line {ln}: {txt}" for ln, txt in hits),
        )

    def test_backend_src_py_files_clean(self):
        py_files = _collect_py_files()
        self.assertGreater(len(py_files), 10, "Expected at least 10 Python source files")
        for path in py_files:
            with self.subTest(file=str(path.relative_to(_REPO_ROOT))):
                self._check_file(path)


class TestGl238GlxxxCleanupConfigFiles(unittest.TestCase):
    """Key config/root files must not contain GL-NNN references."""

    def _assert_no_gl(self, path: pathlib.Path):
        rel = path.relative_to(_REPO_ROOT)
        if not path.exists():
            self.skipTest(f"{rel} does not exist")
        content = path.read_text(encoding="utf-8")
        hits = [
            (i + 1, line.rstrip())
            for i, line in enumerate(content.splitlines())
            if _GL_RE.search(line)
        ]
        self.assertEqual(
            hits,
            [],
            f"{rel} still contains GL-NNN references:\n"
            + "\n".join(f"  line {ln}: {txt}" for ln, txt in hits),
        )

    def test_changelog_clean(self):
        self._assert_no_gl(_REPO_ROOT / "CHANGELOG.md")

    def test_requirements_clean(self):
        self._assert_no_gl(_REPO_ROOT / "requirements.txt")

    def test_docker_compose_postgres_clean(self):
        self._assert_no_gl(_REPO_ROOT / "docker-compose.postgres.yml")

    def test_postgres_ci_workflow_clean(self):
        self._assert_no_gl(_REPO_ROOT / ".github" / "workflows" / "postgres-ci.yml")


if __name__ == "__main__":
    unittest.main()
