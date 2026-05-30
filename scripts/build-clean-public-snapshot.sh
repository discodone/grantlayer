#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="build-clean-public-snapshot.sh"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

OUTPUT_DIR=""
ALLOW_DIRTY=0
TMPFILE=""
EXCLUDE_LISTFILE=""

print_help() {
    cat <<EOF
Usage: $SCRIPT_NAME [--output <dir>] [--allow-dirty] [--help]

GL-161: Build Clean Public Snapshot — local snapshot build only.

This script creates a persistent local directory containing only the tracked
files from the GrantLayer repository, suitable as a public snapshot candidate
for review before the GL-162 Publish Gate.

What this script does:
  - Resolves the repository root from the script location
  - Checks for a clean tracked tree by default (no uncommitted or staged changes)
  - Creates the output snapshot directory
  - Copies tracked files using git ls-files
  - Excludes .claude/, .git/, .env files, caches, and build artifacts
  - Optionally runs the public-secret-sensitive-scan.sh gate if available
  - Prints file count, exclusion summary, and next validation commands

What this script does NOT do (hard constraints):
  - Does NOT push to any remote
  - Does NOT call the GitHub API
  - Does NOT add or change any git remote
  - Does NOT rewrite git history
  - Does NOT run filter-repo or any history-rewriting tool
  - Does NOT delete commits
  - Does NOT rotate secrets
  - Does NOT create a public repository
  - Does NOT mirror to any remote

Options:
  --output <dir>   Output snapshot directory
                   (default: <repo-root>/grantlayer-public-snapshot)
  --allow-dirty    Skip dirty-tree check — for local testing only
  --help           Show this help and exit

Exit codes:
  0   Snapshot built successfully
  1   Error (dirty tree, missing prerequisites, or unsafe output path)

IMPORTANT: This is a LOCAL-ONLY snapshot build tool.
           No GitHub publication occurs in GL-161.
           GL-162 GitHub Public Repository Metadata / Publish Gate
           makes the final publish decision after manual approval.
EOF
}

cleanup() {
    if [[ -n "$TMPFILE" && -f "$TMPFILE" ]]; then
        rm -f "$TMPFILE"
    fi
    if [[ -n "$EXCLUDE_LISTFILE" && -f "$EXCLUDE_LISTFILE" ]]; then
        rm -f "$EXCLUDE_LISTFILE"
    fi
}
trap cleanup EXIT

while [[ $# -gt 0 ]]; do
    case "${1}" in
        --help)
            print_help
            exit 0
            ;;
        --output)
            if [[ $# -lt 2 ]]; then
                echo "ERROR: --output requires a directory argument." >&2
                exit 1
            fi
            OUTPUT_DIR="${2}"
            shift 2
            ;;
        --allow-dirty)
            ALLOW_DIRTY=1
            shift
            ;;
        *)
            echo "Unknown option: ${1}" >&2
            print_help >&2
            exit 1
            ;;
    esac
done

if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="$REPO_ROOT/grantlayer-public-snapshot"
fi

echo "=== GL-161: Clean Public Snapshot Build ==="
echo "LOCAL SNAPSHOT ONLY — no GitHub publication, no remote changes, no history rewrite"
echo ""
echo "Source repo root : $REPO_ROOT"
echo "Output directory : $OUTPUT_DIR"
echo ""

if [[ ! -f "$REPO_ROOT/LICENSE" ]]; then
    echo "ERROR: LICENSE not found at repo root ($REPO_ROOT)." >&2
    echo "Run this script from within the GrantLayer repository." >&2
    exit 1
fi

echo "--- Step 1: Checking tracked tree cleanliness ---"
if [[ $ALLOW_DIRTY -eq 0 ]]; then
    if ! git -C "$REPO_ROOT" diff --quiet; then
        echo "ERROR: Uncommitted changes to tracked files detected." >&2
        echo "Commit or stash changes before building the snapshot." >&2
        echo "Use --allow-dirty to override for local testing only." >&2
        exit 1
    fi
    if ! git -C "$REPO_ROOT" diff --cached --quiet; then
        echo "ERROR: Staged changes detected." >&2
        echo "Commit or unstage changes before building the snapshot." >&2
        echo "Use --allow-dirty to override for local testing only." >&2
        exit 1
    fi
    echo "OK: Tracked tree is clean (no uncommitted or staged changes)."
