"""Tests for GL-081 PostgreSQL migration runner dict-row access.

Ensures that migration applied-version reading is compatible with SQLite
rows, tuple rows, and PostgreSQL/dict-like rows, and that existing behavior
is preserved.
"""

import os
import sqlite3
import sys
import unittest
from typing import Any
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.migrations.runner import (
    _applied_versions,
    _ensure_migrations_table,
    _version_from_row,
    get_applied_versions,
)


class FakeDictCursorRow:
    """Simulate a psycopg2 DictCursor row that supports both index and key access."""

    def __init__(self, values, keys):
        self._values = values
        self._keys = keys

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._values[self._keys.index(key)]


class FakeMappingRow:
    """Simulate a key-access-only row that is not a dict instance."""

    def __init__(self, data):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]


class TestVersionFromRow(unittest.TestCase):
    """Test _version_from_row with various row types."""

    def test_tuple_row(self):
        self.assertEqual(_version_from_row(("0001_gl032_baseline",)), "0001_gl032_baseline")

    def test_list_row(self):
        self.assertEqual(_version_from_row(["0001_gl032_baseline"]), "0001_gl032_baseline")

    def test_dict_row(self):
        self.assertEqual(_version_from_row({"version": "0001_gl032_baseline"}), "0001_gl032_baseline")

    def test_sqlite3_row(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE t (version TEXT)")
        conn.execute("INSERT INTO t VALUES ('0001_gl032_baseline')")
        row = conn.execute("SELECT version FROM t").fetchone()
        self.assertEqual(_version_from_row(row), "0001_gl032_baseline")

    def test_dict_cursor_row(self):
        row = FakeDictCursorRow(["0001_gl032_baseline"], ["version"])
        self.assertEqual(_version_from_row(row), "0001_gl032_baseline")

    def test_mapping_row(self):
        row = FakeMappingRow({"version": "0001_gl032_baseline"})
        self.assertEqual(_version_from_row(row), "0001_gl032_baseline")

    def test_malformed_row_raises(self):
        class BadRow:
            pass

        with self.assertRaises(ValueError):
            _version_from_row(BadRow())

    def test_malformed_tuple_row_raises(self):
        with self.assertRaises(ValueError):
            _version_from_row(())

    def test_malformed_dict_row_raises(self):
        with self.assertRaises(ValueError):
            _version_from_row({"other_key": "0001_gl032_baseline"})


class TestAppliedVersionsWithFakeRows(unittest.TestCase):
    """Test _applied_versions row extraction with mocked connections."""

    def test_multiple_versions_order_preserved(self):
        class FakeCursor:
            def __init__(self, rows):
                self._rows = rows

            def fetchall(self):
                return self._rows

        class FakeConn:
            def __init__(self, rows):
                self._rows = rows
                self._table_created = True

            def execute(self, *args, **kwargs):
                return FakeCursor(self._rows)

        def fake_table_exists(conn, name):
            return conn._table_created

        rows = [
            {"version": "0001_gl032_baseline"},
            {"version": "0002_gl036_evidence_persistence"},
            {"version": "0003_gl036_r2_evidence_verification"},
        ]
        conn = FakeConn(rows)

        with mock.patch(
            "src.migrations.runner._table_exists", side_effect=fake_table_exists
        ):
            versions = _applied_versions(conn)

        self.assertEqual(
            versions,
            [
                "0001_gl032_baseline",
                "0002_gl036_evidence_persistence",
                "0003_gl036_r2_evidence_verification",
            ],
        )

    def test_malformed_row_does_not_silently_return_empty(self):
        class FakeCursor:
            def fetchall(self):
                return [object()]  # malformed row

        class FakeConn:
            _table_created = True

            def execute(self, *args, **kwargs):
                return FakeCursor()

        with mock.patch("src.migrations.runner._table_exists", return_value=True):
            with self.assertRaises(ValueError):
                _applied_versions(FakeConn())


class TestAppliedVersionsSQLiteIntegration(unittest.TestCase):
    """Test _applied_versions with real SQLite connections."""

    def test_missing_table_returns_empty(self):
        conn = sqlite3.connect(":memory:")
        self.assertEqual(_applied_versions(conn), [])

    def test_empty_table_returns_empty(self):
        conn = sqlite3.connect(":memory:")
        _ensure_migrations_table(conn)
        self.assertEqual(_applied_versions(conn), [])

    def test_populated_table_returns_versions(self):
        conn = sqlite3.connect(":memory:")
        _ensure_migrations_table(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            ("0001_gl032_baseline", "2024-01-01T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            ("0002_gl036_evidence_persistence", "2024-01-02T00:00:00Z"),
        )
        conn.commit()
        self.assertEqual(
            _applied_versions(conn),
            ["0001_gl032_baseline", "0002_gl036_evidence_persistence"],
        )

    def test_sqlite_row_factory_compatibility(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        _ensure_migrations_table(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            ("0001_gl032_baseline", "2024-01-01T00:00:00Z"),
        )
        conn.commit()
        self.assertEqual(_applied_versions(conn), ["0001_gl032_baseline"])

    def test_get_applied_versions_integration(self):
        conn = sqlite3.connect(":memory:")
        self.assertEqual(get_applied_versions(conn), [])
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            ("0001_gl032_baseline", "2024-01-01T00:00:00Z"),
        )
        conn.commit()
        self.assertEqual(get_applied_versions(conn), ["0001_gl032_baseline"])


if __name__ == "__main__":
    unittest.main()
