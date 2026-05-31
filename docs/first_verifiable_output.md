# First Verifiable Output

## Purpose

This GL-168 example gives an external developer a first GrantLayer-style
verifiable institutional record without starting the backend or configuring any
external service.

The example writes one deterministic JSON file containing:

- A synthetic grant request
- A deterministic approval decision
- Evidence items with SHA-256 hashes
- A sealed evidence bundle
- A chained audit trail
- A compact compliance readiness summary

## What It Demonstrates

The script shows the shape of a local, verifiable record: evidence content is
hashed, the evidence bundle references those hashes, and audit events are
linked with previous event hashes. The output is stable so developers can rerun
the command and compare the generated JSON with the committed example artifact.

## What It Does Not Claim

This is not a production deployment guide. It does not start the GrantLayer
backend, call an API, authenticate an operator, publish anything, or contact
GitHub. It uses synthetic local example data only. It does not claim production
SaaS readiness. This example does not claim production SaaS readiness, and
tenant isolation is not implemented.

## Run Command

From the repository root:

```bash
python3 examples/first_verifiable_output.py --output /tmp/grantlayer_first_output.json
```

Expected output path:

```text
/tmp/grantlayer_first_output.json
```

The generated file should match:

```text
examples/first_verifiable_output.json
```

## Evidence Hashes

Each evidence item contains `content_sha256`, computed from a canonical JSON
form of the evidence content. The evidence bundle then stores the ordered list
of evidence item hashes and its own `bundle_sha256`. This lets a reviewer detect
whether evidence content changed after the example record was generated.

## Audit Trail

Each audit event contains `event_hash`. Starting with the second event, each
event also stores `previous_event_hash`, linking it to the event before it. This
creates a simple deterministic chain for the synthetic workflow.

## Local Safety

The example requires only Python standard library modules. It requires no
network calls, uses no secrets, requires no backend service startup, requires no
GitHub auth, and uses no real customer data.