else
    echo "WARNING: --allow-dirty specified. Dirty-tree check skipped (local testing only)."
fi

UNTRACKED_COUNT=$(git -C "$REPO_ROOT" ls-files --others --exclude-standard | wc -l || true)
if [[ "$UNTRACKED_COUNT" -gt 0 ]]; then
    echo "INFO: $UNTRACKED_COUNT untracked file(s) present — not included in snapshot."
fi
echo ""

echo "--- Step 2: Preparing output directory ---"
if [[ -d "$OUTPUT_DIR" ]]; then
    ENTRY_COUNT=$(find "$OUTPUT_DIR" -maxdepth 1 -mindepth 1 | wc -l || true)
    if [[ "$ENTRY_COUNT" -gt 0 ]]; then
        echo "ERROR: Output directory already exists and is not empty: $OUTPUT_DIR" >&2
        echo "Remove or choose a different output path." >&2
        exit 1
    fi
else
    mkdir -p "$OUTPUT_DIR"
fi
echo "OK: Output directory ready: $OUTPUT_DIR"
echo ""

echo "--- Step 3: Building tracked file list (applying exclusions) ---"

# GL-162B: Public export exclusion list.
# Internal GL gate/scanner/review test fixtures and synthetic secret/path marker
# fixtures are excluded from the public snapshot. These files are internal
# publication controls and intentionally contain scanner-triggering patterns
# (as test assertions, synthetic examples, or forbidden-marker lists).
# Excluding them does NOT weaken internal validation — the source repo retains
# all files and the internal scanner still runs against the full tree.
PUBLIC_EXPORT_EXCLUDE=(
    # Internal GL public-readiness validation tests containing scanner meta strings
    "backend/tests/test_gl157_public_secret_sensitive_scan_gate.py"
    "backend/tests/test_gl158_git_history_exposure_review_public_snapshot_decision.py"
    "backend/tests/test_gl159_github_private_mirror_dry_run.py"
    "backend/tests/test_gl160_public_github_go_no_go_decision.py"
    "backend/tests/test_gl161_clean_public_snapshot_build.py"
    "backend/tests/test_gl162_github_public_repository_publish_gate.py"
    "backend/tests/test_gl162a_pre_publication_security_review_fixes.py"
    "backend/tests/test_gl162b_public_snapshot_scanner_clean_export.py"
    # Internal scanner/meta docs that intentionally contain blocker examples
    "docs/public_secret_sensitive_scan_gate.md"
    "docs/git_history_exposure_review_public_snapshot_decision.md"
    "docs/github_private_mirror_dry_run.md"
    "docs/public_github_go_no_go_decision.md"
    "docs/clean_public_snapshot_build.md"
    "docs/github_public_repository_publish_gate.md"
    # Internal examples containing synthetic private-key markers, internal path, or overclaim fixtures
    "docs/examples/gl132/tenant_workspace_boundary_decision.json"
    "docs/examples/gl133/external_security_review_preparation.json"
    "docs/examples/gl136/key_hygiene.json"
    "docs/examples/gl151/public_readme_repo_metadata_polish.json"
    "docs/examples/gl152/public_checklist_blocker_fixes.json"
    "docs/examples/gl153/license_contributing_security_decision.json"
    "docs/examples/gl157/public_secret_sensitive_scan_gate.json"
    "docs/examples/gl158/git_history_exposure_review_public_snapshot_decision.json"
    "docs/examples/gl159/github_private_mirror_dry_run.json"
    "docs/examples/gl160/public_github_go_no_go_decision.json"
    "docs/examples/gl161/clean_public_snapshot_build.json"
    "docs/examples/gl162/github_public_repository_publish_gate.json"
    "docs/examples/gl162b/public_snapshot_scanner_clean_export.json"
    # Internal operational and planning docs (contain env var / token patterns as configuration examples
    # or internal path / overclaim references not suited for public developer-preview export)
    "docs/architecture.md"
    "docs/developer_adoption_strategy_intake.md"
    "docs/external_security_review_preparation.md"
    "docs/operations/deployment.md"
    "docs/pilot_readiness_release_cut.md"
    "docs/production_architecture_operations_readiness_review.md"
    "docs/production_runtime_gate.md"
    "docs/public_github_readiness_pack.md"
    "docs/security_remediation_intake_2026_05_26.md"
    "docs/sprint_2_plan.md"
    "docs/tenant_workspace_boundary_decision.md"
    # Operational Docker Compose and demo scripts (contain env var token patterns)
    "docker-compose.yml"
    "docker-compose.postgres.yml"
    "scripts/demo.sh"
    # GL-162C: Internal backend CI workflow — requires backend/ which is intentionally
    # excluded from the public snapshot. Publishing this workflow causes spurious CI
    # failures on the public GitHub repository.
    ".github/workflows/postgres-ci.yml"
    # GL-162C: CI compatibility validation test and artifact (internal — excluded to
    # keep the public snapshot free of backend test infrastructure references)
    "backend/tests/test_gl162c_public_snapshot_ci_compatibility.py"
    "docs/examples/gl162c/public_github_ci_snapshot_compatibility.json"
    # GL-162C follow-up: standalone CI compatibility test script under scripts/ — contains
    # internal hostname strings as test assertions (_INTERNAL_HOSTNAMES list); blocked by
    # the public scanner. Excluded here so future snapshot builds cannot accidentally
    # include it if the file is ever added under scripts/ in the source repo.
    "scripts/test_gl162c_public_snapshot_ci_compatibility.py"
)

