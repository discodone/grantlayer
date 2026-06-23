"""GL-311 — Schemathesis stateful fuzz tests.

Marked "contract" — excluded from `make test`, run with `make test-contract`.

These tests use schemathesis to generate and execute test cases against the
live OpenAPI spec. They validate grants CRUD and auth paths.
"""

from __future__ import annotations

import pytest

# Optional dependency. Under pytest the pytestmark below skips every test in
# this module when schemathesis is absent. We deliberately do NOT use
# pytest.importorskip(), because that raises at import time and breaks
# `unittest discover` (used by scripts/run-full-backend-suite.sh) with a module
# load error instead of a clean skip. With this guard the module imports cleanly
# under unittest (it defines no TestCase, so it contributes zero tests there).
try:
    import schemathesis
except ImportError:  # pragma: no cover - exercised only when dependency missing
    schemathesis = None

pytestmark = pytest.mark.skipif(
    schemathesis is None, reason="schemathesis not installed"
)


@pytest.fixture(scope="module")
def app():
    from backend.src.api.app import create_app
    return create_app()


@pytest.fixture(scope="module")
def schema(app):
    return schemathesis.from_wsgi("/api/openapi.json", app=app)


@pytest.mark.contract
def test_grants_crud_fuzz(schema):
    """Stateful fuzz test for grants CRUD endpoints."""
    grants_schema = schema.filter(
        lambda case: "/v1/grants" in case.path
    )
    for case in grants_schema:
        with case.as_werkzeug_client() as client:
            response = case.call_wsgi(client)
            # Accept 2xx, 4xx — reject 5xx
            assert response.status_code < 500, (
                f"Server error on {case.method} {case.path}: "
                f"{response.status_code} {response.text[:200]}"
            )


@pytest.mark.contract
def test_auth_endpoint_fuzz(schema):
    """Fuzz the auth/token endpoint for 5xx errors."""
    auth_schema = schema.filter(
        lambda case: "/auth" in case.path
    )
    for case in auth_schema:
        with case.as_werkzeug_client() as client:
            response = case.call_wsgi(client)
            assert response.status_code < 500, (
                f"Server error on {case.method} {case.path}: "
                f"{response.status_code}"
            )
