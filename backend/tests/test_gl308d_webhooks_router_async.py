"""GL-308 — Direct async router tests using httpx.AsyncClient + ASGITransport.

These tests run handlers natively in the async test loop, giving coverage tools
full visibility into the async function bodies that TestClient's thread-bridge hides.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import uuid

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.asyncio


_JWT_KEYS = [
    "GRANTLAYER_JWT_SECRET", "GRANTLAYER_JWT_PRIVATE_KEY", "GRANTLAYER_JWT_PUBLIC_KEY",
    "GRANTLAYER_JWT_ALGORITHM", "GRANTLAYER_JWT_PRIVATE_KEY_FILE",
    "GRANTLAYER_JWT_PUBLIC_KEY_FILE", "GRANTLAYER_REQUIRE_ADMIN_TOKEN", "GRANTLAYER_ENABLE_OIDC",
]


def _setup_env(admin_token: str, db_path: str):
    """Configure environment and DB for an isolated test."""
    saved = {k: os.environ.get(k) for k in _JWT_KEYS}
    saved["GRANTLAYER_ADMIN_TOKEN"] = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
    saved["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = os.environ.get("GRANTLAYER_ENABLE_OPERATOR_MODEL")

    for k in _JWT_KEYS:
        os.environ.pop(k, None)
    os.environ["GRANTLAYER_ADMIN_TOKEN"] = admin_token
    os.environ["GRANTLAYER_ENABLE_OPERATOR_MODEL"] = "false"
    os.environ.pop("GRANTLAYER_DATABASE_URL", None)

    import backend.src.core.db as _db
    import backend.src.core.config as _cfg
    orig_db_path = _db.DB_PATH_OR_URL
    orig_db_alias = getattr(_db, "DB_PATH", None)
    orig_enable_op = _cfg.ENABLE_OPERATOR_MODEL

    _db.DB_PATH_OR_URL = db_path
    _db.DB_PATH = db_path
    _db._sa_engine = None
    _db._async_engine = None
    _db._session_maker = None
    _db._async_session_maker = None
    _cfg.ENABLE_OPERATOR_MODEL = False
    _db.init_db()

    return saved, orig_db_path, orig_db_alias, orig_enable_op


def _restore_env(saved, orig_db_path, orig_db_alias, orig_enable_op):
    import backend.src.core.db as _db
    import backend.src.core.config as _cfg

    _db.DB_PATH_OR_URL = orig_db_path
    if orig_db_alias is not None:
        _db.DB_PATH = orig_db_alias
    _db._sa_engine = None
    _db._async_engine = None
    _db._session_maker = None
    _db._async_session_maker = None
    _cfg.ENABLE_OPERATOR_MODEL = orig_enable_op

    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


async def _get_client(app):
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ── Async router tests ────────────────────────────────────────────────────────

async def test_async_create_webhook():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    token = "async-test-create-wh"
    saved, odp, oda, ooe = _setup_env(token, tmp.name)
    try:
        from backend.src.api.app import create_app
        app = create_app()
        client = await _get_client(app)
        async with client:
            resp = await client.post(
                "/v1/webhooks",
                json={"url": "https://example.com/hook", "events": ["grant.created"]},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["active"] is True
    finally:
        _restore_env(saved, odp, oda, ooe)
        os.unlink(tmp.name)


async def test_async_list_webhooks():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    token = "async-test-list-wh"
    saved, odp, oda, ooe = _setup_env(token, tmp.name)
    try:
        from backend.src.api.app import create_app
        app = create_app()
        client = await _get_client(app)
        async with client:
            await client.post(
                "/v1/webhooks",
                json={"url": "https://example.com/hook", "events": ["grant.created"]},
                headers={"Authorization": f"Bearer {token}"},
            )
            resp = await client.get(
                "/v1/webhooks",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
    finally:
        _restore_env(saved, odp, oda, ooe)
        os.unlink(tmp.name)


async def test_async_get_webhook_by_id():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    token = "async-test-get-wh"
    saved, odp, oda, ooe = _setup_env(token, tmp.name)
    try:
        from backend.src.api.app import create_app
        app = create_app()
        client = await _get_client(app)
        async with client:
            create_resp = await client.post(
                "/v1/webhooks",
                json={"url": "https://example.com/hook", "events": ["grant.created"]},
                headers={"Authorization": f"Bearer {token}"},
            )
            wh_id = create_resp.json()["id"]
            resp = await client.get(
                f"/v1/webhooks/{wh_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert resp.json()["id"] == wh_id
    finally:
        _restore_env(saved, odp, oda, ooe)
        os.unlink(tmp.name)


async def test_async_get_webhook_not_found():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    token = "async-test-get-notfound"
    saved, odp, oda, ooe = _setup_env(token, tmp.name)
    try:
        from backend.src.api.app import create_app
        app = create_app()
        client = await _get_client(app)
        async with client:
            resp = await client.get(
                f"/v1/webhooks/{uuid.uuid4()}",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 404
        assert resp.json()["errorCode"] == "webhook_not_found"
    finally:
        _restore_env(saved, odp, oda, ooe)
        os.unlink(tmp.name)


async def test_async_delete_webhook():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    token = "async-test-delete-wh"
    saved, odp, oda, ooe = _setup_env(token, tmp.name)
    try:
        from backend.src.api.app import create_app
        app = create_app()
        client = await _get_client(app)
        async with client:
            create_resp = await client.post(
                "/v1/webhooks",
                json={"url": "https://example.com/hook", "events": ["grant.created"]},
                headers={"Authorization": f"Bearer {token}"},
            )
            wh_id = create_resp.json()["id"]
            del_resp = await client.delete(
                f"/v1/webhooks/{wh_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert del_resp.status_code == 204
    finally:
        _restore_env(saved, odp, oda, ooe)
        os.unlink(tmp.name)


async def test_async_delete_webhook_not_found():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    token = "async-test-delete-notfound"
    saved, odp, oda, ooe = _setup_env(token, tmp.name)
    try:
        from backend.src.api.app import create_app
        app = create_app()
        client = await _get_client(app)
        async with client:
            resp = await client.delete(
                f"/v1/webhooks/{uuid.uuid4()}",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 404
    finally:
        _restore_env(saved, odp, oda, ooe)
        os.unlink(tmp.name)


async def test_async_get_deliveries():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    token = "async-test-deliveries"
    saved, odp, oda, ooe = _setup_env(token, tmp.name)
    try:
        from backend.src.api.app import create_app
        app = create_app()
        client = await _get_client(app)
        async with client:
            create_resp = await client.post(
                "/v1/webhooks",
                json={"url": "https://example.com/hook", "events": ["grant.created"]},
                headers={"Authorization": f"Bearer {token}"},
            )
            wh_id = create_resp.json()["id"]
            resp = await client.get(
                f"/v1/webhooks/{wh_id}/deliveries",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert resp.json()["items"] == []
        assert resp.json()["total"] == 0
    finally:
        _restore_env(saved, odp, oda, ooe)
        os.unlink(tmp.name)


async def test_async_get_deliveries_not_found():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    token = "async-test-deliveries-404"
    saved, odp, oda, ooe = _setup_env(token, tmp.name)
    try:
        from backend.src.api.app import create_app
        app = create_app()
        client = await _get_client(app)
        async with client:
            resp = await client.get(
                f"/v1/webhooks/{uuid.uuid4()}/deliveries",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 404
    finally:
        _restore_env(saved, odp, oda, ooe)
        os.unlink(tmp.name)


async def test_async_test_endpoint_records_failed_delivery():
    """POST /test records a failed delivery when the target is unreachable."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    token = "async-test-endpoint"
    saved, odp, oda, ooe = _setup_env(token, tmp.name)
    try:
        from backend.src.api.app import create_app
        app = create_app()
        client = await _get_client(app)

        async with client:
            create_resp = await client.post(
                "/v1/webhooks",
                json={"url": "http://93.184.216.34:19997/hook", "events": ["grant.created"]},
                headers={"Authorization": f"Bearer {token}"},
            )
            wh_id = create_resp.json()["id"]

            # Use a connection refused error for the target — doesn't affect the ASGI test client
            with patch("backend.src.webhooks.router._httpx.AsyncClient") as mock_cls:
                mock_inst = mock_cls.return_value.__aenter__.return_value
                mock_inst.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
                mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                test_resp = await client.post(
                    f"/v1/webhooks/{wh_id}/test",
                    headers={"Authorization": f"Bearer {token}"},
                )
        assert test_resp.status_code == 200
        data = test_resp.json()
        assert data["status"] == "failed"
        assert data["eventType"] == "webhook.test"
        assert data["webhookId"] == wh_id
    finally:
        _restore_env(saved, odp, oda, ooe)
        os.unlink(tmp.name)


