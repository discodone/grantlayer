# GL-189 Grant Lifecycle Evidence Bundle

## Purpose

This GL-189 example shows a deterministic, local-only grant lifecycle record
with evidence hashes and an audit chain. It gives reviewers a second runnable
public example after the first verifiable output by simulating a minimal grant
flow end to end.

The example writes one JSON file containing:

- A synthetic grant request
- A fixed lifecycle sequence
- Evidence items with SHA-256 hashes
- A chained audit trail
- A final evidence bundle summary
- A deterministic verification summary

## Run Command

From the repository root:

```bash
python3 examples/grant_lifecycle_evidence_bundle.py
```

Default output path:

```text
/tmp/grantlayer_grant_lifecycle_evidence_bundle.json
```

Custom output path:

```bash
python3 examples/grant_lifecycle_evidence_bundle.py --output /tmp/grantlayer_grant_lifecycle_evidence_bundle_custom.json
```

Reference artifact:

```text
examples/grant_lifecycle_evidence_bundle.json
```

## How To Compare Output

Generate the example with the default or custom output path, then compare the
result against the committed reference artifact:

```bash
diff -u examples/grant_lifecycle_evidence_bundle.json /tmp/grantlayer_grant_lifecycle_evidence_bundle.json
```

An empty diff means the example is deterministic and matches the committed
reference.

## What The Example Demonstrates

The script demonstrates a minimal grant lifecycle with stable evidence and
audit records. The lifecycle steps are:

1. `submitted`
2. `evidence_attached`
3. `eligibility_checked`
4. `approval_recommended`
5. `bundle_generated`

The evidence items show the shape of a synthetic budget summary, an eligibility
statement, and a review note. The audit chain shows how each event hash links
to the previous one, and the bundle hash summarizes the final sealed evidence
bundle.

## Evidence Items

Each evidence item contains an `evidence_id`, an `evidence_type`, a structured
`content` object, and a `content_sha256` hash computed from canonical JSON.
This makes the evidence payload stable and easy to verify.

## Audit Chain Hashes

Each audit-chain entry contains an `event_index`, an `event_type`, an
`event_hash`, and a `previous_event_hash`.

The first event uses `null` for `previous_event_hash`. Every later event stores
the hash of the event before it, which makes the audit trail deterministic and
easy to validate.

## Bundle Hash

The top-level `bundle_sha256` is computed from the canonical JSON form of the
`evidence_bundle` object. That summary includes the grant ID, event count,
evidence count, final audit hash, and the hash algorithm used.

## Safety Properties

This example is safe for public preview:

- No network required
- No backend required
- No secrets required
- No customer data required
- Synthetic/demo data only
- No production SaaS claim
- Tenant isolation is not claimed

## What It Does Not Demonstrate

- It does not start the GrantLayer backend
- It does not call any network service
- It does not require a database
- It does not use real grants or private institutional data
- It does not claim production SaaS readiness
- It does not claim tenant/workspace isolation is implemented

## Troubleshooting

- If the output differs from the reference artifact, check that the example
  script was not edited locally and that the committed reference file is still
  intact.
- If `diff -u` reports changes, rerun the generator command and compare again.
- If the command fails, verify that `python3` is available and that the output
  directory is writable.

## Relation To The First Verifiable Output

The first verifiable output introduced a deterministic GrantLayer-style record.
This GL-189 example extends that idea by adding a lifecycle sequence, evidence
bundle summary, and a linked audit chain so reviewers can see more product
value without needing any backend service.

## Non-Goals

- No public GitHub push is performed by the example
- No visibility or publication settings are changed
- No backend API behavior is changed
- No OpenAPI, schema, or migration changes are made

## Next Recommended Issue

GL-189P Public Snapshot Push for Second Runnable Example
