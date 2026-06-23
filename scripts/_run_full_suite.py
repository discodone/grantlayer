#!/usr/bin/env python3
"""Full backend suite runner (unittest), excluding doc-guard modules.

Invoked by scripts/run-full-backend-suite.sh.

Why this exists instead of a bare ``python3 -m unittest discover``:

  * The functional gate (``pytest -m "not doc_guard and not scope_guard"``)
    excludes doc-guard tests via pytest markers applied in
    ``backend/tests/conftest.py``. ``unittest discover`` does NOT load
    conftest.py and cannot apply those markers, so it would sweep in ~121
    doc-guard modules.
  * Doc-guard tests assert that public-snapshot documentation artifacts
    (e.g. ``sdk/python/grantlayer_client.py``, public CHANGELOG content)
    exist and contain expected phrases. Those artifacts are produced by
    ``scripts/build-clean-public-snapshot.sh`` and are intentionally absent
    from the internal working tree, so the doc-guard tests cannot pass here.
    They are validated separately during the public-snapshot push.

This runner therefore discovers the full backend suite and excludes exactly
the modules in the canonical ``DOC_GUARD_MODULES`` list — the same set the
pytest gate excludes. The exclusion is logged (not hidden), and the excluded
module names are printed so nothing is silently dropped.

It does NOT alter, skip, or weaken any functional test — in particular all
tenant-scope / control-plane enforcement tests are functional (not doc-guard)
and run normally.
"""

from __future__ import annotations

import sys
import unittest

# backend/tests is importable as a package because the repo root is on sys.path
# (the script is run from the repo root). Add backend/tests for the module list.
sys.path.insert(0, "backend/tests")

from _doc_guard_modules import DOC_GUARD_MODULES  # noqa: E402


def _short_module_name(test: unittest.TestCase) -> str:
    """Return the bare module name, e.g. 'test_gl147_minimal_python_sdk'."""
    return type(test).__module__.rsplit(".", 1)[-1]


def _filter_suite(suite: unittest.TestSuite, excluded: set[str]) -> unittest.TestSuite:
    """Recursively drop tests whose module is in ``excluded``."""
    kept = unittest.TestSuite()
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            kept.addTest(_filter_suite(item, excluded))
        else:
            if _short_module_name(item) not in excluded:
                kept.addTest(item)
    return kept


def main() -> int:
    loader = unittest.TestLoader()
    full = loader.discover("backend/tests")

    excluded_present = sorted(DOC_GUARD_MODULES)
    print(
        f"Excluding {len(excluded_present)} doc-guard modules "
        f"(public-snapshot artifact checks; same set the pytest gate excludes):"
    )
    for name in excluded_present:
        print(f"  - {name}")
    print("")

    filtered = _filter_suite(full, set(DOC_GUARD_MODULES))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(filtered)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
