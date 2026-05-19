# GrantLayer Observability and Structured Logging Baseline Design

> GrantLayer turns agentic grant workflows into verifiable institutional records.
>
> GrantLayer macht agentische Förderprozesse zu prüfbaren institutionellen Nachweisen.

## 1. Purpose

This document establishes the **observability and structured logging baseline** for GrantLayer as a reusable, adaptable API-first product core. It prepares the path for future observability, logging, and tracing readiness without implementing any of them.

It clarifies:
- what observability means for GrantLayer and what it does not include at this stage
- the structured logging baseline that all future implementation must follow
- the required log event categories and structured log fields
- how correlation IDs connect requests, workflows, and executions across log entries
- the clear boundary between operational logs, product audit records, security events, and debug traces
- what must be redacted or never logged, especially secrets, tokens, and sensitive data
- the error logging policy expected from future implementations
- what operators need to see in logs for safe operations
- candidate metrics and tracing patterns for future implementation
- how observability expectations differ across local, dev, test, staging, and runtime modes
- which production-readiness gaps remain before observability is complete
- the future implementation sequence for observability-related work

This is a **product-foundation observability design document**.

GL-071 explicitly states:
- GL-071 adds no observability implementation. GL-071 does not implement any observability.
- GL-071 adds no logging implementation. GL-071 does not implement any logging.
- GL-071 adds no metrics implementation. GL-071 does not implement any metrics.
- GL-071 adds no tracing implementation. GL-071 does not implement any tracing.
- GL-071 does not make GrantLayer production-ready.
- GL-071 does not implement any logging, metrics, tracing, monitoring, or runtime configuration.
- It does not implement runtime configuration, monitoring, or any other observability stack component.

## 2. Observability principles for GrantLayer

GrantLayer observability should follow these principles:

- **Observability serves operational safety first** — operators must be able to detect, triage, and recover from incidents without needing to read source code.
- **Structured logs are the primary signal** — every log entry should be machine-parseable JSON with consistent, documented fields.
- **Audit and provenance are separate from operational logs** — product audit records and provenance events belong to the product domain and may need separate storage, retention, and access controls. Operational logs exist for system health.
- **Security events require dedicated treatment** — authentication failures, permission denials, and anomalies must be logged, but not mixed casually with debug output.
- **Debug traces are not operational logs** — debug-level output is for developers and should be disabled in production.
- **Logs never include secrets or sensitive payloads** — raw secrets, access tokens, private keys, and full evidence payloads must never appear in logs.
- **Correlation IDs tie events together** — a single workflow spans many log lines; correlation fields must make it easy to reconstruct the chain.
- **Cardinality discipline** — log fields used for grouping and filtering must be bounded and documented.
- **No observability implementation is added in GL-071** — this document is purely a design and readiness baseline.

## 3. Structured logging baseline

All future logging in GrantLayer should emit structured JSON with the following baseline:

- **Single JSON object per log line** — no multi-line stack traces mixed with the event record; stack traces should be fields inside the JSON.
- **Consistent top-level fields** — `timestamp`, `level`, `msg`, `eventType`, and `correlationId` are always present.
- **Explicit event types** — every log entry declares its category via `eventType`.
- **Human-readable but machine-parseable** — `msg` is a short human-readable sentence; machine data lives in typed fields.
- **No variable-rate fields in top-level keys** — dynamic names (e.g., user IDs as keys) must live inside a `details` or `context` sub-object.
- **UTF-8 output** — all log output must be valid UTF-8.
- **Monotonic wall-clock timestamps with time zone** — timestamps should use ISO 8601 with explicit offset or UTC (`Z`).

## 4. Required log event categories

Future GrantLayer implementations must support at least these event categories:

- **api_request** — HTTP/API request start and completion; method, path, status, latency.
- **api_error** — unhandled or structured API errors; status code, error code, error message.
- **auth_event** — login, logout, identity verification attempts, and outcomes.
- **permission_decision** — authorization checks, granted or denied, with policy context.
- **evidence_verification** — evidence submitted for verification and the result.
- **approval_transition** — grant state changes, who initiated them, and the resulting state.
- **policy_evaluation** — policy rules evaluated during a request or workflow step.
- **persistence_operation** — database reads and writes, success or failure, not the raw query.
- **configuration_event** — runtime configuration changes, reloads, or validation results.
- **operator_action** — operator-initiated commands, configuration changes, or recoveries.

Each category should map to a known `eventType` value and have a stable schema. See `docs/examples/gl071/observability_event_model.json` for a representative example.

## 5. Required structured log fields

Every structured log entry should include:

- `timestamp` — ISO 8601 with timezone
- `level` — `ERROR`, `WARN`, `INFO`, `DEBUG`, or a documented custom severity
- `msg` — short human-readable description
- `eventType` — one of the event categories or a documented extension
- `serviceName` — the emitting component (e.g., `grantlayer-api`)
- `serviceVersion` — the deployed version identifier

