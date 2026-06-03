# GL-190: Demo Endpoint Safety Guard

## Context

GrantLayer exposes demo-only endpoints that are disabled by default
(`GRANTLAYER_ENABLE_DEMO_ENDPOINTS=false`).  These endpoints are intended
exclusively for local development and demonstration purposes.

An external security review flagged a gap: when `GRANTLAYER_ENABLE_DEMO_ENDPOINTS=true`
is combined with a non-localhost host binding (e.g. `GRANTLAYER_HOST=0.0.0.0`),
demo endpoints become reachable from non-local network interfaces without any
startup-level block.  The existing startup gate (GL-089) only enforces demo
endpoint restrictions in non-local/production-like `RUNTIME_MODE` values;
it does not inspect the actual host bind address.

## Threat / Risk Statement

Binding demo endpoints to a non-local interface increases the network attack
surface of a development instance.  Demo endpoints are not subject to the
same hardening expectations as production endpoints.  Accidental or
misconfigured public exposure could allow access that was not intended.

This guard does not address authentication or authorization directly — those
layers remain in place regardless.  The goal is to prevent silent misconfiguration.

## Implemented Behavior

A new function `config.demo_endpoint_public_exposure_errors(host)` is called
from `server.run()` before the server binds, regardless of `RUNTIME_MODE`.

If all three conditions hold:
1. `GRANTLAYER_ENABLE_DEMO_ENDPOINTS=true`
2. The effective bind host is NOT in the local host set
3. `GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS` is not set to a truthy value

…then startup is aborted with:

```
FATAL: Demo endpoint public exposure blocked. Server will not start.
ERROR: demo_endpoints_public_exposure_blocked. Demo endpoints are enabled
with a non-local host binding. Set GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS=true
to explicitly acknowledge.
```

## Local / Test Allowed Behavior

The following bind host values are treated as local and bypass the guard:

- `localhost`
- `127.0.0.1`
- `::1`
- `""` (empty / unset, treated as default local context)

Host values are normalized with `.strip().lower()` before comparison.

Demo endpoints enabled on these hosts start normally.  `RUNTIME_MODE` values
of `local` and `test` are not special-cased by this guard — the host binding
is the determining factor.

## Non-Local Blocked Behavior

Any host value NOT in the local set (e.g. `0.0.0.0`, `192.168.x.x`, `::`,
public IP addresses) causes startup to fail unless the explicit acknowledgement
is present.

## Explicit Acknowledgement

Set `GRANTLAYER_ALLOW_PUBLIC_DEMO_ENDPOINTS=true` (or `1`, `yes`, `on`) to
explicitly acknowledge the risk and allow demo endpoints to bind to a non-local
host.  This is intentional and auditable — it requires a deliberate environment
variable change.

The variable is parsed by the same `_env_bool` helper used throughout the
configuration module.  Arbitrary non-boolean strings are not accepted.

## Startup Error Name

```
demo_endpoints_public_exposure_blocked
```

The error text is safe, deterministic, and contains no secrets, tokens,
endpoint paths, or exploit details.

## Safety Properties

| Property | Status |
|---|---|
| No secret exposure | Yes — error text contains no tokens or credentials |
| No exploit details | Yes — no endpoint names, attack patterns, or bypass hints |
| Safe deterministic startup error | Yes — same inputs produce same error |
| Local development preserved | Yes — localhost / 127.0.0.1 / ::1 unaffected |
| Non-local demo exposure guarded | Yes — blocked without explicit ack |
| Existing startup gate preserved | Yes — GL-089 mode-based gate unchanged |
| Health/readiness unaffected | Yes — check runs before server binds; health/readiness unrelated |
| Production SaaS not claimed | Yes — not claimed |
| Tenant isolation not claimed | Yes — not claimed |

## Non-Goals

- This issue does not redesign authentication or authorization.
- This issue does not change production deployment requirements.
- This issue does not modify the OpenAPI contract (no endpoint behavior change visible to clients).
- This issue does not address rate limiting, CORS, or other security layers.
- This issue does not enforce demo endpoint restrictions beyond host binding.

## Validation Summary

- `python3 -m py_compile backend/src/config.py backend/src/server.py` — pass
- `python3 -m py_compile backend/tests/test_gl190_demo_endpoint_safety_guard.py` — pass
- `python3 -m unittest backend.tests.test_gl190_demo_endpoint_safety_guard -v` — 44/44 pass, 2 skipped (docs not present at test time, resolved at commit)
- GL-189, GL-188, GL-187, GL-084, GL-089 regression suites — see full suite result

## Next Recommended Issue

GL-191: Public Developer Experience Polish Pack
