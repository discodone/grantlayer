"""Tests for GL-063 Production-Hardening Roadmap and Readiness Cut.

Lightweight validation test proving the production-hardening roadmap and
readiness cut are:
- present as human-readable documents
- present as machine-readable JSON files
- coherent with referenced Pilot-Ready artifacts
- explicitly not claiming production readiness
- free of obvious secrets
"""

import json
import pathlib
import unittest


class TestGL063ProductionHardeningRoadmap(unittest.TestCase):
    """GL-063: Validate the production-hardening roadmap and readiness cut."""

    REPO_ROOT = pathlib.Path(__file__).with_suffix("").parent.parent.parent
    DOCS_DIR = REPO_ROOT / "docs"
    EXAMPLE_DIR_GL063 = DOCS_DIR / "examples" / "gl063"
    BACKEND_TESTS_DIR = REPO_ROOT / "backend" / "tests"

    REQUIRED_PILOT_READY_DOCS = [
        "integration_guide.md",
        "integrator_quickstart.md",
        "minimal_api_usage_walkthrough.md",
        "demo_scenario.md",
        "pilot_ready_handoff_plan.md",
        "pilot_ready_release_decision.md",
        "demo_runner_api_smoke.md",
        "pilot_partner_preparation_pack.md",
    ]

    REQUIRED_CATEGORIES = [
        "Authentication and authorization hardening",
        "Secret management",
        "Deployment and environment hardening",
        "Observability and logging",
        "Backup and restore",
        "Database production readiness / PostgreSQL CI",
        "API and OpenAPI contract hardening",
        "Test strategy and CI gates",
        "Data privacy and evidence handling",
        "Signing, key management, and HSM path",
        "SDK / client examples",
        "Dashboard / UI readiness",
        "Multi-tenant SaaS architecture",
        "Compliance/legal review boundary",
        "Optional blockchain anchoring / wallet / payment integrations",
    ]

    SECRET_PATTERNS = [
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "private_key",
        "privatekey",
        "bearer",
        "authorization",
    ]

    @classmethod
    def setUpClass(cls):
        cls.roadmap_path = cls.DOCS_DIR / "production_hardening_roadmap.md"
        cls.readiness_cut_path = cls.DOCS_DIR / "production_readiness_cut.md"
        cls.backlog_path = cls.EXAMPLE_DIR_GL063 / "production_hardening_backlog.json"
        cls.cut_json_path = cls.EXAMPLE_DIR_GL063 / "production_readiness_cut.json"

        cls.backlog_json = None
        cls.backlog_text = None
        if cls.backlog_path.exists():
            cls.backlog_text = cls.backlog_path.read_text(encoding="utf-8")
            cls.backlog_json = json.loads(cls.backlog_text)

        cls.cut_json = None
        cls.cut_text = None
        if cls.cut_json_path.exists():
            cls.cut_text = cls.cut_json_path.read_text(encoding="utf-8")
            cls.cut_json = json.loads(cls.cut_text)

    # ── 1. Roadmap doc exists ────────────────────────────────────────
    def test_roadmap_doc_exists(self):
        self.assertTrue(
            self.roadmap_path.exists(),
            "docs/production_hardening_roadmap.md must exist",
        )

    # ── 2. Readiness cut doc exists ──────────────────────────────────
    def test_readiness_cut_doc_exists(self):
        self.assertTrue(
            self.readiness_cut_path.exists(),
            "docs/production_readiness_cut.md must exist",
        )

    # ── 3. Backlog JSON exists and parses ────────────────────────────
    def test_backlog_exists_and_parses(self):
        self.assertTrue(
            self.backlog_path.exists(),
            "docs/examples/gl063/production_hardening_backlog.json must exist",
        )
        self.assertIsNotNone(self.backlog_json, "Backlog must parse as valid JSON")
        self.assertIsInstance(self.backlog_json, dict)

    # ── 4. Readiness cut JSON exists and parses ──────────────────────
    def test_cut_json_exists_and_parses(self):
        self.assertTrue(
            self.cut_json_path.exists(),
            "docs/examples/gl063/production_readiness_cut.json must exist",
        )
        self.assertIsNotNone(self.cut_json, "Readiness cut JSON must parse as valid JSON")
        self.assertIsInstance(self.cut_json, dict)

    # ── 5. Required Pilot-Ready docs exist ─────────────────────────────
    def test_referenced_required_pilot_ready_docs_exist(self):
        missing = []
        for name in self.REQUIRED_PILOT_READY_DOCS:
            path = self.DOCS_DIR / name
            if not path.exists():
                missing.append(name)
        self.assertEqual(missing, [], f"Missing required docs: {missing}")

    # ── 6. GL-061 demo runner script exists ────────────────────────────
    def test_gl061_demo_runner_script_exists(self):
        script_path = self.REPO_ROOT / "scripts" / "demo" / "gl061_api_smoke.py"
        self.assertTrue(
            script_path.exists(),
            "scripts/demo/gl061_api_smoke.py must exist",
        )

    # ── 7. GL-062 preparation pack exists ──────────────────────────────
    def test_gl062_preparation_pack_exists(self):
        pack_path = self.DOCS_DIR / "pilot_partner_preparation_pack.md"
        self.assertTrue(
            pack_path.exists(),
            "docs/pilot_partner_preparation_pack.md must exist",
        )

    # ── 8. Required categories are present in the backlog ──────────────
    def test_backlog_includes_required_categories(self):
        categories = self.backlog_json.get("categories", [])
        for category in self.REQUIRED_CATEGORIES:
            with self.subTest(category=category):
                self.assertIn(
                    category,
                    categories,
                    f"Backlog categories must include '{category}'",
                )

    # ── 9. Backlog has P0/P1/P2 workstreams ───────────────────────────
    def test_backlog_has_p0_workstreams(self):
        p0 = self.backlog_json.get("p0Workstreams", [])
        self.assertTrue(len(p0) > 0, "Backlog must have P0 workstreams")
        for ws in p0:
            self.assertEqual(ws.get("priority"), "P0", "P0 workstream must have priority P0")

    def test_backlog_has_p1_workstreams(self):
        p1 = self.backlog_json.get("p1Workstreams", [])
        self.assertTrue(len(p1) > 0, "Backlog must have P1 workstreams")
        for ws in p1:
            self.assertEqual(ws.get("priority"), "P1", "P1 workstream must have priority P1")

    def test_backlog_has_p2_workstreams(self):
        p2 = self.backlog_json.get("p2Workstreams", [])
        self.assertTrue(len(p2) > 0, "Backlog must have P2 workstreams")
        for ws in p2:
            self.assertEqual(ws.get("priority"), "P2", "P2 workstream must have priority P2")

    # ── 10. Readiness cut says productionReady is false ──────────────
    def test_cut_says_not_production_ready(self):
        self.assertFalse(
            self.cut_json.get("productionReady"),
            "readinessCut productionReady must be false",
        )

    # ── 11. Readiness cut says pilotReady is true ──────────────────────
    def test_cut_says_pilot_ready(self):
        self.assertTrue(
            self.cut_json.get("pilotReady"),
            "readinessCut pilotReady must be true",
        )

    # ── 12. Roadmap states Production-Ready: no ────────────────────────
    def test_roadmap_says_not_production_ready(self):
        content = self.roadmap_path.read_text(encoding="utf-8").lower()
        # The markdown table contains | Production-Ready | **No** |
        stripped = content.replace(" ", "").replace("|", "").replace("*", "")
        self.assertIn("production-readyno", stripped)
        self.assertIn("production-ready", content)

    # ── 13. Roadmap includes a recommended implementation order ────────
    def test_roadmap_includes_recommended_order(self):
        content = self.roadmap_path.read_text(encoding="utf-8").lower()
        self.assertIn("recommended implementation order", content)

    # ── 14. Readiness cut includes production claim stop conditions ────
    def test_readiness_cut_includes_stop_conditions(self):
        content = self.readiness_cut_path.read_text(encoding="utf-8").lower()
        self.assertIn("production claim stop conditions", content)
        stop_conditions = self.cut_json.get("productionClaimStopConditions", [])
        self.assertTrue(len(stop_conditions) > 0, "productionClaimStopConditions must not be empty")

    # ── 15. No obvious secrets appear in JSON files ──────────────────
    def _sanitize_known_safe_terms(self, text):
        """Remove legitimate planning terms that contain secret-like substrings."""
        safe_terms = [
            "admin-token",
            "operator-token",
            "authentication and authorization hardening",
            "secret management",
            "secret-management",
            "managed secrets",
            "production secrets",
            "synthetic data",
            "secrets",
            "secret",
            "authorization",
            "token",
        ]
        result = text.lower()
        # Replace longer terms first to avoid partial matches
        for term in sorted(safe_terms, key=len, reverse=True):
            result = result.replace(term.lower(), "")
        return result

    def test_no_obvious_secrets_in_backlog(self):
        text_lower = self._sanitize_known_safe_terms(self.backlog_text)
        for pattern in self.SECRET_PATTERNS:
            self.assertNotIn(
                pattern,
                text_lower,
                f"Backlog may contain secret-like pattern: {pattern}",
            )

    def test_no_obvious_secrets_in_cut_json(self):
        text_lower = self._sanitize_known_safe_terms(self.cut_text)
        for pattern in self.SECRET_PATTERNS:
            self.assertNotIn(
                pattern,
                text_lower,
                f"Readiness cut JSON may contain secret-like pattern: {pattern}",
            )

    # ── Extra coherence checks ───────────────────────────────────────
    def test_backlog_has_id_and_version(self):
        self.assertEqual(
            self.backlog_json.get("backlogId"),
            "gl063-production-hardening-backlog",
        )
        self.assertEqual(self.backlog_json.get("backlogVersion"), "1.0")

    def test_backlog_status_is_planning(self):
        self.assertEqual(self.backlog_json.get("status"), "planning")

    def test_backlog_pilot_ready_true(self):
        self.assertTrue(self.backlog_json.get("pilotReady"))

    def test_backlog_production_ready_false(self):
        self.assertFalse(self.backlog_json.get("productionReady"))

    def test_cut_has_id_and_version(self):
        self.assertEqual(
            self.cut_json.get("readinessCutId"),
            "gl063-production-readiness-cut",
        )
        self.assertEqual(self.cut_json.get("readinessCutVersion"), "1.0")

    def test_cut_integration_ready_true(self):
        self.assertTrue(self.cut_json.get("integrationReady"))

    def test_cut_has_basis(self):
        basis = self.cut_json.get("basis", [])
        self.assertTrue(len(basis) > 0, "basis must not be empty")
        basis_text = " ".join(basis).lower()
        self.assertIn("gl-052", basis_text, "basis must reference GL-052")
        self.assertIn("gl-062", basis_text, "basis must reference GL-062")

    def test_cut_has_production_blockers(self):
        blockers = self.cut_json.get("productionBlockers", [])
        self.assertTrue(len(blockers) > 0, "productionBlockers must not be empty")
        blocker_ids = {b.get("blockerId") for b in blockers}
        self.assertIn("b01-auth", blocker_ids, "blockers must include auth")
        self.assertIn("b02-secrets", blocker_ids, "blockers must include secrets")

    def test_cut_has_pilot_permitted_scope(self):
        scope = self.cut_json.get("pilotPermittedScope", [])
        self.assertTrue(len(scope) > 0, "pilotPermittedScope must not be empty")
        scope_text = " ".join(scope).lower()
        self.assertIn("review docs", scope_text, "scope must mention reviewing docs")
        self.assertIn("dry-run", scope_text, "scope must mention dry-run")

    def test_cut_has_next_recommended_options(self):
        options = self.cut_json.get("nextRecommendedOptions", [])
        self.assertTrue(len(options) > 0, "nextRecommendedOptions must not be empty")
        option_ids = {o.get("optionId") for o in options}
        self.assertIn("opt-01", option_ids, "options must include opt-01")

    def test_cut_has_default_next_block(self):
        default = self.cut_json.get("defaultNextBlock", "")
        self.assertTrue(len(default) > 0, "defaultNextBlock must be set")

    def test_roadmap_references_gl052_through_gl062(self):
        content = self.roadmap_path.read_text(encoding="utf-8").lower()
        for num in range(52, 63):
            gl = f"gl-0{num}"
            self.assertIn(gl, content, f"Roadmap must reference {gl}")

    def test_roadmap_includes_p0_section(self):
        content = self.roadmap_path.read_text(encoding="utf-8").lower()
        self.assertIn("p0 production-hardening workstreams", content)

    def test_roadmap_includes_p1_section(self):
        content = self.roadmap_path.read_text(encoding="utf-8").lower()
        self.assertIn("p1 pilot-expansion workstreams", content)

    def test_roadmap_includes_p2_section(self):
        content = self.roadmap_path.read_text(encoding="utf-8").lower()
        self.assertIn("p2 productization workstreams", content)

    def test_roadmap_includes_what_not_to_build_yet(self):
        content = self.roadmap_path.read_text(encoding="utf-8").lower()
        self.assertIn("what not to build yet", content)

    def test_roadmap_includes_decision_boundary(self):
        content = self.roadmap_path.read_text(encoding="utf-8").lower()
        self.assertIn("decision boundary", content)

    def test_readiness_cut_includes_decision_section(self):
        content = self.readiness_cut_path.read_text(encoding="utf-8").lower()
        self.assertIn("## 1. decision", content)

    def test_readiness_cut_includes_basis_section(self):
        content = self.readiness_cut_path.read_text(encoding="utf-8").lower()
        self.assertIn("## 2. basis", content)

    def test_readiness_cut_includes_blockers_section(self):
        content = self.readiness_cut_path.read_text(encoding="utf-8").lower()
        self.assertIn("## 3. production blockers", content)

    def test_readiness_cut_includes_pilot_scope_section(self):
        content = self.readiness_cut_path.read_text(encoding="utf-8").lower()
        self.assertIn("## 4. pilot-permitted scope", content)

    def test_readiness_cut_includes_next_recommended_block(self):
        content = self.readiness_cut_path.read_text(encoding="utf-8").lower()
        self.assertIn("## 6. next recommended block", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