async def test_async_test_endpoint_not_found():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    token = "async-test-endpoint-404"
    saved, odp, oda, ooe = _setup_env(token, tmp.name)
    try:
        from backend.src.api.app import create_app
        app = create_app()
        client = await _get_client(app)
        async with client:
            resp = await client.post(
                f"/v1/webhooks/{uuid.uuid4()}/test",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 404
    finally:
        _restore_env(saved, odp, oda, ooe)
        os.unlink(tmp.name)


async def test_async_test_endpoint_success_response():
    """POST /test records a successful delivery when target returns 2xx."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    token = "async-test-endpoint-ok"
    saved, odp, oda, ooe = _setup_env(token, tmp.name)
    try:
        from backend.src.api.app import create_app
        app = create_app()
        client = await _get_client(app)

        async with client:
            create_resp = await client.post(
                "/v1/webhooks",
                json={"url": "https://example.com/hook", "events": ["grant.created"]},
                headers={"Authorization": f"Bearer {token}"},
            )
            wh_id = create_resp.json()["id"]

            with patch("backend.src.webhooks.router._httpx.AsyncClient") as mock_cls:
                mock_resp = MagicMock()
                mock_resp.status_code = 201
                mock_inst = mock_cls.return_value.__aenter__.return_value
                mock_inst.post = AsyncMock(return_value=mock_resp)
                mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                test_resp = await client.post(
                    f"/v1/webhooks/{wh_id}/test",
                    headers={"Authorization": f"Bearer {token}"},
                )
        assert test_resp.status_code == 200
        data = test_resp.json()
        assert data["status"] == "success"
        assert data["httpStatus"] == 201
    finally:
        _restore_env(saved, odp, oda, ooe)
        os.unlink(tmp.name)
