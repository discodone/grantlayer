# GrantLayer Runtime Configuration and Environment Model

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose

This document defines the runtime and environment model for GrantLayer as a **reusable, adaptable API-first product core**.

It clarifies:
- which runtime modes GrantLayer should support
- which configuration categories belong to the product foundation
- what is safe for local, test, and demo defaults
- what must be explicit before any production use
- what should remain configurable instead of hard-coded
- what later implementation blocks should build

This is a **product-foundation architecture and planning document**. It does not implement runtime configuration code, a config loader, or any deployment automation.

## 2. Product configuration principle

GrantLayer should make runtime mode, environment assumptions, secrets, persistence, auth, and external integrations **explicit**.

Local, test, and demo defaults must not accidentally become production behavior. Every runtime mode must be declared, validated, and respected by the product core and its extensions. Configuration that affects data integrity, security, auditability, or compliance must not rely on implicit defaults in production.

## 3. Runtime modes

GrantLayer supports the following runtime modes, from least to most constrained:

### 3.1 local-dev

- **Purpose**: developer convenience during active development
- **Allowed defaults**: SQLite, local file paths, demo admin tokens, in-memory fixtures, simplified logging, no external secret manager, no backup guarantee, no observability stack
- **Production claim boundary**: **must not** be described as production-ready or pilot-ready

### 3.2 test

- **Purpose**: deterministic automated verification in CI and local test suites
- **Allowed defaults**: SQLite in-memory or temporary files, synthetic data, mock auth, deterministic fixtures, no external integrations, no network exposure
- **Production claim boundary**: **must not** be described as production-ready or pilot-ready

### 3.3 demo

- **Purpose**: illustrative non-production walkthrough for integrators, partners, and stakeholders
- **Allowed defaults**: demo fixtures, example data, local-only binding, simplified auth, no real secrets, no backup/restore guarantee, no compliance certification
- **Production claim boundary**: **must not** be described as production-ready; explicitly labeled as demonstration only

### 3.4 integration

- **Purpose**: controlled external technical integration with partner systems
- **Allowed defaults**: partner-agreed database and auth configuration, limited network exposure, basic observability, documented backup expectations
- **Production claim boundary**: **must not** be described as production-ready without explicit partner agreement and documented constraints

### 3.5 staging

- **Purpose**: production-like validation before production deployment
- **Allowed defaults**: same backend and auth as production target, realistic data (synthetic or anonymized), full observability, backup/restore tested, network exposure limited and documented
- **Production claim boundary**: **must not** be described as production-ready; explicitly labeled as pre-production validation

### 3.6 production

- **Purpose**: explicit hardened operation only
- **Allowed defaults**: **none** — every required configuration must be explicit, validated, and fail-closed if missing
- **Production claim boundary**: may be described as production-ready **only** when all required configuration is explicit, validated, and monitored

## 4. Configuration categories

The following configuration categories define the product foundation boundary between safe local/test/demo defaults and production-required explicit settings:

1. **Runtime mode** — the declared mode (`local-dev`, `test`, `demo`, `integration`, `staging`, `production`). Must be validated on startup.
2. **Database backend** — which persistence backend is active (SQLite, PostgreSQL, or future backends). Must be explicit in production.
3. **Persistence path / connection** — file path or connection string. Must be explicit and reachable in production.
4. **Admin/operator access** — who can mutate Product Core state and how roles are assigned. Must be explicit in production.
5. **Authentication provider** — local token, OAuth, JWT, SSO, or mTLS. Must be explicit in production; demo defaults must not persist.
6. **Secret management** — how keys, tokens, and credentials are sourced, rotated, and stored. Must be explicit in production; no demo keypairs allowed.
7. **Signing/key management** — how Ed25519 or future signing keys are managed. Must be explicit in production.
8. **Evidence storage** — where evidence bundles are persisted. Must be durable and explicit in production.
9. **Evidence verification strategy** — default SHA-256 recomparison or additional strategies. Must be documented in production.
10. **Audit/provenance retention** — how long audit events and provenance records are retained. Must be explicit in production.
11. **Compliance/readiness profile** — which compliance dimensions are enforced and how readiness is evaluated. Must be documented in production.
12. **Policy/rule pack profile** — which policy rules are active and where they are loaded from. Must be explicit in production.
13. **API server binding / network exposure** — host, port, and whether the server is exposed beyond localhost. Must be explicit and restricted in production.
14. **CORS / external access** — which origins and clients are permitted. Must be explicit in production.
15. **Logging / observability** — structured logging, metrics, alerting, and tracing configuration. Must be explicit in production.
16. **Backup / restore** — automated backup schedule, retention, point-in-time recovery, and disaster runbooks. Must be explicit in production.
17. **Feature flags / extension toggles** — which extensions and experimental features are enabled. Must be explicit in production.
18. **External integrations** — which external services are connected and how they are authenticated. Must be explicit in production.
19. **Demo/test fixture mode** — whether synthetic fixtures are loaded and how they are isolated from real data. Must be disabled in production.
20. **Safe failure behavior** — how the system behaves when configuration is missing, invalid, or untrusted. Must fail closed in production.

## 5. Safe local/test/demo defaults

The following defaults are acceptable only outside production:

- **SQLite local database** — acceptable for local-dev, test, and demo; not acceptable for production without explicit justification
- **Local file paths** — acceptable for evidence storage in local-dev and test; production requires durable, explicit storage
- **Demo admin tokens** — acceptable for local-dev and demo; production requires real auth provider configuration
- **In-memory/test fixtures** — acceptable for test and demo; must be isolated from real data and disabled in production
- **Local-only API binding** (`localhost` or `127.0.0.1`) — acceptable for local-dev, test, and demo; production requires explicit network exposure rules
- **Simplified logging** — acceptable for local-dev and test; production requires structured logging and observability configuration
- **No external secret manager** — acceptable for local-dev and test; production requires explicit secret management
- **No backup/restore guarantee** — acceptable for local-dev, test, and demo; production requires explicit backup configuration
- **No production observability** — acceptable for local-dev, test, and demo; production requires explicit observability configuration
- **Demo evidence examples** — acceptable for demo and test; must not be presented as real institutional records

## 6. Production-required explicit configuration

Production mode must require explicit settings for the following. The system must refuse to start if any required configuration is missing or invalid.

- **Runtime mode** — must be explicitly set to `production`
- **Database backend and connection** — must specify backend type and connection details
- **Auth provider** — must specify the authentication mechanism and configuration
- **Operator/admin access model** — must define roles, assignments, and enforcement
- **Secret management** — must specify secret source, rotation policy, and access controls
- **Signing/key management** — must specify key source, rotation, and storage
- **Evidence storage** — must specify durable storage backend and retention
- **Retention policy** — must specify audit, provenance, and evidence retention periods
- **Observability/logging** — must specify structured logging, metrics, and alerting configuration
- **Backup/restore** — must specify schedule, retention, and recovery procedures
- **Network binding** — must specify host, port, and TLS configuration
- **CORS/external access** — must specify permitted origins and access controls
- **Deployment environment** — must specify container, host, or orchestration context
- **Compliance/legal boundary** — must specify which compliance dimensions are enforced and which remain external

## 7. Configuration boundaries

The following boundaries protect the Product Core from accidental implicit behavior:

- **Product Core should read configuration through a defined boundary** — not by scattering environment variable reads throughout modules.
- **Modules should not read arbitrary environment variables directly** — all configuration should pass through a validated configuration boundary.
- **Secrets must not be written into records, logs, examples, or exports** — no plaintext tokens, keys, or credentials in evidence bundles, audit events, or error messages.
- **Extension/adaptor behavior should be configured explicitly** — adapters should not fall back to hidden defaults; they should declare their configuration requirements.
- **Production mode should fail closed if required configuration is missing** — the system must refuse to start rather than assume a safe default.

