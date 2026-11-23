"""Server wiring of the e-mail OTP (SMTP replaced by a recorder). Uses its own throw-away database."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["PARKQ_DB"] = str(Path(_tmp) / "otp_delivery.db")
os.environ["PARKQ_DEV"] = "0"
os.environ["DATABASE_URL"] = ""   # tests use their own SQLite file; never a real Postgres
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from fastapi.testclient import TestClient  # noqa: E402

import db  # noqa: E402
import mailer  # noqa: E402
import server  # noqa: E402

db.init(reset=True)
CFG = {"host": "smtp.example.com", "port": 587, "user": "u", "password": "p", "sender": "ParkQ <no-reply@example.com>"}


class TestOtpDelivery(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server.app)
        self.sent = []
        self._orig = (server.MAIL, mailer.send_otp)
        server.MAIL = CFG
        mailer.send_otp = lambda to, code, ttl, config, **kw: self.sent.append((to, code, ttl))

    def tearDown(self):
        server.MAIL, mailer.send_otp = self._orig

    def test_IT20_configured_sends_mail_and_hides_code(self):
        r = self.client.post("/api/auth/otp", json={"email": "Driver@Example.com", "accept": True})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["via"], "email")
        self.assertNotIn("dev_code", body)
        self.assertEqual(len(self.sent), 1)
        to, code, ttl = self.sent[0]
        self.assertEqual((to, ttl, len(code)), ("driver@example.com", 5, 6))
        # the mailed code really logs the user in
        v = self.client.post("/api/auth/verify", json={"email": "driver@example.com", "code": code})
        self.assertEqual(v.status_code, 200)
        self.assertTrue(v.json()["is_new"])

    def test_IT21_mail_failure_returns_502_and_invalidates_code(self):
        def boom(*a, **k):
            raise mailer.MailError("down")
        mailer.send_otp = boom
        r = self.client.post("/api/auth/otp", json={"email": "fail@example.com", "accept": True})
        self.assertEqual((r.status_code, r.json()["code"]), (502, "MAIL_FAILED"))
        v = self.client.post("/api/auth/verify", json={"email": "fail@example.com", "code": "000000"})
        self.assertEqual(v.json()["code"], "OTP_NOT_FOUND")

    def test_IT22_not_configured_and_not_dev_is_503(self):
        server.MAIL = {}
        r = self.client.post("/api/auth/otp", json={"email": "x@example.com", "accept": True})
        self.assertEqual((r.status_code, r.json()["code"]), (503, "MAIL_NOT_CONFIGURED"))

    def test_IT23_otp_expires_after_five_minutes(self):
        self.client.post("/api/auth/otp", json={"email": "late@example.com", "accept": True})
        code = self.sent[-1][1]
        conn = db.connect()
        conn.execute("UPDATE otps SET expires_at = expires_at - 400 WHERE email='late@example.com'")
        conn.close()
        v = self.client.post("/api/auth/verify", json={"email": "late@example.com", "code": code})
        self.assertEqual(v.json()["code"], "OTP_EXPIRED")


if __name__ == "__main__":
    unittest.main()
