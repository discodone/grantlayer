# GrantLayer Deployment Package and Runtime Modes Design

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose

This document defines how GrantLayer should later be packaged, run, configured, and deployed as a **reusable, adaptable API-first product core**.

It clarifies:
- which deployment/runtime modes GrantLayer should support
- what a reference deployment package should contain
- what belongs to product packaging versus environment-specific deployment
- how local, demo, test, integration, staging, and production runtime modes should map to deployment expectations
- which deployment defaults are safe outside production
- which production deployment requirements must be explicit
- which later implementation blocks should build packaging and runtime behavior

This is a **product-foundation deployment design document**. It does not implement Docker, deployment automation, runtime configuration code, CI, or infrastructure.

## 2. Product deployment principle

GrantLayer should **separate product package, runtime configuration, secret source, auth provider, persistence backend, and deployment environment**.

The product package owns the runnable application code, the stable API contract, and the canonical configuration schema. The deployment environment owns the runtime mode declaration, the host or container layout, the network exposure, and the operational runbooks.

**Local, demo, and test convenience must not accidentally become production deployment behavior.** Any runtime mode that permits non-production defaults must explicitly declare that it is not production-ready, and the package labeling must reinforce this boundary.

## 3. Runtime mode to deployment mode mapping

### 3.1 local-dev

- **Purpose**: developer convenience during active development
- **Deployment expectation**: runs as a local process with local-only binding; no external dependencies required
- **Allowed defaults**: SQLite, local file paths, demo fixtures, in-memory fixtures, simplified logging, no observability stack, no backup guarantee, no external secret manager, no production auth provider
- **Production claim boundary**: **must not** be described as production-ready or pilot-ready

### 3.2 test

- **Purpose**: deterministic automated verification in CI and local test suites
- **Deployment expectation**: ephemeral process with isolated storage; no network exposure; no external integrations
- **Allowed defaults**: SQLite in-memory or temporary files, synthetic data, mock auth, deterministic fixtures, simplified logging, no external integrations, no network exposure
- **Production claim boundary**: **must not** be described as production-ready or pilot-ready

### 3.3 demo

- **Purpose**: illustrative non-production walkthrough for integrators, partners, and stakeholders
- **Deployment expectation**: local or temporary hosted instance with local-only or documented limited binding; demo fixtures preloaded
- **Allowed defaults**: demo fixtures, example data, local-only API binding, simplified auth, no real secrets, no backup/restore guarantee, no compliance certification
- **Production claim boundary**: **must not** be described as production-ready; explicitly labeled as demonstration only

### 3.4 integration

- **Purpose**: controlled external technical integration with partner systems
- **Deployment expectation**: partner-agreed host or container with documented constraints; limited network exposure
- **Allowed defaults**: partner-agreed database and auth configuration, limited network exposure, basic observability, documented backup expectations, documented constraints
- **Production claim boundary**: **must not** be described as production-ready without explicit partner agreement and documented constraints

### 3.5 staging

- **Purpose**: production-like validation before production deployment
- **Deployment expectation**: production target layout without production data; same package as production target; full observability enabled
- **Allowed defaults**: same backend and auth as production target, realistic but synthetic data, full observability, backup/restore tested, network exposure limited and documented
- **Production claim boundary**: **must not** be described as production-ready; explicitly labeled as pre-production validation

### 3.6 production

- **Purpose**: explicit hardened operation only
- **Deployment expectation**: production-hardened deployment with explicit configuration, validated secrets, explicit auth, durable persistence, explicit observability, explicit backup/restore, health checks, and documented runbooks
- **Allowed defaults**: **none** — every required configuration must be explicit, validated, and fail-closed if missing
- **Production claim boundary**: may be described as production-ready **only** when all required deployment configuration is explicit, validated, and monitored

## 4. Deployment package components

A reference GrantLayer deployment package should contain the following components. Each component is described in terms of scope (product package versus environment), intent, and production requirement.

