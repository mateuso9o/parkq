"""Sends the login OTP by e-mail over plain SMTP (works with Brevo, Gmail app passwords, any SMTP relay).

Settings come from environment variables, so no secret ever lives in the repository:
  PARKQ_SMTP_HOST, PARKQ_SMTP_PORT (default 587), PARKQ_SMTP_USER, PARKQ_SMTP_PASS, PARKQ_SMTP_FROM
"""
import smtplib
from email.message import EmailMessage
from email.utils import formataddr


class MailError(Exception):
    """The OTP e-mail could not be sent."""


def config_from_env(env) -> dict:
    user = env.get("PARKQ_SMTP_USER", "")
    return {
        "host": env.get("PARKQ_SMTP_HOST", ""),
        "port": int(env.get("PARKQ_SMTP_PORT", "587")),
        "user": user,
        "password": env.get("PARKQ_SMTP_PASS", ""),
        "sender": env.get("PARKQ_SMTP_FROM", formataddr(("ParkQ", user)) if user else ""),
    }


def is_configured(config: dict) -> bool:
    return bool(config.get("host") and config.get("sender"))


def build_message(to: str, code: str, ttl_minutes: int, sender: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"รหัส OTP ParkQ ของคุณคือ {code}"
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(
        f"รหัส OTP สำหรับเข้าสู่ระบบ ParkQ: {code}\n\n"
        f"รหัสนี้ใช้ได้ {ttl_minutes} นาที และใช้ได้ครั้งเดียว\n"
        "หากคุณไม่ได้ขอรหัสนี้ ให้เพิกเฉยต่ออีเมลฉบับนี้ ห้ามบอกรหัสกับผู้อื่น\n\n"
        "— ทีม ParkQ"
    )
    return msg


def send_otp(to: str, code: str, ttl_minutes: int, config: dict, smtp_factory=smtplib.SMTP) -> None:
    if not is_configured(config):
        raise MailError("SMTP is not configured")
    msg = build_message(to, code, ttl_minutes, config["sender"])
    try:
        with smtp_factory(config["host"], config["port"], timeout=15) as smtp:
            smtp.starttls()
            if config.get("user"):
                smtp.login(config["user"], config["password"])
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException) as e:
        raise MailError(f"could not send e-mail: {e}") from e
