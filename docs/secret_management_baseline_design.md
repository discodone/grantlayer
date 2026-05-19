# GrantLayer Secret Management Baseline Design

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose

This document defines the secret management baseline for GrantLayer as a **reusable, adaptable API-first product core**.

It clarifies:
- which secret types GrantLayer may need
- which values must never be stored in records, examples, logs, exports, or fixtures
- which local/test/demo shortcuts are acceptable outside production
- which production secret requirements must be explicit before production use
- which secret source boundaries should remain configurable
- which later implementation blocks should build runtime secret behavior

This is a **product-foundation security design document**. It does not implement secret management code.

## 2. Product secret management principle

GrantLayer should keep **secrets outside Product Core records, examples, exports, logs, and fixtures**.

The Product Core owns the contract of what secrets are needed, where they must not appear, and what production behavior must enforce. The Product Core does not depend on one specific vault, secret manager, or credential provider. Secret sourcing, rotation, and storage should remain replaceable adapter boundaries.

Local, test, and demo secret placeholders must **not accidentally become production behavior**. Any runtime mode that permits placeholder secrets must explicitly declare that it is not production-ready.

## 3. Runtime-mode secret expectations

### 3.1 local-dev

- **Secret expectation**: developer convenience; deterministic or placeholder secrets acceptable
- **Allowed shortcut**: local-only demo signing key reference, no external secret manager, no credential rotation
- **Secret source expectation**: may be a local file path or inline placeholder; must be clearly labeled as non-production
- **Production claim boundary**: **must not** be described as production-ready

### 3.2 test

- **Secret expectation**: deterministic automated verification; synthetic secrets acceptable
- **Allowed shortcut**: test-only fixture identifiers, mock secret sources, no real credentials
- **Secret source expectation**: in-memory or temporary; must be isolated from production data
- **Production claim boundary**: **must not** be described as production-ready

### 3.3 demo

- **Secret expectation**: illustrative non-production walkthrough; placeholder secrets acceptable
- **Allowed shortcut**: demo fixture identifiers, local-only references, no real credential values
- **Secret source expectation**: local-only and labeled as synthetic; must not resemble real secrets
- **Production claim boundary**: **must not** be described as production-ready; explicitly labeled as demonstration only

### 3.4 integration

- **Secret expectation**: controlled external technical integration; partner-agreed secret handling
- **Allowed shortcut**: partner-agreed secret source with documented constraints
- **Secret source expectation**: partner-agreed secret manager or environment boundary
- **Production claim boundary**: **must not** be described as production-ready without explicit partner agreement and documented constraints

### 3.5 staging

- **Secret expectation**: production-like validation; same secret target as production
- **Allowed shortcut**: same secret source and rotation target as production; realistic but synthetic data
- **Secret source expectation**: production-like secret manager or validated environment boundary
- **Production claim boundary**: **must not** be described as production-ready; explicitly labeled as pre-production validation

### 3.6 production

- **Secret expectation**: explicit hardened operation only
- **Allowed shortcut**: **none** — every required secret must come from an explicit, validated source, and the system must fail-closed if missing
- **Secret source expectation**: explicit secret manager, validated environment boundary, or approved secret provider
- **Production claim boundary**: may be described as production-ready **only** when all required secret sources are explicit, validated, and monitored

## 4. Secret categories

The following secret categories define the secret inventory GrantLayer may need. Each category must be sourced, stored, and logged according to the rules in this document.

### 4.1 Admin/operator tokens

- **Purpose**: authenticate and authorize human operators and admins
- **Sensitivity**: high — direct access to Product Core state
- **Production requirement**: must come from explicit auth provider; must not be demo or default tokens

### 4.2 Service-to-service credentials

- **Purpose**: authenticate internal and external services to each other
- **Sensitivity**: high — automated access to workflow and data boundaries
- **Production requirement**: must come from explicit service identity provider; must support rotation

### 4.3 Auth provider credentials

- **Purpose**: client secrets, shared secrets, or validation keys for the active auth provider
- **Sensitivity**: critical — compromise allows identity forgery
- **Production requirement**: must be explicit and validated; must not appear in logs or records

### 4.4 Database credentials

- **Purpose**: connection authentication for the active persistence backend
- **Sensitivity**: critical — full data access
- **Production requirement**: must be explicit and sourced through secret boundary; must not appear in logs or error messages

### 4.5 Signing key material

- **Purpose**: Ed25519 or future signing keys for grants, evidence, and provenance
- **Sensitivity**: critical — compromise allows signature forgery
- **Production requirement**: must be explicit, rotated, and stored in a managed secret boundary; no synthetic or demo keypairs

### 4.6 Evidence storage credentials

- **Purpose**: access keys or tokens for external evidence storage backends
- **Sensitivity**: high — evidence tampering or deletion risk
- **Production requirement**: must be explicit and durable; must not appear in evidence bundle metadata

