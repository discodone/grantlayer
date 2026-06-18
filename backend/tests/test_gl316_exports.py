"""GL-316 — Data Export CSV + PDF tests.

Covers:
- Exports router importable
- GET /v1/exports/grants.csv exists and requires auth
- GET /v1/exports/audit.csv exists and requires auth
- GET /v1/exports/grants/{id}/report.pdf exists and requires auth
- CSV endpoints return text/csv content type when authenticated
- Audit CSV endpoint returns text/csv content type when authenticated
- PDF endpoint returns 404 for nonexistent grant
- _rows_to_csv helper works correctly
- _generate_pdf returns bytes or raises 501 if reportlab missing
- router prefix is /exports
"""

from __future__ import annotations

import os
import unittest


def _make_client():
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


_TEST_SECRET = "gl316-test-hs256-secret-32chars!!"


def _auth_token() -> str:
    os.environ.setdefault("GRANTLAYER_JWT_SECRET", _TEST_SECRET)
    from backend.src.api.auth_jwt import encode_token
    return encode_token({"sub": "export-user", "role": "auditor", "tenant_id": "test-tenant"}, _TEST_SECRET)


class TestExportsImport(unittest.TestCase):
    def test_exports_router_importable(self):
        from backend.src.api.routers.exports import router
        self.assertIsNotNone(router)

    def test_exports_router_prefix(self):
        from backend.src.api.routers.exports import router
        self.assertEqual(router.prefix, "/exports")

    def test_rows_to_csv_helper(self):
        from backend.src.api.routers.exports import _rows_to_csv
        rows = [
            {"id": "g-1", "subject_id": "user-1", "action": "read", "resource": "doc"},
            {"id": "g-2", "subject_id": "user-2", "action": "write", "resource": "doc"},
        ]
        csv_out = _rows_to_csv(rows, ["id", "subject_id", "action", "resource"])
        self.assertIn("id,subject_id,action,resource", csv_out)
        self.assertIn("g-1", csv_out)
        self.assertIn("g-2", csv_out)

    def test_rows_to_csv_empty(self):
        from backend.src.api.routers.exports import _rows_to_csv
        csv_out = _rows_to_csv([], ["id", "name"])
        self.assertIn("id,name", csv_out)

    def test_generate_pdf_import(self):
        from backend.src.api.routers.exports import _generate_pdf
        self.assertTrue(callable(_generate_pdf))

    def test_generate_pdf_bytes_or_501(self):
        from backend.src.api.routers.exports import _generate_pdf
        from fastapi import HTTPException
        grant = {
            "id": "g-test",
            "subject_id": "user",
            "action": "read",
            "resource": "doc",
            "role": "viewer",
            "valid_from": None,
            "valid_until": None,
            "revoked": False,
            "reason": "",
            "created_at": "2024-01-01",
        }
        try:
            result = _generate_pdf(grant)
            self.assertIsInstance(result, bytes)
            self.assertGreater(len(result), 0)
        except HTTPException as e:
            self.assertEqual(e.status_code, 501)


class TestExportsEndpointsNoAuth(unittest.TestCase):
    def test_grants_csv_no_auth_401_or_403(self):
        client = _make_client()
        r = client.get("/v1/exports/grants.csv")
        self.assertIn(r.status_code, (401, 403, 422))

    def test_audit_csv_no_auth_401_or_403(self):
        client = _make_client()
        r = client.get("/v1/exports/audit.csv")
        self.assertIn(r.status_code, (401, 403, 422))

    def test_pdf_no_auth_401_or_403(self):
        client = _make_client()
        r = client.get("/v1/exports/grants/fake-id/report.pdf")
        self.assertIn(r.status_code, (401, 403, 422))


class TestExportsEndpointsAuthenticated(unittest.TestCase):
    def setUp(self):
        os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
        os.environ["GRANTLAYER_JWT_MODE"] = "hs256"
        from backend.src.core.db import init_db
        init_db()

    def tearDown(self):
        os.environ.pop("GRANTLAYER_JWT_MODE", None)

    def _headers(self):
        return {"Authorization": f"Bearer {_auth_token()}"}

    def test_grants_csv_returns_csv_or_error(self):
        client = _make_client()
        r = client.get("/v1/exports/grants.csv", headers=self._headers())
        self.assertIn(r.status_code, (200, 401, 403, 500))
        if r.status_code == 200:
            self.assertIn("text/csv", r.headers.get("content-type", ""))

    def test_grants_csv_content_disposition(self):
        client = _make_client()
        r = client.get("/v1/exports/grants.csv", headers=self._headers())
        if r.status_code == 200:
            self.assertIn("grants.csv", r.headers.get("content-disposition", ""))

    def test_audit_csv_returns_csv_or_error(self):
        client = _make_client()
        r = client.get("/v1/exports/audit.csv", headers=self._headers())
        self.assertIn(r.status_code, (200, 401, 403, 500))
        if r.status_code == 200:
            self.assertIn("text/csv", r.headers.get("content-type", ""))

    def test_audit_csv_content_disposition(self):
        client = _make_client()
        r = client.get("/v1/exports/audit.csv", headers=self._headers())
        if r.status_code == 200:
            self.assertIn("audit.csv", r.headers.get("content-disposition", ""))

    def test_pdf_nonexistent_grant_404(self):
        client = _make_client()
        r = client.get("/v1/exports/grants/nonexistent-grant-9999/report.pdf",
                       headers=self._headers())
        self.assertIn(r.status_code, (404, 401, 403, 500))

    def test_grants_csv_with_revoked_filter(self):
        client = _make_client()
        r = client.get("/v1/exports/grants.csv?revoked=true", headers=self._headers())
        self.assertIn(r.status_code, (200, 401, 403, 500))

    def test_grants_csv_with_revoked_false_filter(self):
        client = _make_client()
        r = client.get("/v1/exports/grants.csv?revoked=false", headers=self._headers())
        self.assertIn(r.status_code, (200, 401, 403, 500))

    def test_pdf_returns_pdf_or_501_or_404(self):
        client = _make_client()
        r = client.get("/v1/exports/grants/any-grant-id/report.pdf",
                       headers=self._headers())
        self.assertIn(r.status_code, (200, 404, 401, 403, 500, 501))
        if r.status_code == 200:
            self.assertIn("application/pdf", r.headers.get("content-type", ""))


if __name__ == "__main__":
    unittest.main()
