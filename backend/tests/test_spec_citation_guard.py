"""Doc-guard: docs/SPECIFICATION.md code citations must match the real code.

The spec is only useful to an independent re-implementer if every `file:line`
citation and every quoted code behavior still points at the real code. Line
numbers drift whenever code above them moves (e.g. gl-401 inserted `_get_hmac_key`
at the top of audit_compliance.py; gl-407 rewrote the verify endpoint and changed
the row-hash verify ordering), silently breaking the spec's verifiability.

Design (code-is-truth, line numbers are NOT hardcoded here — they are computed
from the current source, so this guard itself never goes stale on line shifts):
  * LINE_CITATIONS: each entry names a STABLE code anchor (a `def`, a constant,
    or an exact code line). The guard locates that anchor in the current source,
    computes its 1-based line, and asserts the spec cites that line
    (`basename:LINE`, matching both `:LINE` and `:LINE-…` ranges). A stale line
    citation fails here.
  * SPEC_QUOTES: an exact code string that must appear BOTH in the source and in
    the spec — for behavior the spec describes in prose/quote (e.g. the row-hash
    verification ORDER BY). A drifted behavioral description fails here.

Robustness note: anchors are symbol/string based, so unrelated line shifts do
NOT break this guard — only a citation that no longer matches reality does. When
a cited symbol is renamed/removed, its anchor is not found and the guard fails
loudly, naming the citation to fix.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = _ROOT / "docs" / "SPECIFICATION.md"

_AC = "backend/src/api/routers/audit_compliance.py"
_AL = "backend/src/audit/audit_log.py"
_VA = "scripts/verify-anchor.py"

# (spec_section, repo_relative_file, stable_anchor_substring)
# The spec must cite the anchor's CURRENT line.
LINE_CITATIONS: list[tuple[str, str, str]] = [
    # --- §3 sequence assignment / ordering / locking ---
    ("§3", _AL, "_AUDIT_HASH_CHAIN_WRITE_LOCK = RLock()"),
    ("§3", _AL, "_PG_AUDIT_CHAIN_LOCK_KEY = 6252"),
    ("§3", _AL, "# PostgreSQL: omit seq so the column DEFAULT (nextval from sequence) fires."),
    ("§3", _AL, "def _get_next_seq_sqlite("),
    ("§3", _AL, "SELECT pg_advisory_xact_lock({_PG_AUDIT_CHAIN_LOCK_KEY})"),
    ("§3", _AL, "def _fetch_all_audit_events_ordered("),
    ("§3", _AL, "def _filter_chain_rows("),
    ("§3", _AC, ".order_by(nullslast(_AuditEventORM.seq.asc()), _AuditEventORM.id.asc())"),
    # --- §4.1 export-fold entry canonical ---
    ("§4.1", _AC, "def _entry_canonical("),
    ("§4.1", _AC, '_forward_only_when_null = ("reason_code",)'),
    ("§4.1", _AC, 'clean = {k: v for k, v in record.items() if not k.startswith("_")}'),
    ("§4.1", _VA, "def entry_canonical("),
    ("§4.1", _VA, '_FORWARD_ONLY_WHEN_NULL = ("reason_code",)'),
    # --- §4.2 row-hash canonical ---
    ("§4.2", _AL, "def _hash_payload("),
    ("§4.2", _AL, "def _compute_row_hash("),
    # --- §5.1 row-hash chain ---
    ("§5.1", _AL, "def _get_latest_row_hash("),
    ("§5.1", _AL, "def verify_audit_hash_chain("),
    # --- §5.2 export fold chain ---
    ("§5.2", _AC, "def _iter_chain("),
    ("§5.2", _AC, 'record = {**event, "_chain_hash": entry_hash, "_prev_hash": prev_hash}'),
    ("§5.2", _VA, "def chain_hash("),
    # --- §5.3 export file format ---
    ("§5.3", _AC, '"_type": "manifest"'),
    ("§5.3", _AC, "def _sign_manifest("),
    # --- §6 fold / head derivation ---
    ("§6", _AC, "def recompute_head_from_records("),
    ("§6", _AC, "def anchor_head("),
]

# (spec_section, repo_relative_file, exact_code_string_the_spec_must_quote)
SPEC_QUOTES: list[tuple[str, str, str]] = [
    # §3 / §5.1 row-hash verification order (gl-407 changed this from
    # timestamp-ordered to seq-ordered; the spec must describe the real ORDER BY).
    ("§3/§5.1", _AL, "ORDER BY (seq IS NULL), seq ASC, id ASC"),
]


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def _line_of(text: str, anchor: str, rel: str) -> int:
    idx = text.find(anchor)
    if idx == -1:
        raise AssertionError(
            f"anchor not found in {rel} (symbol renamed/removed?): {anchor!r}"
        )
    return text.count("\n", 0, idx) + 1


def _cited(spec: str, basename: str, line: int) -> bool:
    """True if the anchor's line is an ENDPOINT of some `basename:A` / `basename:A-B`
    citation in the spec (start of a single/range cite, or the end of a range).

    Endpoint (not interval) matching is deliberate: it accepts a def cited at
    either end of its range (e.g. an RLock at the end of a `:20-23` block) while
    NOT letting an unrelated stale range silently "cover" a symbol that drifted
    into its interior.
    """
    endpoints: set[int] = set()
    for m in re.finditer(rf"{re.escape(basename)}:(\d+)(?:-(\d+))?", spec):
        endpoints.add(int(m.group(1)))
        if m.group(2):
            endpoints.add(int(m.group(2)))
    return line in endpoints


def test_spec_line_citations_match_code() -> None:
    spec = _read("docs/SPECIFICATION.md")
    failures: list[str] = []
    for section, rel, anchor in LINE_CITATIONS:
        src = _read(rel)
        line = _line_of(src, anchor, rel)
        basename = Path(rel).name
        if not _cited(spec, basename, line):
            failures.append(
                f"{section}: {basename} — anchor {anchor!r} is at line {line}, "
                f"but the spec does not cite {basename}:{line}"
            )
    if failures:
        pytest.fail(
            "Stale spec code citations (line drift) — re-anchor to current code:\n"
            + "\n".join(f"  - {f}" for f in failures)
        )


def test_spec_quotes_match_code_behavior() -> None:
    spec = _read("docs/SPECIFICATION.md")
    failures: list[str] = []
    for section, rel, snippet in SPEC_QUOTES:
        src = _read(rel)
        if snippet not in src:
            failures.append(
                f"{section}: guard snippet no longer in {rel} (update the guard "
                f"AND the spec): {snippet!r}"
            )
        elif snippet not in spec:
            failures.append(
                f"{section}: the spec does not quote the current code behavior "
                f"from {Path(rel).name}: {snippet!r}"
            )
    if failures:
        pytest.fail(
            "Stale spec behavioral citations — re-anchor to current code:\n"
            + "\n".join(f"  - {f}" for f in failures)
        )
