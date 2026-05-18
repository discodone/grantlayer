"""Regression tests for GL-049 server and OpenAPI minor cleanup."""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestGL049Cleanup(unittest.TestCase):
    """Verify GL-049 cleanup: no duplicate imports, all error dicts use _gl030_error, no duplicate OpenAPI."""

    def test_no_duplicate_compliance_readiness_import(self):
        """Verify the duplicate import of build_compliance_readiness_summary is removed."""
        import_path = "from .compliance_readiness import build_compliance_readiness_summary"
        with open(os.path.join(os.path.dirname(__file__), '..', 'src', 'server.py')) as f:
            content = f.read()
        
        count = content.count(import_path)
        self.assertEqual(count, 1, f"Found {count} occurrences of '{import_path}', expected 1")

    def test_all_404_errors_use_gl030_error(self):
        """Verify all 404 error responses use _gl030_error() instead of inline dicts."""
        with open(os.path.join(os.path.dirname(__file__), '..', 'src', 'server.py')) as f:
            content = f.read()
        
        # Count inline dict patterns
        inline_patterns = [
            '{"error": "Grant execution not found", "errorCode": "grant_execution_not_found",',
            '{"error": "Execution not found", "errorCode": "execution_not_found",',
            '"reason": "The requested grant execution does not exist."}',
            '"reason": "The requested execution does not exist."}',
        ]
        
        for pattern in inline_patterns:
            self.assertEqual(content.count(pattern), 0,
                           f"Found inline error dict pattern: {pattern[:50]}...")

    def test_duplicate_gl032_fields_removed(self):
        """Verify duplicate GL-032 readiness fields are removed from OpenAPI."""
        with open(os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'openapi.yaml')) as f:
            content = f.read()
        
        # Count duplicates of GL-032 readiness fields block
        duplicate_block = '''                  # GL-032 readiness fields
                  dbConnected: { type: boolean, description: "True if SELECT 1 succeeds against SQLite." }
                  dbSizeBytes: { type: integer, nullable: true, description: "Size of the DB file in bytes; null for in-memory DB." }
                  journalMode: { type: string, nullable: true, description: "SQLite PRAGMA journal_mode result (e.g. wal)." }
                  dbPathKind: { type: string, enum: [file, memory], description: "Whether the DB is file-backed or in-memory." }'''
        
        occurrences = content.count(duplicate_block)
        self.assertEqual(occurrences, 0, f"Found {occurrences} occurrences of duplicate GL-032 block, expected 0 (duplicates cleaned up)")


if __name__ == '__main__':
    unittest.main()