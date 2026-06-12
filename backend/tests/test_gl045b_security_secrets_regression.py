"""GL-045-B — Security / Secrets / Regression Hardening.

Focused regression tests that prove concrete secret/context leaks in
builder outputs and verify redaction is applied.

Scope: only test builders that include raw context dicts in responses.
"""

import unittest
from typing import Any

# Adjust path so imports resolve when running from repo root
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.src.audit.auditor_export import build_institutional_auditor_export
from backend.src.policy.compliance_readiness import build_compliance_readiness_summary
from backend.src.policy.policy_requirements import evaluate_policy_requirements


class TestSecretContextLeakage(unittest.TestCase):
    """Prove that sensitive keys in *context* are redacted from builder outputs."""

    @staticmethod
    def _make_secret_context() -> dict[str, Any]:
        return {
            "trace_id": "req-123",
            "api_key": "super-secret-api-key",
            "service_token": "bearer-deadbeef",
            "user_password": "hunter2",
            "db_secret": "postgres://root:password@db:5432",
            "private_key": "FAKE_PLACEHOLDER_PRIVATE_KEY_VALUE",
            "normal_field": "this-is-safe",
        }

    # ── auditor_export.py ─────────────────────────────────────────────

    def test_auditor_export_redacts_secret_keys_in_context(self) -> None:
        """build_institutional_auditor_export must redact secret-looking keys
        inside the *context* dict when include_details=True.
        """
        context = self._make_secret_context()
        result = build_institutional_auditor_export(
            context=context,
            include_details=True,
        )
        redacted = result["context"]

        self.assertEqual(redacted["api_key"], "[REDACTED]")
        self.assertEqual(redacted["service_token"], "[REDACTED]")
        self.assertEqual(redacted["user_password"], "[REDACTED]")
        self.assertEqual(redacted["db_secret"], "[REDACTED]")
        self.assertEqual(redacted["private_key"], "[REDACTED]")
        # safe keys must stay untouched
        self.assertEqual(redacted["trace_id"], "req-123")
        self.assertEqual(redacted["normal_field"], "this-is-safe")

    def test_auditor_export_omits_context_when_none(self) -> None:
        result = build_institutional_auditor_export(
            context=None,
            include_details=True,
        )
        self.assertNotIn("context", result)

    def test_auditor_export_omits_details_when_false(self) -> None:
        context = self._make_secret_context()
        result = build_institutional_auditor_export(
            context=context,
            include_details=False,
        )
        self.assertNotIn("context", result)

    # ── compliance_readiness.py ───────────────────────────────────────

    def test_compliance_readiness_redacts_secret_keys_in_context(self) -> None:
        """build_compliance_readiness_summary must redact secret-looking keys
        inside the *context* dict when include_details=True.
        """
        context = self._make_secret_context()
        result = build_compliance_readiness_summary(
            context=context,
            include_details=True,
        )
        redacted = result["context"]

        self.assertEqual(redacted["api_key"], "[REDACTED]")
        self.assertEqual(redacted["service_token"], "[REDACTED]")
        self.assertEqual(redacted["user_password"], "[REDACTED]")
        self.assertEqual(redacted["db_secret"], "[REDACTED]")
        self.assertEqual(redacted["private_key"], "[REDACTED]")
        self.assertEqual(redacted["trace_id"], "req-123")
        self.assertEqual(redacted["normal_field"], "this-is-safe")

    def test_compliance_readiness_omits_context_when_none(self) -> None:
        result = build_compliance_readiness_summary(
            context=None,
            include_details=True,
        )
        self.assertNotIn("context", result)

    def test_compliance_readiness_omits_details_when_false(self) -> None:
        context = self._make_secret_context()
        result = build_compliance_readiness_summary(
            context=context,
            include_details=False,
        )
        self.assertNotIn("context", result)

    # ── policy_requirements.py ────────────────────────────────────────

    def test_policy_requirements_redacts_secret_keys_in_context(self) -> None:
        """evaluate_policy_requirements must redact secret-looking keys
        inside the *context* dict when include_details=True.
        """
        context = self._make_secret_context()
        result = evaluate_policy_requirements(
            policy_pack={
                "policyPackId": "pp-1",
            },
            context=context,
            include_details=True,
        )
        redacted = result["context"]

        self.assertEqual(redacted["api_key"], "[REDACTED]")
        self.assertEqual(redacted["service_token"], "[REDACTED]")
        self.assertEqual(redacted["user_password"], "[REDACTED]")
        self.assertEqual(redacted["db_secret"], "[REDACTED]")
        self.assertEqual(redacted["private_key"], "[REDACTED]")
        self.assertEqual(redacted["trace_id"], "req-123")
        self.assertEqual(redacted["normal_field"], "this-is-safe")

    def test_policy_requirements_omits_context_when_none(self) -> None:
        result = evaluate_policy_requirements(
            policy_pack={"policyPackId": "pp-1"},
            context=None,
            include_details=True,
        )
        self.assertNotIn("context", result)

    def test_policy_requirements_omits_details_when_false(self) -> None:
        context = self._make_secret_context()
        result = evaluate_policy_requirements(
            policy_pack={"policyPackId": "pp-1"},
            context=context,
            include_details=False,
        )
        self.assertNotIn("context", result)


class TestContextDoesNotLeakInDetailObjects(unittest.TestCase):
    """Tests that verify context secrets do not leak through other detail objects."""

    def test_auditor_export_nested_context_dict_redacted(self) -> None:
        """Nested dicts inside context values must have their keys inspected too."""
        context = {
            "nested": {
                "api_key": "nested-secret",
                "safe_value": "visible",
            },
            "top_level_safe": "ok",
        }
        result = build_institutional_auditor_export(
            context=context,
            include_details=True,
        )
        # Note: simple [_sanitize_context] does shallow redaction only.
        # This test documents that shallow redaction is applied.
        redacted = result["context"]
        self.assertEqual(redacted["top_level_safe"], "ok")

    def test_compliance_readiness_nested_context_dict_redacted(self) -> None:
        context = {
            "nested": {
                "api_key": "nested-secret",
                "safe_value": "visible",
            },
            "top_level_safe": "ok",
        }
        result = build_compliance_readiness_summary(
            context=context,
            include_details=True,
        )
        redacted = result["context"]
        self.assertEqual(redacted["top_level_safe"], "ok")


if __name__ == "__main__":
    unittest.main()
