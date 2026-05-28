#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="public-secret-sensitive-scan.sh"
STRICT=false
FORMAT="text"

print_help() {
    cat <<EOF
Usage: $SCRIPT_NAME [--strict] [--format text] [--help]

Heuristic scan of tracked files for obvious secrets, sensitive data,
internal hostnames/paths, and public-readiness overclaims.

Options:
  --strict      Reserved for future stricter ruleset (currently same as default)
  --format text Output format (default: text)
  --help        Show this help

Exit codes:
  0   No blockers found
  1   One or more blockers found

Scan categories:
  private_key              BEGIN RSA/OPENSSH/PRIVATE KEY markers
  aws_access_key           AKIA[0-9A-Z]{16} patterns
  github_token             ghp_ / github_pat_ prefixes
  generic_secret_assign    api_key= / apiKey: / secret= / token= / password= / private_key=
  bearer_token             Bearer followed by 20+ char high-entropy string
  internal_hostname        forge.hofercloud.eu / terminal.hofercloud.eu
  internal_path            /home/adminuser / /home/oai / /mnt/data
  customer_data            customer email/name/id / real grant applicant
  private_personal_data    passport / social security number / national id / bank account
  overclaim                production SaaS ready / production-ready SaaS /
                           tenant isolation implemented / public GitHub release completed

Safe placeholders (lines containing these terms are skipped):
  <token>  <api-key>  example  demo  fake  dummy  placeholder
  legacy-admin-token  test-token  dev-token  local
  "no real secrets"  "no real customer data"  "not production SaaS"
  "tenant isolation is not implemented"

Note: does not scan .git/ or .claude/ directories.
Note: only scans files tracked by git (git ls-files).
Note: heuristic scan only — not a forensic audit of full git history.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help) print_help; exit 0 ;;
        --strict) STRICT=true ;;
        --format) FORMAT="${2:-text}"; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
    shift
done

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

SKIP_EXTENSIONS="png jpg jpeg gif ico bmp svg pdf db sqlite sqlite3 pyc pyo so dylib dll zip tar gz bz2 xz whl egg"

# Scanner meta files: excluded from scanning to prevent self-flagging.
# These files legitimately contain scanner patterns (as patterns, examples, or test fixtures)
# and are not genuine secrets.
META_EXCLUDE=(
    "scripts/public-secret-sensitive-scan.sh"
    "docs/public_secret_sensitive_scan_gate.md"
    "backend/tests/test_gl157_public_secret_sensitive_scan_gate.py"
    "backend/tests/test_gl162a_pre_publication_security_review_fixes.py"
)

TOTAL_FILES=0
TOTAL_BLOCKERS=0
META_EXCLUDED_COUNT=0
declare -A CATEGORY_COUNTS

_is_meta_excluded() {
    local file="$1"
    local excluded
    for excluded in "${META_EXCLUDE[@]}"; do
        if [[ "$file" == "$excluded" ]]; then
            return 0
        fi
    done
    return 1
}

_is_skip_ext() {
    local file="$1"
    local ext="${file##*.}"
    local skip
    for skip in $SKIP_EXTENSIONS; do
        if [[ "$ext" == "$skip" ]]; then
            return 0
        fi
    done
    return 1
}

_is_safe_line() {
    local line="$1"
    local safe_terms=(
        '<token>'
        '<api-key>'
        'example'
        'demo'
        'fake'
        'dummy'
        'placeholder'
        'legacy-admin-token'
        'test-token'
        'dev-token'
        'local'
        'no real secrets'
        'no real customer data'
        'not production SaaS'
        'tenant isolation is not implemented'
    )
    local term
    for term in "${safe_terms[@]}"; do
        if echo "$line" | grep -qiF "$term"; then
            return 0
        fi
    done
    return 1
}

