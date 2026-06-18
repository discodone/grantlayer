"""GL-338 — Architecture document correctness.

Tests verify that docs/architecture.md describes the actual codebase:
- FastAPI is mentioned
- Service layer is mentioned
- Repository layer is mentioned
- SQLAlchemy is mentioned
- Multi-tenancy (tenant_id/workspace_id) is mentioned
- OPA is mentioned
- Audit hash-chain is mentioned
- Raw SQL exceptions are documented
"""

from __future__ import annotations

import os
import unittest


def _arch_content() -> str:
    path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "docs", "architecture.md")
    )
    with open(path) as f:
        return f.read()


class TestArchitectureDocContent(unittest.TestCase):
    def setUp(self):
        self.content = _arch_content()

    def test_mentions_fastapi(self):
        self.assertIn("FastAPI", self.content, "architecture.md must mention FastAPI")

    def test_mentions_service_layer(self):
        self.assertIn("Service layer", self.content, "architecture.md must describe service layer")

    def test_mentions_repository_layer(self):
        self.assertIn("Repository", self.content, "architecture.md must describe repository layer")

    def test_mentions_sqlalchemy(self):
        self.assertIn("SQLAlchemy", self.content, "architecture.md must mention SQLAlchemy")

    def test_mentions_opa(self):
        self.assertIn("OPA", self.content, "architecture.md must mention OPA policy engine")

    def test_mentions_tenant_id(self):
        self.assertIn("tenant_id", self.content, "architecture.md must mention multi-tenancy")

    def test_mentions_workspace_id(self):
        self.assertIn("workspace_id", self.content, "architecture.md must mention workspace_id")

    def test_mentions_audit_hash_chain(self):
        self.assertIn("hash", self.content.lower(), "architecture.md must mention audit hash-chain")

    def test_no_server_py_reference(self):
        self.assertNotIn(
            "server.py", self.content,
            "architecture.md must not reference the deleted server.py"
        )

    def test_no_stdlib_http_reference(self):
        self.assertNotIn(
            "stdlib", self.content,
            "architecture.md must not reference old stdlib HTTP server"
        )

    def test_raw_sql_exceptions_documented(self):
        self.assertIn(
            "text(", self.content,
            "architecture.md must document the known raw text() SQL exceptions"
        )

    def test_fail_closed_opa_documented(self):
        self.assertIn(
            "fail-closed", self.content,
            "architecture.md must document OPA fail-closed posture"
        )

    def test_ssrf_documented(self):
        self.assertIn(
            "SSRF", self.content,
            "architecture.md must document webhook SSRF guard"
        )

    def test_jwt_strict_claims_documented(self):
        self.assertIn(
            "JWT_STRICT_CLAIMS", self.content,
            "architecture.md must document JWT_STRICT_CLAIMS default"
        )