TMPFILE=$(mktemp /tmp/gl161-file-list-XXXXXXXX.txt)
EXCLUDE_LISTFILE=$(mktemp /tmp/gl162b-excl-XXXXXXXX.txt)
printf '%s\n' "${PUBLIC_EXPORT_EXCLUDE[@]}" > "$EXCLUDE_LISTFILE"

git -C "$REPO_ROOT" ls-files \
    | grep -v '^\.claude' \
    | grep -v '^\.env$' \
    | awk '!/^\.env\./ || /^\.env\.example$/' \
    | grep -v '__pycache__' \
    | grep -v '\.pyc$' \
    | grep -v '^tmp/' \
    | grep -v '^\.tmp/' \
    | grep -v '^dist/' \
    | grep -v '^build/' \
    | grep -v '^backend/' \
    | grep -vFxf "$EXCLUDE_LISTFILE" \
    > "$TMPFILE" || true

FILE_COUNT=$(wc -l < "$TMPFILE" | tr -d ' ')
echo "Tracked files after exclusions: $FILE_COUNT"
echo ""

echo "--- Step 4: Copying files to snapshot directory ---"
if [[ "$FILE_COUNT" -eq 0 ]]; then
    echo "ERROR: No files to copy after applying exclusions." >&2
    exit 1
fi
(cd "$REPO_ROOT" && tar -T "$TMPFILE" -cf -) | tar -xf - -C "$OUTPUT_DIR"
echo "OK: $FILE_COUNT file(s) copied to $OUTPUT_DIR"
echo ""

echo "--- Step 5: Verifying snapshot exclusions ---"
if [[ -e "$OUTPUT_DIR/.git" ]]; then
    echo "FAIL: .git found in snapshot — must be excluded." >&2
    exit 1
else
    echo "OK: .git excluded (full internal history not published per GL-158 decision)."
fi

if [[ -e "$OUTPUT_DIR/.claude" ]]; then
    echo "FAIL: .claude found in snapshot — must be excluded." >&2
    exit 1
else
    echo "OK: .claude excluded (internal tooling must never be published)."
fi

if [[ -d "$OUTPUT_DIR/.github/workflows" ]]; then
    BAD_WORKFLOWS=$(grep -rl 'backend[./]tests' "$OUTPUT_DIR/.github/workflows/" 2>/dev/null || true)
    if [[ -n "$BAD_WORKFLOWS" ]]; then
        echo "FAIL: workflow(s) referencing backend.tests found in snapshot (GL-162C):" >&2
        echo "$BAD_WORKFLOWS" >&2
        exit 1
    else
        echo "OK: no backend-dependent CI workflows in .github/workflows/ (GL-162C)."
    fi
else
    echo "OK: .github/workflows/ absent or empty — no backend-dependent CI workflows (GL-162C)."
fi
echo ""

