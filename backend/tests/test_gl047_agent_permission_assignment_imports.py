"""GL-047 regression test: agent_permission_assignments import compatibility.

Verifies that backend/src/agent_permission_assignments.py can be imported
via the package (relative imports) without requiring absolute 'src.*' paths.
"""

import unittest


class TestGL047AgentPermissionAssignmentImports(unittest.TestCase):
    """Regression test for GL-047 — package import compatibility."""

    def test_import_via_package_succeeds(self) -> None:
        """Importing agent_permission_assignments from the package must work."""
        try:
            from backend.src.policy import agent_permission_assignments  # type: ignore[import]
        except ImportError as exc:
            self.fail(f"Package import of agent_permission_assignments failed: {exc}")

    def test_resolve_function_is_callable(self) -> None:
        """The resolve_agent_permission_assignment function must be importable and callable."""
        from backend.src.policy.agent_permission_assignments import (  # type: ignore[import]
            resolve_agent_permission_assignment,
        )
        self.assertTrue(callable(resolve_agent_permission_assignment))

    def test_no_absolute_src_imports_in_module(self) -> None:
        """The module must not contain absolute 'from src.' imports."""
        import inspect
        import backend.src.policy.agent_permission_assignments as module  # type: ignore[import]

        source = inspect.getsource(module)
        self.assertNotIn(
            "from src.agent_permissions",
            source,
            "Absolute import 'from src.agent_permissions' still present; use relative imports",
        )
        self.assertNotIn(
            "from src.agent_permission_profiles",
            source,
            "Absolute import 'from src.agent_permission_profiles' still present; use relative imports",
        )

    def test_basic_resolution_works_after_import(self) -> None:
        """A simple resolution call must succeed after package import."""
        from backend.src.policy.agent_permission_assignments import (  # type: ignore[import]
            resolve_agent_permission_assignment,
        )

        result = resolve_agent_permission_assignment(
            agent_id="agent-123",
            requested_scope="evidence:read",
            assigned_scopes=["evidence:read"],
            assigned_profiles=[],
            resource_type="evidence",
            resource_id="ev-456",
        )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["matchedScope"], "evidence:read")
        self.assertEqual(result["reason"], "scope_matched")


if __name__ == "__main__":
    unittest.main()