### 4.7 External integration credentials

- **Purpose**: API keys, tokens, or certificates for partner and third-party services
- **Sensitivity**: high — external data and control surface
- **Production requirement**: must be explicit and scoped; must be rotated on partner change

### 4.8 Webhook secrets

- **Purpose**: shared secrets to verify incoming webhook payloads
- **Sensitivity**: high — webhook spoofing risk
- **Production requirement**: must be explicit and rotated; must not be hard-coded

### 4.9 Encryption keys

- **Purpose**: keys for encrypting sensitive fields at rest or in transit
- **Sensitivity**: critical — decryption of institutional data
- **Production requirement**: must be explicit, rotated, and managed; must not appear in backups unencrypted

### 4.10 Session/token signing secrets

- **Purpose**: keys used to sign session tokens, state tokens, or transient auth artifacts
- **Sensitivity**: high — session hijacking risk
- **Production requirement**: must be explicit, rotated, and different from auth provider credentials

### 4.11 API client credentials

- **Purpose**: credentials issued to integrators and external clients
- **Sensitivity**: medium–high — scoped access to Product Core API
- **Production requirement**: must be explicit, scoped, and revocable; must not appear in OpenAPI examples

### 4.12 Backup storage credentials

- **Purpose**: access keys or tokens for backup and restore storage
- **Sensitivity**: high — full data exfiltration risk
- **Production requirement**: must be explicit and scoped to backup operations only

### 4.13 Observability/logging sink credentials

- **Purpose**: tokens or API keys for metrics, logging, or alerting backends
- **Sensitivity**: medium — observability data may contain operational detail
- **Production requirement**: must be explicit; must not appear in startup logs or diagnostics

### 4.14 Optional blockchain/wallet keys

- **Purpose**: optional signing keys for blockchain anchoring or wallet operations
- **Sensitivity**: high–critical depending on on-chain value
- **Production requirement**: if enabled, must be explicit, managed, and kept off-chain in Product Core records

### 4.15 Demo/test placeholder identifiers

- **Purpose**: non-secret labels and fixture identifiers used in local, test, and demo environments
- **Sensitivity**: none — these are not real credentials
- **Production requirement**: **must not** be present in production; must be clearly labeled as placeholders

## 5. Allowed local/test/demo shortcuts

The following shortcuts are acceptable **only outside production**:

- **Deterministic placeholder identifiers** — synthetic labels like `demo-admin` or `test-operator` that carry no real secret value
- **Local-only demo admin token references without real secret values** — references that describe where a token would come from, not the token itself
- **Test-only fake identity labels that are not credentials** — fixture names that are clearly not real accounts or passwords
- **Local SQLite path references** — file paths for local development that contain no credentials
- **Fixture IDs** — deterministic synthetic identifiers used in test fixtures
- **Disabled external integrations** — integrations that are explicitly turned off, requiring no live credentials
- **Dry-run-only smoke manifests** — manifests that simulate secret resolution without real values

These shortcuts are **not valid production secrets**. Production must replace all shortcuts with explicit secret source configuration, validated credentials, and managed rotation.

## 6. Production-required secret behavior

Production mode must require the following secret behavior. The system must refuse to start if any required secret is missing, invalid, or uses a placeholder.

- **Explicit secret source** — the secret manager or source must be declared and validated
- **No hard-coded default secrets** — no secret may be embedded in source code, config files, or defaults
- **No demo/default admin token** — production must not accept demo or synthetic operator tokens
- **No secrets in examples or fixtures** — examples and fixtures must use labels and placeholders only
- **No secrets in logs or exports** — logs, audit records, evidence bundles, and exports must never contain secret values
- **Explicit database credential source** — database credentials must be sourced through the secret boundary
- **Explicit auth provider credential source** — auth provider secrets must be sourced through the secret boundary
- **Explicit signing/key management source** — signing keys must be sourced through the secret boundary
- **Explicit evidence storage credential source where external storage is used** — evidence storage access must be sourced through the secret boundary
- **Rotation and revocation expectations** — secrets must support rotation and revocation; stale secrets must be rejected
- **Fail-closed startup behavior if required secrets are missing** — the system must refuse to start rather than assume a safe default

## 7. Secret source boundary

The following boundary rules protect the Product Core from accidental secret leakage and provider lock-in:

- **Product Core should not depend on one specific vault or secret provider** — the core owns the secret contract, not provider-specific fields
- **Environment variables may be a future source, but should be validated through a config boundary** — raw environment reads should not scatter through modules
- **External secret managers may be future adapters** — HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, Google Secret Manager, and others may all be future adapter targets
- **Provider-specific secret fields should not leak into Product Core records** — audit records and evidence bundles should reference secret source names, not raw values
- **Secret values should be resolved only at runtime where needed** — secrets should not be loaded eagerly into global state unless required
- **Examples should use labels/placeholders, not secret-looking values** — docs, fixtures, and OpenAPI examples must use obvious placeholders like `<SIGNING_KEY_SOURCE>`

