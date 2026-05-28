#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="github-private-mirror-dry-run.sh"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

print_help() {
    cat <<EOF
Usage: $SCRIPT_NAME [--help]

GL-159: GitHub Private Mirror Dry Run — local validation only.

This script creates a temporary local snapshot of the GrantLayer repository
working tree for validation purposes. It is a DRY RUN ONLY tool.

What this script does:
  - Creates a temporary local snapshot directory
  - Copies tracked files using git ls-files (excludes .claude/ and .git/)
  - Verifies required files are present in the snapshot
  - Prints instructions for running the scan gate and validation tests
  - Cleans up the snapshot directory

What this script does NOT do (hard constraints):
  - Does NOT push to GitHub or any remote
  - Does NOT call the GitHub API
  - Does NOT add or change any git remote
  - Does NOT rewrite git history or run history-rewriting tools
  - Does NOT perform history-filtering operations
  - Does NOT delete commits
  - Does NOT rotate secrets
  - Does NOT create a public repository
  - Does NOT mirror to any remote

Options:
  --help    Show this help

Exit codes:
  0   Dry run completed successfully
  1   Dry run validation failure (missing required files or .claude/.git present)

IMPORTANT: This is a dry-run only tool. No GitHub publication occurs.
           GL-160 makes the final go/no-go publication decision.
EOF
}

if [[ "${1:-}" == "--help" ]]; then
    print_help
    exit 0
fi

echo "=== GL-159: GitHub Private Mirror Dry Run ==="
echo "DRY RUN ONLY — no GitHub publication, no remote changes, no history rewrite"
echo ""

# Verify we are in the repo root
if [[ ! -f "$REPO_ROOT/LICENSE" ]]; then
    echo "ERROR: LICENSE not found at repo root. Run from the GrantLayer repository." >&2
    exit 1
fi

# Verify .claude is not tracked (safety check)
if git -C "$REPO_ROOT" ls-files --error-unmatch .claude/ >/dev/null 2>&1; then
    echo "WARNING: .claude/ appears to be tracked. Will be excluded from snapshot." >&2
fi

# Create temporary snapshot directory
SNAPSHOT_DIR=$(mktemp -d /tmp/grantlayer-snapshot-XXXXXXXX)
echo "Snapshot directory: $SNAPSHOT_DIR"
echo ""

cleanup() {
    if [[ -d "$SNAPSHOT_DIR" ]]; then
        rm -rf "$SNAPSHOT_DIR"
        echo ""
        echo "Snapshot directory cleaned up: $SNAPSHOT_DIR"
    fi
}
trap cleanup EXIT

echo "--- Step 1: Copying tracked files (excluding .claude/ and .git/) ---"
# Use git ls-files to copy only tracked files, explicitly excluding .claude/
git -C "$REPO_ROOT" ls-files | grep -v '^\.claude/' | (cd "$REPO_ROOT" && tar -T - -cf -) | tar -xf - -C "$SNAPSHOT_DIR"
echo "File copy complete."
echo ""

echo "--- Step 2: Verifying exclusions ---"
if [[ -d "$SNAPSHOT_DIR/.git" ]]; then
    echo "FAIL: .git/ found in snapshot — must be excluded" >&2
    exit 1
else
    echo "OK: .git/ excluded"
fi

if [[ -d "$SNAPSHOT_DIR/.claude" ]]; then
    echo "FAIL: .claude/ found in snapshot — must be excluded" >&2
    exit 1
else
    echo "OK: .claude/ excluded"
fi
echo ""

echo "--- Step 3: Verifying required files in snapshot ---"
MISSING=0
required_files=(
    "LICENSE"
    "README.md"
    "CONTRIBUTING.md"
    "SECURITY.md"
    "AGENTS.md"
    "llms.txt"
)
required_dirs=(
    "docs"
    "examples"
    "sdk"
    ".github"
)

for f in "${required_files[@]}"; do
    if [[ -f "$SNAPSHOT_DIR/$f" ]]; then
        echo "OK: $f"
    else
        echo "MISSING: $f" >&2
        MISSING=$((MISSING + 1))
    fi
done

for d in "${required_dirs[@]}"; do
    if [[ -d "$SNAPSHOT_DIR/$d" ]]; then
        echo "OK: $d/"
    else
        echo "MISSING: $d/" >&2
        MISSING=$((MISSING + 1))
    fi
done

if [[ $MISSING -gt 0 ]]; then
    echo "" >&2
    echo "FAIL: $MISSING required item(s) missing from snapshot." >&2
    exit 1
fi
echo ""

echo "--- Step 4: Verifying no GitHub remote configured ---"
REMOTES=$(git -C "$REPO_ROOT" remote -v 2>/dev/null || true)
if echo "$REMOTES" | grep -qi "github.com"; then
    echo "WARNING: A github.com remote appears to be configured. Verify this is intentional." >&2
    echo "$REMOTES" >&2
else
    echo "OK: No github.com remote configured"
fi
echo ""

echo "--- Step 5: Snapshot contents summary ---"
echo "Top-level items in snapshot:"
ls "$SNAPSHOT_DIR"
echo ""

echo "--- Step 6: Next validation steps ---"
cat <<'INSTRUCTIONS'
To complete GL-159 dry-run validation, run from the repository root:

  # Scan gate (GL-157)
  bash scripts/public-secret-sensitive-scan.sh

  # GL-159 targeted validation test
  python3 -m unittest backend.tests.test_gl159_github_private_mirror_dry_run -v

  # GL-158 regression
  python3 -m unittest backend.tests.test_gl158_git_history_exposure_review_public_snapshot_decision -v

  # GL-157 regression
  python3 -m unittest backend.tests.test_gl157_public_secret_sensitive_scan_gate -v

  # Security boundary regression
  python3 -m unittest backend.tests.test_security_boundary_regression -v

  # Full backend suite (if time allows)
  bash scripts/run-full-backend-suite.sh

INSTRUCTIONS

echo "=== DRY RUN ONLY: No GitHub publication performed. ==="
echo "=== Snapshot will be cleaned up automatically. ==="
echo "=== Pass results to GL-160 for final go/no-go decision. ==="
