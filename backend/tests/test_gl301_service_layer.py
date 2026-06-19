"""GL-301 — Service Layer tests.

Verifies GrantService, GrantRequestService, and OperatorService
encapsulate business logic correctly and that DI factories wire them up.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

import pytest

from backend.src.auth.operator_service import OperatorService
from backend.src.core.repositories import IGrantRepository, IGrantRequestRepository, IOperatorRepository
from backend.src.grants.grant_request_service import GrantRequestService
from backend.src.grants.grant_service import GrantService


# ── GrantService unit tests ───────────────────────────────────────────────


def _make_mock_session():
    """Create a mock SA session with a connection."""
    sess = MagicMock()
    sess.connection.return_value = MagicMock()
    return sess


def _future_dates():
    now = datetime.datetime.now(datetime.timezone.utc)
    vf = (now + datetime.timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    vu = (now + datetime.timedelta(days=30)).isoformat().replace("+00:00", "Z")
    return vf, vu


class TestGrantServiceUnit:
    def setup_method(self):
        self.repo = MagicMock(spec=IGrantRepository)
        self.session = _make_mock_session()
        self.svc = GrantService(repo=self.repo, session=self.session)

    def test_get_grant_delegates_to_repo(self):
        self.repo.get.return_value = None
        result = self.svc.get_grant("gid", "tenant1", "ws1")
        self.repo.get.assert_called_once_with("gid", tenant_id="tenant1", workspace_id="ws1")
        assert result is None

    def test_list_grants_returns_items_and_total(self):
        self.repo.list.return_value = []
        self.repo.count.return_value = 0
        items, total = self.svc.list_grants("t1", "w1", limit=10, offset=0)
        assert items == []
        assert total == 0
        self.repo.list.assert_called_once()
        self.repo.count.assert_called_once()

    def test_create_grant_signs_and_creates(self):
        from backend.src.core.models import Grant
        vf, vu = _future_dates()
        grant = Grant(
            subject_id="agent-1",
            role="viewer",
            action="read",
            resource="doc/1",
            valid_from=vf,
            valid_until=vu,
            created_by="op1",
            reason="test",
        )
        self.repo.create.return_value = None

        with patch("backend.src.grants.grant_service._sign_grant") as mock_sign, \
             patch("backend.src.grants.grant_service._audit_log") as mock_audit:
            mock_sign.return_value = ("sig_hex", "hash_hex", "key_id")
            result = self.svc.create_grant(grant, "t1", "w1")

        assert result.signature == "sig_hex"
        assert result.payload_hash == "hash_hex"
        assert result.signing_key_id == "key_id"
        self.repo.create.assert_called_once_with(grant, "t1", "w1")
        mock_audit.append_event.assert_called_once()

    def test_create_grant_sets_operator_id_as_created_by(self):
        from backend.src.core.models import Grant
        vf, vu = _future_dates()
        grant = Grant(
            subject_id="agent-1",
            role="viewer",
            action="read",
            resource="doc/1",
            valid_from=vf,
            valid_until=vu,
            created_by="original-creator",
            reason="test",
        )
        with patch("backend.src.grants.grant_service._sign_grant") as mock_sign, \
             patch("backend.src.grants.grant_service._audit_log"):
            mock_sign.return_value = ("s", "h", "k")
            result = self.svc.create_grant(grant, "t1", "w1", operator_id="op-override")

        assert result.created_by == "op-override"

    def test_revoke_grant_delegates_to_repo(self):
        self.repo.revoke.return_value = True
        result = self.svc.revoke_grant("gid", "t1", "w1", "op1", "reason")
        self.repo.revoke.assert_called_once_with("gid", "op1", "reason", tenant_id="t1", workspace_id="w1")
        assert result is True


# ── GrantRequestService unit tests ────────────────────────────────────────


class TestGrantRequestServiceUnit:
    def setup_method(self):
        self.repo = MagicMock(spec=IGrantRequestRepository)
        self.grant_repo = MagicMock(spec=IGrantRepository)
        self.session = _make_mock_session()
        self.svc = GrantRequestService(
            repo=self.repo,
            grant_repo=self.grant_repo,
            session=self.session,
        )

    def test_get_request_delegates_to_repo(self):
        self.repo.get.return_value = None
        result = self.svc.get_request("rid", "t1", "w1")
        self.repo.get.assert_called_once_with("rid", tenant_id="t1", workspace_id="w1")
        assert result is None

    def test_list_requests_returns_items_and_total(self):
        self.repo.list.return_value = []
        self.repo.count.return_value = 5
        items, total = self.svc.list_requests("t1", "w1")
        assert items == []
        assert total == 5

    def test_create_request_delegates_to_repo(self):
        from backend.src.core.models import GrantRequest
        req = MagicMock(spec=GrantRequest)
        self.repo.create.return_value = req
        result = self.svc.create_request(req, "t1", "w1")
        self.repo.create.assert_called_once_with(req, "t1", "w1")
        assert result is req

    def test_approve_request_raises_on_not_found(self):
        self.repo.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            self.svc.approve_request("rid", "op1", tenant_id="t1", workspace_id="w1")

    def test_approve_request_raises_on_wrong_status(self):
        req = MagicMock()
        req.status = "approved"
        req.requested_by = "op2"
        self.repo.get.return_value = req
        with pytest.raises(ValueError, match="Cannot approve"):
            self.svc.approve_request("rid", "op1", tenant_id="t1", workspace_id="w1")

    def test_approve_request_raises_on_self_approval(self):
        req = MagicMock()
        req.status = "requested"
        req.requested_by = "op1"
        req.created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.repo.get.return_value = req
        with pytest.raises(ValueError, match="Self-approval"):
            self.svc.approve_request("rid", "op1", tenant_id="t1", workspace_id="w1")

    def test_deny_request_raises_on_not_found(self):
        self.repo.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            self.svc.deny_request("rid", "op1", "bad reason", tenant_id="t1", workspace_id="w1")

    def test_deny_request_raises_on_wrong_status(self):
        req = MagicMock()
        req.status = "denied"
        self.repo.get.return_value = req
        with pytest.raises(ValueError, match="Cannot deny"):
            self.svc.deny_request("rid", "op1", "reason", tenant_id="t1", workspace_id="w1")

    def test_revoke_request_raises_on_wrong_status(self):
        req = MagicMock()
        req.status = "requested"
        self.repo.get.return_value = req
        with pytest.raises(ValueError, match="Cannot revoke"):
            self.svc.revoke_request("rid", "op1", "reason", tenant_id="t1", workspace_id="w1")


# ── OperatorService unit tests ────────────────────────────────────────────


class TestOperatorServiceUnit:
    def setup_method(self):
        self.repo = MagicMock(spec=IOperatorRepository)
        self.svc = OperatorService(repo=self.repo)

    def test_revoke_operator_delegates_to_repo(self):
        self.repo.revoke.return_value = True
        assert self.svc.revoke_operator("op1") is True
        self.repo.revoke.assert_called_once_with("op1")

    def test_rotate_token_delegates_to_repo(self):
        self.repo.rotate_token.return_value = "new-token"
        result = self.svc.rotate_token("op1")
        assert result == "new-token"

    def test_get_operator_safe_returns_none_when_not_found(self):
        self.repo.get_any.return_value = None
        result = self.svc.get_operator_safe("op1")
        assert result is None

    def test_get_operator_safe_returns_safe_dict(self):
        from backend.src.auth.operators import Operator
        op = Operator(operator_id="op1", name="Test", role="owner", tenant_id="t1")
        self.repo.get_any.return_value = op
        result = self.svc.get_operator_safe("op1")
        assert result is not None
        assert "token" not in result
        assert result["operatorId"] == "op1"
        assert result["name"] == "Test"

    def test_list_operators_for_admin_excludes_tokens(self):
        from backend.src.auth.operators import Operator
        ops = [
            Operator(operator_id="op1", name="A", role="owner", tenant_id="t1"),
            Operator(operator_id="op2", name="B", role="auditor", tenant_id="t1"),
        ]
        self.repo.list.return_value = ops
        result = self.svc.list_operators_for_admin()
        assert len(result) == 2
        for item in result:
            assert "token" not in item
            assert "tokenHash" not in item

    def test_create_operator_generates_token_if_not_provided(self):
        from backend.src.auth.operators import Operator
        op = Operator(operator_id="op1", name="Test", role="owner", tenant_id="t1")
        self.repo.create.return_value = (op, "generated-token")
        result_op, token = self.svc.create_operator("Test", "owner", "t1")
        assert token == "generated-token"
        # repo.create was called with a token (auto-generated)
        call_args = self.repo.create.call_args
        assert call_args[0][2] is not None  # token arg

    def test_create_operator_uses_provided_token(self):
        from backend.src.auth.operators import Operator
        op = Operator(operator_id="op1", name="Test", role="owner", tenant_id="t1")
        self.repo.create.return_value = (op, "my-token")
        self.svc.create_operator("Test", "owner", "t1", token="my-token")
        call_args = self.repo.create.call_args
        assert call_args[0][2] == "my-token"


# ── DI factory smoke tests ────────────────────────────────────────────────


class TestDIFactories:
    def test_get_grant_service_injectable(self):
        from backend.src.api.deps import get_grant_service
        assert callable(get_grant_service)

    def test_get_grant_request_service_injectable(self):
        from backend.src.api.deps import get_grant_request_service
        assert callable(get_grant_request_service)

    def test_get_operator_service_injectable(self):
        from backend.src.api.deps import get_operator_service
        assert callable(get_operator_service)

    def test_grants_router_uses_grant_service(self):
        """grants.py router must use AsyncGrantService via DI (GL-305 migration)."""
        import pathlib
        source = pathlib.Path("backend/src/api/routers/grants.py").read_text()
        assert "GrantService" in source
        assert "get_async_grant_service" in source

    def test_grant_requests_router_uses_grant_request_service(self):
        """grant_requests.py must use AsyncGrantRequestService via DI (GL-305 migration)."""
        import pathlib
        source = pathlib.Path("backend/src/api/routers/grant_requests.py").read_text()
        assert "GrantRequestService" in source
        assert "get_async_grant_request_service" in source

    def test_admin_router_uses_operator_service(self):
        """admin.py must use AsyncOperatorService via DI (GL-305 migration)."""
        import pathlib
        source = pathlib.Path("backend/src/api/routers/admin.py").read_text()
        assert "OperatorService" in source
        assert "get_async_operator_service" in source


# ── Integration smoke via TestClient ─────────────────────────────────────

import os
import tempfile
import unittest

try:
    from fastapi.testclient import TestClient
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

_SKIP = unittest.skipUnless(_FASTAPI_AVAILABLE, "FastAPI not installed")
_JWT_SECRET = "test-secret-gl301"


class _IntegrationBase(unittest.TestCase):
    def setUp(self):
        import backend.src.core.config as _cfg
        import backend.src.core.db as _db
        from backend.src.api.app import create_app
        from backend.src.api.auth_jwt import create_dev_token

        self._cfg = _cfg
        self._db = _db

        self._orig_op = _cfg.ENABLE_OPERATOR_MODEL
        self._orig_plaintext = _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE
        self._orig_db = _db.DB_PATH_OR_URL
        self._orig_admin = _cfg.GRANTLAYER_ADMIN_TOKEN
        self._orig_jwt_env = os.environ.get("GRANTLAYER_JWT_SECRET", "")

        os.environ["GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"] = "true"
        os.environ["GRANTLAYER_JWT_SECRET"] = _JWT_SECRET
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = True
        _cfg.ENABLE_OPERATOR_MODEL = False
        _cfg.GRANTLAYER_ADMIN_TOKEN = "test-admin-token-gl301"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "test-admin-token-gl301"
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        _db.DB_PATH_OR_URL = self._db_path
        _db.DB_PATH = self._db_path
        _db.init_db()

        self.client = TestClient(create_app(), raise_server_exceptions=True)
        self.jwt_header = {"Authorization": f"Bearer {create_dev_token(secret=_JWT_SECRET)}"}
        self.admin_header = {"Authorization": "Bearer test-admin-token-gl301"}

    def tearDown(self):
        self._cfg.ENABLE_OPERATOR_MODEL = self._orig_op
        self._cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = self._orig_plaintext
        self._cfg.GRANTLAYER_ADMIN_TOKEN = self._orig_admin
        self._db.DB_PATH_OR_URL = self._orig_db
        self._db.DB_PATH = self._orig_db
        if self._orig_jwt_env:
            os.environ["GRANTLAYER_JWT_SECRET"] = self._orig_jwt_env
        else:
            os.environ.pop("GRANTLAYER_JWT_SECRET", None)
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        try:
            os.unlink(self._db_path)
        except OSError:
            pass


@_SKIP
class TestGrantsRouterIntegration(_IntegrationBase):
    def test_list_grants_requires_auth(self):
        resp = self.client.get("/v1/grants")
        self.assertIn(resp.status_code, (401, 403))

    def test_list_grants_with_jwt(self):
        resp = self.client.get(
            "/v1/grants",
            headers={**self.jwt_header, "X-Workspace-Id": "default"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("items", data)

    def test_get_grant_not_found_returns_404(self):
        resp = self.client.get(
            "/v1/grants/nonexistent-grant-id",
            headers={**self.jwt_header, "X-Workspace-Id": "default"},
        )
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        self.assertEqual(data["errorCode"], "grant_not_found")


@_SKIP
class TestGrantRequestsRouterIntegration(_IntegrationBase):
    def test_list_grant_requests_requires_auth(self):
        resp = self.client.get("/v1/grant-requests")
        self.assertIn(resp.status_code, (401, 403))

    def test_list_grant_requests_with_jwt(self):
        resp = self.client.get(
            "/v1/grant-requests",
            headers={**self.jwt_header, "X-Workspace-Id": "default"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("items", data)

    def test_get_grant_request_not_found(self):
        resp = self.client.get(
            "/v1/grant-requests/nonexistent-id",
            headers={**self.jwt_header, "X-Workspace-Id": "default"},
        )
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        self.assertEqual(data["errorCode"], "grant_request_not_found")


@_SKIP
class TestAdminRouterIntegration(_IntegrationBase):
    def test_list_operators_requires_auth(self):
        resp = self.client.get("/v1/admin/operators")
        self.assertIn(resp.status_code, (401, 403))

    def test_list_operators_with_admin_token(self):
        resp = self.client.get(
            "/v1/admin/operators",
            headers=self.jwt_header,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_create_operator_returns_201(self):
        resp = self.client.post(
            "/v1/admin/operators",
            headers=self.jwt_header,
            # GL-347: admin operator creation is now tenant-scoped. The dev JWT is
            # scoped to tenant "demo", so the operator must be created in "demo"
            # (a cross-tenant create would correctly be rejected with 403).
            json={"name": "Test Operator GL301", "tenantId": "demo", "role": "owner"},
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("operatorId", data)
        self.assertIn("token", data)
        self.assertNotIn("tokenHash", data)
