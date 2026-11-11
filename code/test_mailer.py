"""Unit tests for the OTP e-mail sender (SMTP is faked, nothing is sent)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
import mailer  # noqa: E402

CFG = {"host": "smtp.example.com", "port": 587, "user": "u", "password": "p", "sender": "ParkQ <no-reply@example.com>"}


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.sent, self.tls, self.login_args = host, port, [], False, None
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, **kw):
        self.tls = True

    def login(self, user, password):
        self.login_args = (user, password)

    def send_message(self, msg):
        self.sent.append(msg)


class TestMailer(unittest.TestCase):
    def setUp(self):
        FakeSMTP.instances = []

    def test_UT30_message_contains_code_and_recipient(self):
        # Arrange / Act
        msg = mailer.build_message("somchai@example.com", "123456", 5, CFG["sender"])
        # Assert
        self.assertEqual(msg["To"], "somchai@example.com")
        self.assertEqual(msg["From"], CFG["sender"])
        self.assertIn("123456", msg.get_content())
        self.assertIn("5", msg.get_content())

    def test_UT31_send_uses_tls_login_and_sends_once(self):
        # Act
        mailer.send_otp("somchai@example.com", "654321", 5, config=CFG, smtp_factory=FakeSMTP)
        # Assert
        smtp = FakeSMTP.instances[0]
        self.assertEqual((smtp.host, smtp.port), ("smtp.example.com", 587))
        self.assertTrue(smtp.tls)
        self.assertEqual(smtp.login_args, ("u", "p"))
        self.assertEqual(len(smtp.sent), 1)

    def test_UT32_unconfigured_raises(self):
        # Act / Assert
        with self.assertRaises(mailer.MailError):
            mailer.send_otp("a@b.co", "111111", 5, config={}, smtp_factory=FakeSMTP)

    def test_UT33_smtp_failure_wrapped(self):
        # Arrange
        class Boom(FakeSMTP):
            def send_message(self, msg):
                raise OSError("network down")
        # Act / Assert
        with self.assertRaises(mailer.MailError):
            mailer.send_otp("a@b.co", "111111", 5, config=CFG, smtp_factory=Boom)

    def test_UT34_config_from_env(self):
        # Arrange
        env = {"PARKQ_SMTP_HOST": "h", "PARKQ_SMTP_USER": "u", "PARKQ_SMTP_PASS": "p", "PARKQ_SMTP_FROM": "ParkQ <x@y.z>"}
        # Act
        cfg = mailer.config_from_env(env)
        # Assert
        self.assertEqual((cfg["host"], cfg["port"], cfg["user"], cfg["password"]), ("h", 587, "u", "p"))
        self.assertTrue(mailer.is_configured(cfg))
        self.assertFalse(mailer.is_configured(mailer.config_from_env({})))


if __name__ == "__main__":
    unittest.main()
