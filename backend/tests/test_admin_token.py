import os
import unittest

from backend.src.auth.auth import check_admin_token, admin_token_is_configured


class TestDemoAdminToken(unittest.TestCase):
    def setUp(self):
        self.old_token = os.environ.get("GRANTLAYER_ADMIN_TOKEN")
        self.old_require = os.environ.get("GRANTLAYER_REQUIRE_ADMIN_TOKEN")

    def tearDown(self):
        if self.old_token is None:
            os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        else:
            os.environ["GRANTLAYER_ADMIN_TOKEN"] = self.old_token

        if self.old_require is None:
            os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        else:
            os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = self.old_require

    def test_no_env_token_allows_legacy_demo_mode(self):
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        ok, status, payload = check_admin_token(None)
        self.assertTrue(ok)
        self.assertEqual(status, 200)
        self.assertEqual(payload, {})

    def test_missing_token_is_401_when_env_set(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "demo-token"
        os.environ.pop("GRANTLAYER_REQUIRE_ADMIN_TOKEN", None)
        ok, status, payload = check_admin_token(None)
        self.assertFalse(ok)
        self.assertEqual(status, 401)
        self.assertEqual(payload["error"], "admin_token_required")
        self.assertEqual(payload["errorCode"], "admin_token_required")
        self.assertEqual(payload["reason"], "Admin token is required for this endpoint.")

    def test_wrong_token_is_403_when_env_set(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "demo-token"
        ok, status, payload = check_admin_token("Bearer wrong-token")
        self.assertFalse(ok)
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "admin_token_invalid")
        self.assertEqual(payload["errorCode"], "admin_token_invalid")
        self.assertEqual(payload["reason"], "The provided admin token is invalid.")

    def test_correct_token_is_allowed(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "demo-token"
        ok, status, payload = check_admin_token("Bearer demo-token")
        self.assertTrue(ok)
        self.assertEqual(status, 200)
        self.assertEqual(payload, {})

    def test_token_value_is_not_returned(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "super-secret-demo-token"
        ok, status, payload = check_admin_token("Bearer wrong-token")
        self.assertFalse(ok)
        self.assertNotIn("super-secret-demo-token", str(payload))

    def test_admin_token_is_configured(self):
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "demo-token"
        self.assertTrue(admin_token_is_configured())
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        self.assertFalse(admin_token_is_configured())

    # New tests for REQUIRE_ADMIN_TOKEN
    def test_require_admin_true_without_token_fails(self):
        """When REQUIRE_ADMIN_TOKEN is true and no token configured, fail closed."""
        os.environ.pop("GRANTLAYER_ADMIN_TOKEN", None)
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        ok, status, payload = check_admin_token(None)
        self.assertFalse(ok)
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "admin_token_required")
        self.assertEqual(payload["errorCode"], "admin_token_required")
        self.assertEqual(payload["reason"], "Admin token is required for this endpoint.")

    def test_require_admin_true_with_valid_token_allows(self):
        """When REQUIRE_ADMIN_TOKEN is true and valid token, allow."""
        os.environ["GRANTLAYER_ADMIN_TOKEN"] = "prod-token"
        os.environ["GRANTLAYER_REQUIRE_ADMIN_TOKEN"] = "true"
        ok, status, payload = check_admin_token("Bearer prod-token")
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