## 8. Environment matrix summary

| Mode | Purpose | Defaults | Production claim |
|------|---------|----------|------------------|
| `local-dev` | Developer convenience | SQLite, demo tokens, local files, no observability | No |
| `test` | Deterministic automated verification | In-memory fixtures, mock auth, no network | No |
| `demo` | Illustrative non-production walkthrough | Demo fixtures, local binding, no real secrets | No |
| `integration` | Controlled external technical integration | Partner-agreed config, limited exposure | Only with documented constraints |
| `staging` | Production-like validation | Same target backend as prod, full observability | No — pre-production only |
| `production` | Explicit hardened operation only | None — all required config must be explicit | Only when fully configured and validated |

## 9. Future implementation expectations

The following implementation blocks should be built after this planning document is accepted:

1. **Configuration schema / loader** — a validated configuration schema and loader that reads from a defined boundary.
2. **Runtime mode validation** — startup validation that rejects invalid or undeclared runtime modes.
3. **Production fail-closed config checks** — explicit checks that refuse to start in production mode if required configuration is missing.
4. **Secret source abstraction** — a boundary that abstracts secret storage so the Product Core does not depend on a specific vault or manager.
5. **Database backend selection** — explicit backend selection with validation and connection testing.
6. **Evidence storage backend selection** — explicit evidence storage configuration with durability checks.
7. **Auth provider configuration** — explicit auth provider setup with fallback rejection in production.
8. **Observability configuration** — structured logging, metrics, and alerting setup.
9. **Backup/restore configuration** — automated backup schedule and restore validation.
10. **Extension/adaptor toggle configuration** — explicit enable/disable for extensions and experimental features.

## 10. What not to implement yet

This block does **not** implement:

- A configuration loader or parser
- Production deployment automation or containers
- Secret manager integration (HashiCorp Vault, AWS Secrets Manager, etc.)
- Auth provider integration (OAuth, JWT, SSO, mTLS)
- Docker or deployment setup
- PostgreSQL CI gating
- Monitoring stack (Prometheus, Grafana, etc.)
- Backup system implementation
- Plugin runtime or adapter framework
- SaaS tenant configuration
- Multi-tenant isolation

These remain valid future workstreams but must be scoped in separate issues.

## 11. Decision boundary

GrantLayer should **not** claim production readiness until runtime mode, secrets, auth, persistence, observability, and backup configuration are **explicit, validated, and fail closed** in production mode.

Any statement to external partners, documentation, or marketing materials must include the non-production constraint. If a partner asks about production timelines, reference this model, the GL-063 production-hardening roadmap, and the GL-064 API/OpenAPI contract hardening review.

---

## See also

- [`docs/product_architecture_extension_boundaries.md`](product_architecture_extension_boundaries.md) — GL-065 product architecture and extension boundaries
- [`docs/production_auth_operator_access_design.md`](production_auth_operator_access_design.md) — GL-067 production auth and operator access design
- [`docs/production_hardening_roadmap.md`](production_hardening_roadmap.md) — GL-063 production-hardening roadmap
- [`docs/api_openapi_contract_hardening_review.md`](api_openapi_contract_hardening_review.md) — GL-064 API/OpenAPI contract hardening review
- [`docs/examples/gl066/runtime_environment_matrix.json`](examples/gl066/runtime_environment_matrix.json) — machine-readable runtime environment matrix
- [`docs/examples/gl066/configuration_contract_catalog.json`](examples/gl066/configuration_contract_catalog.json) — machine-readable configuration contract catalog
- [`backend/tests/test_gl066_runtime_configuration_environment_model.py`](../backend/tests/test_gl066_runtime_configuration_environment_model.py) — validation test for this runtime configuration environment model
