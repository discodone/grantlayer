"""GL-305 — Async FastAPI migration tests.

Verifies:
- All FastAPI endpoint functions are async def
- AsyncSession and async repositories exist
- Async services exist
- ORM-backed endpoints use async deps
- Full CRUD flow works correctly via async paths
"""

from __future__ import annotations

import inspect
import os
import pathlib
import tempfile
import uuid

import pytest

ROUTERS_DIR = pathlib.Path("backend/src/api/routers")


# ── Static analysis: all endpoints must be async def ─────────────────────


@pytest.mark.scope_guard
class TestAllEndpointsAreAsync:
    """Verify every router endpoint is async def, not plain def."""

    def test_no_sync_public_endpoints_in_routers(self):
        """All router endpoint functions must be async def."""
        violations: list[str] = []
        import re

        for path in ROUTERS_DIR.glob("*.py"):
            if path.name == "__init__.py":
                continue
            source = path.read_text()
            lines = source.split("\n")
            for i, line in enumerate(lines):
                stripped = line.strip()
                # Find public def (not _helper) preceded by @router decorator
                if stripped.startswith("def ") and not stripped.startswith("def _"):
                    # Check backwards for @router decorator
                    for j in range(i - 1, max(i - 10, -1), -1):
                        prev = lines[j].strip()
                        if prev.startswith("@router.") or prev.startswith("@app."):
                            violations.append(f"{path.name}:{i + 1}: {stripped[:80]}")
                            break
                        if prev and not prev.startswith("@") and not prev.startswith(")") and not prev.startswith("#"):
                            break
        assert not violations, (
            "These endpoint functions must be 'async def':\n" + "\n".join(violations)
        )


# ── Module existence checks ────────────────────────────────────────────────


class TestAsyncInfrastructureExists:
    """Verify async infrastructure components exist in the codebase."""

    def test_get_async_db_exists(self):
        """db.py must export get_async_db (async generator dependency)."""
        from backend.src.core.db import get_async_db
        assert inspect.isasyncgenfunction(get_async_db)

    def test_async_session_maker_exists(self):
        """db.py must export get_async_session_maker."""
        from backend.src.core.db import get_async_session_maker
        assert callable(get_async_session_maker)

    def test_async_grant_repo_exists(self):
        from backend.src.core.repositories_sqlalchemy import SqlAlchemyAsyncGrantRepository
        assert SqlAlchemyAsyncGrantRepository is not None

    def test_async_grant_request_repo_exists(self):
        from backend.src.core.repositories_sqlalchemy import SqlAlchemyAsyncGrantRequestRepository
        assert SqlAlchemyAsyncGrantRequestRepository is not None

    def test_async_grant_execution_repo_exists(self):
        from backend.src.core.repositories_sqlalchemy import SqlAlchemyAsyncGrantExecutionRepository
        assert SqlAlchemyAsyncGrantExecutionRepository is not None

    def test_async_operator_repo_exists(self):
        from backend.src.core.repositories_sqlalchemy import SqlAlchemyAsyncOperatorRepository
        assert SqlAlchemyAsyncOperatorRepository is not None

    def test_async_grant_service_exists(self):
        from backend.src.grants.grant_service import AsyncGrantService
        assert AsyncGrantService is not None

    def test_async_grant_request_service_exists(self):
        from backend.src.grants.grant_request_service import AsyncGrantRequestService
        assert AsyncGrantRequestService is not None

    def test_async_operator_service_exists(self):
        from backend.src.auth.operator_service import AsyncOperatorService
        assert AsyncOperatorService is not None

    def test_async_grant_service_methods_are_coroutines(self):
        """AsyncGrantService methods must be coroutine functions."""
        from backend.src.grants.grant_service import AsyncGrantService
        assert inspect.iscoroutinefunction(AsyncGrantService.get_grant)
        assert inspect.iscoroutinefunction(AsyncGrantService.list_grants)
        assert inspect.iscoroutinefunction(AsyncGrantService.create_grant)
        assert inspect.iscoroutinefunction(AsyncGrantService.revoke_grant)

    def test_async_grant_request_service_methods_are_coroutines(self):
        from backend.src.grants.grant_request_service import AsyncGrantRequestService
        assert inspect.iscoroutinefunction(AsyncGrantRequestService.get_request)
        assert inspect.iscoroutinefunction(AsyncGrantRequestService.list_requests)
        assert inspect.iscoroutinefunction(AsyncGrantRequestService.create_request)
        assert inspect.iscoroutinefunction(AsyncGrantRequestService.approve_request)
        assert inspect.iscoroutinefunction(AsyncGrantRequestService.deny_request)
        assert inspect.iscoroutinefunction(AsyncGrantRequestService.revoke_request)

    def test_async_repo_methods_are_coroutines(self):
        from backend.src.core.repositories_sqlalchemy import SqlAlchemyAsyncGrantRepository
        assert inspect.iscoroutinefunction(SqlAlchemyAsyncGrantRepository.get)
        assert inspect.iscoroutinefunction(SqlAlchemyAsyncGrantRepository.list)
        assert inspect.iscoroutinefunction(SqlAlchemyAsyncGrantRepository.create)
        assert inspect.iscoroutinefunction(SqlAlchemyAsyncGrantRepository.revoke)
        assert inspect.iscoroutinefunction(SqlAlchemyAsyncGrantRepository.count)


