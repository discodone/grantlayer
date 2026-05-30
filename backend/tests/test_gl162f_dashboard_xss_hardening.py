"""
GL-162F Validation: Dashboard XSS Hardening Before Snapshot Push.

Covers:
1. escapeHtml helper function is defined in dashboard/index.html
2. escapeHtml escapes all five required characters: &, <, >, ", '
3. No raw API-derived fields in HTML attribute contexts (title=, onclick=)
4. No duplicate title attributes on the same element
5. Clipboard onclick replaced with safe dataset approach (no inline ID string)
6. All table-row rendering functions apply escapeHtml to API fields
7. Evidence artifact JSON exists and is valid
8. Branch scope guard
"""

import json
import os
import pathlib
import re
import subprocess
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_DASHBOARD = _REPO_ROOT / "dashboard" / "index.html"
_ARTIFACT = _REPO_ROOT / "docs" / "examples" / "gl162f" / "dashboard_xss_hardening.json"

# API-derived field names that must be escaped before innerHTML insertion.
_GRANT_FIELDS = [
    "g.id", "g.subject_id", "g.role", "g.action", "g.resource",
    "g.signingKeyId", "g.payloadHash", "g.reason",
]
_CHALLENGE_FIELDS = [
    "c.id", "c.subject_id", "c.action", "c.resource",
]
_AUDIT_FIELDS = [
    "e.subject_id", "e.role", "e.action", "e.resource",
    "e.challenge_id", "e.challenge_result", "e.grant_signature_result", "e.reason",
]
_FLOW_FIELDS = [
    "data.tamperedField", "data.oldValue", "data.newValue",
    "data.reason", "sigResult",
]


def _dashboard_text():
    return _DASHBOARD.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. escapeHtml function defined
# ---------------------------------------------------------------------------

class TestGL162FEscapeHtmlDefined(unittest.TestCase):

    def test_escape_html_function_defined(self):
        """dashboard/index.html must define function escapeHtml."""
        self.assertIn("function escapeHtml", _dashboard_text(),
                      "dashboard/index.html must define escapeHtml()")

    def test_escape_html_escapes_ampersand(self):
        """escapeHtml must map & to &amp;."""
        self.assertIn("'&amp;'", _dashboard_text(),
                      "escapeHtml must escape & to &amp;")

    def test_escape_html_escapes_lt(self):
        """escapeHtml must map < to &lt;."""
        self.assertIn("'&lt;'", _dashboard_text(),
                      "escapeHtml must escape < to &lt;")

    def test_escape_html_escapes_gt(self):
        """escapeHtml must map > to &gt;."""
        self.assertIn("'&gt;'", _dashboard_text(),
                      "escapeHtml must escape > to &gt;")

    def test_escape_html_escapes_double_quote(self):
        """escapeHtml must map \" to &quot;."""
        self.assertIn("'&quot;'", _dashboard_text(),
                      "escapeHtml must escape \" to &quot;")

    def test_escape_html_escapes_apostrophe(self):
        """escapeHtml must map ' to &#039;."""
        self.assertIn("'&#039;'", _dashboard_text(),
                      "escapeHtml must escape ' to &#039;")


# ---------------------------------------------------------------------------
# 2. No raw API fields in HTML attribute contexts
# ---------------------------------------------------------------------------

class TestGL162FNoRawApiFieldsInAttributes(unittest.TestCase):

    def _assert_no_raw_pattern(self, pattern, msg):
        """Assert that the regex pattern does not match the dashboard source."""
        text = _dashboard_text()
        matches = re.findall(pattern, text)
        self.assertEqual(matches, [], f"{msg}\nFound: {matches}")

    def test_no_raw_field_in_title_attribute(self):
        """No API field must appear unescaped inside a title=\"...\" attribute."""
        # Matches title="${anyField}" where the field is not wrapped in escapeHtml(
        self._assert_no_raw_pattern(
            r'title="\$\{(?!escapeHtml)[a-z_\.]+[^}]*\}"',
            "Raw API field found in title= attribute context"
        )

    def test_no_raw_id_in_onclick_string(self):
        """No API-derived ID must appear raw inside an onclick='...' string literal."""
        # Matches onclick="...writeText('${anyField}')..." without escapeHtml
        self._assert_no_raw_pattern(
            r"onclick=['\"].*writeText\('\\$\{(?!escapeHtml)",
            "Raw ID found in clipboard writeText onclick handler"
        )

    def test_no_raw_id_in_revoke_onclick(self):
        """revokeGrant onclick must use escapeHtml for the ID parameter."""
        text = _dashboard_text()
        # Old pattern: onclick="revokeGrant('${g.id}')"
        self.assertNotIn("revokeGrant('${g.id}')", text,
                         "revokeGrant onclick must escape g.id with escapeHtml")
        # New pattern must be present
        self.assertIn("revokeGrant('${escapeHtml(g.id)}')", text,
                      "revokeGrant onclick must use escapeHtml(g.id)")

    def test_no_duplicate_title_attribute_on_challenge_td(self):
        """The challenge ID cell must not have two title= attributes."""
        text = _dashboard_text()
        # The old bug: title="${c.id}" ... title="Click to copy: ${c.id}"
        self.assertNotIn('title="${c.id}"', text,
                         "Duplicate/raw title=${c.id} must be removed from challenge cell")

    def test_clipboard_uses_dataset_not_inline_id(self):
        """Clipboard writeText must use this.dataset.cid, not inline '${c.id}'."""
        text = _dashboard_text()
        self.assertIn("this.dataset.cid", text,
                      "Clipboard onclick must read from data-cid dataset attribute")
        self.assertIn("data-cid=\"${escapeHtml(c.id)}\"", text,
                      "Challenge ID cell must store ID in data-cid with escapeHtml")


