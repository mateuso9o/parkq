"""Integration tests: drive the running ParkQ server through its REST API (system-level Test Cases in W9).

Run the server first (PARKQ_DEV=1), then:  python -m unittest test_api_flow -v
"""
import json
import os
import threading
import unittest
import urllib.error
import urllib.request

BASE = os.environ.get("PARKQ_URL", "http://127.0.0.1:8000")


def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def login(role):
    return call("GET", f"/api/dev/login?role={role}")[1]["token"]


def new_driver(phone):
    """Register a fresh driver through the real OTP flow and return (token, vehicle_id)."""
    _, otp = call("POST", "/api/auth/otp", {"phone": phone, "accept": True})
    _, v = call("POST", "/api/auth/verify", {"phone": phone, "code": otp["dev_code"]})
    tok = v["token"]
    if v["is_new"]:
        call("POST", "/api/auth/register", {"name": "ทดสอบ ระบบ", "plate": "ทส " + phone[-4:], "province": "กรุงเทพมหานคร"}, tok)
    return tok, call("GET", "/api/vehicles", token=tok)[1][0]["id"]


def book_and_pay(tok, vid, lot="LOT01", hours=2):
    _, t = call("POST", "/api/bookings", {"lot_id": lot, "mode": "now", "hours": hours, "vehicle_id": vid}, tok)
    _, p = call("POST", "/api/payments", {"ticket_id": t["id"], "method": "promptpay"}, tok)
    call("POST", f"/api/payments/{p['id']}/simulate")
    return call("GET", f"/api/tickets/{t['id']}", token=tok)[1]


class TestAuth(unittest.TestCase):
    def test_IT01_otp_validation(self):
        # TC-ACC-02 / TC-ACC-03
        self.assertEqual(call("POST", "/api/auth/otp", {"phone": "089123456", "accept": True})[1]["code"], "INVALID_PHONE")
        self.assertEqual(call("POST", "/api/auth/otp", {"phone": "0891112222", "accept": False})[1]["code"], "TERMS_REQUIRED")

    def test_IT02_wrong_otp_three_times(self):
        # TC-ACC-06
        call("POST", "/api/auth/otp", {"phone": "0897770001", "accept": True})
        codes = [call("POST", "/api/auth/verify", {"phone": "0897770001", "code": "000000"})[1]["code"] for _ in range(3)]
        self.assertEqual(codes, ["OTP_WRONG", "OTP_WRONG", "OTP_LOCKED"])

    def test_IT03_register_new_user(self):
        # TC-ACC-05
        tok, vid = new_driver("0897770002")
        self.assertTrue(vid)
        self.assertEqual(call("GET", "/api/me", token=tok)[1]["phone"], "0897770002")

    def test_IT04_duplicate_plate(self):
        # TC-ACC-09
        tok, _ = new_driver("0897770003")
        code = call("POST", "/api/vehicles", {"plate": "ทส 0003", "province": "กรุงเทพมหานคร"}, tok)[1]["code"]
        self.assertEqual(code, "DUPLICATE_PLATE")


