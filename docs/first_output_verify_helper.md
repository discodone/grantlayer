# First Output Verify Helper

## GL-188 Purpose

This helper gives external developers a single command to generate the first
verifiable output example and compare it with the committed reference artifact.
It shortens the trust-building path from "run the example" to "verify the
example matches the repository's canonical JSON."

## Command

From the repository root:

```bash
scripts/verify-first-output.sh
```

Optional custom output path:

```bash
scripts/verify-first-output.sh /tmp/grantlayer_first_output_verify_custom.json
```

## Expected Success Output

The helper prints concise status messages and exits `0` on an exact match:

```text
Running first verifiable output generator...
Comparing generated output with committed reference...
MATCH: /tmp/grantlayer_first_output_verify.json
```

## What It Verifies

- `examples/first_verifiable_output.py` runs successfully.
- The generated JSON is written to a temp or user-specified output path.
- The generated JSON matches `examples/first_verifiable_output.json` exactly.
- The helper exits non-zero if the generator fails or the JSON differs.

## What It Does Not Verify

- It does not start the backend.
- It does not call any network service.
- It does not require secrets.
- It does not validate unrelated backend, API, or deployment behavior.

## Local Safety

This helper requires no network, no backend server, no secrets, and no real customer data. It only writes to the requested output path or the default temp path.

## Relation To First Verifiable Output

The original first verifiable output example demonstrates the deterministic
GrantLayer-style record shape. This helper adds a lightweight comparison step
so a developer can quickly confirm the committed reference artifact still
matches the generator output.

## Non-Goals

- No publication workflow changes.
- No GitHub repository setting changes.
- No backend runtime changes.
- No expansion to a second runnable example.

## Troubleshooting

- If the command exits non-zero, inspect the generator output and the diff
  printed by the helper.
- If the default temp file is stale, rerun the helper or pass a custom output
  path.
- If the example script fails, run the generator directly with the same output
  path to isolate the error.

## Safety Confirmations

- no network required
- no backend required
- no secrets required
- no customer data required

## Next Recommended Issue

GL-189 Second Runnable Example / Grant Lifecycle Evidence Bundle
