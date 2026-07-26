# GrantLayer Chain Specification

**Status:** normative description of the implemented behaviour, derived from and
verified against the source at the commit that introduced this document. Where
this text and the code disagree, **the code wins** — file:line citations are
given for every claim so the reader can check. This document describes what the
system *does*, not what a future version ideally should do; known gaps are
listed in [Open spec questions](#11-open-spec-questions), not silently resolved.

**Goal:** an independent developer, in any language, can implement a verifier
that validates GrantLayer's Cardano mainnet anchors against a public NDJSON
export — without running any GrantLayer code. The dependency-free
`scripts/verify-anchor.py` is the reference implementation of exactly that.

---

## 1. Overview: two hash layers

GrantLayer maintains **two distinct hash constructions**. Conflating them is
the most likely implementation error, so the distinction comes first:

| Layer | Where it lives | Canonical form | Purpose |
|---|---|---|---|
| **Row-hash chain** (`row_hash`/`prev_hash`) | Database columns, written at insert time | Compact JSON, *selected* fields (§4.2) | In-database tamper evidence, per event, across the whole deployment |
| **Export fold** (`_chain_hash`/`_prev_hash`, head `h`) | Computed over export entries | Default-spaced JSON, *all* entry fields (§4.1) | The value that is **anchored on-chain**; independently recomputable from the export file alone |

The on-chain anchor commits to the **export fold head only**. The row-hash
chain participates in anchoring *indirectly*: `row_hash`, `prev_hash`, and
`seq` are ordinary data fields of each export entry and are therefore hashed
*as content* by the fold. An external verifier never needs to recompute a
`row_hash` — but any tampering with those stored values changes the fold.

---

## 2. Data model: the audit event

Source of truth: `backend/src/core/models.py:149` (dataclass `AuditEvent`) and
`backend/src/core/orm.py:63` (table `audit_events`).

| Field | Type | Nullable | Meaning |
|---|---|---|---|
| `id` | str (UUIDv4) | no | Event identity, generated at creation |
| `timestamp` | str (ISO-8601) | no | Creation time. **Stored and hashed as an opaque string** — no normalization; both `…Z` and `…+00:00` suffixes occur in real data |
| `subject_id` | str | no | Acting subject (agent identity, or the witnessing operator on lifecycle events) |
| `role` | str | no | Subject role (`agent`, `owner`, …) |
| `action` | str | no | The action decided/recorded (tool name, `pg_dump`, `api_key_created`, or the grant tuple on lifecycle events) |
| `resource` | str | no | Target resource |
| `approved` | bool | no | The decision. In the DB an integer 0/1 (`orm.py:71`); in export entries a JSON boolean |
| `reason` | str | no | Human-readable reason |
| `matched_grant_id` | str | yes | Grant that matched, on decision events |
| `challenge_id` | str | yes | Challenge used, if any |
| `challenge_present` | bool | no (default false) | Whether a challenge was presented |
| `challenge_result` | str | no (default `"legacy_mode"`) | `valid` / `invalid` / `missing_data` / `legacy_mode` … |
| `grant_signature_result` | str | no (default `"not_checked"`) | Ed25519 signature check outcome for the matched grant |
| `row_hash` | str (64-hex) | yes (NULL on pre-chain rows) | This event's row-hash (§5.1) |
| `prev_hash` | str (64-hex) | yes | Previous event's `row_hash` (deployment-wide chain; NULL for the first hashed row) |
| `tenant_id` | str | yes (NULL = pre-migration) | Tenant context |
| `workspace_id` | str | no | Owning workspace; genuinely global events use an explicit system-workspace sentinel, never NULL (`models.py`, comment above the field) |
| `scope` | str | yes | `tenant` / `tenant_admin` / `system` / `public` |
| `seq` | int (BigInteger) | yes (NULL = pre-migration-0013 rows) | Global insertion-order counter (§3) |
| `reason_code` | str | yes | Stable machine decision code; None on non-decision events **and on every event written before the column existed**. Forward-only in the canonical (§4.3) |

**Hashed vs not hashed:** which of these participate in which hash is defined
entirely by the two canonicalizations in §4 — the row-hash canonical uses a
fixed subset; the export fold canonical uses *every* key present in the entry
dict (including `row_hash`, `prev_hash`, `seq` themselves), minus the
underscore-prefixed chain metadata the exporter adds.

---

## 3. Sequence assignment and total ordering

- `seq` is a **deployment-global** monotone insertion counter, not
  per-workspace: on PostgreSQL it is populated by the column's BIGSERIAL-style
  sequence default (the insert deliberately omits `seq` so `nextval` fires —
  `backend/src/audit/audit_log.py:316`); on SQLite it is computed in Python
  under the process write lock (`audit_log.py:370`).
- Writes are serialized so `prev_hash` linkage and `seq` cannot interleave:
  PostgreSQL takes a transaction-scoped exclusive advisory lock
  `pg_advisory_xact_lock(6252)` before reading the latest `row_hash`
  (`audit_log.py:412`, key constant at `audit_log.py:27`); SQLite uses a
  process-local `RLock` (`audit_log.py:20-23`).
- **The anchored total order is `seq` ascending** with `id` ascending as a
  formal tiebreak, NULL `seq` explicitly LAST: `_load_workspace_entries` orders
  `ORDER BY seq ASC NULLS LAST, id ASC`
  (`backend/src/api/routers/audit_compliance.py:315`). The `NULLS LAST` is
  normative, not cosmetic: SQLite sorts NULL first in ASC while PostgreSQL
  sorts it last, so without it the two backends would fold *different chains*
  for the same data whenever pre-seq-migration rows exist (§11.3).
  Because a workspace's chain is a *filtered view* of the global table, the
  `seq` values inside one workspace's export are increasing but **not
  contiguous** (the real epoch-1 export starts at `seq: 3`).
- The row-hash chain's own verification order is **`seq` ascending, NULL `seq`
  last** — `ORDER BY (seq IS NULL), seq ASC, id ASC`
  (`audit_log.py:126`, query text at `audit_log.py:139`), matching the anchored
  order so a timestamp/`seq` inversion under concurrent writes can no longer flag
  an honest chain (gl-407 changed this from the earlier `timestamp ASC, seq ASC`);
  rows with `row_hash IS NULL` are skipped (`audit_log.py:143`).

---

## 4. Canonicalization rules

A second implementation must produce **byte-identical** output. Both
canonicals are JSON texts produced with the semantics of Python's
`json.dumps`; the details that matter for byte-identity are spelled out below.

### 4.1 Export-fold entry canonical (the anchored one)

Definition: `audit_compliance.py:52-70` (`_entry_canonical`), independently
re-implemented at `scripts/verify-anchor.py:79-92` (`entry_canonical`).

Given one export entry (a JSON object):

1. **Drop every key that starts with `_`** (the exporter's chain metadata:
   `_chain_hash`, `_prev_hash`; the manifest's `_type` etc. — verifier side
   `verify-anchor.py:83`; export side operates pre-insertion at
   `audit_compliance.py:91`).
2. **Omit forward-only fields whose value is null.** The allow-list is
   exactly `("reason_code",)` — `audit_compliance.py:59`,
   `verify-anchor.py:76`. This is **not** "drop every null": every other
   field with a null value (`matched_grant_id`, `challenge_id`, `tenant_id`,
   `scope`, `prev_hash`, …) **stays in the canonical as `null`**. A key that
   is *absent* from the entry (e.g. `reason_code` in exports produced before
   the column existed) simply contributes nothing — which is the same bytes
   as present-and-omitted; that equivalence is what keeps historical anchors
   recomputable (introduced with the reason_code work, gl-376; see also
   `models.py` comment on `reason_code`).
3. **Serialize** the remaining key→value map as JSON with:
   - keys sorted by Unicode code point (Python `sort_keys=True`),
   - **default separators: `", "` between members and `": "` after keys**
     (note the spaces — `_entry_canonical` does *not* pass `separators`),
   - `ensure_ascii=True`: every non-ASCII character escaped as `\uXXXX`,
   - JSON literals `true`/`false`/`null`, integers unquoted, no float values
     occur in practice,
   - no trailing newline.

Worked micro-example (from the golden vectors,
`backend/tests/fixtures/fold_golden_vectors.json`): an entry with
`reason_code: null` canonicalizes to

```
{"action": "read", "approved": true, "challenge_id": null, "challenge_present": false, "challenge_result": "legacy_mode", "grant_signature_result": "valid", "id": "g1", "matched_grant_id": null, "prev_hash": null, "reason": "ok", "resource": "res/1", "role": "agent", "row_hash": "aaaa…", "scope": null, "seq": 1, "subject_id": "s1", "tenant_id": null, "timestamp": "2026-01-01T00:00:00Z", "workspace_id": "w1"}
```

— `reason_code` gone, every other null kept, spaces after `:` and `,`.

An **empty-string** `reason_code` is *kept* (the omit rule fires on null
only) — covered by a dedicated golden vector.

### 4.2 Row-hash canonical (database layer — not what anchors commit to)

Definition: `audit_log.py:55-83` (`_hash_payload`). A **fixed field subset**
in a dict, serialized with `sort_keys=True` and **compact separators
`(",", ":")`** (no spaces — deliberately different from §4.1):

`id, timestamp, subject_id, role, action, resource, approved (coerced bool),
reason, matched_grant_id, challenge_id, challenge_present (coerced bool),
challenge_result, grant_signature_result, prev_hash` — plus `tenant_id` **only
when non-null** (dual-mode rule so pre-tenant rows keep their stored hashes,
`audit_log.py:61-63,81-82`). `row_hash` itself, `workspace_id`, `scope`,
`seq`, and `reason_code` are **not** part of this payload.

`row_hash = SHA-256(canonical UTF-8)` hex — `audit_log.py:86-89`.

---

## 5. Hash chains

### 5.1 Row-hash chain (database)

Each insert reads the latest existing `row_hash` (deployment-wide, `NULL`
skipped — `audit_log.py:37-52`) as `prev_hash`, computes
`row_hash = SHA-256(_hash_payload(event, prev_hash))`, and stores both, all
under the advisory lock (§3). Verification (`audit_log.py:271`) walks in `seq`
order (`ORDER BY (seq IS NULL), seq ASC, id ASC`), recomputes each hash, and
checks each row's `prev_hash` equals its predecessor's `row_hash`.

### 5.2 Export fold chain (anchored)

Primitive (single shared definition on the backend:
`audit_compliance.py:79-95` `_iter_chain`; verifier:
`verify-anchor.py:95-97,137-163`):

```
GENESIS = "0" * 64                                  # 64 ASCII zeros
entry_hash_i = SHA-256( hex(prev) || canonical_i )   # string concatenation,
                                                     # NO separator, UTF-8
prev_0 = GENESIS ;  prev_i = entry_hash_{i-1}
head (h) = entry_hash_N  ;  entry count (s) = N
```

The previous hash is concatenated as its **64-char lowercase hex string**,
not as raw bytes. Each exported data line additionally carries
`_chain_hash` (its own entry hash) and `_prev_hash` (the running value before
it) — `audit_compliance.py:197` — which let a verifier name the exact broken
line rather than only detecting "head differs" (`verify-anchor.py:144-162`).

### 5.3 Export file format (NDJSON)

One JSON object per line (`ensure_ascii=True`):

- N **data lines**: the entry dict plus `_chain_hash`/`_prev_hash`.
- 1 **manifest footer**: `{"_type": "manifest", "_entry_count": N,
  "_final_hash": <head>, "_hmac_signature": <hex>}` —
  `audit_compliance.py:204-208`. Data after the footer is a verification
  error (`verify-anchor.py:130-132`).
- `_hmac_signature` = HMAC-SHA-256 over the newline-joined list of all entry
  hashes (`audit_compliance.py:113-116`), keyed by GrantLayer's private audit
  HMAC key. It is an **optional insider check only** — anchor verification
  neither needs nor uses it (`verify-anchor.py:256-270`).

---

## 6. Fold, head derivation, and fold parity

The anchored head for a workspace is `anchor_head(session, workspace_id)`
(`audit_compliance.py:379-381`) = `recompute_head_from_records(...)`
(`audit_compliance.py:97-110`) over `_load_workspace_entries` (§3 ordering):
**full chain, no date filter, no limit, seq ASC**.

**Fold parity (gl-378):** the anchor-side fold and the public-export-side fold
are the *same functions* on the backend (`_iter_chain` /
`recompute_head_from_records` are shared — `audit_compliance.py:79`
docstring), and the standalone verifier is a **deliberate, independent
re-implementation** of the identical algorithm
(`verify-anchor.py:53-58,68-76`). The two implementations are held
byte-identical by the golden vectors (§9): a drift in either direction fails
its test.

⚠️ Parity is about the *per-entry canonical and fold algorithm* — **not** the
input ordering of the public `/export` endpoint's DEFAULT mode; the
`?order=anchor` mode serves the anchored ordering directly. See §11.2.

---

## 7. Anchor format and on-chain encoding

- Payload (`backend/src/anchoring/models.py:27-54`, `AnchorPayload`):
  exactly three fields, nothing else —

  ```json
  { "h": "<64 lowercase hex chars — the fold head>",
    "s": <entry count, non-negative integer>,
    "t": "<ISO-8601 UTC timestamp of the anchor run, 'Z' suffix>" }
  ```

  Construction rejects a `0x` prefix, non-64-hex `h`, bool/negative `s`,
  empty `t` (`models.py:38-50`). `t` is produced by
  `head_to_payload` (`backend/src/anchoring/writer.py:67-74`) — it is the
  anchor-run wall-clock time, **not** any event timestamp.
- **Cardano metadata label: `923350`** (`anchoring/models.py:19`; integer key
  on-chain, string key `"923350"` in Koios JSON responses —
  `verify-anchor.py:61`).
- **Extra-key tolerance (decided 2026-07-25):** verifiers MUST read only
  `h`, `s`, `t` and tolerate unknown additional keys in the payload map — the
  reference implementation already behaves this way (`verify-anchor.py:230-232`
  reads the three keys and ignores the rest). A future format revision may add
  keys (e.g. a version marker `v`) without breaking conforming verifiers.
- Embedding: a metadata-only mainnet transaction; the payload map is placed
  under the label via PyCardano
  `AlonzoMetadata(metadata=Metadata({923350: payload.to_dict()}))`
  (`writer.py:174`), built/signed/submitted by `submit_anchor`
  (`writer.py:130+`). Guards before any network touch: minimum chain length
  (`assert_chain_anchorable`, `writer.py:50-64`), pinned wallet address, fee
  ceiling, production-database requirement. The worker job reads the head
  *after* its own chain-witnessed grant exercise commits, so every anchor
  covers the exercise event that authorized it
  (`backend/src/workers/jobs.py:290-295`).
- Anchors are **cadence-free**: each is an explicit operator act, not a
  scheduled job. There are four mainnet anchors at the time of writing
  (epochs 1–4, s = 7 / 17 / 25 / 29).

---

## 8. Independent verification walkthrough

Reference implementation: `scripts/verify-anchor.py` — Python stdlib only, no
GrantLayer imports, no Cardano library; chain access via the keyless public
Koios API. Given an export file and a transaction id
(`verify-anchor.py:214-274`):

1. **Parse** the NDJSON: collect data lines; the `_type == "manifest"` line is
   the footer; any data line after it fails.
2. **Recompute the head**: left-fold per §5.2, cross-checking each line's
   stored `_prev_hash` (linkage) and `_chain_hash` (content) so a broken line
   is named precisely.
3. **Fetch the on-chain payload**: `POST {koios}/tx_metadata` with the tx
   hash; read `metadata["923350"]` → `{h, s, t}`
   (`verify-anchor.py:190-201`). Discovery of candidate anchor transactions:
   `GET {koios}/tx_by_metalabel?_label=923350` (`verify-anchor.py:204-208`).
4. **Check counts**: data-line count must equal on-chain `s` (closes tail
   truncation) and, if a manifest is present, its `_entry_count` too.
5. **Check the head**: recomputed head must equal on-chain `h` byte-for-byte.
   This is the authoritative anti-rewrite check.
6. Exit 0 with a report, or exit 1 with the precise failure.

An implementer in another language needs: SHA-256, a JSON serializer capable
of §4.1's exact output (sorted keys, `", "`/`": "` separators, `\uXXXX`
escapes), and HTTPS GET/POST. Nothing else.

