#!/usr/bin/env python3
"""GL-209 audit export check.

Read-only, deterministic audit-export governance check for Developer Preview /
Controlled Preview. The script emits a manifest-style summary only; it does not
export raw audit payloads, evidence payloads, request bodies, tokens, DSNs, or
private data.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path


PLAN_STEPS = [
    "step_01: Confirm GL-209 data boundary is synthetic/demo only",
    "step_02: Confirm audit source history remains immutable and read-only",
    "step_03: Verify audit hash-chain before any derived export when a DB is explicitly configured",
    "step_04: Build a manifest/check summary with counts and integrity status only",
    "step_05: Refuse or redact secret-like fields in derived outputs",
    "step_06: Write derived manifest only to an explicit or temporary path",
    "step_07: Report remaining blockers without production-readiness claims",
]

SENSITIVE_PATTERNS = (
    re.compile(r"bearer\s+[a-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"authorization", re.IGNORECASE),
    re.compile(r"token(_hash|_lookup_hash)?", re.IGNORECASE),
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"private[_ -]?key", re.IGNORECASE),
    re.compile(r"postgres(ql)?://", re.IGNORECASE),
    re.compile(r"sqlite://", re.IGNORECASE),
    re.compile(r"customer[_ -]?data", re.IGNORECASE),
    re.compile(r"private[_ -]?grant", re.IGNORECASE),
    re.compile(r"institutional[_ -]?data", re.IGNORECASE),
    re.compile(r"request[_ -]?body", re.IGNORECASE),
    re.compile(r"evidence[_ -]?payload", re.IGNORECASE),
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _iter_values(value: object):
    if isinstance(value, dict):
        for item in value.values():
            yield from _iter_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_values(item)
    else:
        yield value


def _assert_safe_text(value: object) -> None:
    for item in _iter_values(value):
        text = json.dumps(item, sort_keys=True, ensure_ascii=True)
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(text):
                raise ValueError("derived manifest contains secret-like or disallowed data")


def _sample_manifest() -> dict:
    manifest = {
        "issue_id": "GL-209",
        "mode": "synthetic_sample",
        "data_boundary": "synthetic/demo only",
        "source_audit_mutated": False,
        "source_audit_redacted": False,
        "hash_chain_verified": "not_applicable_sample_mode",
        "checked_events": 0,
        "export_type": "derived_manifest_only",
        "includes_raw_audit_payloads": False,
        "includes_evidence_payloads": False,
        "includes_request_bodies": False,
        "includes_tokens_or_hashes": False,
        "includes_real_customer_private_data": False,
        "production_readiness_claimed": False,
        "compliance_certification_claimed": False,
        "remaining_blockers": [
            "production retention schedule",
            "legal/compliance hold process",
            "production export approval workflow",
            "production backup retention/encryption/offsite strategy",
        ],
    }
    _assert_safe_text(manifest)
    return manifest


def _write_manifest(manifest: dict, output: str | None) -> Path:
    if output:
        output_path = Path(output)
    else:
        handle = tempfile.NamedTemporaryFile(
            prefix="grantlayer_gl209_audit_export_check_",
            suffix=".json",
            delete=False,
        )
        handle.close()
        output_path = Path(handle.name)
    output_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _run_plan() -> int:
    print("[GL-209] Audit Export Check — PLAN mode")
    for step in PLAN_STEPS:
        print(f"[GL-209]   {step}")
    print("[GL-209] No DB connection is opened in plan mode.")
    print("[GL-209] No audit source rows are mutated.")
    print("[GL-209] No production readiness or compliance certification is claimed.")
    return 0


def _run_dry_run() -> int:
    print("[GL-209] Audit Export Check — DRY-RUN mode")
    print("[GL-209] No DB connection is opened.")
    print("[GL-209] Source audit history remains immutable and untouched.")
    print("[GL-209] Derived exports must omit raw tokens, hashes, DSNs, request bodies, and evidence payloads.")
    print("[GL-209] Dry-run complete.")
    return 0


def _run_sample(output: str | None) -> int:
    print("[GL-209] Audit Export Check — SYNTHETIC SAMPLE mode")
    manifest = _sample_manifest()
    output_path = _write_manifest(manifest, output)
    print(f"[GL-209] Wrote safe derived manifest: {output_path}")
    print("[GL-209] No DB connection opened; no source audit rows mutated.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GL-209 read-only audit export check")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true", help="show the audit export governance plan")
    mode.add_argument("--dry-run", action="store_true", help="validate safety defaults without DB access")
    mode.add_argument("--sample", action="store_true", help="write a synthetic/demo manifest only")
    parser.add_argument("--output", help="optional output path for --sample")
    args = parser.parse_args(argv)

    if args.output and not args.sample:
        parser.error("--output is only valid with --sample")

    if str(_repo_root()) not in sys.path:
        sys.path.insert(0, str(_repo_root()))

    if args.plan:
        return _run_plan()
    if args.dry_run:
        return _run_dry_run()
    return _run_sample(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
