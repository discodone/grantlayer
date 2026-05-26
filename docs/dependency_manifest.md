# GL-137 Python Dependency Manifest

## Scope

This issue adds minimal, accurate Python dependency manifests and developer setup documentation for the GrantLayer backend. It is **not** production code work, package publishing, SDK work, or tenant/workspace implementation.

## Purpose

- Reproducible developer setup via `pip install -r requirements-dev.txt`
- Public GitHub readiness: reviewers can see exact runtime and dev dependencies
- External security review support: dependency surface is explicit and auditable

## Runtime Manifest

File: `requirements.txt`

Includes only non-standard-library runtime dependencies actually imported by `backend/src/*`:

- `cryptography>=42.0.0` — used by `backend/src/crypto_signing.py` for Ed25519 signatures and key serialization.
- `psycopg2-binary>=2.9.0` — lazy-imported by `backend/src/db.py` when a `postgres://` or `postgresql://` database URL is configured. SQLite3 (stdlib) is the default backend.

## Dev Manifest

File: `requirements-dev.txt`

Includes the runtime manifest via:

```text
-r requirements.txt
```

No additional dev-only dependencies are required. All existing tests use the standard library `unittest` framework.

## Install Commands

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
```

## Validation Commands

```bash
python3 -m unittest backend.tests.test_gl137_dependency_manifest -v
python3 -m unittest backend.tests.test_gl136_key_hygiene -v
python3 -m unittest backend.tests.test_security_boundary_regression -v
```

Full backend suite (if GL-121 runner is available):

```bash
scripts/run-full-backend-suite.sh
```

## Non-Goals

- No package publishing via PyPI or setuptools.
- No SDK packaging.
- No `pyproject.toml` or `setup.py` unless introduced by a later issue.
- No production behavior change.
- No endpoint/API changes.
- No database schema or migration changes.
- No frontend, website, or design changes.

## Security

- Dependency files must not contain secrets (private keys, passwords, tokens, API keys).
- GL-136 key hygiene rules must remain passing. No tracked demo keys may be introduced.

## Next Issue

- **GL-138** Remove Duplicate `check_admin_token` Stub