### 4.1 Application package

- **Scope**: product package
- **Intent**: the runnable GrantLayer application code, dependencies, and entry points
- **Production requirement**: must be built from validated source with reproducible build steps; no debug or test code in production artifact

### 4.2 Configuration schema

- **Scope**: product package plus environment-specific values
- **Intent**: the validated schema that defines which configuration fields are required, optional, and per-runtime-mode
- **Production requirement**: must be explicit and versioned; production must refuse to start if required fields are missing or invalid

### 4.3 Runtime mode declaration

- **Scope**: environment-specific
- **Intent**: the declared runtime mode (`local-dev`, `test`, `demo`, `integration`, `staging`, `production`)
- **Production requirement**: must be explicitly set; must be validated on startup; must fail closed if undeclared or invalid

### 4.4 Database / persistence configuration

- **Scope**: environment-specific
- **Intent**: which persistence backend is active and how it is connected (SQLite, PostgreSQL, or future backends)
- **Production requirement**: must be explicit, durable, reachable; must not default to SQLite or in-memory without explicit justification

### 4.5 Secret source configuration

- **Scope**: environment-specific
- **Intent**: how keys, tokens, and credentials are sourced, rotated, and stored
- **Production requirement**: must be explicit; no demo or placeholder secrets; must fail closed if secret source is missing

### 4.6 Auth / operator access configuration

- **Scope**: environment-specific
- **Intent**: which auth provider and operator access model is active
- **Production requirement**: must be explicit and validated; no demo tokens or default passwords; must fail closed if missing

### 4.7 Evidence storage configuration

- **Scope**: environment-specific
- **Intent**: where evidence bundles are persisted and how they are retrieved
- **Production requirement**: must be durable, explicit, and scoped; must not leak storage credentials into evidence metadata

### 4.8 Policy / rule pack configuration

- **Scope**: product package plus environment-specific selection
- **Intent**: which policy rules are active and where they are loaded from
- **Production requirement**: must be explicit; must not load demo or unverified rule packs in production

### 4.9 Observability / logging configuration

- **Scope**: environment-specific
- **Intent**: structured logging, metrics, alerting, and tracing backends and thresholds
- **Production requirement**: must be explicit; must not leak sink credentials in startup output or diagnostics

### 4.10 Backup / restore configuration

- **Scope**: environment-specific
- **Intent**: automated backup schedule, retention policy, point-in-time recovery, and disaster runbooks
- **Production requirement**: must be explicit; must not claim durability without tested restore procedures

### 4.11 Health / readiness checks

- **Scope**: product package with environment-specific endpoints
- **Intent**: health and readiness probes that verify the application is running and dependencies are reachable
- **Production requirement**: must be implemented and exposed; must not leak secrets or sensitive configuration in responses

### 4.12 API / OpenAPI contract artifact

- **Scope**: product package
- **Intent**: the versioned OpenAPI specification that defines the API contract
- **Production requirement**: must match the deployed application version; must be available to integrators

### 4.13 Demo / sample data bundle

- **Scope**: product package (for local/demo/test only)
- **Intent**: deterministic fixtures, example grants, evidence bundles, and policy rules for walkthroughs
- **Production requirement**: must not be loaded in production; must be labeled as non-production

### 4.14 Integration example bundle

- **Scope**: product package
- **Intent**: example API calls, SDK snippets, and partner integration patterns
- **Production requirement**: must not contain real credentials or secrets; must be labeled as examples only

### 4.15 Operator runbook

- **Scope**: environment-specific (reference version in product package)
- **Intent**: step-by-step instructions for common operator tasks (restart, migrate, inspect evidence, export audit record, rotate key)
- **Production requirement**: must be specific to the target environment; must not contain secrets

### 4.16 Upgrade / migration notes

- **Scope**: product package
- **Intent**: documented steps and compatibility expectations between versions
- **Production requirement**: must be deterministic and tested; must include rollback guidance

