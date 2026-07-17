"""RED tests — API-key requests must resolve into the KEY'S bound workspace.

Current bugs (audited, both resolvers in backend/src/api/deps.py):
  sync  :116  effective_workspace = workspace_id or api_payload["workspace_id"]
  async :68   (same expression)
A client-supplied X-Workspace-Id OVERRIDES the key's server-side binding with
no membership or tenant validation (resolution_mode "api_key" skips both), and
a key with an empty binding silently resolves into "" instead of being refused.

Desired behavior (asserted here, so these fail today):
  * an API-key request resolves into the key's bound workspace, only;
  * a workspace header that MISMATCHES the binding → 403, fail-closed;
  * a matching header (or none) → allowed, bound workspace;
  * a missing/empty binding → refused, never a fallback.
Internal-JWT resolution is untouched by this contract.

Self-provisions a private SQLite DB (temp .db + GRANTLAYER_DB + db reload) —
listed in _sqlite_only_modules.py per the harness convention.
"""

import asyncio
import importlib
import os
import sys
import tempfile
import unittest
import uuid

from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_ENV_KEYS = ("GRANTLAYER_DB", "GRANTLAYER_DATABASE_URL")


class _ApiKeyResolverBase(unittest.TestCase):
    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig_env = {k: os.environ.get(k) for k in _ENV_KEYS}
        os.environ["GRANTLAYER_DB"] = self.tmp_db.name
        os.environ.pop("GRANTLAYER_DATABASE_URL", None)

        import backend.src.core.db as db_mod
        importlib.reload(db_mod)
        db_mod.init_db()
        self.db_mod = db_mod

        self.ws_a = str(uuid.uuid4())
        self.ws_b = str(uuid.uuid4())
        self._insert_workspace(self.ws_a, "res-ws-a")
        self._insert_workspace(self.ws_b, "res-ws-b")

    def tearDown(self):
        os.unlink(self.tmp_db.name)
        for key, orig in self._orig_env.items():
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig
        # Re-derive core.db module state from the RESTORED env: a bare env
        # restore leaves the reloaded module's DB_PATH_OR_URL frozen at this
        # test's (now deleted) temp path and poisons every later test that
        # uses the ambient process DB.
        import backend.src.core.db as db_mod
        importlib.reload(db_mod)

    def _insert_workspace(self, ws_id, slug):
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO workspaces
                       (id, tenant_id, name, slug, owner_id, status,
                        created_at, updated_at)
                   VALUES (?, 'demo', ?, ?, 'system', 'active',
                           '2026-07-17T00:00:00Z', '2026-07-17T00:00:00Z')""",
                (ws_id, slug, slug),
            )
            conn.commit()
        finally:
            conn.close()

    def _insert_api_key(self, bound_workspace):
        """Insert an api_keys row directly; return the raw gl_live_ key."""
        from backend.src.api.routers.api_keys import _hash_key

        raw = f"gl_live_{uuid.uuid4().hex}{uuid.uuid4().hex}"
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO api_keys
                       (id, workspace_id, user_id, key_hash, name, scopes,
                        created_at)
                   VALUES (?, ?, 'key-user', ?, 'resolver-test', '["read_only"]',
                           '2026-07-17T00:00:00Z')""",
                (str(uuid.uuid4()), bound_workspace, _hash_key(raw)),
            )
            conn.commit()
        finally:
            conn.close()
        return raw

    # ── resolver invocation seams ────────────────────────────────────────
    def _resolve_sync(self, raw_key, header_workspace):
        from backend.src.api.deps import resolve_auth_and_workspace

        return resolve_auth_and_workspace(
            f"Bearer {raw_key}", ["owner", "grant_admin"], header_workspace
        )

    def _resolve_async(self, raw_key, header_workspace):
        from backend.src.api.deps import async_resolve_auth_and_workspace

        async def _inner():
            from backend.src.core.db import get_async_session_maker

            maker = get_async_session_maker()
            async with maker() as db:
                return await async_resolve_auth_and_workspace(
                    f"Bearer {raw_key}",
                    ["owner", "grant_admin"],
                    db,
                    workspace_id=header_workspace,
                )

        return asyncio.run(_inner())