# ── Integration tests via TestClient ─────────────────────────────────────


class TestAsyncEndpointsViaHTTP:
    """Integration tests verifying async endpoints work correctly end-to-end."""

    def setup_method(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp_db.close()
        self._orig_db = os.environ.get("GRANTLAYER_DB")
        self._orig_url = os.environ.get("GRANTLAYER_DATABASE_URL")
        self._orig_admin = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self._orig_op_model = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")
        # Save and clear JWT env vars so other tests don't bleed in
        _jwt_keys = [
            "GRANTLAYER_JWT_SECRET",
            "GRANTLAYER_JWT_PRIVATE_KEY",
            "GRANTLAYER_JWT_PUBLIC_KEY",
            "GRANTLAYER_JWT_ALGORITHM",
            "GRANTLAYER_JWT_PRIVATE_KEY_FILE",
            "GRANTLAYER_JWT_PUBLIC_KEY_FILE",
            "GRANTLAYER_REQUIRE_ADMIN_TOKEN",
        ]
        self._orig_jwt_env = {k: os.environ.pop(k, None) for k in _jwt_keys}

        # Point BOTH sync and async engines at the temp DB
        import backend.src.core.db as _db
        self._orig_db_path = _db.DB_PATH_OR_URL
        self._orig_db_path_alias = getattr(_db, "DB_PATH", None)
        _db.DB_PATH_OR_URL = self.tmp_db.name
        _db.DB_PATH = self.tmp_db.name
        # Reset engine caches so they rebuild with new URL
        _db._sa_engine = None
        _db._async_engine = None
        _db._session_maker = None
        _db._async_session_maker = None

        os.environ.pop("GRANTLAYER_DATABASE_URL", None)
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "test-admin-gl305"
        os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"

        # Patch cached config so operator model is off for this test
        import backend.src.core.config as _cfg
        self._orig_enable_operator_model = _cfg.ENABLE_OPERATOR_MODEL
        _cfg.ENABLE_OPERATOR_MODEL = False

        # Initialize DB schema (tables) before spinning up the app
        _db.init_db()

        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        self.client = TestClient(create_app(), raise_server_exceptions=True)

    def teardown_method(self):
        import backend.src.core.db as _db
        _db.DB_PATH_OR_URL = self._orig_db_path
        if self._orig_db_path_alias is not None:
            _db.DB_PATH = self._orig_db_path_alias
        _db._sa_engine = None
        _db._async_engine = None
        _db._session_maker = None
        _db._async_session_maker = None

        os.unlink(self.tmp_db.name)
        if self._orig_db:
            os.environ["GRANTLAYER_DB"] = self._orig_db
        if self._orig_url:
            os.environ["GRANTLAYER_DATABASE_URL"] = self._orig_url
        if self._orig_admin:
            os.environ["GRANTLAYER_ADMIN_TOKEN"] = self._orig_admin
        else:
            os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        if self._orig_op_model:
            os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = self._orig_op_model
        else:
            os.environ.pop("GRANTLAYER_ENABLE_OPERATOR_MODEL", None)
        # Restore config patches
        import backend.src.core.config as _cfg
        _cfg.ENABLE_OPERATOR_MODEL = self._orig_enable_operator_model

        # Restore JWT env vars
        for k, v in self._orig_jwt_env.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)

    def _grant_payload(self):
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        return {
            "subjectId": f"agent-{uuid.uuid4().hex[:8]}",
            "role": "viewer",
            "action": "read",
            "resource": "file://test",
            "validFrom": now.isoformat().replace("+00:00", "Z"),
            "validUntil": (now + datetime.timedelta(days=1)).isoformat().replace("+00:00", "Z"),
            "createdBy": "test-operator",
            "reason": "GL-305 async test",
        }

    def test_list_grants_returns_200(self):
        resp = self.client.get(
            "/v1/grants",
            headers={"Authorization": "Bearer test-admin-gl305"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] == 0

    def test_create_grant_async_endpoint(self):
        payload = self._grant_payload()
        resp = self.client.post(
            "/v1/grants",
            json=payload,
            headers={"Authorization": "Bearer test-admin-gl305"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["role"] == "viewer"

    def test_get_grant_async_endpoint(self):
        payload = self._grant_payload()
        create_resp = self.client.post(
            "/v1/grants",
            json=payload,
            headers={"Authorization": "Bearer test-admin-gl305"},
        )
        assert create_resp.status_code == 201
        grant_id = create_resp.json()["id"]

        get_resp = self.client.get(
            f"/v1/grants/{grant_id}",
            headers={"Authorization": "Bearer test-admin-gl305"},
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == grant_id

    def test_create_grant_async_audit_event_created(self):
        """Creating a grant via async endpoint should produce an audit event."""
        payload = self._grant_payload()
        resp = self.client.post(
            "/v1/grants",
            json=payload,
            headers={"Authorization": "Bearer test-admin-gl305"},
        )
        assert resp.status_code == 201
        grant_id = resp.json()["id"]

        audit_resp = self.client.get(
            "/v1/audit-events",
            headers={"Authorization": "Bearer test-admin-gl305"},
        )
        assert audit_resp.status_code == 200
        events = audit_resp.json().get("items", [])
        grant_events = [e for e in events if e.get("matched_grant_id") == grant_id]
        assert len(grant_events) >= 1, f"No audit event for grant {grant_id}"

    def test_list_grants_after_create_returns_one(self):
        payload = self._grant_payload()
        self.client.post(
            "/v1/grants",
            json=payload,
            headers={"Authorization": "Bearer test-admin-gl305"},
        )
        resp = self.client.get(
            "/v1/grants",
            headers={"Authorization": "Bearer test-admin-gl305"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_health_endpoint_is_async(self):
        resp = self.client.get("/health")
        assert resp.status_code in (200, 503)

    def test_readiness_endpoint_is_async(self):
        resp = self.client.get("/readiness")
        assert resp.status_code in (200, 503)

    def test_get_nonexistent_grant_returns_404(self):
        resp = self.client.get(
            f"/v1/grants/{uuid.uuid4()}",
            headers={"Authorization": "Bearer test-admin-gl305"},
        )
        assert resp.status_code == 404

    def test_audit_events_endpoint_async(self):
        resp = self.client.get(
            "/v1/audit-events",
            headers={"Authorization": "Bearer test-admin-gl305"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data


# ── Async db URL generation tests ────────────────────────────────────────

class TestAsyncDbUrl:
    def test_sqlite_async_url(self):
        from backend.src.core import db as _db
        orig = _db.DB_PATH_OR_URL
        orig_backend = _db.DB_BACKEND
        try:
            _db.DB_PATH_OR_URL = "/tmp/test.db"
            _db.DB_BACKEND = "sqlite"
            url = _db._async_db_url()
            assert url.startswith("sqlite+aiosqlite:///")
            assert "/tmp/test.db" in url
        finally:
            _db.DB_PATH_OR_URL = orig
            _db.DB_BACKEND = orig_backend

    def test_sqlite_memory_async_url(self):
        from backend.src.core import db as _db
        orig = _db.DB_PATH_OR_URL
        orig_backend = _db.DB_BACKEND
        try:
            _db.DB_PATH_OR_URL = ":memory:"
            _db.DB_BACKEND = "sqlite"
            url = _db._async_db_url()
            assert "aiosqlite" in url
            assert ":memory:" in url
        finally:
            _db.DB_PATH_OR_URL = orig
            _db.DB_BACKEND = orig_backend