Optional but strongly recommended fields:

- `sourceFile` — file path relative to repo root
- `sourceLine` — line number
- `threadId` / `processId` — runtime identifiers for concurrency debugging

Never emit dynamic or sensitive data as top-level keys.

## 6. Correlation IDs / request IDs / workflow IDs / execution IDs

To reconstruct a single workflow across log entries, the following correlation fields are required:

- **requestId** — ties all log entries generated during a single HTTP/API request.
- **correlationId** — a higher-level identifier that may span multiple requests (e.g., a batch or external callback).
- **workflowId** — ties all steps of a single GrantLayer workflow (e.g., grant request → approval → execution).
- **executionId** — ties all operations within a single execution instance (e.g., one grant fulfillment run).
- **actorId** — the identity of the human or system performing the action.
- **agentId** — the specific agent or service instance that handled the request.

These IDs must be propagated across:
- inbound API requests
- outbound API and integration calls
- internal async tasks and background jobs
- database transactions where appropriate

Future implementations should ensure these IDs appear in headers (e.g., `X-Request-ID`, `X-Correlation-ID`) so external systems can correlate as well.

## 7. Boundary between product audit records, security events, operational logs, and debug traces

GrantLayer must keep these four streams conceptually separate even if they share the same transport in early implementations.

### 7.1 Product audit records
- **Purpose** — permanent, append-only record of decisions and state changes.
- **Examples** — grant approved, evidence verified, operator overridden policy rule.
- **Retention** — long-term, governed by institutional and regulatory requirements.
- **Access** — restricted to auditors, compliance officers, and the provenance system.
- **Integrity** — must be tamper-evident (cryptographic hashes or signatures).
- **Location** — stored in durable, possibly immutable storage, not ephemeral log files.

### 7.2 Security events
- **Purpose** — detection and forensic analysis of security-relevant activity.
- **Examples** — failed login, permission denied, rate limit exceeded, anomaly detected.
- **Retention** — long-term, possibly with escalation to a SIEM.
- **Sensitivity** — must not include raw secrets, but must include enough context for investigation.

### 7.3 Operational logs
- **Purpose** — system health, performance, and operator incident response.
- **Examples** — request latency, database connection pool status, service start/stop, config reload.
- **Retention** — moderate, typically days to weeks depending on volume.
- **Access** — operators and SREs.

### 7.4 Debug traces
- **Purpose** — developer troubleshooting and detailed request inspection.
- **Examples** — full request/response dumps, detailed stack traces with local variables.
- **Retention** — very short; may be sampled or disabled entirely in production.
- **Access** — developers only.
- **Rule** — must never be enabled in production, and must never contain sensitive data.

**Key rule:** Operational logs are separate from product audit/provenance records. An event may appear in both, but the streams have different schemas, retention, and access controls. Secrets, tokens, private keys, and full sensitive payloads must never be logged in any stream.

## 8. Sensitive data and secret redaction rules

The following must be redacted or omitted from all logs, traces, and metrics:

- **Raw secrets** — passwords, private keys, API secrets, encryption keys.
- **Access tokens** — bearer tokens, JWT bodies, session cookies, refresh tokens.
- **Private keys** — Ed25519 signing keys, TLS private keys, SSH keys.
- **Full evidence payloads** — large or sensitive evidence documents should be referenced by ID or hash, never inlined.
- **Raw personal data** — unless explicitly allowed by future data classification policy, personal identifiers, financial account numbers, and contact details should be hashed, masked, or omitted.

Redaction rules for future implementation:
- Replace redacted fields with a standard marker such as `[REDACTED]` or `{"__redacted": true, "fieldName": "password"}`.
- Do not truncate or partially mask in a way that leaks information (e.g., showing the last four digits of a token).
- Apply redaction before serialization to the log sink.
- Log redaction failures as a separate `configuration_event` or `security_event`.
- In test/demo environments, use synthetic placeholder values that follow the same redaction rules as production.

## 9. Error logging policy

Future GrantLayer error logging should follow these rules:

- **Structured error fields** — every error log must include `errorCode`, `errorMessage`, and optionally `errorCategory`.
- **No stack traces in INFO logs** — stack traces belong in ERROR or DEBUG output only.
- **User-facing vs operator-facing** — user-facing errors go to the API response; operator-facing details go to logs. Never expose internal paths or database details to API consumers.
- **Rate limiting for repeated errors** — identical repeated errors should be throttled in logs to prevent log floods.
- **Context preservation** — an error log must include the same correlation IDs as the request that triggered it.
- **Failure classification** — transient vs permanent, internal vs external, retryable vs fatal.

## 10. Operator visibility requirements

Operators running GrantLayer in production must be able to answer these questions from logs and metrics alone:

- Is the API healthy and responding within latency targets?
- Are authentication and authorization decisions succeeding or failing?
- Are persistence operations succeeding or timing out?
- Are workflows progressing through states as expected?
- Are there anomalies in error rates or traffic patterns?
- What specific request or workflow is failing right now?
- When did the current configuration version take effect?

Operator dashboards (future scope) should surface these signals without needing direct database access.

## 11. Minimal metrics candidates

Metrics are not implemented in GL-071. Future implementation should consider at minimum:

- **Request count and latency** — by endpoint, method, and status code.
- **Error rate** — by error category and endpoint.
- **Auth event count** — successes and failures.
- **Permission decision count** — granted vs denied.
- **Workflow state transition count** — by from-state and to-state.
- **Persistence operation latency** — by operation type, not raw SQL.
- **Active connection gauge** — database or external service connections.
- **Config reload event count** — success and failure.

These metrics should use bounded labels (low cardinality) to avoid metric explosion. Secret values, user IDs, and raw query text must never be part of metric labels.

## 12. Minimal tracing candidates

Distributed tracing is not implemented in GL-071. Future implementation should consider:

- **One trace per API request** — root span on request entry.
- **Sub-spans for major operations** — auth check, permission evaluation, persistence operation, integration call.
- **Span attributes** — service name, event type, and correlation IDs.
- **Error tagging** — spans that encounter errors should be marked with the error category.
- **Sampling** — production should use head-based or tail-based sampling to control volume.

Traces must not include sensitive payloads or secret values in span attributes.

## 13. Local/dev/test/runtime mode differences

Observability expectations differ across runtime modes:

### local / dev
- Structured logging may be pretty-printed to stdout.
- DEBUG level may be enabled by default.
- Debug traces may be printed.
- No production-ready claim is made.

### test
- Logs should be deterministic and isolated per test.
- DEBUG level may be enabled for failing tests.
- No persistent log storage.
- Correlation IDs should be predictable for test assertions.

### staging / pilot
- Structured JSON logging to a single sink.
- INFO or WARN minimum level.
- Debug traces disabled.
- Metrics may be emitted but not necessarily collected by a full monitoring stack.

### production (future)
- Structured JSON logging to a dedicated, durable sink.
- WARN or INFO minimum level; ERROR always emitted.
- Debug traces strictly disabled.
- Metrics collected by a monitoring stack.
- Tracing sampled at a configurable rate.
- Secrets and sensitive data explicitly redacted.
- Log retention, rotation, and access controls enforced.

## 14. Production-readiness gaps

GL-071 does not claim production observability readiness. The following gaps remain to be closed by later implementation blocks:

- Structured logging library is not integrated.
- Log aggregation sink is not configured.
- Metrics collection and export are not implemented.
- Distributed tracing is not implemented.
- Log redaction helpers are not implemented.
- Production log retention and rotation policies are not enforced.
- Operator dashboard and alerting are not built.
- SIEM integration for security events is not implemented.
- Audit/provenance storage separation from operational logs is not implemented.
- Performance benchmarks for logging overhead are not established.
- Cross-service correlation ID propagation across external integrations is not implemented.
- Production log access controls and encryption at rest are not configured.

## 15. Future implementation sequence

The following sequence is recommended for observability-related implementation blocks after GL-071:

1. **Logging library integration** — choose and configure a structured logging library; emit baseline fields; implement redaction helpers.
2. **Request/response correlation** — inject `X-Request-ID`, `X-Correlation-ID` headers; propagate through the stack.
3. **Event category implementation** — implement emitters for the required event categories (api_request, auth_event, etc.).
4. **Metrics collection** — instrument candidate metrics with bounded labels; expose a `/metrics` or OTLP endpoint.
5. **Error logging hardening** — classify errors; implement rate limiting; separate user-facing and operator-facing output.
6. **Distributed tracing** — integrate OpenTelemetry or equivalent; implement sampling; add sub-spans for major operations.
7. **Security event pipeline** — dedicated security event formatter; consider SIEM export.
8. **Audit/provenance separation** — separate durable storage for audit records; enforce access controls.
9. **Operator dashboards and alerting** — build or configure dashboards; define SLOs and alert thresholds.
10. **Production hardening** — retention, rotation, encryption, access controls, and performance validation.

Each block should be gated by the preceding blocks to avoid building dashboards on untraced logs or alerting on unclassified errors.

## Non-goals

- GL-071 does not implement any logging or observability stack.
- GL-071 does not choose a specific logging library, metrics backend, or tracing system.
- GL-071 does not define log storage, retention, or compression formats.
- GL-071 does not create dashboards, alerts, or SLOs.
- GL-071 does not create operator runbooks for incident response.
- GL-071 does not implement secret handling beyond stating that secrets must not be logged.
- GL-071 does not implement runtime configuration.
- GL-071 does not implement authentication, authorization, or permission decisions.
- GL-071 does not implement persistence or database operations.
- GL-071 does not claim production readiness.