class TestApiKeyResolverSync(_ApiKeyResolverBase):
    def test_no_header_resolves_bound_workspace(self):
        """Positive control (passes today): no header → the key's binding."""
        raw = self._insert_api_key(self.ws_a)
        _, ws_ctx = self._resolve_sync(raw, None)
        self.assertEqual(ws_ctx["workspace_id"], self.ws_a)
        self.assertEqual(ws_ctx["resolution_mode"], "api_key")

    def test_matching_header_resolves_bound_workspace(self):
        """Positive control (passes today): matching header → allowed."""
        raw = self._insert_api_key(self.ws_a)
        _, ws_ctx = self._resolve_sync(raw, self.ws_a)
        self.assertEqual(ws_ctx["workspace_id"], self.ws_a)

    def test_mismatching_header_is_refused(self):
        """RED: header naming a DIFFERENT workspace must 403 — today it
        silently overrides the key's binding."""
        raw = self._insert_api_key(self.ws_a)
        try:
            _, ws_ctx = self._resolve_sync(raw, self.ws_b)
        except HTTPException as exc:
            self.assertEqual(exc.status_code, 403)
        else:
            self.fail(
                "CLIENT OVERRIDE: key bound to workspace A was resolved into "
                f"header workspace {ws_ctx['workspace_id']!r} "
                f"(binding {self.ws_a!r})"
            )

    def test_empty_binding_is_refused(self):
        """RED: a key with an empty workspace binding must be refused —
        today it resolves into the empty string."""
        raw = self._insert_api_key("")
        try:
            _, ws_ctx = self._resolve_sync(raw, None)
        except HTTPException as exc:
            self.assertEqual(exc.status_code, 403)
        else:
            self.fail(
                "UNBOUND KEY ACCEPTED: empty workspace binding resolved into "
                f"{ws_ctx['workspace_id']!r} instead of being refused"
            )


class TestApiKeyResolverAsync(_ApiKeyResolverBase):
    def test_no_header_resolves_bound_workspace(self):
        raw = self._insert_api_key(self.ws_a)
        _, ws_ctx = self._resolve_async(raw, None)
        self.assertEqual(ws_ctx["workspace_id"], self.ws_a)
        self.assertEqual(ws_ctx["resolution_mode"], "api_key")

    def test_matching_header_resolves_bound_workspace(self):
        raw = self._insert_api_key(self.ws_a)
        _, ws_ctx = self._resolve_async(raw, self.ws_a)
        self.assertEqual(ws_ctx["workspace_id"], self.ws_a)

    def test_mismatching_header_is_refused(self):
        raw = self._insert_api_key(self.ws_a)
        try:
            _, ws_ctx = self._resolve_async(raw, self.ws_b)
        except HTTPException as exc:
            self.assertEqual(exc.status_code, 403)
        else:
            self.fail(
                "CLIENT OVERRIDE (async): key bound to workspace A was "
                f"resolved into header workspace {ws_ctx['workspace_id']!r} "
                f"(binding {self.ws_a!r})"
            )

    def test_empty_binding_is_refused(self):
        raw = self._insert_api_key("")
        try:
            _, ws_ctx = self._resolve_async(raw, None)
        except HTTPException as exc:
            self.assertEqual(exc.status_code, 403)
        else:
            self.fail(
                "UNBOUND KEY ACCEPTED (async): empty workspace binding "
                f"resolved into {ws_ctx['workspace_id']!r}"
            )


