"""Unit tests for the SQLite -> PostgreSQL translation in db.py (pure functions, no database needed)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
import db  # noqa: E402


class TestTranslation(unittest.TestCase):
    def test_UT40_placeholders(self):
        self.assertEqual(db.to_pg("SELECT * FROM t WHERE a=? AND b=?"), "SELECT * FROM t WHERE a=%s AND b=%s")

    def test_UT41_insert_or_ignore(self):
        out = db.to_pg("INSERT OR IGNORE INTO vehicles(a,b) VALUES (?,?)")
        self.assertEqual(out, "INSERT INTO vehicles(a,b) VALUES (%s,%s) ON CONFLICT DO NOTHING")

    def test_UT42_literal_percent_is_escaped(self):
        self.assertEqual(db.to_pg("SELECT 1 WHERE x LIKE '5%' AND y=?"), "SELECT 1 WHERE x LIKE '5%%' AND y=%s")

    def test_UT43_schema_types(self):
        out = db.pg_schema(db.SCHEMA)
        self.assertIn("id SERIAL PRIMARY KEY", out)
        self.assertNotIn("INTEGER PRIMARY KEY", out)
        self.assertIn("lat DOUBLE PRECISION", out)
        self.assertIn("created_at BIGINT", out)

    def test_UT44_row_access_by_name_and_index(self):
        row = db.Row({"id": 7, "name": "x"})
        self.assertEqual((row["id"], row[0], row[1], dict(row)), (7, 7, "x", {"id": 7, "name": "x"}))


if __name__ == "__main__":
    unittest.main()