## 8.1 Worked example — mainnet epoch-1 anchor (verified against reality)

Known-good values, re-verified with the reference implementation while
writing this document:

| | |
|---|---|
| Transaction | `820b74da9a96072c055ac9f234cca88d1c6b0a29ec4a63270f78bff807e07c1a` |
| Block | 13694777 |
| Label | 923350 |
| On-chain `h` | `9c00b97663d46445b02058bb56bf8fd18997c30a457628be00061f3096d00969` |
| On-chain `s` | 7 |
| On-chain `t` | `2026-07-18T16:08:33.066986Z` |

The export's first data line (public workspace-bootstrap event) begins the
fold with `_prev_hash = "0"*64`; note its `seq` is **3**, not 1 — the
workspace chain is a seq-ascending *subset* of the global table (§3), and
this export predates the `reason_code` column, so that key is absent
entirely (equivalent bytes to present-and-null, §4.1 rule 2).

Reference run:

```
$ python3 scripts/verify-anchor.py --ndjson <epoch1-export>.ndjson \
    --tx-id 820b74da9a96072c055ac9f234cca88d1c6b0a29ec4a63270f78bff807e07c1a \
    --network mainnet
  VERIFIED — export matches the on-chain anchor
  recomputed head: 9c00b97663d46445b02058bb56bf8fd18997c30a457628be00061f3096d00969
  entry count    : 7 (matches on-chain s)
  anchored at    : 2026-07-18T16:08:33.066986Z
$ echo $?
0
```