class TestApiKeyCreationBinding(_ApiKeyResolverBase):
    """RED — API-key CREATION binds the key to the creator's RESOLVED workspace.

    Today POST /v1/api-keys derives the binding from a raw JWT claim
    (payload.get("workspace_id") or "default") with no workspace resolution:
    internal JWTs carry no workspace claim, so every key binds to "default"
    regardless of the creator's actual workspace, and callers without any
    resolvable workspace still mint keys.

    Desired (asserted here): creation resolves the workspace through the
    standard resolver machinery; the created key's binding IS the resolved
    workspace; a request-body workspace_id is rejected fail-loud with no key
    row; no resolvable workspace → 403 and no key row; demo-context creation
    works via REAL membership resolution; and end-to-end, a key created under
    workspace A resolves back into A when used.
    """

    _JWT_SECRET = "apikey-binding-test-secret-0123456789abcdef"

    def setUp(self):
        super().setUp()
        self._orig_jwt = {
            k: os.environ.get(k)
            for k in ("GRANTLAYER_JWT_SECRET", "GRANTLAYER_JWT_PUBLIC_KEY")
        }
        os.environ["GRANTLAYER_JWT_SECRET"] = self._JWT_SECRET
        os.environ.pop("GRANTLAYER_JWT_PUBLIC_KEY", None)

    def tearDown(self):
        for key, orig in self._orig_jwt.items():
            if orig is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig
        super().tearDown()

    def _jwt(self, *, sub, role, tenant_id):
        from backend.src.api.auth_jwt import encode_token

        return encode_token(
            {
                "sub": sub,
                "role": role,
                "tenant_id": tenant_id,
                "iss": "grantlayer",
                "aud": "grantlayer-api",
            },
            self._JWT_SECRET,
        )

    def _insert_membership(self, workspace_id, operator_id):
        conn = self.db_mod.get_conn()
        try:
            conn.execute(
                """INSERT INTO workspace_members
                       (id, workspace_id, operator_id, role, joined_at, status)
                   VALUES (?, ?, ?, 'workspace_member',
                           '2026-07-17T00:00:00Z', 'active')""",
                (str(uuid.uuid4()), workspace_id, operator_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _client(self):
        from fastapi.testclient import TestClient

        from backend.src.api.app import create_app

        return TestClient(create_app(), raise_server_exceptions=False)

    def _post_key(self, token, *, header_workspace=None, body_extra=None):
        headers = {"Authorization": f"Bearer {token}"}
        if header_workspace is not None:
            headers["X-Workspace-Id"] = header_workspace
        body = {"name": "binding-test", "scopes": ["read_only"]}
        if body_extra:
            body.update(body_extra)
        return self._client().post("/v1/api-keys", json=body, headers=headers)

    def _key_row_workspace(self, key_id):
        conn = self.db_mod.get_conn()
        try:
            row = conn.execute(
                "SELECT workspace_id FROM api_keys WHERE id = ?", (key_id,)
            ).fetchone()
            return row["workspace_id"] if row is not None else None
        finally:
            conn.close()

    def _key_row_count(self):
        conn = self.db_mod.get_conn()
        try:
            return conn.execute("SELECT COUNT(*) AS n FROM api_keys").fetchone()["n"]
        finally:
            conn.close()

    def test_key_binds_to_creators_resolved_workspace(self):
        """(i) RED: creator resolved into workspace A → key row bound to A."""
        token = self._jwt(sub="creator-1", role="owner", tenant_id="demo")
        resp = self._post_key(token, header_workspace=self.ws_a)
        self.assertEqual(resp.status_code, 201, f"harness broke: {resp.text}")
        key_id = resp.json()["id"]
        self.assertEqual(
            self._key_row_workspace(key_id),
            self.ws_a,
            "created key is not bound to the creator's resolved workspace "
            f"{self.ws_a}",
        )

    def test_body_workspace_id_is_rejected(self):
        """(ii) RED: a request-body workspace_id must be rejected fail-loud
        and create NO key row — today a matching value is accepted."""
        token = self._jwt(sub="creator-2", role="owner", tenant_id="demo")
        before = self._key_row_count()
        resp = self._post_key(
            token,
            header_workspace="default",
            body_extra={"workspace_id": "default"},
        )
        self.assertIn(
            resp.status_code,
            (400, 422),
            "body workspace_id was accepted instead of rejected: "
            f"{resp.status_code} {resp.text}",
        )
        self.assertEqual(self._key_row_count(), before, "a key row was created")

    def test_no_resolvable_workspace_is_refused(self):
        """(iii) RED: a caller with NO resolvable workspace (non-demo tenant,
        no membership, no header) must get 403 and create no key row."""
        token = self._jwt(sub="creator-3", role="grant_admin", tenant_id="hofer")
        before = self._key_row_count()
        resp = self._post_key(token)
        self.assertEqual(
            resp.status_code,
            403,
            "creation without a resolvable workspace was allowed: "
            f"{resp.status_code} {resp.text}",
        )
        self.assertEqual(self._key_row_count(), before, "a key row was created")

    def test_demo_context_creation_works_via_membership_resolution(self):
        """(iv) Positive control: a REGULAR-role demo-tenant creator with a
        real membership row resolves via single_membership (not any fallback)
        and creation works, bound to the membership workspace."""
        self._insert_membership(self.ws_a, "creator-4")
        token = self._jwt(sub="creator-4", role="grant_admin", tenant_id="demo")
        resp = self._post_key(token)
        self.assertEqual(resp.status_code, 201, f"membership creation broke: {resp.text}")
        key_id = resp.json()["id"]
        self.assertEqual(
            self._key_row_workspace(key_id),
            self.ws_a,
            "key not bound to the membership-resolved workspace",
        )

    def test_end_to_end_created_key_resolves_into_its_workspace(self):
        """(v) RED: a key created under workspace A must RESOLVE into A when
        used (creation binding + resolver binding, tied together)."""
        token = self._jwt(sub="creator-5", role="owner", tenant_id="demo")
        resp = self._post_key(token, header_workspace=self.ws_a)
        self.assertEqual(resp.status_code, 201, f"harness broke: {resp.text}")
        raw_key = resp.json()["key"]

        _, ws_ctx = self._resolve_sync(raw_key, None)
        self.assertEqual(
            ws_ctx["workspace_id"],
            self.ws_a,
            "a key created under workspace A does not resolve into A",
        )


if __name__ == "__main__":
    unittest.main()