### 4.17 Extension / adaptor configuration

- **Scope**: environment-specific
- **Intent**: which extensions, adapters, and optional integrations are enabled
- **Production requirement**: must be explicit; must not load unverified or unauthorized extensions

### 4.18 Production hardening checklist

- **Scope**: product package (reference) and environment-specific (completed)
- **Intent**: a checklist that verifies deployment-critical configuration before a production claim is made
- **Production requirement**: must be completed and signed off before any production claim

## 5. Safe local / test / demo package defaults

The following defaults are acceptable **only outside production**:

- **Local process execution** — single-process startup with no container orchestration
- **SQLite or local persistence** — acceptable for local-dev, test, and demo; not acceptable for production without explicit justification
- **Local-only API binding** (`localhost` or `127.0.0.1`) — acceptable for local-dev, test, and demo; production requires explicit network exposure rules
- **Demo / sample data** — acceptable for demo and test; must be isolated from real data and clearly labeled
- **Dry-run smoke behavior** — acceptable for test and demo; does not validate real dependencies
- **Placeholder identities** — acceptable for local-dev, test, and demo; must not be described as real authentication
- **Disabled external integrations** — acceptable for local-dev, test, and demo; reduces setup friction at the cost of functional coverage
- **Simplified logging** — acceptable for local-dev and test; production requires structured logging and observability configuration
- **No backup / restore guarantee** — acceptable for local-dev, test, and demo; production requires explicit backup configuration
- **No production secret manager** — acceptable for local-dev and test; production requires explicit secret management

These defaults are **not valid production deployment behavior**. Production must replace all shortcuts with explicit deployment-critical configuration, validated dependencies, and documented runbooks.

## 6. Production-required deployment behavior

Production mode must require the following deployment behavior. The system must refuse to start if any required deployment-critical configuration is missing, invalid, or uses a non-production default.

- **Explicit runtime mode** — must be explicitly set to `production` and validated on startup
- **Explicit deployment environment** — must declare the target environment context (host, container, or orchestration)
- **Explicit database / persistence backend** — must specify backend type and connection details; must validate reachability
- **Explicit secret source** — must declare secret manager or source; must validate reachability and value validity
- **Explicit auth / operator access configuration** — must specify auth provider and operator bootstrap; must validate role mapping
- **Explicit evidence storage configuration** — must specify durable storage backend and retention
- **Explicit observability / logging configuration** — must specify structured logging, metrics, and alerting configuration
- **Explicit backup / restore plan** — must specify schedule, retention, and recovery procedures; must be tested
- **Explicit network binding / exposure** — must specify host, port, TLS, and access restrictions
- **Explicit health / readiness checks** — must be implemented and returning accurate status
- **Explicit production hardening checklist** — must be completed and verified before startup
- **Fail-closed behavior for missing required configuration** — the system must refuse to start rather than assume a safe default

## 7. Deployment boundaries

The following boundaries protect the Product Core from accidental implicit deployment behavior and deployment-specific coupling:

- **Product Core should not depend on one hosting platform** — the core should run wherever the runtime configuration boundary is satisfied; Docker, Kubernetes, cloud deployment, and bare-metal are all potential future targets
- **Docker / Kubernetes / cloud deployment may be future packaging options, not Product Core assumptions** — future packaging layers may wrap the product package, but the Product Core must not require them
- **Deployment-specific configuration should stay outside Product Core records** — host names, container IDs, and infrastructure metadata should not appear in evidence bundles, audit records, or provenance records
- **Secrets must not be baked into images, docs, examples, fixtures, or logs** — the build process must not embed credentials into artifacts
- **Extension / adaptor configuration should be environment-specific** — which adapters are active should be part of runtime configuration, not hard-coded into the product package
- **Production mode should fail closed if deployment-critical configuration is missing** — missing, invalid, or unvalidated deployment configuration must block startup

## 8. Reference package expectation

