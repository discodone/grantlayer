#!/usr/bin/env bash
# GrantLayer MVP — GL-125 Operational Smoke Tests Runner
#
# Usage (from repo root):
#   ./scripts/run-operational-smoke-tests.sh
#
# Compact operational smoke test bundle for quick post-deployment
# or pre-release validation.
#
# Does NOT require external services.
# Does NOT modify files.
# Does NOT hide failures.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

echo "=== GrantLayer Operational Smoke Test Bundle ==="
echo "Repository root: ${REPO_ROOT}"
echo "Command: python3 -m unittest backend.tests.test_gl125_operational_smoke_bundle -v"
echo ""

export PYTHONPATH="${PYTHONPATH:-}:${REPO_ROOT}/backend"

EXIT_CODE=0
python3 -m unittest backend.tests.test_gl125_operational_smoke_bundle -v || EXIT_CODE=$?

echo ""
echo "=== Operational Smoke Tests Finished ==="
echo "Exit code: ${EXIT_CODE}"

exit "${EXIT_CODE}"
