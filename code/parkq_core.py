"""ParkQ core business rules.

Pure functions shared by the web backend and the gate (IoT) controller:
fees, lot status, booking rules, QR e-ticket tokens and input validation.
"""
import hashlib
import hmac
import math
import re
from datetime import datetime, timedelta, timezone

GRACE_MINUTES = 15            # free minutes before the first hour / after booking end
MAX_ADVANCE_DAYS = 7          # how far ahead a booking may start
MIN_BOOKING_HOURS = 1
MAX_BOOKING_HOURS = 24
FREE_CANCEL_MINUTES = 60      # cancel at least this long before start -> full refund
EARLY_ENTRY_MINUTES = 30      # QR becomes valid this long before booking start
NO_SHOW_MINUTES = 30          # booking released if not entered this long after start
NEARLY_FULL_RATIO = 0.20      # below this share of free slots the lot is "nearly full"

PHONE_RE = re.compile(r"^0[689]\d{8}$")
PLATE_RE = re.compile(r"^(\d{0,1}[ก-ฮ]{1,2})\s?(\d{1,4})$")


# ---------- validation ----------

def is_valid_phone(phone: str) -> bool:
    """Thai mobile number: 10 digits starting 06, 08 or 09."""
    return bool(PHONE_RE.match(phone or ""))


def is_valid_plate(plate: str) -> bool:
    """Thai car plate such as 'กข 1234' or '1กข 1234'."""
    return bool(PLATE_RE.match((plate or "").strip()))


# ---------- fees ----------

def parking_fee(minutes: int, rate_per_hour: int) -> int:
    """Fee for a walk-in stay: first GRACE_MINUTES free, then every started hour is charged."""
    if minutes < 0 or rate_per_hour < 0:
        raise ValueError("minutes and rate must be non-negative")
    if minutes <= GRACE_MINUTES:
        return 0
    return math.ceil(minutes / 60) * rate_per_hour


def booking_price(hours: int, rate_per_hour: int) -> int:
    """Price paid up front for a reservation of whole hours."""
    if not MIN_BOOKING_HOURS <= hours <= MAX_BOOKING_HOURS:
        raise ValueError(f"booking must be {MIN_BOOKING_HOURS}-{MAX_BOOKING_HOURS} hours")
    return hours * rate_per_hour


def overstay_fee(booked_end: datetime, exit_time: datetime, rate_per_hour: int) -> int:
    """Extra charge when leaving after the booked end time (GRACE_MINUTES tolerated)."""
    over = (exit_time - booked_end).total_seconds() / 60
    if over <= GRACE_MINUTES:
        return 0
    return math.ceil(over / 60) * rate_per_hour


def refund_amount(paid: int, start: datetime, cancel_time: datetime) -> int:
    """Full refund when cancelled at least FREE_CANCEL_MINUTES before start, otherwise none."""
    if cancel_time >= start:
        return 0
    if start - cancel_time >= timedelta(minutes=FREE_CANCEL_MINUTES):
        return paid
    return 0


# ---------- lot status ----------

def available_slots(capacity: int, occupied: int, reserved: int) -> int:
    """Free slots that can still be sold: capacity minus cars parked and active reservations."""
    if min(capacity, occupied, reserved) < 0:
        raise ValueError("counts must be non-negative")
    return max(capacity - occupied - reserved, 0)


def lot_status(capacity: int, occupied: int, reserved: int) -> str:
    """'AVAILABLE', 'NEARLY_FULL' or 'FULL' as shown on the map and lot cards."""
    free = available_slots(capacity, occupied, reserved)
    if free == 0:
        return "FULL"
    if free / capacity < NEARLY_FULL_RATIO:
        return "NEARLY_FULL"
    return "AVAILABLE"


# ---------- booking ----------

def validate_booking(now: datetime, start: datetime, hours: int, free_slots: int) -> str | None:
    """Return an error code, or None when the booking may be created."""
    if free_slots <= 0:
        return "LOT_FULL"
    if start < now - timedelta(minutes=1):
        return "START_IN_PAST"
    if start > now + timedelta(days=MAX_ADVANCE_DAYS):
        return "TOO_FAR_AHEAD"
    if not MIN_BOOKING_HOURS <= hours <= MAX_BOOKING_HOURS:
        return "INVALID_DURATION"
    return None


def is_no_show(start: datetime, now: datetime, entered: bool) -> bool:
    """A booking not entered NO_SHOW_MINUTES after start is released back to the lot."""
    return not entered and now > start + timedelta(minutes=NO_SHOW_MINUTES)


# ---------- QR e-ticket ----------

def make_ticket_token(ticket_id: str, lot_id: str, start: datetime, end: datetime, secret: bytes) -> str:
    """Signed QR payload: id|lot|start|end|signature. Cannot be forged without the secret."""
    body = f"{ticket_id}|{lot_id}|{int(start.timestamp())}|{int(end.timestamp())}"
    sig = hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{body}|{sig}"


def check_entry(token: str, lot_id: str, now: datetime, secret: bytes, used_ids: set) -> str:
    """Gate decision for a scanned QR: 'OK' or the reason the gate stays closed."""
    parts = token.split("|")
    if len(parts) != 5:
        return "INVALID_QR"
    ticket_id, t_lot, t_start, t_end, sig = parts
    body = "|".join(parts[:4])
    expected = hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, expected):
        return "INVALID_QR"
    if t_lot != lot_id:
        return "WRONG_LOT"
    if ticket_id in used_ids:
        return "ALREADY_USED"
    # Compare epoch seconds, not datetimes, so the server and the gate may run in different time zones.
    now_ts, start_ts, end_ts = now.timestamp(), int(t_start), int(t_end)
    if now_ts < start_ts - EARLY_ENTRY_MINUTES * 60:
        return "TOO_EARLY"
    if now_ts > start_ts + NO_SHOW_MINUTES * 60:
        return "NO_SHOW_RELEASED"
    if now_ts > end_ts:
        return "EXPIRED"
    return "OK"


def verify_token(token: str, secret: bytes) -> dict | None:
    """Decode a signed ticket token, or None when it is malformed or forged."""
    parts = (token or "").strip().split("|")
    if len(parts) != 5:
        return None
    body = "|".join(parts[:4])
    expected = hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(parts[4], expected):
        return None
    return {"ticket_id": parts[0], "lot_id": parts[1], "start": int(parts[2]), "end": int(parts[3])}


def check_exit(token: str, lot_id: str, status: str, now: datetime, rate_per_hour: int, secret: bytes) -> tuple[str, int]:
    """Exit gate decision for the same QR used to enter: (result, overstay fee to pay first).

    Tickets go WAITING -> PARKED -> DONE; only a PARKED ticket may leave through the exit gate.
    """
    info = verify_token(token, secret)
    if info is None:
        return "INVALID_QR", 0
    if info["lot_id"] != lot_id:
        return "WRONG_LOT", 0
    if status != "PARKED":
        return ("ALREADY_EXITED", 0) if status == "DONE" else ("NOT_ENTERED", 0)
    # Both sides as aware datetimes (lesson from DEF-01): naive `now` is read as the machine's local time.
    end = datetime.fromtimestamp(info["end"], tz=timezone.utc)
    fee = overstay_fee(end, now.astimezone(timezone.utc), rate_per_hour)
    return ("PAY_OVERSTAY", fee) if fee else ("OK", 0)