A new implementation is correct for this example iff it reproduces the same
head from the same 7 data lines and accepts the same on-chain payload.

---

## 9. Golden vectors — the conformance fixture

`backend/tests/fixtures/fold_golden_vectors.json` is a **data-only** fixture:
raw entries → expected canonical string → expected chain hash, plus multi-entry
chains → expected heads, seeded from `"0"*64`. It covers the tricky cases:
all-null optionals, populated `reason_code`, **empty-string** `reason_code`
(kept, not omitted), and a mixed null/non-null chain.

Both existing implementations are tested against it from independent entry
points (`backend/tests/test_fold_golden_vectors.py`: one class imports the
backend fold, the other loads `scripts/verify-anchor.py` by file path) — a
drift in either fails. **A third implementation should treat this file as its
conformance suite**: reproduce every `expected_canonical` byte-for-byte and
every expected hash/head before touching real exports. The fixture is plain
JSON with no code, so it ports to any language trivially.

---

## 10. What an anchor proves — and does not

Consistent with the reference verifier's own statement
(`verify-anchor.py:4-18`) and the public verify page (`site/verify/index.html`):

**Proves:** at the anchor's block time, an immutable on-chain commitment
existed to an audit chain of exactly `s` entries whose fold head was `h`. A
matching export is byte-for-byte the chain as it stood then; post-anchor
rewriting, reordering, truncation, or padding of those `s` entries is
detectable by anyone, without trusting GrantLayer.

