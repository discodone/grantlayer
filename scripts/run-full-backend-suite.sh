#!/usr/bin/env bash
# GrantLayer MVP — GL-121 Full Backend Suite Runner
#
# Usage (from repo root):
#   ./scripts/run-full-backend-suite.sh
#
# With custom timeout (must be >= 900 seconds):
#   FULL_SUITE_TIMEOUT_SECONDS=1200 ./scripts/run-full-backend-suite.sh
#
# This script exists because the full backend suite now takes longer than
# many agent shell tool limits (120000 ms / 120 s). Coding agents should
# run targeted tests and relevant regressions instead.
#
# Runs the full FUNCTIONAL backend suite via unittest. Doc-guard modules are
# excluded — they assert that public-snapshot documentation artifacts (e.g.
# sdk/python/, public CHANGELOG content) exist, but those artifacts are built
# by scripts/build-clean-public-snapshot.sh and are intentionally absent from
# the internal tree. This mirrors the pytest gate (-m "not doc_guard"), which
# cannot be applied by `unittest discover` because it never loads conftest.py.
# The excluded module names are printed at the start of the run (not hidden).
#
# Does NOT require external services.
# Does NOT modify files.
# Does NOT hide functional failures.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

# ── Timeout configuration ──
FULL_SUITE_TIMEOUT_SECONDS="${FULL_SUITE_TIMEOUT_SECONDS:-1800}"

# Reject unsafe short timeouts unless in test mode
if [[ "${FULL_SUITE_TIMEOUT_SECONDS}" -lt 900 ]]; then
    if [[ "${FULL_SUITE_ALLOW_SHORT_TIMEOUT:-}" != "true" ]]; then
        echo "ERROR: FULL_SUITE_TIMEOUT_SECONDS (${FULL_SUITE_TIMEOUT_SECONDS}) is below the minimum safe value of 900 seconds." >&2
        echo "Set FULL_SUITE_ALLOW_SHORT_TIMEOUT=true to override for testing." >&2
        exit 1
    fi
fi

# ── Determine timeout command availability ──
TIMEOUT_CMD=""
if command -v timeout >/dev/null 2>&1; then
    TIMEOUT_CMD="timeout"
elif command -v gtimeout >/dev/null 2>&1; then
    TIMEOUT_CMD="gtimeout"
fi

# ── Run the suite ──
echo "=== GrantLayer Full Backend Suite Runner ==="
echo "Repository root: ${REPO_ROOT}"
echo "Timeout: ${FULL_SUITE_TIMEOUT_SECONDS} seconds"
echo "Command: python3 scripts/_run_full_suite.py (unittest discover, doc-guard modules excluded)"
echo ""

export PYTHONPATH="${PYTHONPATH:-}:${REPO_ROOT}/backend"

# The test suite expects GRANTLAYER_RUNTIME_MODE=test. Under pytest this is set
# by backend/tests/conftest.py, but `unittest discover` does NOT load conftest,
# so set it here too (respecting any explicit override). Without this the suite
# runs in production mode and the plaintext test signing key is rejected,
# producing hundreds of spurious PermissionError failures.
export GRANTLAYER_RUNTIME_MODE="${GRANTLAYER_RUNTIME_MODE:-test}"

EXIT_CODE=0
if [[ -n "${TIMEOUT_CMD}" ]]; then
    echo "--- Running with ${TIMEOUT_CMD} ---"
    ${TIMEOUT_CMD} "${FULL_SUITE_TIMEOUT_SECONDS}s" python3 scripts/_run_full_suite.py || EXIT_CODE=$?
else
    echo "WARNING: 'timeout' command not found. Running without timeout guard." >&2
    python3 scripts/_run_full_suite.py || EXIT_CODE=$?
fi

echo ""
echo "=== Full Backend Suite Finished ==="
echo "Exit code: ${EXIT_CODE}"

exit "${EXIT_CODE}"