## 8. Forbidden secret locations

Secrets must not appear in:

- committed source code
- docs examples
- JSON fixtures
- OpenAPI examples
- logs
- auditor exports
- evidence bundle metadata
- provenance records
- compliance readiness summaries
- git history
- screenshots
- test output

## 9. Redaction and audit expectations

Secret handling must meet the following redaction and audit expectations:

- **Secret-bearing configuration must be redacted in diagnostics** — startup logs, health checks, and config dumps must mask or omit secret values
- **Denied access or missing-secret failures should be auditable where appropriate** — failed secret resolution should produce audit records when feasible
- **Audit records must not contain secret values** — no plaintext tokens, keys, or credentials in audit logs
- **Secret source names may be recorded, but secret values must not** — it is acceptable to log that a secret was resolved from `vault://signing-key`, but not the value itself
- **External integration failures must not leak credentials** — error messages from external services must be sanitized before inclusion in logs or API responses

## 10. Production fail-closed rules

Production mode must enforce the following fail-closed secret behavior:

- **Production mode must not start with missing required secret source** — the system must refuse to start if any required secret source is not configured
- **Production mode must not silently fall back to demo secrets** — no automatic fallback to synthetic or demo credentials
- **Production mode must not allow placeholder secrets** — placeholder identifiers like `demo-admin` must be rejected
- **Production mode must fail closed if secret-bearing config is incomplete** — missing, invalid, or unvalidated secret configuration must block startup
- **Production mode must not expose secret values through API or logs** — no endpoint or log may return a secret value

## 11. Future implementation expectations

The following implementation blocks should be built after this planning document is accepted:

1. **Secret configuration schema** — a validated schema that declares required secrets, their sources, and rotation expectations
2. **Runtime secret source validation** — startup checks that verify secret sources are reachable and returning valid values
3. **Production fail-closed startup checks** — explicit checks that refuse to start in production mode if required secrets are missing
4. **Secret redaction helper** — a utility that masks or omits secret-bearing fields from logs, diagnostics, and exports
5. **Signing/key management abstraction** — a boundary that abstracts key storage and rotation so the Product Core does not depend on one key provider
6. **Database credential configuration** — explicit database credential sourcing with masking in logs and error messages
7. **Auth provider secret configuration** — explicit auth provider secret sourcing with validation and rotation expectations
8. **Evidence storage credential configuration** — explicit evidence storage credential sourcing where external storage is used
9. **Observability sink secret configuration** — explicit observability backend credential sourcing with redaction in startup output
10. **Integration tests for secret leakage prevention** — tests that verify secrets do not appear in logs, exports, responses, or fixtures under any runtime mode

## 12. What not to implement yet

This block does **not** implement:

- vault integration
- secret loader
- environment variable loader
- key rotation
- HSM integration
- KMS integration
- OAuth/JWT/SSO secret handling
- production deployment secrets
- Kubernetes secrets
- Docker secrets
- cloud secret manager
- wallet custody
- payment keys

These remain valid future workstreams but must be scoped in separate issues.

## 13. Decision boundary

GrantLayer should **not** claim production secret management readiness until secret sources, required production secrets, redaction, fail-closed startup checks, and leakage-prevention tests are implemented and verified.

Any statement to external partners, documentation, or marketing materials must include the non-production constraint. If a partner asks about production timelines, reference this model, the GL-067 production auth and operator access design, the GL-066 runtime configuration environment model, and the GL-063 production-hardening roadmap.

---

## See also

- [`docs/production_auth_operator_access_design.md`](production_auth_operator_access_design.md) — GL-067 production auth and operator access design
- [`docs/runtime_configuration_environment_model.md`](runtime_configuration_environment_model.md) — GL-066 runtime configuration and environment model
- [`docs/production_hardening_roadmap.md`](production_hardening_roadmap.md) — GL-063 production-hardening roadmap
- [`docs/product_architecture_extension_boundaries.md`](product_architecture_extension_boundaries.md) — GL-065 product architecture and extension boundaries
- [`docs/deployment_package_runtime_modes_design.md`](deployment_package_runtime_modes_design.md) — GL-069 deployment package and runtime modes design
- [`docs/examples/gl068/secret_inventory_model.json`](examples/gl068/secret_inventory_model.json) — machine-readable secret inventory model
- [`docs/examples/gl068/secret_handling_policy_catalog.json`](examples/gl068/secret_handling_policy_catalog.json) — machine-readable secret handling policy catalog
- [`backend/tests/test_gl068_secret_management_baseline_design.py`](../backend/tests/test_gl068_secret_management_baseline_design.py) — validation test for this secret management baseline design