echo "--- Step 6: Exclusion summary ---"
echo "Standard exclusions:"
echo "  .git             (full internal git history — not published per GL-158 decision)"
echo "  .claude          (internal tooling — must never be published)"
echo "  .env / .env.*    (real environment files — may contain local secrets; .env.example included)"
echo "  __pycache__      (Python bytecode cache)"
echo "  *.pyc            (compiled Python files)"
echo "  tmp/ .tmp/       (temporary files)"
echo "  dist/ build/     (build output artifacts)"
echo "  backend/         (internal backend source and tests — contains legitimate code patterns"
echo "                    that trigger the scanner heuristic; not needed for developer preview)"
echo ""
echo "GL-162B public-export-only exclusions (internal gate/scanner/meta fixtures):"
for f in "${PUBLIC_EXPORT_EXCLUDE[@]}"; do
    echo "  $f"
done
echo ""
echo "Public-export exclusions applied: ${#PUBLIC_EXPORT_EXCLUDE[@]} file(s)"
echo "Note: source repo retains all files — internal validation is not weakened."
echo ""

echo "--- Step 7: Optional scan gate ---"
SCAN_SCRIPT="$REPO_ROOT/scripts/public-secret-sensitive-scan.sh"
if [[ -x "$SCAN_SCRIPT" ]]; then
    echo "Running public-secret-sensitive-scan.sh scan gate..."
    bash "$SCAN_SCRIPT" || {
        echo "WARNING: Scan gate reported issues. Review output before GL-162." >&2
    }
else
    echo "INFO: public-secret-sensitive-scan.sh not found or not executable — skipping."
    echo "INFO: Run manually: bash scripts/public-secret-sensitive-scan.sh"
fi
echo ""

echo "--- Step 8: Next validation steps ---"
cat <<'INSTRUCTIONS'
To validate the snapshot before GL-162, run from the repository root:

  # GL-162C targeted validation (CI snapshot compatibility)
  python3 -m unittest backend.tests.test_gl162c_public_snapshot_ci_compatibility -v

  # GL-162B targeted validation test (scanner-clean snapshot)
  python3 -m unittest backend.tests.test_gl162b_public_snapshot_scanner_clean_export -v

  # GL-161 targeted validation test
  python3 -m unittest backend.tests.test_gl161_clean_public_snapshot_build -v

  # Scan gate (GL-157) on source repo
  bash scripts/public-secret-sensitive-scan.sh

  # Validate snapshot is scanner-clean (run from within the snapshot after git init + git add .):
  #   cd <output-dir> && git init && git add . && bash scripts/public-secret-sensitive-scan.sh
  # NOTE: Running git init inside the snapshot leaves a .git directory there.
  # When copying the snapshot into the persistent publish clone, you MUST exclude .git:
  #   rsync (preferred):
  #     rsync -a --delete --exclude='.git' <snapshot>/ <publish-clone>/
  #   cp fallback (if rsync unavailable — do NOT use 'cp -a <snapshot>/. <publish-clone>/'):
  #     find <snapshot>/ -mindepth 1 -maxdepth 1 ! -name '.git' -exec cp -a {} <publish-clone>/ \;

  # GL-164A targeted validation test (language classification + copy safety)
  python3 -m unittest backend.tests.test_gl164a_public_repo_discovery_metadata -v

  # GL-160 regression
  python3 -m unittest backend.tests.test_gl160_public_github_go_no_go_decision -v

  # GL-159 regression
  python3 -m unittest backend.tests.test_gl159_github_private_mirror_dry_run -v

  # GL-158 regression
  python3 -m unittest backend.tests.test_gl158_git_history_exposure_review_public_snapshot_decision -v

  # Security boundary regression
  python3 -m unittest backend.tests.test_security_boundary_regression -v

  # Full backend suite (required before GL-162)
  bash scripts/run-full-backend-suite.sh

INSTRUCTIONS

echo "=== Snapshot build complete ==="
echo "Source repo root : $REPO_ROOT"
echo "Output snapshot  : $OUTPUT_DIR"
echo "Included files   : $FILE_COUNT"
echo ""
echo "LOCAL SNAPSHOT ONLY: No GitHub publication performed."
echo "Pass snapshot path and validation results to GL-162 Publish Gate."
