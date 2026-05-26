#!/usr/bin/env bash
# GrantLayer MVP — GL-126 Production Runtime Gate Runner
#
# Usage (from repo root):
#   ./scripts/run-production-runtime-gate.sh
#
# Narrow pre-deploy / pre-release validation gate.
# Checks runtime mode classification, production-like config safety,
# and secret-handling conventions without requiring external services.
#
# Does NOT require external services.
# Does NOT modify files.
# Does NOT hide failures.
# Does NOT print secret values.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

echo "=== GrantLayer Production Runtime Gate ==="
echo "Repository root: ${REPO_ROOT}"
echo "Command: python3 -m unittest backend.tests.test_gl126_production_runtime_gate -v"
echo ""

export PYTHONPATH="${PYTHONPATH:-}:${REPO_ROOT}/backend"

EXIT_CODE=0
python3 -m unittest backend.tests.test_gl126_production_runtime_gate -v || EXIT_CODE=$?

echo ""
echo "=== Production Runtime Gate Finished ==="
echo "Exit code: ${EXIT_CODE}"

exit "${EXIT_CODE}"
