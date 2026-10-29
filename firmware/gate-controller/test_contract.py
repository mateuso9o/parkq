"""Firmware <-> API contract test for the ParkQ Gate Controller.

Replays the exact HTTP calls src/main.cpp makes against a live ParkQ server:
  POST /api/iot/{lot}/slots           {"device_key": K, "slots": [0|1 x4]}
  GET  /api/iot/{lot}/commands?device_key=K   -> [{"id","gate","command"}, ...]
  POST /api/gate/{lot}/{in|out}/scan  {"token": T} -> 200 + {"open": bool}

Start a server first (fresh DB):
  PARKQ_RESET=1 PARKQ_DEV=1 python -m uvicorn server:app --app-dir app --host 127.0.0.1 --port 8765
Run:
  python -m unittest discover -s firmware/gate-controller -p "test_contract.py" -v
Env: PARKQ_URL (default http://127.0.0.1:8765), PARKQ_DB (default app/parkq.db).
"""
import json
import os
import re
import sqlite3
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "hardware" / "gate-controller"))
import design  # noqa: E402

BASE = os.environ.get("PARKQ_URL", "http://127.0.0.1:8765")
DB = Path(os.environ.get("PARKQ_DB", ROOT / "app" / "parkq.db"))
LOT = "LOT02"   # the seeded lot that has a device_key (LOT01, 03, 04 have none)


def call(method, path, body=None, token=None):
    req = urllib.request.Request(
        BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def server_up():
    try:
        urllib.request.urlopen(BASE + "/api/gate/%s/info" % LOT, timeout=2).read()
        return True
    except Exception:
        return False


def device_key():
    con = sqlite3.connect(DB)
    try:
        return con.execute("SELECT device_key FROM lots WHERE id=?", (LOT,)).fetchone()[0]
    finally:
        con.close()


class TestPins(unittest.TestCase):
    def test_pins_match_pcb(self):
        text = (HERE / "include" / "pins.h").read_text()
        pins = {m.group(1): int(m.group(2)) for m in re.finditer(r"^#define\s+PIN_(\w+)\s+(\d+)", text, re.M)}
        self.assertEqual(pins, design.GPIO_MAP)


@unittest.skipUnless(server_up(), "ParkQ server not reachable at %s (start it, or set PARKQ_URL)" % BASE)
class TestApiContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = device_key()
        cls.admin = call("GET", "/api/dev/login?role=admin")[1]["token"]

    def firmware_get_commands(self):
        # exactly pollCommands(): GET /api/iot/{lot}/commands?device_key=...
        return call("GET", "/api/iot/%s/commands?device_key=%s" % (LOT, self.key))

    def manual_open(self, gate="in"):
        return call("POST", "/api/staff/open", {"lot_id": LOT, "gate": gate, "reason": "contract test"}, self.admin)

    def test_slots_post_shape(self):
        # exactly sendSlots(): {"device_key": ..., "slots": [1,1,0,0]}
        st, res = call("POST", "/api/iot/%s/slots" % LOT, {"device_key": self.key, "slots": [1, 1, 0, 0]})
        self.assertEqual(st, 200)
        self.assertEqual(res["occupied"], 2)
        st, res = call("POST", "/api/iot/%s/slots" % LOT, {"device_key": self.key, "slots": [0, 0, 0, 0]})
        self.assertEqual((st, res["occupied"]), (200, 0))

    def test_slots_bad_key_rejected(self):
        st, _ = call("POST", "/api/iot/%s/slots" % LOT, {"device_key": "wrong", "slots": [0, 0, 0, 0]})
        self.assertEqual(st, 403)

    def test_commands_poll_shape(self):
        self.firmware_get_commands()          # drain anything queued by other tests
        self.assertEqual(self.manual_open("in")[0], 200)
        st, cmds = self.firmware_get_commands()
        self.assertEqual(st, 200)
        self.assertIsInstance(cmds, list)
        self.assertIn({"gate": "in", "command": "OPEN"}, [{k: c[k] for k in ("gate", "command")} for c in cmds])

    def test_commands_returned_once(self):
        # Stale-OPEN risk: the server marks commands done=1 in the same request
        # that returns them, so a queued OPEN is delivered exactly once; the next
        # poll is empty and an old OPEN can't re-open the barrier later.
        # (If the response is lost in transit the OPEN is lost too - fail closed.)
        self.firmware_get_commands()
        self.manual_open("out")
        first = self.firmware_get_commands()[1]
        second = self.firmware_get_commands()[1]
        self.assertEqual([(c["gate"], c["command"]) for c in first], [("out", "OPEN")])
        self.assertEqual(second, [])

    def test_commands_bad_key_rejected(self):
        st, _ = call("GET", "/api/iot/%s/commands?device_key=wrong" % LOT)
        self.assertEqual(st, 403)

    def test_scan_bad_token(self):
        # sendScan() treats "HTTP 200 and open:true" as allowed; anything else is the red path.
        for gate in ("in", "out"):
            st, res = call("POST", "/api/gate/%s/%s/scan" % (LOT, gate), {"token": "garbage-not-a-token"})
            self.assertFalse(st == 200 and res.get("open") is True, (gate, st, res))
            if st == 200:
                self.assertIs(res["open"], False)   # firmware reads this field


if __name__ == "__main__":
    unittest.main()
