# Set GRANTLAYER_RUNTIME_MODE=test before any backend.src.core.config import
# so the startup gate is skipped and production-mode defaults don't break tests.
# Individual tests that need a specific mode override this in setUp/tearDown.
import os as _os
_os.environ.setdefault("GRANTLAYER_RUNTIME_MODE", "test")

"""
Pytest configuration for GrantLayer backend tests.

Auto-marks doc-guard and scope-guard tests so the suites can be run
independently:

  pytest -m "not doc_guard and not scope_guard"
  pytest                       # all tests (~9 400 tests, includes doc-guards)

Doc-guard tests verify that documentation artifacts (Markdown files, JSON
evidence bundles, scope-guard invariants) exist and contain the expected
content. They are correct and useful but do NOT exercise application code,
so they should not be counted when assessing functional test coverage.

The canonical module list lives in _doc_guard_modules.py so it can be
imported by both this conftest and the standalone runner script.
"""

try:
    import pytest

    from ._doc_guard_modules import DOC_GUARD_MODULES

    def _is_scope_guard_item(item) -> bool:
        item_name = item.name.lower()
        class_name = item.cls.__name__.lower() if item.cls is not None else ""
        return (
            "scopeguard" in class_name
            or "scope_guard" in class_name
            or "forbiddenchange" in class_name
            or "forbidden_change" in class_name
            or "noforbidden" in class_name
            or "no_forbidden" in class_name
            or "scopeguard" in item_name
            or "scope_guard" in item_name
            or "branch_scope_guard" in item_name
            or "changed_files" in item_name
            or "forbidden_files" in item_name
            or "forbidden_paths" in item_name
            or "forbidden_changes" in item_name
            or "no_backend_src" in item_name
            or "no_openapi" in item_name
            or "no_migration" in item_name
            or "no_dependency" in item_name
            or "no_github_workflow" in item_name
            or "no_frontend" in item_name
            or "no_production_deployment_config" in item_name
            or item_name in {
                "test_no_production_code_changed",
                "test_no_backend_src_changes",
            }
        )

    def pytest_collection_modifyitems(items: list) -> None:
        doc_guard_mark = pytest.mark.doc_guard
        scope_guard_mark = pytest.mark.scope_guard
        for item in items:
            module_name = item.module.__name__.split(".")[-1]
            if module_name in DOC_GUARD_MODULES:
                item.add_marker(doc_guard_mark)
            if _is_scope_guard_item(item):
                item.add_marker(scope_guard_mark)

except ImportError:
    pass  # pytest not installed; conftest is a no-op in that environment
