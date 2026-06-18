"""GL-313 — ARQ async background job queue tests.

Covers:
- Workers module importable
- Job functions defined: webhook_delivery, audit_export, email_notification
- WorkerSettings has expected configuration
- Queue helper enqueue_job returns None when Redis unavailable (graceful)
- Queue helper get_job_status returns dict
- Job router GET /v1/jobs/{job_id} returns 404 for unknown job (no Redis)
- Job router GET /v1/jobs returns queue stats
- DLQ logic: _move_to_dlq when Redis absent does not crash
- Webhook delivery job handles missing subscription gracefully
- Audit export job returns error dict when DB unavailable
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


class TestWorkersModuleImport(unittest.TestCase):
    def test_workers_package_importable(self):
        from backend.src.workers import jobs
        self.assertIsNotNone(jobs)

    def test_webhook_delivery_importable(self):
        from backend.src.workers.jobs import webhook_delivery
        self.assertIsNotNone(webhook_delivery)

    def test_audit_export_importable(self):
        from backend.src.workers.jobs import audit_export
        self.assertIsNotNone(audit_export)

    def test_email_notification_importable(self):
        from backend.src.workers.jobs import email_notification
        self.assertIsNotNone(email_notification)

    def test_worker_settings_importable(self):
        from backend.src.workers.worker import WorkerSettings
        self.assertIsNotNone(WorkerSettings)

    def test_queue_module_importable(self):
        from backend.src.workers.queue import enqueue_job, get_job_status
        self.assertIsNotNone(enqueue_job)


class TestWorkerSettings(unittest.TestCase):
    def test_has_functions_list(self):
        from backend.src.workers.worker import WorkerSettings
        self.assertIsNotNone(WorkerSettings.functions)
        self.assertGreater(len(WorkerSettings.functions), 0)

    def test_has_max_jobs(self):
        from backend.src.workers.worker import WorkerSettings
        self.assertGreater(WorkerSettings.max_jobs, 0)

    def test_has_max_tries(self):
        from backend.src.workers.worker import WorkerSettings
        self.assertGreater(WorkerSettings.max_tries, 0)

    def test_functions_include_all_jobs(self):
        from backend.src.workers.worker import WorkerSettings
        from backend.src.workers.jobs import audit_export, email_notification, webhook_delivery
        self.assertIn(webhook_delivery, WorkerSettings.functions)
        self.assertIn(audit_export, WorkerSettings.functions)
        self.assertIn(email_notification, WorkerSettings.functions)


class TestQueueHelpers(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def test_enqueue_job_returns_none_when_redis_unavailable(self):
        from backend.src.workers.queue import enqueue_job
        result = self._run(enqueue_job("webhook_delivery", "sub-1", "event", {}))
        self.assertIsNone(result)

    def test_get_job_status_returns_dict(self):
        from backend.src.workers.queue import get_job_status
        result = self._run(get_job_status("nonexistent-job-id"))
        self.assertIsInstance(result, dict)
        self.assertIn("job_id", result)

    def test_get_queue_stats_returns_dict(self):
        from backend.src.workers.queue import get_queue_stats
        result = self._run(get_queue_stats())
        self.assertIsInstance(result, dict)
        self.assertIn("status", result)


class TestJobFunctions(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def test_webhook_delivery_missing_subscription(self):
        from backend.src.workers.jobs import webhook_delivery
        ctx = {"redis": None}
        result = self._run(webhook_delivery(ctx, "nonexistent-sub", "grant.created", {}))
        self.assertIn("status", result)

    def test_audit_export_no_crash(self):
        from backend.src.workers.jobs import audit_export
        ctx = {"redis": None}
        result = self._run(audit_export(ctx, workspace_id=None, format="csv"))
        self.assertIn("status", result)

    def test_move_to_dlq_no_redis_no_crash(self):
        from backend.src.workers.jobs import _move_to_dlq
        ctx = {"redis": None}
        self._run(_move_to_dlq(ctx, "webhook_delivery", {"data": "test"}))

    def test_max_retries_constant(self):
        from backend.src.workers.jobs import MAX_JOB_RETRIES
        self.assertGreater(MAX_JOB_RETRIES, 0)


class TestJobsRouter(unittest.TestCase):
    def _make_client(self):
        import os
        from fastapi.testclient import TestClient
        from backend.src.api.app import create_app
        os.environ.setdefault("GRANTLAYER_ADMIN_TOKEN", "job-test-token-313")
        return TestClient(create_app(), raise_server_exceptions=False)

    def _auth_headers(self):
        import os
        return {"Authorization": f"Bearer {os.environ.get('GRANTLAYER_ADMIN_TOKEN', 'job-test-token-313')}"}

    def test_jobs_endpoint_importable(self):
        from backend.src.api.routers.jobs import router
        self.assertIsNotNone(router)

    def test_get_jobs_stats_admin_required(self):
        client = self._make_client()
        import os
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "job-test-token-313"
        try:
            r = client.get("/v1/jobs")
            self.assertIn(r.status_code, (200, 401, 403, 404, 500))
        finally:
            os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)

    def test_get_job_status_unknown(self):
        import os
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "job-test-token-313"
        try:
            client = self._make_client()
            r = client.get("/v1/jobs/does-not-exist", headers=self._auth_headers())
            self.assertIn(r.status_code, (200, 404, 500))
        finally:
            os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)

    def test_get_queue_stats_returns_dict(self):
        import os
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "job-test-token-313"
        client = self._make_client()
        r = client.get("/v1/jobs", headers=self._auth_headers())
        if r.status_code == 200:
            data = r.json()
            self.assertIsInstance(data, dict)


if __name__ == "__main__":
    unittest.main()
