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
# Requires pytest + pytest-xdist:
#   pytest -n auto -m "not doc_guard and not scope_guard"
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

echo "Runner: pytest -n auto -m 'not doc_guard and not scope_guard'"
echo ""
python3 -m pytest backend/tests/ -n auto \
    -m "not doc_guard and not scope_guard" \
    -o cache_dir=/tmp/grantlayer-pytest-cache \
    --tb=short -q || EXIT_CODE=$?

echo ""
echo "=== Functional Tests Finished ==="
echo "Exit code: ${EXIT_CODE}"

exit "${EXIT_CODE}"
