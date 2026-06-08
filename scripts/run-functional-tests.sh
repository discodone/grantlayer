#!/usr/bin/env bash
# GrantLayer MVP — Functional Tests Runner
#
# Runs only real behaviour tests: HTTP endpoints, DB operations, auth checks,
# grant lifecycle, workspace enforcement.  Doc-guard tests (which only verify
# that Markdown / JSON artifact files exist and contain expected phrases) are
# excluded.
#
# Usage (from repo root):
#   ./scripts/run-functional-tests.sh
#
# With pytest installed:
#   pytest -m "not doc_guard"
#
# Expected counts (approximate, grows as features are added):
#   ~120 test files, ~3 400 test methods
#
# Does NOT require external services (uses in-memory SQLite).
# Does NOT modify files.
# Does NOT hide failures.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

export PYTHONPATH="${PYTHONPATH:-}:${REPO_ROOT}/backend"

echo "=== GrantLayer Functional Tests ==="
echo "Repository root: ${REPO_ROOT}"
echo ""

EXIT_CODE=0

# Prefer pytest (marker-based filtering) when available.
if python3 -c "import pytest" 2>/dev/null; then
    echo "Runner: pytest -m 'not doc_guard'"
    echo ""
    python3 -m pytest backend/tests/ -m "not doc_guard" -v || EXIT_CODE=$?
else
    echo "Runner: python3 -m unittest (standalone, pytest not installed)"
    echo ""
    # Build the list of functional modules and run them with unittest.
    python3 - << 'PYEOF'
import importlib
import os
import sys
import unittest

REPO_ROOT = os.getcwd()  # run-functional-tests.sh does cd "${REPO_ROOT}" before this
sys.path.insert(0, os.path.join(REPO_ROOT, "backend"))

# Import the canonical exclusion list.
from tests._doc_guard_modules import DOC_GUARD_MODULES

tests_dir = os.path.join(REPO_ROOT, "backend", "tests")
loader = unittest.TestLoader()
suite = unittest.TestSuite()

for fname in sorted(os.listdir(tests_dir)):
    if not fname.endswith(".py") or not fname.startswith("test_"):
        continue
    module_name = fname[:-3]
    if module_name in DOC_GUARD_MODULES:
        continue
    try:
        mod = importlib.import_module(f"tests.{module_name}")
        suite.addTests(loader.loadTestsFromModule(mod))
    except Exception as exc:
        print(f"WARNING: could not load tests.{module_name}: {exc}", file=sys.stderr)

runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
PYEOF
    EXIT_CODE=$?
fi

echo ""
echo "=== Functional Tests Finished ==="
echo "Exit code: ${EXIT_CODE}"

exit "${EXIT_CODE}"
