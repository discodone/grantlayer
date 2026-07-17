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


if __name__ == "__main__":
    unittest.main()