**Does not prove:** that the entries were correct, complete, or honest when
first written (a tamperer controlling the log *before* the anchor anchors the
doctored file); anything about entries' semantic truth; and **nothing about
events appended after the newest anchor**. That un-anchored window has
strictly weaker protection: the row-hash chain alone cannot expose a
database-level rewrite of it (truncation to an earlier prefix, full re-link
after an edit, or a mutated field re-hashed in place all still verify — the
gl-384 adversarial results), and no on-chain commitment covers it until the
next anchor is published. Anchors are deliberately cadence-free, so this
window has no bounded length. This is the structural trade-off of periodic
anchoring, not a defect.

---

## 11. Spec questions and their resolutions (decided 2026-07-25)

Each item below was flagged as an implicit rule while this spec was derived
from the code, then decided explicitly rather than resolved silently.

1. **No fold/format version identifier.** The on-chain payload is exactly
   `{h, s, t}` and the export has no version marker. Any future change to the
   canonical form or fold would be breaking with no in-band signal; today the
   only compatibility mechanism is the forward-only-when-null allow-list
   (§4.1). **Decision: deferred** — no `v` field until the first actual
   format change; instead, extra-key tolerance is declared normatively in §7,
   so a future `v` can be added without breaking conforming verifiers.
2. **Public `/export` order vs anchored order.** The public export endpoint
   feeds the fold a `timestamp DESC, seq DESC`, limit-capped list
   (`audit_log.py:479`, `audit_compliance.py:154-159`), while the anchored
   head uses the full chain in `seq ASC` order (§3). A default `/export`
   download is internally consistent (its own `_chain_hash` lines verify) but
   its head will **not** equal any anchor. Verifying against an anchor
   requires an anchor-ordered full export (`_build_anchor_export`).
   **Decision: the default order stays unchanged and this spec documents it
   honestly; an explicit `?order=anchor` export mode (seq ASC, full chain) is
   a named follow-up item.**
   **Follow-up landed 2026-07-25 (gl-400):** `GET /v1/audit/export?order=anchor`
   returns the FULL workspace chain in the anchored order, byte-identical to
   `_build_anchor_export` (the endpoint delegates to it — one authoritative
   ordering, no reimplementation), so its manifest `_final_hash` is directly
   comparable against on-chain anchors. Window parameters
   (`limit`/`start_date`/`end_date`) are rejected with 400
   (`anchor_order_no_window`) — a windowed "anchor" export would fold a head
   that verifies against no anchor. The default order remains byte-identical
   to before (pinned by `test_gl400_order_anchor_export.py`).