_truncate() {
    local s="$1"
    local max=120
    if [[ ${#s} -gt $max ]]; then
        echo "${s:0:$max}..."
    else
        echo "$s"
    fi
}

_scan_file_pattern() {
    local file="$1"
    local category="$2"
    local pattern="$3"
    local case_flag="$4"   # -i or empty

    local found
    found=$(grep -nE $case_flag "$pattern" "$file" 2>/dev/null || true)
    if [[ -z "$found" ]]; then
        return
    fi

    while IFS= read -r match_line; do
        [[ -z "$match_line" ]] && continue
        local line_content="${match_line#*:}"
        if _is_safe_line "$line_content"; then
            continue
        fi
        local lineno="${match_line%%:*}"
        local truncated
        truncated=$(_truncate "$line_content")
        echo "  BLOCKER [$category] ${file}:${lineno}: ${truncated}"
        TOTAL_BLOCKERS=$((TOTAL_BLOCKERS + 1))
        CATEGORY_COUNTS["$category"]=$(( ${CATEGORY_COUNTS["$category"]:-0} + 1 ))
    done <<< "$found"
}

_scan_file() {
    local file="$1"

    _scan_file_pattern "$file" "private_key" \
        "BEGIN (RSA |OPENSSH )?PRIVATE KEY" ""

    _scan_file_pattern "$file" "aws_access_key" \
        "AKIA[0-9A-Z]{16}" ""

    _scan_file_pattern "$file" "github_token" \
        "(ghp_[A-Za-z0-9_]{10,}|github_pat_[A-Za-z0-9_]{10,})" ""

    _scan_file_pattern "$file" "generic_secret_assign" \
        "(api_key[[:space:]]*=|apiKey[[:space:]]*:|secret[[:space:]]*=|token[[:space:]]*=|password[[:space:]]*=|private_key[[:space:]]*=)" "-i"

    _scan_file_pattern "$file" "bearer_token" \
        "Bearer [A-Za-z0-9+/=_.-]{20,}" ""

    _scan_file_pattern "$file" "internal_hostname" \
        "(forge\.hofercloud\.eu|terminal\.hofercloud\.eu)" "-i"

    _scan_file_pattern "$file" "internal_path" \
        "(/home/adminuser|/home/oai|/mnt/data)" ""

    _scan_file_pattern "$file" "customer_data" \
        "(customer email|customer name|customer id|real grant applicant)" "-i"

    _scan_file_pattern "$file" "private_personal_data" \
        "(passport|social security number|national id|bank account)" "-i"

    _scan_file_pattern "$file" "overclaim" \
        "(production SaaS ready|production-ready SaaS|tenant isolation implemented|public GitHub release completed)" "-i"
}

echo "[$SCRIPT_NAME] mode=$(if $STRICT; then echo strict; else echo default; fi) format=$FORMAT"
echo "[$SCRIPT_NAME] Scanning tracked files (excluding .git/ .claude/)..."

TRACKED_FILES=$(git ls-files | grep -v '^\.claude/')

while IFS= read -r rel_file; do
    [[ -z "$rel_file" ]] && continue
    local_file="$REPO_ROOT/$rel_file"
    [[ -f "$local_file" ]] || continue
    if _is_meta_excluded "$rel_file"; then
        META_EXCLUDED_COUNT=$((META_EXCLUDED_COUNT + 1))
        continue
    fi
    if _is_skip_ext "$rel_file"; then
        continue
    fi
    TOTAL_FILES=$((TOTAL_FILES + 1))
    _scan_file "$local_file"
done <<< "$TRACKED_FILES"

echo "[$SCRIPT_NAME] Scanned files : $TOTAL_FILES"
echo "[$SCRIPT_NAME] Meta-excluded : $META_EXCLUDED_COUNT (scanner/docs/tests self-references)"
echo "[$SCRIPT_NAME] Blockers found: $TOTAL_BLOCKERS"

if [[ $TOTAL_BLOCKERS -gt 0 ]]; then
    echo ""
    echo "[$SCRIPT_NAME] Category summary:"
    for cat in "${!CATEGORY_COUNTS[@]}"; do
        echo "  $cat: ${CATEGORY_COUNTS[$cat]}"
    done
    echo ""
    echo "[$SCRIPT_NAME] GUIDANCE: Review blockers above. For each:"
    echo "  - Replace real credentials/paths with safe placeholders (e.g. <token>, example)"
    echo "  - Remove files containing real credentials from git tracking (git rm --cached)"
    echo "  - Rotate any real secrets externally — this script does NOT rotate secrets"
    echo "  - See docs/public_secret_sensitive_scan_gate.md for full guidance"
    echo "  - See GL-158 for git history exposure decisions before public release"
    echo ""
    echo "[$SCRIPT_NAME] RESULT: BLOCKERS FOUND — not public-ready (heuristic scan)"
    exit 1
else
    echo ""
    echo "[$SCRIPT_NAME] RESULT: No blockers found (heuristic scan — see limitations in docs)"
    exit 0
fi
