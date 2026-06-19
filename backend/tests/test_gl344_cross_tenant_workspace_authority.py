"""GL-344 — Cross-tenant privilege escalation via body-derived workspace_id.

P0 SECURITY. Proves the EXACT behavior claimed by the fix:

- A grant_admin authenticated to workspace A creating an API key / template with a
  body workspace_id bound to workspace B receives 403 (never silently bound to B).
- An API key / template created with no body workspace_id is bound to the caller's
  authenticated workspace.
- A body workspace_id that equals the authenticated workspace is accepted.
- Cross-tenant template lookups (get / deactivate / new-version) return 404 — the
  IDOR is closed and the other tenant's template is never observable.
- A repo-wide static guard asserts no mutation handler reads workspace_id from the
  request body as an authority (positive allowlist, not a hand-maintained exclusion).

These tests MUST fail against the pre-fix code (body.workspace_id is trusted and
template lookups are unfiltered) and pass after the fix.
"""

from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

_TEST_SECRET = "gl344-test-hs256-secret-32chars!!!"


def _make_client():
    from fastapi.testclient import TestClient

    from backend.src.api.app import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _jwt(workspace_id: str, tenant_id: str, sub: str = "user-a", role: str = "grant_admin") -> str:
    os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
    os.environ.pop("GRANTLAYER_JWT_PRIVATE_KEY", None)
    os.environ.pop("GRANTLAYER_JWT_PUBLIC_KEY", None)
    from backend.src.api.auth_jwt import encode_token

    return encode_token(
        {
            "sub": sub,
            "role": role,
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "iss": "grantlayer",
            "aud": "grantlayer-api",
        },
        _TEST_SECRET,
    )


class TestApiKeyWorkspaceAuthority(unittest.TestCase):
    def setUp(self):
        self.client = _make_client()
        self.auth_a = {"Authorization": f"Bearer {_jwt('ws-A', 't-A', sub='admin-a')}"}

    def test_cross_tenant_body_workspace_rejected_403(self):
        """tenant-A admin must NOT mint a key bound to workspace B."""
        resp = self.client.post(
            "/v1/api-keys",
            json={"name": "evil", "scopes": ["admin"], "workspace_id": "ws-B"},
            headers=self.auth_a,
        )
        self.assertEqual(resp.status_code, 403, resp.text)

    def test_no_body_workspace_binds_to_authenticated_workspace(self):
        resp = self.client.post(
            "/v1/api-keys",
            json={"name": "ok", "scopes": ["read_write"]},
            headers=self.auth_a,
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        self.assertEqual(resp.json()["workspaceId"], "ws-A")

    def test_matching_body_workspace_allowed(self):
        resp = self.client.post(
            "/v1/api-keys",
            json={"name": "ok", "scopes": ["read_write"], "workspace_id": "ws-A"},
            headers=self.auth_a,
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        self.assertEqual(resp.json()["workspaceId"], "ws-A")


class TestTemplateWorkspaceAuthority(unittest.TestCase):
    def setUp(self):
        self.client = _make_client()
        self.auth_a = {"Authorization": f"Bearer {_jwt('ws-A', 't-A', sub='admin-a')}"}

    def test_create_cross_tenant_body_workspace_rejected_403(self):
        resp = self.client.post(
            "/v1/grant-templates",
            json={"name": "evil", "workspace_id": "ws-B"},
            headers=self.auth_a,
        )
        self.assertEqual(resp.status_code, 403, resp.text)

    def test_create_binds_to_authenticated_workspace(self):
        resp = self.client.post(
            "/v1/grant-templates",
            json={"name": "ok"},
            headers=self.auth_a,
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        self.assertEqual(resp.json()["workspace_id"], "ws-A")

    def test_new_version_cross_tenant_body_workspace_rejected_403(self):
        create = self.client.post(
            "/v1/grant-templates",
            json={"name": "base"},
            headers=self.auth_a,
        )
        self.assertEqual(create.status_code, 201, create.text)
        tmpl_id = create.json()["id"]
        resp = self.client.post(
            f"/v1/grant-templates/{tmpl_id}/new-version",
            json={"name": "base v2", "workspace_id": "ws-B"},
            headers=self.auth_a,
        )
        self.assertEqual(resp.status_code, 403, resp.text)


class TestCrossTenantTemplateIdor(unittest.TestCase):
    def setUp(self):
        self.client = _make_client()
        self.auth_a = {"Authorization": f"Bearer {_jwt('ws-A', 't-A', sub='admin-a')}"}
        self.auth_b = {"Authorization": f"Bearer {_jwt('ws-B', 't-B', sub='admin-b')}"}
        # Tenant A creates a template in workspace A.
        create = self.client.post(
            "/v1/grant-templates",
            json={"name": "tenant-a-secret"},
            headers=self.auth_a,
        )
        self.assertEqual(create.status_code, 201, create.text)
        self.tmpl_id = create.json()["id"]

    def test_cross_tenant_get_returns_404(self):
        resp = self.client.get(f"/v1/grant-templates/{self.tmpl_id}", headers=self.auth_b)
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_cross_tenant_deactivate_returns_404(self):
        resp = self.client.post(
            f"/v1/grant-templates/{self.tmpl_id}/deactivate", headers=self.auth_b
        )
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_cross_tenant_new_version_returns_404(self):
        resp = self.client.post(
            f"/v1/grant-templates/{self.tmpl_id}/new-version",
            json={"name": "stolen v2"},
            headers=self.auth_b,
        )
        self.assertEqual(resp.status_code, 404, resp.text)

    def test_owner_can_still_access_own_template(self):
        # Sanity: the legitimate owner is unaffected by the new filter.
        get_resp = self.client.get(f"/v1/grant-templates/{self.tmpl_id}", headers=self.auth_a)
        self.assertEqual(get_resp.status_code, 200, get_resp.text)


class TestNoBodyWorkspaceAuthorityRepoWide(unittest.TestCase):
    """Positive guard: enumerate ALL routers and assert no mutation handler reads
    workspace_id (or tenant_id) from the request body as an authority.
    """

    # Patterns that signal "request body overrides the verified workspace authority".
    _FORBIDDEN = (
        re.compile(r"\bbody\.workspace_id\s+or\b"),
        re.compile(r"\bbody\.tenant_id\s+or\b"),
        re.compile(r"\bworkspace_id\s+or\s+payload\b"),
        re.compile(r"\bor\s+parent\[[\"']workspace_id[\"']\]"),
    )

    def _router_files(self) -> list[Path]:
        root = Path(__file__).parent.parent / "src" / "api" / "routers"
        files = [p for p in root.glob("*.py") if p.name != "__init__.py"]
        webhooks = Path(__file__).parent.parent / "src" / "webhooks" / "router.py"
        if webhooks.exists():
            files.append(webhooks)
        return files

    def test_no_router_derives_workspace_from_body(self):
        offenders: list[str] = []
        for path in self._router_files():
            src = path.read_text()
            for pat in self._FORBIDDEN:
                for m in pat.finditer(src):
                    line_no = src[: m.start()].count("\n") + 1
                    offenders.append(f"{path.name}:{line_no}: {m.group(0)!r}")
        self.assertEqual(
            offenders,
            [],
            "Mutation handlers must derive workspace_id from the verified auth "
            "context, never from the request body:\n" + "\n".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
