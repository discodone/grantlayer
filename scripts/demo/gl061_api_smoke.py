#!/usr/bin/env python3
"""GrantLayer GL-061 Demo Runner / API Smoke Script.

Provides a local dry-run confidence check for Pilot-Ready artifacts.
Loads the smoke manifest, validates referenced example files, stable IDs,
and prints an ordered smoke plan. Does not perform network access by default.

Usage:
    python3 scripts/demo/gl061_api_smoke.py --dry-run
    python3 scripts/demo/gl061_api_smoke.py --dry-run --base-url http://localhost:8000
"""

import argparse
import json
import pathlib
import sys


SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
MANIFEST_PATH = REPO_ROOT / "docs" / "examples" / "gl061" / "api_smoke_manifest.json"


def load_json(path: pathlib.Path, label: str) -> dict:
    if not path.exists():
        raise SystemExit(f"[ERROR] {label} not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[ERROR] {label} is not valid JSON: {path} ({exc})")
    if not isinstance(data, dict):
        raise SystemExit(f"[ERROR] {label} must be a JSON object: {path}")
    return data


def validate_manifest(manifest: dict) -> None:
    required_fields = {
        "smokeId",
        "smokeVersion",
        "defaultMode",
        "networkRequiredByDefault",
        "productionReady",
        "stableIds",
        "steps",
        "referencedExamples",
        "verificationCommands",
        "nonGoals",
        "relatedArtifacts",
    }
    missing = required_fields - set(manifest.keys())
    if missing:
        raise SystemExit(f"[ERROR] Manifest missing fields: {sorted(missing)}")

    smoke_id = manifest.get("smokeId")
    if smoke_id != "gl061-api-smoke":
        raise SystemExit(f"[ERROR] Unexpected smokeId: {smoke_id}")

    if manifest.get("defaultMode") != "dry-run":
        raise SystemExit("[ERROR] Manifest defaultMode must be 'dry-run'")

    if manifest.get("networkRequiredByDefault") is not False:
        raise SystemExit("[ERROR] Manifest networkRequiredByDefault must be false")

    if manifest.get("productionReady") is not False:
        raise SystemExit("[ERROR] Manifest productionReady must be false")

    stable_ids = manifest.get("stableIds")
    if not isinstance(stable_ids, dict) or not stable_ids:
        raise SystemExit("[ERROR] Manifest stableIds must be a non-empty object")

    expected_ids = {
        "workflowId": "gl057-workflow-001",
        "subjectId": "gl057-subject-001",
        "grantRequestId": "gl057-request-001",
        "grantId": "gl057-grant-001",
        "executionId": "gl057-execution-001",
        "evidenceId": "gl057-evidence-001",
        "policyId": "gl057-policy-001",
        "auditorExportId": "gl057-auditor-export-001",
    }
    for key, expected in expected_ids.items():
        actual = stable_ids.get(key)
        if actual != expected:
            raise SystemExit(
                f"[ERROR] stableIds.{key} must be '{expected}', got '{actual}'"
            )

    steps = manifest.get("steps")
    if not isinstance(steps, list) or len(steps) == 0:
        raise SystemExit("[ERROR] Manifest steps must be a non-empty list")

    for i, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise SystemExit(f"[ERROR] Step {i} must be an object")
        step_num = step.get("stepNumber")
        if step_num != i:
            raise SystemExit(
                f"[ERROR] Step {i} has stepNumber {step_num}, expected {i}"
            )
        for field in ("name", "exampleFile"):
            if not step.get(field):
                raise SystemExit(f"[ERROR] Step {i} missing '{field}'")

    referenced = manifest.get("referencedExamples")
    if not isinstance(referenced, list) or len(referenced) == 0:
        raise SystemExit("[ERROR] Manifest referencedExamples must be a non-empty list")


def _safe_repo_path(base: pathlib.Path, rel: str, label: str) -> pathlib.Path:
    """Resolve rel relative to base and reject traversal outside base."""
    resolved = (base / rel).resolve()
    if not str(resolved).startswith(str(base.resolve())):
        raise SystemExit(f"[ERROR] {label} path escapes repo root: {rel!r}")
    return resolved


def validate_referenced_examples(manifest: dict) -> None:
    referenced = manifest.get("referencedExamples", [])
    seen = set()
    for entry in referenced:
        path_str = entry.get("path")
        if not path_str:
            raise SystemExit("[ERROR] referencedExamples entry missing 'path'")
        if path_str in seen:
            raise SystemExit(f"[ERROR] Duplicate referencedExamples path: {path_str}")
        seen.add(path_str)
        path = _safe_repo_path(REPO_ROOT, path_str, "referencedExamples")
        load_json(path, f"referenced example '{path_str}'")

    steps = manifest.get("steps", [])
    for step in steps:
        step_file = step.get("exampleFile")
        if not step_file:
            continue
        path = _safe_repo_path(REPO_ROOT, step_file, "step exampleFile")
        if not path.exists():
            raise SystemExit(f"[ERROR] Step example file not found: {step_file}")
        try:
            load_json(path, f"step example '{step_file}'")
        except SystemExit:
            raise


def print_smoke_plan(manifest: dict, base_url: str | None) -> None:
    smoke_id = manifest["smokeId"]
    steps = manifest["steps"]
    mode = manifest["defaultMode"]
    network = manifest["networkRequiredByDefault"]

    print("=" * 60)
    print("GrantLayer Demo Runner / API Smoke Script")
    print("=" * 60)
    print(f"smokeId       : {smoke_id}")
    print(f"smokeVersion  : {manifest['smokeVersion']}")
    print(f"defaultMode   : {mode}")
    print(f"networkRequiredByDefault : {network}")
    print(f"productionReady : {manifest['productionReady']}")
    if base_url:
        print(f"baseUrl       : {base_url} (planned only, no live calls in GL-061)")
    print("-" * 60)
    print("Ordered Smoke Plan")
    print("-" * 60)
    for step in steps:
        num = step["stepNumber"]
        name = step["name"]
        example = step.get("exampleFile", "—")
        openapi = step.get("openapiPath", "—")
        print(f"  {num:2d}. {name}")
        print(f"      example : {example}")
        print(f"      openapi : {openapi}")
    print("-" * 60)
    print(f"Total steps: {len(steps)}")
    print("Status: dry-run validation passed")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="GrantLayer GL-061 Demo Runner / API Smoke Script"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Validate manifest and example files locally without network access (default)",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Optional base URL for future local API smoke (planned only in GL-061)",
    )
    args = parser.parse_args()

    if args.base_url and not args.dry_run:
        print(
            "[WARN] Live API smoke mode is not supported in GL-061. "
            "Falling back to dry-run.",
            file=sys.stderr,
        )
        args.dry_run = True

    manifest = load_json(MANIFEST_PATH, "smoke manifest")
    validate_manifest(manifest)
    validate_referenced_examples(manifest)
    print_smoke_plan(manifest, args.base_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