# ---------------------------------------------------------------------------
# 3. Required escapeHtml calls in each rendering function
# ---------------------------------------------------------------------------

class TestGL162FEscapeHtmlAppliedToAllFields(unittest.TestCase):

    def _assert_escaped(self, field, label=None):
        text = _dashboard_text()
        pattern = f"escapeHtml({field}"
        self.assertIn(pattern, text,
                      f"{label or field} must be wrapped in escapeHtml()")

    # --- updateTamperSelect ---

    def test_tamper_select_escapes_grant_id(self):
        self._assert_escaped("g.id", "updateTamperSelect: g.id")

    def test_tamper_select_escapes_subject_id(self):
        self._assert_escaped("g.subject_id", "updateTamperSelect: g.subject_id")

    def test_tamper_select_escapes_role(self):
        self._assert_escaped("g.role", "updateTamperSelect: g.role")

    def test_tamper_select_escapes_action(self):
        self._assert_escaped("g.action", "updateTamperSelect: g.action")

    # --- compare-flow-log (addFlowEntry callers) ---

    def test_flow_log_escapes_tampered_field(self):
        self._assert_escaped("data.tamperedField", "flow-log: data.tamperedField")

    def test_flow_log_escapes_old_value(self):
        self._assert_escaped("data.oldValue", "flow-log: data.oldValue")

    def test_flow_log_escapes_new_value(self):
        self._assert_escaped("data.newValue", "flow-log: data.newValue")

    def test_flow_log_escapes_sig_result(self):
        self._assert_escaped("sigResult", "flow-log: sigResult")

    def test_flow_log_escapes_data_reason(self):
        self._assert_escaped("data.reason", "flow-log: data.reason")

    # --- loadGrants ---

    def test_load_grants_escapes_resource(self):
        self._assert_escaped("g.resource", "loadGrants: g.resource")

    def test_load_grants_escapes_signing_key_id(self):
        self._assert_escaped("g.signingKeyId", "loadGrants: g.signingKeyId")

    def test_load_grants_escapes_payload_hash(self):
        self._assert_escaped("g.payloadHash", "loadGrants: g.payloadHash")

    def test_load_grants_escapes_reason(self):
        self._assert_escaped("g.reason", "loadGrants: g.reason")

    # --- loadChallenges ---

    def test_load_challenges_escapes_subject_id(self):
        self._assert_escaped("c.subject_id", "loadChallenges: c.subject_id")

    def test_load_challenges_escapes_action(self):
        self._assert_escaped("c.action", "loadChallenges: c.action")

    def test_load_challenges_escapes_resource(self):
        self._assert_escaped("c.resource", "loadChallenges: c.resource")

    # --- loadAudit ---

    def test_load_audit_escapes_subject_id(self):
        self._assert_escaped("e.subject_id", "loadAudit: e.subject_id")

    def test_load_audit_escapes_role(self):
        self._assert_escaped("e.role", "loadAudit: e.role")

    def test_load_audit_escapes_action(self):
        self._assert_escaped("e.action", "loadAudit: e.action")

    def test_load_audit_escapes_resource(self):
        self._assert_escaped("e.resource", "loadAudit: e.resource")

    def test_load_audit_escapes_challenge_id(self):
        self._assert_escaped("e.challenge_id", "loadAudit: e.challenge_id")

    def test_load_audit_escapes_challenge_result(self):
        self._assert_escaped("e.challenge_result", "loadAudit: e.challenge_result")

    def test_load_audit_escapes_grant_signature_result(self):
        self._assert_escaped("e.grant_signature_result", "loadAudit: e.grant_signature_result")

    def test_load_audit_escapes_reason(self):
        self._assert_escaped("e.reason", "loadAudit: e.reason")


