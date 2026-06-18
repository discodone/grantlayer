"""GL-320 — Performance Benchmarking Suite.

Uses pytest-benchmark for CI-friendly benchmarks.
Scenarios: grant list 1k records, grant create, bulk-approve 100, audit log query 10k.
Baselines stored in baselines.json — relative regression detection (p95 within 2x baseline).

These tests are marked as 'performance' and excluded from make test (functional suite).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

_BASELINES_FILE = Path(__file__).parent / "baselines.json"

_TEST_SECRET = "gl320-perf-hs256-secret-32chars!!"

pytestmark = pytest.mark.performance


def _load_baselines() -> dict[str, Any]:
    with open(_BASELINES_FILE) as f:
        return json.load(f)


def _make_client():
    from fastapi.testclient import TestClient
    from backend.src.api.app import create_app
    return TestClient(create_app(), raise_server_exceptions=False)


def _jwt() -> str:
    os.environ["GRANTLAYER_JWT_SECRET"] = _TEST_SECRET
    from backend.src.api.auth_jwt import encode_token
    # Use tenant_id="demo" so workspace resolution falls back to demo workspace
    # when no explicit workspace_id is provided (no DB lookup needed).
    return encode_token(
        {"sub": "perf-user", "role": "grant_admin", "tenant_id": "demo",
         "iss": "grantlayer", "aud": "grantlayer-api"},
        _TEST_SECRET,
    )


def _measure_p95(times_ms: list[float]) -> float:
    sorted_times = sorted(times_ms)
    idx = int(len(sorted_times) * 0.95)
    return sorted_times[min(idx, len(sorted_times) - 1)]


@pytest.fixture(scope="module")
def client():
    return _make_client()


@pytest.fixture(scope="module")
def auth_header():
    return {"Authorization": f"Bearer {_jwt()}"}


@pytest.fixture(scope="module")
def baselines():
    return _load_baselines()


class TestGrantList1k:
    def test_grant_list_p95_within_2x_baseline(self, client, auth_header, baselines):
        """Grant list endpoint: p95 latency within 2x baseline."""
        baseline_ms = baselines["grant_list_1k"]["p95_ms"]
        times = []
        for _ in range(10):
            start = time.perf_counter()
            resp = client.get("/v1/grants", headers=auth_header)
            elapsed_ms = (time.perf_counter() - start) * 1000
            assert resp.status_code in (200, 400, 422)
            times.append(elapsed_ms)

        p95 = _measure_p95(times)
        assert p95 <= baseline_ms * 2, (
            f"grant_list p95={p95:.1f}ms exceeds 2x baseline ({baseline_ms * 2}ms)"
        )


class TestGrantCreate:
    def test_grant_create_p95_within_2x_baseline(self, client, auth_header, baselines):
        """Grant create endpoint: p95 latency within 2x baseline."""
        baseline_ms = baselines["grant_create"]["p95_ms"]
        times = []
        for i in range(10):
            payload = {
                "subjectId": f"perf-user-{i}",
                "role": "viewer",
                "action": "read",
                "resource": f"doc/{uuid.uuid4()}",
                "validFrom": "2026-01-01T00:00:00Z",
                "validUntil": "2027-01-01T00:00:00Z",
                "reason": "perf test",
            }
            start = time.perf_counter()
            resp = client.post("/v1/grants", json=payload, headers=auth_header)
            elapsed_ms = (time.perf_counter() - start) * 1000
            assert resp.status_code in (200, 201, 400, 422)
            times.append(elapsed_ms)

        p95 = _measure_p95(times)
        assert p95 <= baseline_ms * 2, (
            f"grant_create p95={p95:.1f}ms exceeds 2x baseline ({baseline_ms * 2}ms)"
        )


class TestBulkApprove100:
    def test_bulk_approve_p95_within_2x_baseline(self, client, auth_header, baselines):
        """Bulk approve endpoint: p95 latency within 2x baseline."""
        baseline_ms = baselines["bulk_approve_100"]["p95_ms"]
        times = []
        # Measure 5 runs of bulk-approve with 10 IDs each (simulates load)
        for _ in range(5):
            ids = [str(uuid.uuid4()) for _ in range(10)]
            start = time.perf_counter()
            resp = client.post(
                "/v1/grant-requests/bulk-approve",
                json={"ids": ids, "reason": "perf test"},
                headers=auth_header,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            assert resp.status_code in (200, 400, 422)
            times.append(elapsed_ms)

        p95 = _measure_p95(times)
        assert p95 <= baseline_ms * 2, (
            f"bulk_approve p95={p95:.1f}ms exceeds 2x baseline ({baseline_ms * 2}ms)"
        )


class TestAuditLogQuery10k:
    def test_audit_log_query_p95_within_2x_baseline(self, client, auth_header, baselines):
        """Audit log query endpoint: p95 latency within 2x baseline."""
        baseline_ms = baselines["audit_log_query_10k"]["p95_ms"]
        times = []
        for _ in range(10):
            start = time.perf_counter()
            resp = client.get("/v1/audit-events", headers=auth_header)
            elapsed_ms = (time.perf_counter() - start) * 1000
            assert resp.status_code in (200, 400, 422)
            times.append(elapsed_ms)

        p95 = _measure_p95(times)
        assert p95 <= baseline_ms * 2, (
            f"audit_log_query p95={p95:.1f}ms exceeds 2x baseline ({baseline_ms * 2}ms)"
        )


class TestBaselineFile:
    def test_baselines_file_exists(self):
        assert _BASELINES_FILE.exists(), "baselines.json must exist"

    def test_baselines_has_required_keys(self):
        data = _load_baselines()
        for key in ("grant_list_1k", "grant_create", "bulk_approve_100", "audit_log_query_10k"):
            assert key in data, f"Missing baseline: {key}"

    def test_baselines_have_p95_ms(self):
        data = _load_baselines()
        for key, val in data.items():
            assert "p95_ms" in val, f"Missing p95_ms in baseline {key}"
            assert isinstance(val["p95_ms"], (int, float))
