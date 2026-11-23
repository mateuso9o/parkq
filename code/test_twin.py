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


def sql(stmt, *args):
    conn = db.connect()
    try:
        conn.execute(stmt, args)
        conn.commit() if hasattr(conn, "commit") else None
    finally:
        conn.close()


class TestTwinEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server.app)
        for t in ("slot_history", "gate_commands", "gate_logs"):
            sql(f"DELETE FROM {t}")
        sql("UPDATE slots SET occupied=0 WHERE lot_id='LOT02'")
        sql("UPDATE lots SET last_seen=? WHERE id='LOT02'", server.now())
        self.t = server.now()

    def test_IT33_endpoint_shape_and_order(self):
        post_slots(self.client, [1, 0, 0, 0])
        sql("INSERT INTO gate_commands(lot_id,gate,command,created_at) VALUES ('LOT02','in','OPEN',?)", self.t + 1)
        sql("INSERT INTO gate_logs(lot_id,gate,ticket_id,plate,result,method,at) VALUES ('LOT02','in','TK-1','1กข 1234','OK','qr',?)", self.t + 2)
        r = self.client.get("/api/twin/LOT02")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["lot"]["id"], "LOT02")
        self.assertEqual(len(d["slots"]), 4)
        self.assertEqual(d["free"], 3)
        kinds = [e["kind"] for e in d["events"]]
        self.assertEqual(kinds, ["slot", "gate_open", "car_in"])
        ats = [e["at"] for e in d["events"]]
        self.assertEqual(ats, sorted(ats))
        self.assertEqual(d["events"][1]["gate"], "in")

    def test_IT34_events_within_window_only(self):
        sql("INSERT INTO slot_history(lot_id,slot_no,occupied,at) VALUES ('LOT02',2,1,?)", self.t - 5000)
        sql("INSERT INTO slot_history(lot_id,slot_no,occupied,at) VALUES ('LOT02',3,1,?)", self.t - 10)
        d = self.client.get("/api/twin/LOT02?window=600").json()
        self.assertEqual([e["slot_no"] for e in d["events"]], [3])

    def test_IT35_no_personal_fields(self):
        sql("INSERT INTO gate_logs(lot_id,gate,ticket_id,plate,result,method,at) VALUES ('LOT02','out','TK-9','9ฮฮ 9999','OK','qr',?)", self.t)
        text = self.client.get("/api/twin/LOT02").text
        for bad in ("plate", "ticket", "email", "TK-9", "9ฮฮ"):
            self.assertNotIn(bad, text)

    def test_IT36_unknown_lot_404(self):
        self.assertEqual(self.client.get("/api/twin/NOPE").status_code, 404)

    def test_IT37_window_clamped(self):
        d = self.client.get("/api/twin/LOT02?window=99999").json()
        self.assertEqual(d["window"], 1800)
        self.assertEqual(self.client.get("/api/twin/LOT02?window=abc").status_code, 422)

    def test_IT38_lot_without_board_online_false(self):
        d = self.client.get("/api/twin/LOT01").json()
        self.assertFalse(d["lot"]["online"])


if __name__ == "__main__":
    unittest.main()