class TestBookingAndGate(unittest.TestCase):
    def test_IT05_full_journey(self):
        # TC-BKG-01, TC-TKT-02, TC-TKT-03, TC-TKT-08
        tok, vid = new_driver("0897770004")
        before = call("GET", "/api/lots/LOT01")[1]["free"]
        t = book_and_pay(tok, vid)
        self.assertEqual((t["status"], t["amount"]), ("WAITING", 40))
        self.assertEqual(call("GET", "/api/lots/LOT01")[1]["free"], before - 1)          # BR-03 holds the slot
        r_in = call("POST", "/api/gate/LOT01/in/scan", {"token": t["token"]})[1]
        self.assertTrue(r_in["open"])
        again = call("POST", "/api/gate/LOT01/in/scan", {"token": t["token"]})[1]
        self.assertEqual(again["result"], "ALREADY_USED")
        r_out = call("POST", "/api/gate/LOT01/out/scan", {"token": t["token"]})[1]
        self.assertEqual((r_out["result"], r_out["open"]), ("OK", True))
        self.assertEqual(call("GET", f"/api/tickets/{t['id']}", token=tok)[1]["status"], "DONE")

    def test_IT06_wrong_lot_and_forged(self):
        # TC-TKT-04, TC-TKT-06
        tok, vid = new_driver("0897770005")
        t = book_and_pay(tok, vid)
        self.assertEqual(call("POST", "/api/gate/LOT03/in/scan", {"token": t["token"]})[1]["result"], "WRONG_LOT")
        forged = t["token"].replace("LOT01", "LOT03")
        self.assertEqual(call("POST", "/api/gate/LOT03/in/scan", {"token": forged})[1]["result"], "INVALID_QR")

    def test_IT07_booking_rules(self):
        # TC-BKG-02, TC-BKG-04, TC-LOT-01 (full lot)
        tok, vid = new_driver("0897770006")
        too_long = call("POST", "/api/bookings", {"lot_id": "LOT01", "mode": "now", "hours": 25, "vehicle_id": vid}, tok)[1]
        self.assertEqual(too_long["code"], "INVALID_DURATION")
        import time
        far = call("POST", "/api/bookings", {"lot_id": "LOT01", "mode": "advance", "hours": 2, "vehicle_id": vid,
                                             "start_at": int(time.time()) + 8 * 86400}, tok)[1]
        self.assertEqual(far["code"], "TOO_FAR_AHEAD")
        full = call("POST", "/api/bookings", {"lot_id": "LOT04", "mode": "now", "hours": 1, "vehicle_id": vid}, tok)
        self.assertIn(full[1]["code"], ("LOT_FULL", "LOT_CLOSED"))

    def test_IT08_last_slot_not_sold_twice(self):
        # TC-BKG-05 / DEF-03: many drivers race for the last free slots of the 4-slot IoT lot
        admin = login("admin")
        dash = call("GET", "/api/admin/dashboard?lot_id=LOT02", token=admin)[1]
        free = dash["lot"]["free"]
        call("POST", "/api/iot/LOT02/slots", {"device_key": "dev-key-LOT02", "slots": [s["occupied"] for s in dash["slots"]]})
        drivers = [new_driver(f"08977701{i:02d}") for i in range(free + 3)]
        results = []
        def go(tok, vid):
            results.append(call("POST", "/api/bookings", {"lot_id": "LOT02", "mode": "now", "hours": 1, "vehicle_id": vid}, tok)[0])
        threads = [threading.Thread(target=go, args=d) for d in drivers]
        [th.start() for th in threads]
        [th.join() for th in threads]
        self.assertEqual(results.count(200), free)
        self.assertEqual(results.count(409), len(drivers) - free)       # losers get "lot full", never a server error
        self.assertEqual(call("GET", "/api/lots/LOT02")[1]["free"], 0)

    def test_IT09_cancel_refund(self):
        # TC-BKG-08
        import time
        tok, vid = new_driver("0897770007")
        _, t = call("POST", "/api/bookings", {"lot_id": "LOT01", "mode": "advance", "hours": 3, "vehicle_id": vid,
                                              "start_at": int(time.time()) + 3 * 3600}, tok)
        _, p = call("POST", "/api/payments", {"ticket_id": t["id"], "method": "card", "card_number": "4242 4242 4242 4242"}, tok)
        self.assertEqual(p["status"], "PAID")
        self.assertEqual(call("POST", f"/api/tickets/{t['id']}/cancel", {"reason": "เปลี่ยนแผน"}, tok)[1]["refund"], 60)

    def test_IT10_card_declined(self):
        # TC-BKG-07
        tok, vid = new_driver("0897770008")
        _, t = call("POST", "/api/bookings", {"lot_id": "LOT01", "mode": "now", "hours": 1, "vehicle_id": vid}, tok)
        res = call("POST", "/api/payments", {"ticket_id": t["id"], "method": "card", "card_number": "4000 0000 0000 0002"}, tok)
        self.assertEqual((res[0], res[1]["code"]), (402, "CARD_DECLINED"))


class TestBackOffice(unittest.TestCase):
    def test_IT11_staff_open_gate_logged(self):
        # TC-TKT-10
        staff = login("attendant")
        tok, vid = new_driver("0897770009")
        t = book_and_pay(tok, vid)
        found = call("GET", "/api/staff/search?q=" + urllib.parse.quote(t["id"]), token=staff)[1]
        self.assertEqual(found[0]["id"], t["id"])
        no_reason = call("POST", "/api/staff/open", {"lot_id": "LOT01", "gate": "in", "reason": "", "ticket_id": t["id"]}, staff)[1]
        self.assertEqual(no_reason["code"], "REASON_REQUIRED")
        call("POST", "/api/staff/open", {"lot_id": "LOT01", "gate": "in", "reason": "QR สแกนไม่ได้", "ticket_id": t["id"]}, staff)
        logs = call("GET", "/api/admin/dashboard?lot_id=LOT01", token=login("admin"))[1]["logs"]
        self.assertEqual((logs[0]["method"], logs[0]["reason"]), ("staff", "QR สแกนไม่ได้"))

    def test_IT12_admin_rules(self):
        # TC-ADM-01, TC-ADM-03, role check
        admin = login("admin")
        for phone in ("0897770010", "0897770011"):        # two active tickets in LOT01
            book_and_pay(*new_driver(phone))
        lot = call("GET", "/api/lots/LOT01")[1]
        res = call("PUT", "/api/admin/lots/LOT01", {"name": lot["name"], "address": lot["address"], "lat": lot["lat"], "lng": lot["lng"],
                                                     "capacity": 1, "open_time": lot["open_time"], "close_time": lot["close_time"]}, admin)[1]
        self.assertEqual(res["code"], "CAPACITY_BELOW_BOOKINGS")
        rep = call("GET", "/api/admin/report?lot_id=LOT01&date_from=2026-10-01&date_to=2026-10-31", token=admin)[1]
        self.assertEqual(rep["total"], sum(d["revenue"] for d in rep["days"]))
        self.assertEqual(call("GET", "/api/admin/lots", token=login("driver"))[0], 403)


import urllib.parse  # noqa: E402  (used by TestBackOffice)

if __name__ == "__main__":
    unittest.main(verbosity=2)
