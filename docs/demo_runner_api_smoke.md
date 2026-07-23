# GrantLayer Demo Runner / API Smoke Script

> GrantLayer issues time-boxed access grants, enforces them through policy, and records every decision in a verifiable audit trail.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose

This script provides a **local dry-run confidence check** for Pilot-Ready artifacts. It converts the documented demo flow, example JSON files, and expected API sequence into a practical, executable verification step that an integrator or reviewer can run without a live server.

Running the demo runner confirms that:
- the smoke manifest is present and parses correctly,
- all referenced example JSON files are present and valid,
- stable identifiers are coherent across the manifest and examples,
- the documented Product Core sequence is ordered and complete.

It is a **pilot-readiness tooling task**, not a production feature.

## 2. What it validates

The demo runner validates the following without requiring network access or secrets:

- **smoke manifest exists and parses** — `docs/examples/gl061/api_smoke_manifest.json` is valid JSON with required fields.
- **referenced example JSON files exist** — every file listed in `referencedExamples` and `steps` is present and parses as JSON.
- **stable IDs are coherent** — the manifest declares the same stable identifiers used in GL-057 (`gl057-workflow-001`, `gl057-request-001`, etc.).
- **documented Product Core sequence is ordered** — steps are numbered 1 through 11 and match the natural grant flow.
- **no secrets are required** — the script and manifest contain no passwords, tokens, API keys, or private keys.
- **no network is required by default** — dry-run mode performs only local file system validation.

## 3. How to run

### Dry-run (default, no network)

```bash
python3 scripts/demo/gl061_api_smoke.py --dry-run
```

### With optional base-url (planned only, no live calls in GL-061)

```bash
python3 scripts/demo/gl061_api_smoke.py --dry-run --base-url http://localhost:8000
```

### Targeted validation test

```bash
python3 -m unittest backend.tests.test_gl061_demo_runner_api_smoke -v
```

### Full backend test suite

```bash
python3 -m unittest discover backend.tests -v
```

The full suite is expected to pass with **0 failures** and **0 errors**.

## 4. Relationship to existing artifacts

This demo runner builds on top of earlier Integration-Ready and Pilot-Ready artifacts and does not replace them:

- [`docs/integrator_quickstart.md`](integrator_quickstart.md) — minimal static JSON examples with stable identifiers and deterministic data shapes.
- [`docs/minimal_api_usage_walkthrough.md`](minimal_api_usage_walkthrough.md) — API-first walkthrough mapping Product Core stages to OpenAPI paths.
- [`docs/pilot_ready_handoff_plan.md`](pilot_ready_handoff_plan.md) — packages Integration-Ready v0 into a clear technical handoff for pilot discussions.
- [`docs/pilot_ready_release_decision.md`](pilot_ready_release_decision.md) — formally records the current Pilot-Ready state and confirms the default recommended next block is a demo runner / API smoke script.
- [`docs/examples/gl057/`](examples/gl057/) — 12 static JSON files covering every Product Core stage. The smoke manifest references these files directly.
- [`docs/examples/gl058/minimal_api_usage_walkthrough.json`](examples/gl058/minimal_api_usage_walkthrough.json) — machine-readable walkthrough index with stable IDs and OpenAPI path references.

## 5. Dry-run vs future local API smoke

- **Dry-run is the GL-061 supported mode.** The script validates manifests and example files locally. No live API server is required.
- **No live API calls are made in GL-061.** An optional `--base-url` flag is accepted, but if provided the script only prints the planned calls and remains in dry-run mode.
- **Future blocks may add an actual local API smoke run** if a running service is available. That would be a separate task and is not in scope for GL-061.
- **This script is not production monitoring.** It does not poll endpoints, emit metrics, or trigger alerts.

## 6. Non-goals

This demo runner **explicitly does not** provide:

- **Production deployment** — no containers, load balancing, TLS termination, or orchestration instructions.
- **Production monitoring** — no metrics, logging pipelines, alerting, or tracing.
- **Production authentication** — no OAuth, JWT, SSO, or HSM-backed key management.
- **SDK generation** — no client libraries (Python, JavaScript, Go).
- **External API certification** — the script does not certify external services or legal compliance.
- **Legal or compliance advice** — the outputs are structured records to support institutional audit workflows, not to replace legal or regulatory review.
- **Blockchain / wallet / payment integration** — integrity checks use standard SHA-256 and Ed25519 only.
- **Replacing backend tests** — the demo runner is a lightweight local confidence check, not a substitute for the full backend test suite.

## See also

- [`docs/integrator_quickstart.md`](integrator_quickstart.md) — minimal static JSON examples
- [`docs/minimal_api_usage_walkthrough.md`](minimal_api_usage_walkthrough.md) — API-first walkthrough
- [`docs/pilot_ready_handoff_plan.md`](pilot_ready_handoff_plan.md) — pilot-ready handoff plan
- [`docs/pilot_ready_release_decision.md`](pilot_ready_release_decision.md) — pilot-ready release decision
- [`docs/examples/gl061/api_smoke_manifest.json`](examples/gl061/api_smoke_manifest.json) — machine-readable smoke manifest
- [`backend/tests/test_gl061_demo_runner_api_smoke.py`](../backend/tests/test_gl061_demo_runner_api_smoke.py) — validation test for the demo runner
- [`docs/pilot_partner_preparation_pack.md`](pilot_partner_preparation_pack.md) — GL-062 pilot partner preparation pack
