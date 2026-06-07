"""GL-218 Public Export Safety Scan — local-only, dry-run/scan-only helper.

This script scans the current worktree for obvious forbidden public/export
indicators. It is a local safety aid only.

IMPORTANT LIMITATIONS:
- This script is NOT a complete security audit.
- This script is NOT approval to publish or export anything.
- This script does not guarantee the absence of all sensitive content.
- A dedicated security review is required before any public export or push.
- Positive findings require manual review and removal before any export.

Usage:
    python3 scripts/ops/gl218_public_export_safety_scan.py --dry-run
    python3 scripts/ops/gl218_public_export_safety_scan.py --plan
    python3 scripts/ops/gl218_public_export_safety_scan.py --scan
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Files/paths that should never appear in a public export candidate
FORBIDDEN_PATH_PATTERNS: list[str] = [
    "setup.py",
    "package.json",
    "package-lock.json",
    "website-design/",
    "public-export/",
    "public_snapshot/",
    "dist/",
    "deploy/",
    "terraform/",
    "kubernetes/",
    "helm/",
    "cloud/",
    ".github/workflows/",
]

FORBIDDEN_FILENAME_PATTERNS: list[re.Pattern] = [
    re.compile(r"website[_-]design[_-]workspace[_-]import", re.IGNORECASE),
    re.compile(r"sdk[_-]?pyproject\.toml$", re.IGNORECASE),
    re.compile(r"\.env(\..+)?$"),
    re.compile(r".*\.pem$"),
    re.compile(r".*\.key$"),
    re.compile(r"\.secrets?$"),
]

# Secret-like patterns to scan for in exportable text files
SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("postgres_dsn", re.compile(r"postgres(?:ql)?://[^@]+@[^\s\"'`]+", re.IGNORECASE)),
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE)),
    ("pem_private_key", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----")),
    ("aws_secret", re.compile(r"(?:aws_secret_access_key|AWS_SECRET_ACCESS_KEY)\s*=\s*\S+")),
    ("generic_password", re.compile(r"password\s*=\s*['\"](?!changeme|placeholder|<|{{)[^'\"]{8,}['\"]", re.IGNORECASE)),
    ("raw_token_assign", re.compile(r"(?:token|api_key|apikey|secret)\s*=\s*['\"][A-Za-z0-9+/=_-]{24,}['\"]", re.IGNORECASE)),
    ("auth_header", re.compile(r"(?:Authorization|X-Auth-Token)\s*:\s*\S{16,}", re.IGNORECASE)),
]

# Overclaim patterns to scan for in public-facing docs/examples/website/README
OVERCLAIM_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("production_saas_ready", re.compile(r"production\s+SaaS\s+ready", re.IGNORECASE)),
    ("enterprise_ready", re.compile(r"enterprise\s+ready", re.IGNORECASE)),
    ("compliance_certified", re.compile(r"compliance\s+certified", re.IGNORECASE)),
    ("gdpr_ready", re.compile(r"GDPR\s+ready", re.IGNORECASE)),
    ("soc2_ready", re.compile(r"SOC2\s+ready", re.IGNORECASE)),
    ("iso_ready", re.compile(r"ISO\s+ready", re.IGNORECASE)),
    ("official_sdk", re.compile(r"official\s+SDK\s+(?:available|published|released)", re.IGNORECASE)),
    ("official_package", re.compile(r"official\s+package\s+(?:available|published|released)", re.IGNORECASE)),
    ("live_postgres_production_ready", re.compile(r"live\s+postgres(?:ql)?\s+production\s+ready", re.IGNORECASE)),
    ("real_customer_data_ready", re.compile(r"ready\s+for\s+real\s+customer\s+data", re.IGNORECASE)),
    ("private_grant_data_ready", re.compile(r"ready\s+for\s+private\s+grant", re.IGNORECASE)),
    ("public_snapshot_ready", re.compile(r"public\s+snapshot\s+(?:ready|approved|complete)(?!\s+(?:requires|conditional|separate))", re.IGNORECASE)),
]

# Internal infrastructure leak patterns
INTERNAL_INFRA_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("forgejo_url", re.compile(r"https?://(?:forgejo|git)\.internal", re.IGNORECASE)),
    ("private_ip_rfc1918", re.compile(r"\b(?:10\.\d+\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+|192\.168\.\d+\.\d+)\b")),
    ("private_hostname_internal", re.compile(r"\b\w+\.internal\b", re.IGNORECASE)),
    ("home_filesystem_path", re.compile(r"/home/\w+/")),
    ("srv_internal_path", re.compile(r"/srv/internal/")),
]

# Files/directories in the repo that are eligible for export scanning
EXPORT_CANDIDATE_SCAN_PATHS: list[str] = [
    "README.md",
    "SECURITY.md",
    "AGENTS.md",
    "llms.txt",
    "llms-full.txt",
    "docs/openapi.yaml",
    "website/",
    "examples/",
    "scripts/",
    "docs/public_external_review_export_safety_pack.md",
    "docs/examples/gl218/",
]

_REDACT = "[REDACTED]"


def _redact(value: str) -> str:
    if len(value) <= 6:
        return _REDACT
    return value[:3] + _REDACT + value[-3:]


def _is_text_file(path: str) -> bool:
    text_extensions = {
        ".md", ".txt", ".py", ".sh", ".yaml", ".yml", ".json", ".html",
        ".rst", ".toml", ".cfg", ".ini", ".env",
    }
    _, ext = os.path.splitext(path)
    return ext.lower() in text_extensions


def _scan_file_for_secrets(filepath: str, rel: str) -> list[dict]:
    findings = []
    try:
        with open(filepath, encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except OSError:
        return findings

    for name, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            findings.append({
                "type": "secret_pattern",
                "pattern": name,
                "file": rel,
                "line": line_num,
                "match_redacted": _redact(match.group(0)),
            })

    return findings


def _scan_file_for_overclaims(filepath: str, rel: str) -> list[dict]:
    findings = []
    try:
        with open(filepath, encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except OSError:
        return findings

    for name, pattern in OVERCLAIM_PATTERNS:
        for match in pattern.finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            findings.append({
                "type": "overclaim",
                "pattern": name,
                "file": rel,
                "line": line_num,
                "match": match.group(0),
            })

    return findings


def _scan_file_for_internal_infra(filepath: str, rel: str) -> list[dict]:
    findings = []
    try:
        with open(filepath, encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except OSError:
        return findings

    for name, pattern in INTERNAL_INFRA_PATTERNS:
        for match in pattern.finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            findings.append({
                "type": "internal_infra_leakage",
                "pattern": name,
                "file": rel,
                "line": line_num,
                "match_redacted": _redact(match.group(0)),
            })

    return findings


def _check_forbidden_paths(repo_root: str) -> list[dict]:
    findings = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        # Skip .git directory
        dirnames[:] = [d for d in dirnames if d != ".git" and d != "__pycache__" and d != ".pytest_cache"]
        for name in filenames + dirnames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, repo_root)
            for pattern in FORBIDDEN_PATH_PATTERNS:
                if rel.startswith(pattern) or rel == pattern.rstrip("/"):
                    findings.append({
                        "type": "forbidden_path",
                        "pattern": pattern,
                        "file": rel,
                    })
                    break
            for fn_pattern in FORBIDDEN_FILENAME_PATTERNS:
                if fn_pattern.search(rel):
                    findings.append({
                        "type": "forbidden_filename",
                        "pattern": fn_pattern.pattern,
                        "file": rel,
                    })
                    break
    return findings


def _check_package_metadata(repo_root: str) -> list[dict]:
    findings = []
    forbidden_files = [
        "setup.py",
        "package.json",
        "package-lock.json",
        os.path.join("sdk", "pyproject.toml"),
    ]
    for rel in forbidden_files:
        full = os.path.join(repo_root, rel)
        if os.path.exists(full):
            findings.append({
                "type": "package_metadata_found",
                "file": rel,
            })
    return findings


def _scan_candidate_files(repo_root: str) -> tuple[list[dict], list[dict], list[dict]]:
    secret_findings: list[dict] = []
    overclaim_findings: list[dict] = []
    infra_findings: list[dict] = []

    for candidate_rel in EXPORT_CANDIDATE_SCAN_PATHS:
        candidate_abs = os.path.join(repo_root, candidate_rel)
        if os.path.isfile(candidate_abs):
            if _is_text_file(candidate_abs):
                rel = os.path.relpath(candidate_abs, repo_root)
                secret_findings.extend(_scan_file_for_secrets(candidate_abs, rel))
                overclaim_findings.extend(_scan_file_for_overclaims(candidate_abs, rel))
                infra_findings.extend(_scan_file_for_internal_infra(candidate_abs, rel))
        elif os.path.isdir(candidate_abs):
            for dirpath, dirnames, filenames in os.walk(candidate_abs):
                dirnames[:] = [d for d in dirnames if d != "__pycache__" and d != ".git"]
                for fname in filenames:
                    full = os.path.join(dirpath, fname)
                    rel = os.path.relpath(full, repo_root)
                    if _is_text_file(full):
                        secret_findings.extend(_scan_file_for_secrets(full, rel))
                        overclaim_findings.extend(_scan_file_for_overclaims(full, rel))
                        infra_findings.extend(_scan_file_for_internal_infra(full, rel))

    return secret_findings, overclaim_findings, infra_findings


def _print_disclaimer() -> None:
    print("=" * 70)
    print("GL-218 PUBLIC EXPORT SAFETY SCAN")
    print("=" * 70)
    print()
    print("IMPORTANT: This script is NOT a complete security audit.")
    print("IMPORTANT: This script is NOT approval to publish or export.")
    print("IMPORTANT: Positive findings require manual review before any export.")
    print("IMPORTANT: A dedicated security review is required before any export.")
    print()


def _run_plan(repo_root: str) -> None:
    _print_disclaimer()
    print("PLAN MODE — no files will be read or scanned")
    print()
    print("This script will scan the following export candidate paths:")
    for p in EXPORT_CANDIDATE_SCAN_PATHS:
        print(f"  {p}")
    print()
    print("Checks performed:")
    print("  1. Forbidden path/filename patterns")
    print("  2. Package/publish metadata files")
    print("  3. Secret-like patterns in candidate text files")
    print("  4. Overclaim patterns in candidate text files")
    print("  5. Internal infrastructure leakage patterns in candidate text files")
    print()
    print("No scan is performed in plan mode.")
    print("Run with --dry-run or --scan to perform the scan.")
    print()
    print("NOTE: This script does not create export directories, does not push,")
    print("      does not contact external services, and does not require credentials.")


def _run_scan(repo_root: str) -> int:
    _print_disclaimer()
    print("SCAN MODE")
    print(f"Repo root: {repo_root}")
    print()

    all_findings: list[dict] = []

    # 1. Forbidden paths
    print("[1/5] Checking for forbidden paths and filenames...")
    path_findings = _check_forbidden_paths(repo_root)
    all_findings.extend(path_findings)
    if path_findings:
        print(f"  WARN: {len(path_findings)} forbidden path/filename finding(s)")
        for f in path_findings:
            print(f"    - [{f['type']}] {f['file']} (pattern: {f['pattern']})")
    else:
        print("  OK: No forbidden paths or filenames found in scan paths")

    # 2. Package metadata
    print("[2/5] Checking for package/publish metadata files...")
    pkg_findings = _check_package_metadata(repo_root)
    all_findings.extend(pkg_findings)
    if pkg_findings:
        print(f"  WARN: {len(pkg_findings)} package metadata finding(s)")
        for f in pkg_findings:
            print(f"    - [{f['type']}] {f['file']}")
    else:
        print("  OK: No package/publish metadata files found")

    # 3-5. Scan candidate files
    print("[3/5] Scanning candidate files for secret patterns...")
    print("[4/5] Scanning candidate files for overclaim patterns...")
    print("[5/5] Scanning candidate files for internal infrastructure leakage...")
    secret_findings, overclaim_findings, infra_findings = _scan_candidate_files(repo_root)
    all_findings.extend(secret_findings)
    all_findings.extend(overclaim_findings)
    all_findings.extend(infra_findings)

    if secret_findings:
        print(f"\n  WARN: {len(secret_findings)} secret-like pattern finding(s):")
        for f in secret_findings:
            print(f"    - [{f['pattern']}] {f['file']}:{f['line']} -> {f['match_redacted']}")
    else:
        print("  OK: No secret-like patterns found in candidate files")

    if overclaim_findings:
        print(f"\n  WARN: {len(overclaim_findings)} overclaim finding(s):")
        for f in overclaim_findings:
            print(f"    - [{f['pattern']}] {f['file']}:{f['line']} -> {f['match']}")
    else:
        print("  OK: No overclaim patterns found in candidate files")

    if infra_findings:
        print(f"\n  WARN: {len(infra_findings)} internal infrastructure leakage finding(s):")
        for f in infra_findings:
            print(f"    - [{f['pattern']}] {f['file']}:{f['line']} -> {f['match_redacted']}")
    else:
        print("  OK: No internal infrastructure patterns found in candidate files")

    print()
    print("=" * 70)
    if all_findings:
        print(f"SCAN COMPLETE — {len(all_findings)} finding(s) require review before any export.")
        print("All findings must be resolved or classified before any public export or push.")
    else:
        print("SCAN COMPLETE — No obvious forbidden patterns found.")
        print("This result does NOT constitute approval to publish.")
        print("A dedicated security review is still required before any export.")
    print("=" * 70)
    print()
    print("REMINDER: This script is NOT a complete security audit.")
    print("REMINDER: This script is NOT approval to publish or export anything.")
    print("REMINDER: Public snapshot/export requires a later explicit gate issue")
    print("          and explicit approval from the repository owner.")

    return 1 if all_findings else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "GL-218 Public Export Safety Scan — local-only dry-run/scan-only helper. "
            "NOT a complete security audit. NOT approval to publish."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform the scan without modifying any files (default behaviour).",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Alias for --dry-run: perform the scan without modifying any files.",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Print what the scan would do without actually reading or scanning files.",
    )
    args = parser.parse_args()

    if args.plan:
        _run_plan(REPO_ROOT)
        return 0

    # Default: run scan (both --dry-run and --scan trigger scan; no args also scans)
    return _run_scan(REPO_ROOT)


if __name__ == "__main__":
    sys.exit(main())