3. **NULL-`seq` rows in the anchored order.** `ORDER BY seq ASC, id ASC`
   relies on the database's NULL-ordering for pre-migration rows (PostgreSQL
   sorts NULL last in ASC). No live workspace chain contains NULL-seq rows
   today. **Decision: make the NULL ordering explicit (`NULLS LAST`) the next
   time that query is touched; no standalone change.**
   **Done 2026-07-25 (gl-400):** the query now says `NULLS LAST` explicitly
   (§3); pinned by `test_gl400_order_anchor_export.py` (SQLite would
   otherwise sort NULL first and fold a different chain than PostgreSQL).
4. **Timestamp shape is unnormalized.** Both `…Z` and `…+00:00` ISO suffixes
   occur in stored events; the canonicals hash the string as-is.
   **Decision: permanent** — timestamps are opaque strings; no tooling may
   ever normalize them (normalization would break every existing anchor).
5. **HMAC manifest default key.** The manifest signer falls back to a default
   key when the env var is unset (`audit_compliance.py:25-26`). Irrelevant to
   anchor verification (the HMAC is insider-only), but noted so nobody
   mistakes the manifest signature for a public-trust mechanism.
   **Decision: requiring the env var (fail-closed) in production-like modes
   is a named follow-up item.**
   **Follow-up landed 2026-07-25 (gl-401):** production-like modes now refuse
   at BOTH gates when `GRANTLAYER_AUDIT_HMAC_KEY` is unset — the startup gate
   (`config.startup_errors()`) and the signer itself (`_get_hmac_key()`
   raises rather than fall back to the public default constant). local/test
   keep the fallback. Deployment prerequisite: set the env var before
   restarting a production instance. The manifest HMAC remains an
   insider-only check — anchor verification still neither needs nor uses it.