# ---------------------------------------------------------------------------
# 4. No new internal secrets or paths introduced
# ---------------------------------------------------------------------------

class TestGL162FNoNewSecretsOrPaths(unittest.TestCase):

    def test_no_internal_hostname_in_dashboard(self):
        text = _dashboard_text()
        self.assertNotIn("forge.hofercloud.eu", text,
                         "Internal Forgejo hostname must not appear in dashboard")
        self.assertNotIn("hofercloud.eu", text,
                         "Internal domain must not appear in dashboard")

    def test_no_internal_path_in_dashboard(self):
        text = _dashboard_text()
        self.assertNotIn("/home/adminuser", text,
                         "Internal filesystem path must not appear in dashboard")

    def test_no_private_key_markers_in_dashboard(self):
        text = _dashboard_text()
        self.assertNotIn("BEGIN RSA PRIVATE KEY", text)
        self.assertNotIn("BEGIN OPENSSH PRIVATE KEY", text)

    def test_no_backend_dependency_added(self):
        """dashboard/index.html must not add import/require statements."""
        text = _dashboard_text()
        self.assertNotIn("import ", text.split("<script>", 1)[-1].split("</script>")[0]
                         if "<script>" in text else text,
                         "No ES module imports in dashboard script")


# ---------------------------------------------------------------------------
# 5. Evidence artifact
# ---------------------------------------------------------------------------

class TestGL162FArtifact(unittest.TestCase):

    def test_artifact_file_exists(self):
        self.assertTrue(_ARTIFACT.exists(),
                        f"Evidence artifact must exist: {_ARTIFACT}")

    def test_artifact_is_valid_json(self):
        with open(_ARTIFACT, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)

    def test_artifact_issue_id(self):
        with open(_ARTIFACT, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data.get("issue_id"), "GL-162F")

    def test_artifact_escape_html_added(self):
        with open(_ARTIFACT, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIs(data.get("escape_html_helper_added"), True)

    def test_artifact_no_backend_changes(self):
        with open(_ARTIFACT, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIs(data.get("backend_src_changed"), False)

    def test_artifact_no_production_claims(self):
        with open(_ARTIFACT, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIs(data.get("production_saas_ready_claimed"), False)
        self.assertIs(data.get("tenant_isolation_claimed_implemented"), False)

    def test_artifact_no_github_push(self):
        with open(_ARTIFACT, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIs(data.get("pushed_to_github"), False)


# ---------------------------------------------------------------------------
# 6. Branch scope guard
# ---------------------------------------------------------------------------

class TestGL162FBranchScopeGuard(unittest.TestCase):

    _ALLOWED_CHANGED = frozenset({
        "dashboard/index.html",
        "backend/tests/test_gl162f_dashboard_xss_hardening.py",
        "docs/examples/gl162f/dashboard_xss_hardening.json",
    })

    def _get_current_branch(self):
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(_REPO_ROOT), capture_output=True, text=True,
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def _get_diff_files(self):
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "main...HEAD"],
                cwd=str(_REPO_ROOT), capture_output=True, text=True,
            )
            return [f.strip() for f in result.stdout.splitlines() if f.strip()]
        except Exception:
            return []

    def test_scope_guard_on_gl162f_branch(self):
        branch = self._get_current_branch()
        if "162f" not in branch.lower():
            self.skipTest(f"Scope guard only runs on GL-162F branch; current: {branch}")
        changed = self._get_diff_files()
        unexpected = [f for f in changed if f not in self._ALLOWED_CHANGED]
        self.assertEqual(unexpected, [],
                         f"Unexpected files changed on GL-162F branch: {unexpected}\n"
                         f"Allowed: {sorted(self._ALLOWED_CHANGED)}")

    def test_no_backend_src_changed(self):
        branch = self._get_current_branch()
        if "162f" not in branch.lower():
            self.skipTest(f"Scope guard only runs on GL-162F branch; current: {branch}")
        changed = self._get_diff_files()
        backend_src = [f for f in changed if f.startswith("backend/src/")]
        self.assertEqual(backend_src, [],
                         f"backend/src/ must not be modified on GL-162F: {backend_src}")


if __name__ == "__main__":
    unittest.main()
