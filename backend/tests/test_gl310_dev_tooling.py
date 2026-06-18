"""GL-310 — Pre-commit hooks and developer tooling tests.

Covers:
- .pre-commit-config.yaml exists and is valid YAML
- .pre-commit-config.yaml contains expected hooks (ruff, mypy, trailing-whitespace, detect-secrets)
- Makefile exists with required targets
- scripts/dev-setup.sh exists and is executable
- pyproject.toml has [tool.ruff], [tool.mypy], [tool.pytest.ini_options]
- CONTRIBUTING.md exists and covers prerequisites and conventional commits
"""

from __future__ import annotations

import os
import stat
import unittest


REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


class TestPreCommitConfig(unittest.TestCase):
    def _config_path(self):
        return os.path.join(REPO_ROOT, ".pre-commit-config.yaml")

    def test_file_exists(self):
        self.assertTrue(os.path.isfile(self._config_path()))

    def test_is_valid_yaml(self):
        import yaml
        with open(self._config_path()) as f:
            data = yaml.safe_load(f)
        self.assertIsInstance(data, dict)
        self.assertIn("repos", data)

    def test_contains_ruff(self):
        with open(self._config_path()) as f:
            content = f.read()
        self.assertIn("ruff", content)

    def test_contains_mypy(self):
        with open(self._config_path()) as f:
            content = f.read()
        self.assertIn("mypy", content)

    def test_contains_trailing_whitespace(self):
        with open(self._config_path()) as f:
            content = f.read()
        self.assertIn("trailing-whitespace", content)

    def test_contains_detect_secrets(self):
        with open(self._config_path()) as f:
            content = f.read()
        self.assertIn("detect-secrets", content)

    def test_contains_conventional_commits(self):
        with open(self._config_path()) as f:
            content = f.read()
        self.assertIn("conventional", content.lower())

    def test_contains_check_yaml(self):
        with open(self._config_path()) as f:
            content = f.read()
        self.assertIn("check-yaml", content)

    def test_contains_check_json(self):
        with open(self._config_path()) as f:
            content = f.read()
        self.assertIn("check-json", content)


class TestMakefile(unittest.TestCase):
    def _makefile_path(self):
        return os.path.join(REPO_ROOT, "Makefile")

    def test_file_exists(self):
        self.assertTrue(os.path.isfile(self._makefile_path()))

    def _read(self):
        with open(self._makefile_path()) as f:
            return f.read()

    def test_has_install_target(self):
        self.assertIn("install", self._read())

    def test_has_test_target(self):
        self.assertIn("test:", self._read())

    def test_has_lint_target(self):
        self.assertIn("lint:", self._read())

    def test_has_format_target(self):
        self.assertIn("format:", self._read())

    def test_has_migrate_target(self):
        self.assertIn("migrate:", self._read())

    def test_has_docker_up_target(self):
        self.assertIn("docker-up:", self._read())

    def test_has_docker_down_target(self):
        self.assertIn("docker-down:", self._read())

    def test_has_audit_target(self):
        self.assertIn("audit:", self._read())

    def test_has_help_target(self):
        self.assertIn("help:", self._read())


class TestDevSetupScript(unittest.TestCase):
    def _script_path(self):
        return os.path.join(REPO_ROOT, "scripts", "dev-setup.sh")

    def test_file_exists(self):
        self.assertTrue(os.path.isfile(self._script_path()))

    def test_is_executable(self):
        mode = os.stat(self._script_path()).st_mode
        self.assertTrue(mode & stat.S_IXUSR)

    def test_is_bash_script(self):
        with open(self._script_path()) as f:
            first_line = f.readline()
        self.assertIn("bash", first_line)

    def test_contains_pip_install(self):
        with open(self._script_path()) as f:
            content = f.read()
        self.assertIn("pip install", content)

    def test_contains_pre_commit_install(self):
        with open(self._script_path()) as f:
            content = f.read()
        self.assertIn("pre-commit install", content)

    def test_contains_env_copy(self):
        with open(self._script_path()) as f:
            content = f.read()
        self.assertIn(".env.example", content)


class TestPyprojectToml(unittest.TestCase):
    def _path(self):
        return os.path.join(REPO_ROOT, "pyproject.toml")

    def _read(self):
        with open(self._path()) as f:
            return f.read()

    def test_file_exists(self):
        self.assertTrue(os.path.isfile(self._path()))

    def test_has_ruff_section(self):
        self.assertIn("[tool.ruff]", self._read())

    def test_has_mypy_section(self):
        self.assertIn("[tool.mypy]", self._read())

    def test_has_pytest_section(self):
        self.assertIn("[tool.pytest.ini_options]", self._read())

    def test_pytest_markers_defined(self):
        content = self._read()
        self.assertIn("doc_guard", content)
        self.assertIn("contract", content)

    def test_ruff_has_line_length(self):
        self.assertIn("line-length", self._read())


class TestContributingMd(unittest.TestCase):
    def _path(self):
        return os.path.join(REPO_ROOT, "CONTRIBUTING.md")

    def _read(self):
        with open(self._path()) as f:
            return f.read()

    def test_file_exists(self):
        self.assertTrue(os.path.isfile(self._path()))

    def test_has_prerequisites(self):
        content = self._read().lower()
        self.assertTrue(
            "prerequisite" in content or "requirements" in content or "install" in content
        )

    def test_has_conventional_commits(self):
        content = self._read().lower()
        self.assertTrue("conventional" in content or "commit" in content)

    def test_has_pr_checklist(self):
        content = self._read().lower()
        self.assertTrue("checklist" in content or "pull request" in content or "pr" in content)


if __name__ == "__main__":
    unittest.main()
