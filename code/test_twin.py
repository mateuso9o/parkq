"""Digital twin: slot history + public twin endpoint. Own throw-away database."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["PARKQ_DB"] = str(Path(_tmp) / "twin.db")
os.environ["PARKQ_DEV"] = "1"
os.environ["DATABASE_URL"] = ""   # never touch a real Postgres: db.init(reset=True) drops the whole schema
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from fastapi.testclient import TestClient  # noqa: E402

import db  # noqa: E402
import server  # noqa: E402

db.init(reset=True)
KEY = "dev-key-LOT02"


def post_slots(client, slots):
    return client.post("/api/iot/LOT02/slots", json={"device_key": KEY, "slots": slots})


def rows(sql, *args):
    conn = db.connect()
    try:
        return [dict(r) for r in conn.execute(sql, args)]
    finally:
        conn.close()


class TestSlotHistory(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server.app)
        conn = db.connect()
        conn.execute("DELETE FROM slot_history")
        conn.execute("UPDATE slots SET occupied=0 WHERE lot_id='LOT02'")
        conn.commit()
        conn.close()

    def test_IT30_slot_change_recorded(self):
        self.assertEqual(post_slots(self.client, [1, 0, 0, 0]).status_code, 200)
        h = rows("SELECT slot_no, occupied FROM slot_history WHERE lot_id='LOT02'")
        self.assertEqual(h, [{"slot_no": 1, "occupied": 1}])

    def test_IT31_unchanged_not_recorded(self):
        post_slots(self.client, [1, 0, 0, 0])
        post_slots(self.client, [1, 0, 0, 0])
        self.assertEqual(len(rows("SELECT id FROM slot_history WHERE lot_id='LOT02'")), 1)

    def test_IT32_history_failure_does_not_break_iot(self):
        orig = server.record_slot

        def boom(*a, **k):
            raise RuntimeError("history down")
        server.record_slot = boom
        try:
            self.assertEqual(post_slots(self.client, [0, 1, 0, 0]).status_code, 200)
        finally:
            server.record_slot = orig


if __name__ == "__main__":
    unittest.main()
