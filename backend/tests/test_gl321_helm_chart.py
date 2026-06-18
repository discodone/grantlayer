"""GL-321 — Helm Chart and Kubernetes Manifests.

Covers:
- Chart.yaml exists and has required fields
- values.yaml exists and has required keys
- All 7 required templates exist
- deploy/k8s/ raw manifests exist
- deploy/README.md exists and has k3s quickstart
- Makefile has helm-lint target
- values.yaml has no subchart dependencies (production-focused)
"""

from __future__ import annotations

import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_HELM_DIR = _REPO_ROOT / "deploy" / "helm" / "grantlayer"
_K8S_DIR = _REPO_ROOT / "deploy" / "k8s"
_TEMPLATES_DIR = _HELM_DIR / "templates"


class TestChartYaml(unittest.TestCase):
    def setUp(self):
        self.chart_path = _HELM_DIR / "Chart.yaml"

    def test_chart_yaml_exists(self):
        self.assertTrue(self.chart_path.exists())

    def test_chart_yaml_has_name(self):
        content = self.chart_path.read_text()
        self.assertIn("name: grantlayer", content)

    def test_chart_yaml_has_version(self):
        content = self.chart_path.read_text()
        self.assertIn("version:", content)

    def test_chart_yaml_has_app_version(self):
        content = self.chart_path.read_text()
        self.assertIn("appVersion:", content)

    def test_chart_yaml_api_version_v2(self):
        content = self.chart_path.read_text()
        self.assertIn("apiVersion: v2", content)


class TestValuesYaml(unittest.TestCase):
    def setUp(self):
        self.values_path = _HELM_DIR / "values.yaml"
        self.content = self.values_path.read_text()

    def test_values_yaml_exists(self):
        self.assertTrue(self.values_path.exists())

    def test_values_has_replica_count(self):
        self.assertIn("replicaCount", self.content)

    def test_values_has_image(self):
        self.assertIn("image:", self.content)

    def test_values_has_service(self):
        self.assertIn("service:", self.content)

    def test_values_has_ingress(self):
        self.assertIn("ingress:", self.content)

    def test_values_has_autoscaling(self):
        self.assertIn("autoscaling:", self.content)

    def test_values_has_pdb(self):
        self.assertIn("pdb:", self.content)

    def test_values_has_postgresql_external(self):
        self.assertIn("postgresql:", self.content)
        self.assertIn("secretName:", self.content)

    def test_values_has_redis_external(self):
        self.assertIn("redis:", self.content)

    def test_values_no_subchart_dependencies(self):
        # Should NOT have bitnami/postgresql or similar subchart references
        self.assertNotIn("bitnami", self.content)
        self.assertNotIn("redis:", self.content.split("redis:")[1] if "redis:" in self.content else "")


class TestHelmTemplates(unittest.TestCase):
    def test_templates_dir_exists(self):
        self.assertTrue(_TEMPLATES_DIR.exists())

    def test_deployment_api_exists(self):
        self.assertTrue((_TEMPLATES_DIR / "deployment-api.yaml").exists())

    def test_deployment_worker_exists(self):
        self.assertTrue((_TEMPLATES_DIR / "deployment-worker.yaml").exists())

    def test_service_exists(self):
        self.assertTrue((_TEMPLATES_DIR / "service.yaml").exists())

    def test_ingress_exists(self):
        self.assertTrue((_TEMPLATES_DIR / "ingress.yaml").exists())

    def test_configmap_exists(self):
        self.assertTrue((_TEMPLATES_DIR / "configmap.yaml").exists())

    def test_hpa_exists(self):
        self.assertTrue((_TEMPLATES_DIR / "hpa.yaml").exists())

    def test_pdb_exists(self):
        self.assertTrue((_TEMPLATES_DIR / "pdb.yaml").exists())

    def test_helpers_tpl_exists(self):
        self.assertTrue((_TEMPLATES_DIR / "_helpers.tpl").exists())


class TestK8sManifests(unittest.TestCase):
    def test_k8s_dir_exists(self):
        self.assertTrue(_K8S_DIR.exists())

    def test_k8s_deployment_exists(self):
        self.assertTrue((_K8S_DIR / "deployment.yaml").exists())

    def test_k8s_namespace_exists(self):
        self.assertTrue((_K8S_DIR / "namespace.yaml").exists())

    def test_k8s_secret_exists(self):
        self.assertTrue((_K8S_DIR / "secret.yaml").exists())


class TestDeployReadme(unittest.TestCase):
    def setUp(self):
        self.readme_path = _REPO_ROOT / "deploy" / "README.md"

    def test_readme_exists(self):
        self.assertTrue(self.readme_path.exists())

    def test_readme_has_k3s_quickstart(self):
        content = self.readme_path.read_text()
        self.assertIn("k3s", content)

    def test_readme_has_helm_install(self):
        content = self.readme_path.read_text()
        self.assertIn("helm install", content)


class TestMakefileHelmLint(unittest.TestCase):
    def test_makefile_has_helm_lint_target(self):
        makefile = (_REPO_ROOT / "Makefile").read_text()
        self.assertIn("helm-lint", makefile)
        self.assertIn("helm lint", makefile)
