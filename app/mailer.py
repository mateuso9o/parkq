"""Sends the login OTP by e-mail over plain SMTP (works with Brevo, Gmail app passwords, any SMTP relay).

Settings come from environment variables, so no secret ever lives in the repository:
  PARKQ_SMTP_HOST, PARKQ_SMTP_PORT (default 587), PARKQ_SMTP_USER, PARKQ_SMTP_PASS, PARKQ_SMTP_FROM
Or, where outbound SMTP ports are blocked (Render free tier), Brevo's HTTPS API:
  PARKQ_BREVO_KEY (API key) + PARKQ_SMTP_FROM (a sender address verified in Brevo)
"""
import json
import smtplib
import urllib.request
from email.message import EmailMessage
from email.utils import formataddr, parseaddr


class MailError(Exception):
    """The OTP e-mail could not be sent."""


def config_from_env(env) -> dict:
    user = env.get("PARKQ_SMTP_USER", "")
    return {
        "api_key": env.get("PARKQ_BREVO_KEY", ""),   # HTTPS API: works where SMTP ports are blocked (Render free tier)
        "host": env.get("PARKQ_SMTP_HOST", ""),
        "port": int(env.get("PARKQ_SMTP_PORT", "587")),
        "user": user,
        "password": env.get("PARKQ_SMTP_PASS", ""),
        "sender": env.get("PARKQ_SMTP_FROM", formataddr(("ParkQ", user)) if user else ""),
    }


def is_configured(config: dict) -> bool:
    return bool((config.get("api_key") or config.get("host")) and config.get("sender"))


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


BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def _post_json(url: str, headers: dict, body: dict, timeout: int) -> None:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={**headers, "Content-Type": "application/json", "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:   # raises HTTPError (an OSError) on 4xx/5xx
        resp.read()


def _send_via_api(to: str, code: str, ttl_minutes: int, config: dict, http_post) -> None:
    msg = build_message(to, code, ttl_minutes, config["sender"])
    name, address = parseaddr(config["sender"])
    body = {"sender": {"name": name or "ParkQ", "email": address},
            "to": [{"email": to}],
            "subject": msg["Subject"],
            "textContent": msg.get_content()}
    try:
        http_post(BREVO_URL, {"api-key": config["api_key"]}, body, 15)
    except OSError as e:
        raise MailError(f"could not send e-mail via API: {e}") from e


def send_otp(to: str, code: str, ttl_minutes: int, config: dict, smtp_factory=smtplib.SMTP, http_post=_post_json) -> None:
    if not is_configured(config):
        raise MailError("e-mail is not configured")
    if config.get("api_key"):
        return _send_via_api(to, code, ttl_minutes, config, http_post)
    msg = build_message(to, code, ttl_minutes, config["sender"])
    try:
        with smtp_factory(config["host"], config["port"], timeout=15) as smtp:
            smtp.starttls()
            if config.get("user"):
                smtp.login(config["user"], config["password"])
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException) as e:
        raise MailError(f"could not send e-mail: {e}") from e