A future reference deployment package for GrantLayer should include:

- **Runnable application package** — validated build artifact or source tree with reproducible build steps
- **Example non-production configuration** — safe local/demo/test configuration files with explicit non-production warning labels
- **OpenAPI contract artifact** — versioned OpenAPI specification matching the deployed application
- **Example rule packs** — deterministic policy requirements, exclusions, and permission profiles
- **Example evidence fixtures** — structured evidence bundles and verification examples
- **Dry-run smoke script** — lightweight executable confidence check that validates the application starts and health checks respond
- **Operator runbook** — common operations with step-by-step instructions and rollback guidance
- **Production hardening checklist** — pre-deployment verification list covering runtime mode, secrets, auth, persistence, observability, backup/restore, and network exposure
- **Explicit non-production warning labels** — every example, fixture, and demo configuration must be labeled as non-production

## 9. Future implementation expectations

The following implementation blocks should be built after this planning document is accepted:

1. **Configuration schema / loader** — a validated configuration schema and loader that reads from a defined boundary
2. **Runtime mode validation** — startup validation that rejects invalid or undeclared runtime modes
3. **Health / readiness check baseline** — basic health and readiness probes with deterministic responses
4. **Reference local run command** — documented steps to start the application locally for development and demo
5. **Safe non-production example config** — example configuration files with explicit non-production labels and safe defaults
6. **Packaging checklist** — artifact checklist that verifies all package components are present before distribution
7. **Docker / container packaging review** — future review and potential implementation of container packaging (outside Product Core)
8. **Production deployment guide** — documented steps for deploying to a production-hardened environment
9. **CI packaging validation** — automated validation that the package contents are correct and no secrets are embedded
10. **Upgrade / migration guide** — documented steps and compatibility expectations for version upgrades

## 10. What not to implement yet

This block does **not** implement:

- Dockerfile
- docker-compose
- Kubernetes manifests
- cloud deployment
- production CI/CD
- reverse proxy
- TLS automation
- secret manager integration
- monitoring stack
- backup system
- production database automation
- hosted SaaS platform
- multi-tenant deployment

These remain valid future workstreams but must be scoped in separate issues.

## 11. Decision boundary

GrantLayer should **not** claim production deployment readiness until runtime mode, configuration, secrets, auth, persistence, observability, backup/restore, health checks, and deployment hardening are **explicit, validated, and fail closed** in production mode.

Any statement to external partners, documentation, or marketing materials must include the non-production constraint. If a partner asks about production timelines, reference this model, the GL-068 secret management baseline design, the GL-067 production auth and operator access design, the GL-066 runtime configuration environment model, the GL-065 product architecture extension boundaries, and the GL-063 production-hardening roadmap.

---

## See also

- [`docs/runtime_configuration_environment_model.md`](runtime_configuration_environment_model.md) — GL-066 runtime configuration and environment model
- [`docs/secret_management_baseline_design.md`](secret_management_baseline_design.md) — GL-068 secret management baseline design
- [`docs/production_auth_operator_access_design.md`](production_auth_operator_access_design.md) — GL-067 production auth and operator access design
- [`docs/product_architecture_extension_boundaries.md`](product_architecture_extension_boundaries.md) — GL-065 product architecture and extension boundaries
- [`docs/production_hardening_roadmap.md`](production_hardening_roadmap.md) — GL-063 production-hardening roadmap
- [`docs/examples/gl069/deployment_runtime_mode_matrix.json`](examples/gl069/deployment_runtime_mode_matrix.json) — machine-readable deployment runtime mode matrix
- [`docs/examples/gl069/deployment_package_catalog.json`](examples/gl069/deployment_package_catalog.json) — machine-readable deployment package catalog
- [`backend/tests/test_gl069_deployment_package_runtime_modes_design.py`](../backend/tests/test_gl069_deployment_package_runtime_modes_design.py) — validation test for this deployment package and runtime modes design
