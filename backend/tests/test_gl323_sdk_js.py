"""GL-323 — TypeScript/JavaScript SDK.

Covers:
- sdk-js/ directory exists
- package.json has correct name (grantlayer-sdk)
- tsconfig.json strict mode enabled
- src/client.ts exists with GrantLayerClient class
- src/index.ts exports GrantLayerClient
- src/types.ts defines key interfaces
- tests/client.test.ts exists
- README.md with quickstart
- package.json has Jest test script
- Retry logic implementation present (exponential backoff, 429 handling)
- All major endpoints covered in client
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

_SDK_DIR = Path(__file__).parent.parent.parent / "sdk-js"


class TestSdkStructure(unittest.TestCase):
    def test_sdk_dir_exists(self):
        self.assertTrue(_SDK_DIR.exists())

    def test_package_json_exists(self):
        self.assertTrue((_SDK_DIR / "package.json").exists())

    def test_package_name_is_grantlayer_sdk(self):
        pkg = json.loads((_SDK_DIR / "package.json").read_text())
        self.assertEqual(pkg["name"], "grantlayer-sdk")

    def test_package_has_test_script(self):
        pkg = json.loads((_SDK_DIR / "package.json").read_text())
        self.assertIn("test", pkg.get("scripts", {}))

    def test_package_engines_node_18_plus(self):
        pkg = json.loads((_SDK_DIR / "package.json").read_text())
        engines = pkg.get("engines", {})
        self.assertIn("node", engines)
        self.assertIn("18", engines["node"])

    def test_tsconfig_exists(self):
        self.assertTrue((_SDK_DIR / "tsconfig.json").exists())

    def test_tsconfig_strict_mode(self):
        tsconfig = json.loads((_SDK_DIR / "tsconfig.json").read_text())
        self.assertTrue(tsconfig.get("compilerOptions", {}).get("strict"))

    def test_src_dir_exists(self):
        self.assertTrue((_SDK_DIR / "src").exists())

    def test_client_ts_exists(self):
        self.assertTrue((_SDK_DIR / "src" / "client.ts").exists())

    def test_index_ts_exists(self):
        self.assertTrue((_SDK_DIR / "src" / "index.ts").exists())

    def test_types_ts_exists(self):
        self.assertTrue((_SDK_DIR / "src" / "types.ts").exists())

    def test_readme_exists(self):
        self.assertTrue((_SDK_DIR / "README.md").exists())

    def test_readme_has_quickstart(self):
        readme = (_SDK_DIR / "README.md").read_text()
        self.assertIn("GrantLayerClient", readme)
        self.assertIn("npm install", readme)

    def test_tests_dir_exists(self):
        self.assertTrue((_SDK_DIR / "tests").exists())

    def test_jest_test_exists(self):
        self.assertTrue((_SDK_DIR / "tests" / "client.test.ts").exists())


class TestClientImplementation(unittest.TestCase):
    def setUp(self):
        self.client_src = (_SDK_DIR / "src" / "client.ts").read_text()

    def test_grant_layer_client_class(self):
        self.assertIn("class GrantLayerClient", self.client_src)

    def test_list_grants_method(self):
        self.assertIn("listGrants", self.client_src)

    def test_create_grant_method(self):
        self.assertIn("createGrant", self.client_src)

    def test_list_audit_events_method(self):
        self.assertIn("listAuditEvents", self.client_src)

    def test_api_keys_methods(self):
        self.assertIn("createApiKey", self.client_src)
        self.assertIn("revokeApiKey", self.client_src)

    def test_webhook_methods(self):
        self.assertIn("listWebhooks", self.client_src)
        self.assertIn("createWebhook", self.client_src)

    def test_gdpr_methods(self):
        self.assertIn("exportUserData", self.client_src)
        self.assertIn("eraseUserData", self.client_src)

    def test_retry_logic_present(self):
        self.assertIn("maxRetries", self.client_src)
        self.assertIn("retryDelayMs", self.client_src)
        self.assertIn("429", self.client_src)
        self.assertIn("Retry-After", self.client_src)

    def test_fetch_based_no_axios(self):
        self.assertIn("fetch(", self.client_src)
        self.assertNotIn("axios", self.client_src)

    def test_workspace_plan_method(self):
        self.assertIn("updateWorkspacePlan", self.client_src)

    def test_export_audit_log_method(self):
        self.assertIn("exportAuditLog", self.client_src)


class TestTypesDefinitions(unittest.TestCase):
    def setUp(self):
        self.types_src = (_SDK_DIR / "src" / "types.ts").read_text()

    def test_grant_layer_client_options(self):
        self.assertIn("GrantLayerClientOptions", self.types_src)

    def test_grant_interface(self):
        self.assertIn("interface Grant", self.types_src)

    def test_api_key_interface(self):
        self.assertIn("interface ApiKey", self.types_src)

    def test_workspace_interface(self):
        self.assertIn("interface Workspace", self.types_src)

    def test_gl_live_key_format_in_create_response(self):
        self.assertIn("CreateApiKeyResponse", self.types_src)
        self.assertIn("key:", self.types_src)


class TestIndexExports(unittest.TestCase):
    def setUp(self):
        self.index_src = (_SDK_DIR / "src" / "index.ts").read_text()

    def test_exports_grant_layer_client(self):
        self.assertIn("GrantLayerClient", self.index_src)

    def test_exports_from_client(self):
        self.assertIn("from './client", self.index_src)

    def test_exports_types(self):
        self.assertIn("from './types", self.index_src)
