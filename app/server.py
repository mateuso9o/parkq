"""ParkQ web server: REST API for the web app, gate kiosk / ESP32 and the admin back office.

Run:  python -m uvicorn server:app --app-dir app --port 8000
"""
import csv
import io
import math
import os
import secrets
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import qrcode
import qrcode.image.svg
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))
import parkq_core as core  # noqa: E402

import db  # noqa: E402
import mailer  # noqa: E402

SECRET = os.environ.get("PARKQ_SECRET", "parkq-dev-secret").encode()
DEV_MODE = os.environ.get("PARKQ_DEV", "1") == "1"      # shows OTP on screen and enables simulated payments
PUBLIC = os.environ.get("PARKQ_PUBLIC") == "1"            # public demo site: no one-click sign-in links
PROMPTPAY_ID = os.environ.get("PARKQ_PROMPTPAY_ID")      # unset -> demo QR that no bank app can pay
HOLD_SECONDS = 10 * 60
OTP_TTL = 5 * 60
MAIL = mailer.config_from_env(os.environ)           # SMTP settings; unset -> OTP shown on screen in dev mode
BKK = timezone(timedelta(hours=7))
STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="ParkQ API", version="1.0")


class ApiError(HTTPException):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(status, {"code": code, "message": message})


@app.middleware("http")
async def no_stale_assets(request: Request, call_next):
    """Browsers revalidate pages and scripts so an updated app is picked up immediately."""
    res = await call_next(request)
    if not request.url.path.startswith("/api/"):
        res.headers["Cache-Control"] = "no-cache"
    return res


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "ERROR", "message": str(exc.detail)}
    return JSONResponse(detail, status_code=exc.status_code)


def now() -> int:
    return int(time.time())


def get_db():
    conn = db.connect()
    try:
        housekeeping(conn)
        yield conn
    finally:
        conn.close()


def housekeeping(conn):
    """Release unpaid holds and no-show bookings (BR-09) before every request."""
    t = now()
    conn.execute("UPDATE tickets SET status='EXPIRED' WHERE status='PENDING' AND hold_until < ?", (t,))
    conn.execute("UPDATE tickets SET status='NO_SHOW' WHERE status='WAITING' AND start_at + ? < ?",
                 (core.NO_SHOW_MINUTES * 60, t))
    conn.execute("UPDATE payments SET status='EXPIRED' WHERE status='PENDING' AND expires_at < ?", (t,))


def current_user(authorization: str = Header(default=""), conn=Depends(get_db)):
    token = authorization.removeprefix("Bearer ").strip()
    row = conn.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?", (token,)).fetchone()
    if not row:
        raise ApiError(401, "UNAUTHORIZED", "กรุณาเข้าสู่ระบบ")
    return dict(row)


def require_role(*roles):
    def dep(user=Depends(current_user)):
        if user["role"] not in roles:
            raise ApiError(403, "FORBIDDEN", "ไม่มีสิทธิ์เข้าถึงหน้านี้")
        return user
    return dep


# ---------------------------------------------------------------- lots & availability

def lot_counts(conn, lot) -> dict:
    t = now()
    occupied = conn.execute("SELECT COUNT(*) FROM slots WHERE lot_id=? AND occupied=1", (lot["id"],)).fetchone()[0]
    # BR-03 (DEF-02): only bookings already started or starting within 30 minutes hold a slot
    reserved = conn.execute("""SELECT COUNT(*) FROM tickets WHERE lot_id=? AND status IN ('PENDING','WAITING')
                               AND start_at <= ?""", (lot["id"], t + 30 * 60)).fetchone()[0]
    free = core.available_slots(lot["capacity"], occupied, reserved)
    stale = bool(lot["device_id"]) and (lot["last_seen"] or 0) < t - 120
    return {"occupied": occupied, "reserved": reserved, "free": free,
            "status": "STALE" if stale else core.lot_status(lot["capacity"], occupied, reserved),
            "stale": stale}


def is_open(lot, at: int) -> bool:
    hm = datetime.fromtimestamp(at, BKK).strftime("%H:%M")
    return lot["open_time"] <= hm < (lot["close_time"] if lot["close_time"] != "24:00" else "24:01")


def lot_json(conn, lot, detail=False) -> dict:
    d = dict(lot)
    d.pop("device_key", None)
    d.update(lot_counts(conn, lot))
    d["open_now"] = is_open(lot, now())
    d["sellable"] = bool(lot["online"]) and not d["stale"] and d["open_now"]
    if detail:
        d["zones"] = [dict(r) for r in conn.execute(
            """SELECT zone, COUNT(*) total, SUM(occupied) occupied FROM slots WHERE lot_id=? GROUP BY zone""",
            (lot["id"],))]
    return d


def get_lot(conn, lot_id):
    lot = conn.execute("SELECT * FROM lots WHERE id=?", (lot_id,)).fetchone()
    if not lot:
        raise ApiError(404, "LOT_NOT_FOUND", "ไม่พบลานจอด")
    return lot


@app.get("/api/lots")
def list_lots(q: str = "", conn=Depends(get_db)):
    rows = conn.execute("SELECT * FROM lots WHERE online=1 AND (name LIKE ? OR address LIKE ?) ORDER BY id",
                        (f"%{q}%", f"%{q}%")).fetchall()
    return [lot_json(conn, r) for r in rows]


@app.get("/api/lots/{lot_id}")
def lot_detail(lot_id: str, conn=Depends(get_db)):
    return lot_json(conn, get_lot(conn, lot_id), detail=True)


# ---------------------------------------------------------------- auth (ACC_01)

class OtpIn(BaseModel):
    email: str
    accept: bool = False


class VerifyIn(BaseModel):
    email: str
    code: str


def mask_email(email: str) -> str:
    name, _, domain = email.partition("@")
    return f"{name[:1]}{'*' * max(2, len(name) - 1)}@{domain}"


@app.post("/api/auth/otp")
def request_otp(body: OtpIn, conn=Depends(get_db)):
    email = core.normalize_email(body.email)
    if not core.is_valid_email(email):
        raise ApiError(400, "INVALID_EMAIL", "กรุณากรอกอีเมลให้ถูกต้อง")
    if not body.accept:
        raise ApiError(400, "TERMS_REQUIRED", "กรุณายอมรับเงื่อนไขและนโยบายความเป็นส่วนตัว")
    recent = conn.execute("SELECT COUNT(*) FROM otps WHERE email=? AND created_at > ?",
                          (email, now() - 600)).fetchone()[0]
    if recent >= 5:
        raise ApiError(429, "OTP_RATE_LIMIT", "ขอ OTP เกินจำนวนครั้งที่กำหนด กรุณาลองใหม่ภายหลัง")
    conn.execute("UPDATE otps SET used=1 WHERE email=? AND used=0", (email,))
    code = f"{secrets.randbelow(10 ** 6):06d}"
    conn.execute("INSERT INTO otps(email,code,created_at,expires_at) VALUES (?,?,?,?)",
                 (email, code, now(), now() + OTP_TTL))
    res = {"sent": True, "expires_in": OTP_TTL, "masked": mask_email(email)}
    if mailer.is_configured(MAIL):
        try:
            mailer.send_otp(email, code, OTP_TTL // 60, MAIL)
        except mailer.MailError as e:
            print(f"MAIL_FAILED: {e}", flush=True)     # shows in the Render log; never contains credentials
            conn.execute("UPDATE otps SET used=1 WHERE email=? AND used=0", (email,))
            raise ApiError(502, "MAIL_FAILED", "ส่งอีเมลไม่สำเร็จ กรุณาลองใหม่อีกครั้ง")
        res["via"] = "email"
    elif not DEV_MODE:
        raise ApiError(503, "MAIL_NOT_CONFIGURED", "ระบบยังไม่ได้ตั้งค่าการส่งอีเมล")
    else:
        res["dev_code"] = code      # no SMTP account configured: demo mode shows the code on screen
    return res


@app.post("/api/auth/verify")
def verify_otp(body: VerifyIn, conn=Depends(get_db)):
    email = core.normalize_email(body.email)
    otp = conn.execute("SELECT * FROM otps WHERE email=? AND used=0 ORDER BY id DESC LIMIT 1", (email,)).fetchone()
    if not otp:
        raise ApiError(400, "OTP_NOT_FOUND", "กรุณาขอรหัส OTP ใหม่")
    if otp["expires_at"] < now():
        raise ApiError(400, "OTP_EXPIRED", "รหัส OTP หมดอายุ กรุณาขอใหม่")
    if not secrets.compare_digest(body.code, otp["code"]):
        attempts = otp["attempts"] + 1
        conn.execute("UPDATE otps SET attempts=?, used=? WHERE id=?", (attempts, int(attempts >= 3), otp["id"]))
        if attempts >= 3:
            raise ApiError(400, "OTP_LOCKED", "กรอกรหัสผิดครบ 3 ครั้ง กรุณาขอรหัสใหม่")
        raise ApiError(400, "OTP_WRONG", f"รหัส OTP ไม่ถูกต้อง (เหลือ {3 - attempts} ครั้ง)")
    conn.execute("UPDATE otps SET used=1 WHERE id=?", (otp["id"],))
    user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not user:
        conn.execute("INSERT INTO users(email,created_at) VALUES (?,?)", (email, now()))
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    token = secrets.token_urlsafe(24)
    conn.execute("INSERT INTO sessions VALUES (?,?,?)", (token, user["id"], now()))
    return {"token": token, "is_new": not user["name"], "user": dict(user)}


class RegisterIn(BaseModel):
    name: str
    phone: str = ""
    plate: str
    province: str


@app.post("/api/auth/register")
def register(body: RegisterIn, user=Depends(current_user), conn=Depends(get_db)):
    if len(body.name.strip()) < 2:
        raise ApiError(400, "NAME_REQUIRED", "กรุณากรอกชื่อ")
    if body.phone and not core.is_valid_phone(body.phone):
        raise ApiError(400, "INVALID_PHONE", "กรุณากรอกเบอร์โทรศัพท์ให้ถูกต้อง")
    if not core.is_valid_plate(body.plate):
        raise ApiError(400, "INVALID_PLATE", "รูปแบบทะเบียนไม่ถูกต้อง")
    conn.execute("UPDATE users SET name=?, phone=? WHERE id=?", (body.name.strip(), body.phone.strip(), user["id"]))
    conn.execute("INSERT OR IGNORE INTO vehicles(user_id,plate,province,type,is_primary) VALUES (?,?,?,'car',1)",
                 (user["id"], body.plate.strip(), body.province))
    return {"ok": True}


@app.get("/api/me")
def me(user=Depends(current_user)):
    return user


@app.post("/api/auth/logout")
def logout(authorization: str = Header(default=""), conn=Depends(get_db)):
    conn.execute("DELETE FROM sessions WHERE token=?", (authorization.removeprefix("Bearer ").strip(),))
    return {"ok": True}


# ---------------------------------------------------------------- vehicles (ACC_02)

class VehicleIn(BaseModel):
    plate: str
    province: str
    type: str = "car"
    is_primary: bool = False


@app.get("/api/vehicles")
def vehicles(user=Depends(current_user), conn=Depends(get_db)):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM vehicles WHERE user_id=? ORDER BY is_primary DESC, id", (user["id"],))]


def save_vehicle(conn, user, body: VehicleIn, vid=None):
    if not core.is_valid_plate(body.plate):
        raise ApiError(400, "INVALID_PLATE", "รูปแบบทะเบียนไม่ถูกต้อง")
    dup = conn.execute("SELECT id FROM vehicles WHERE user_id=? AND plate=? AND id <> ?",
                       (user["id"], body.plate.strip(), vid or 0)).fetchone()
    if dup:
        raise ApiError(409, "DUPLICATE_PLATE", "มีรถทะเบียนนี้ในบัญชีแล้ว")
    first = conn.execute("SELECT COUNT(*) FROM vehicles WHERE user_id=?", (user["id"],)).fetchone()[0] == 0
    primary = body.is_primary or first
    if primary:
        conn.execute("UPDATE vehicles SET is_primary=0 WHERE user_id=?", (user["id"],))
    if vid:
        conn.execute("UPDATE vehicles SET plate=?, province=?, type=?, is_primary=CASE WHEN ?=1 THEN 1 ELSE is_primary END WHERE id=? AND user_id=?",
                     (body.plate.strip(), body.province, body.type, int(primary), vid, user["id"]))
    else:
        conn.execute("INSERT INTO vehicles(user_id,plate,province,type,is_primary) VALUES (?,?,?,?,?)",
                     (user["id"], body.plate.strip(), body.province, body.type, int(primary)))
    return {"ok": True}


@app.post("/api/vehicles")
def add_vehicle(body: VehicleIn, user=Depends(current_user), conn=Depends(get_db)):
    return save_vehicle(conn, user, body)


@app.put("/api/vehicles/{vid}")
def edit_vehicle(vid: int, body: VehicleIn, user=Depends(current_user), conn=Depends(get_db)):
    return save_vehicle(conn, user, body, vid)


@app.delete("/api/vehicles/{vid}")
def delete_vehicle(vid: int, user=Depends(current_user), conn=Depends(get_db)):
    active = conn.execute("""SELECT COUNT(*) FROM tickets WHERE vehicle_id=? AND user_id=?
                             AND status IN ('PENDING','WAITING','PARKED')""", (vid, user["id"])).fetchone()[0]
    if active:
        raise ApiError(409, "VEHICLE_IN_USE", "รถคันนี้มีตั๋วที่ใช้งานอยู่")
    conn.execute("DELETE FROM vehicles WHERE id=? AND user_id=?", (vid, user["id"]))
    return {"ok": True}


# ---------------------------------------------------------------- bookings & tickets (BKG_01, BKG_02, BKG_04, TKT_01)

class BookingIn(BaseModel):
    lot_id: str
    mode: str                 # now | advance
    hours: int
    vehicle_id: int
    start_at: int | None = None


def ticket_json(conn, t) -> dict:
    d = dict(t)
    lot = conn.execute("SELECT name, address, lat, lng, rate FROM lots WHERE id=?", (t["lot_id"],)).fetchone()
    veh = conn.execute("SELECT plate, province FROM vehicles WHERE id=?", (t["vehicle_id"],)).fetchone()
    d["lot_name"], d["lot_address"], d["lat"], d["lng"] = lot["name"], lot["address"], lot["lat"], lot["lng"]
    d["plate"] = f"{veh['plate']} {veh['province']}" if veh else "-"
    if t["status"] not in ("WAITING", "PARKED"):
        d["token"] = None
    return d


@app.post("/api/bookings")
def create_booking(body: BookingIn, user=Depends(current_user), conn=Depends(get_db)):
    if body.mode not in ("now", "advance"):
        raise ApiError(400, "INVALID_MODE", "โหมดการจองไม่ถูกต้อง")
    veh = conn.execute("SELECT * FROM vehicles WHERE id=? AND user_id=?", (body.vehicle_id, user["id"])).fetchone()
    if not veh:
        raise ApiError(400, "VEHICLE_REQUIRED", "กรุณาเลือกรถ")
    t = now()
    start = t if body.mode == "now" else (body.start_at or 0)
    # DEF-03: BEGIN IMMEDIATE serialises concurrent bookings, so the last slot cannot be sold twice
    conn.execute("BEGIN IMMEDIATE")
    try:
        lot = get_lot(conn, body.lot_id)
        counts = lot_counts(conn, lot)
        if counts["stale"] or not lot["online"]:
            raise ApiError(409, "LOT_UNAVAILABLE", "ลานจอดนี้ปิดการขายชั่วคราว")
        if not is_open(lot, start):
            raise ApiError(400, "LOT_CLOSED", f"ลานจอดเปิด {lot['open_time']}–{lot['close_time']} น.")
        if body.mode == "now":
            free = counts["free"]
        else:
            quota = math.floor(lot["capacity"] * lot["advance_ratio"] / 100)
            overlapping = conn.execute("""SELECT COUNT(*) FROM tickets WHERE lot_id=? AND mode='advance'
                AND status IN ('PENDING','WAITING') AND start_at < ? AND end_at > ?""",
                (lot["id"], start + body.hours * 3600, start)).fetchone()[0]
            free = quota - overlapping
        err = core.validate_booking(datetime.fromtimestamp(t), datetime.fromtimestamp(start), body.hours, free)
        messages = {"LOT_FULL": "ขออภัย ช่วงเวลานี้เต็มแล้ว", "START_IN_PAST": "กรุณาเลือกเวลาในอนาคต",
                    "TOO_FAR_AHEAD": "จองล่วงหน้าได้ไม่เกิน 7 วัน", "INVALID_DURATION": "จำนวนชั่วโมงต้องอยู่ระหว่าง 1–24"}
        if err:
            raise ApiError(409 if err == "LOT_FULL" else 400, err, messages[err])
        n = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] + 1
        tid = f"TK-{n:06d}"
        amount = core.booking_price(body.hours, lot["rate"])
        conn.execute("""INSERT INTO tickets(id,user_id,vehicle_id,lot_id,mode,start_at,end_at,hours,rate,amount,status,
                        hold_until,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,'PENDING',?,?)""",
                     (tid, user["id"], veh["id"], lot["id"], body.mode, start, start + body.hours * 3600, body.hours,
                      lot["rate"], amount, t + HOLD_SECONDS, t))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return ticket_json(conn, conn.execute("SELECT * FROM tickets WHERE id=?", (tid,)).fetchone())


def my_ticket(conn, user, tid):
    t = conn.execute("SELECT * FROM tickets WHERE id=? AND user_id=?", (tid, user["id"])).fetchone()
    if not t:
        raise ApiError(404, "TICKET_NOT_FOUND", "ไม่พบตั๋ว")
    return t


@app.get("/api/tickets")
def tickets(user=Depends(current_user), conn=Depends(get_db)):
    rows = conn.execute("""SELECT * FROM tickets WHERE user_id=? AND status != 'EXPIRED'
                           ORDER BY CASE WHEN status IN ('WAITING','PARKED','PENDING') THEN 0 ELSE 1 END,
                           start_at DESC LIMIT 50""", (user["id"],)).fetchall()
    return [ticket_json(conn, r) for r in rows]


@app.get("/api/tickets/{tid}")
def ticket(tid: str, user=Depends(current_user), conn=Depends(get_db)):
    d = ticket_json(conn, my_ticket(conn, user, tid))
    if d["status"] == "WAITING":
        d["refund_if_cancel"] = core.refund_amount(d["amount"], datetime.fromtimestamp(d["start_at"]), datetime.fromtimestamp(now()))
    return d


@app.post("/api/tickets/{tid}/release")
def release(tid: str, user=Depends(current_user), conn=Depends(get_db)):
    conn.execute("UPDATE tickets SET status='EXPIRED' WHERE id=? AND user_id=? AND status='PENDING'", (tid, user["id"]))
    return {"ok": True}


class CancelIn(BaseModel):
    reason: str = ""


@app.post("/api/tickets/{tid}/cancel")
def cancel(tid: str, body: CancelIn, user=Depends(current_user), conn=Depends(get_db)):
    t = my_ticket(conn, user, tid)
    if t["status"] != "WAITING":
        raise ApiError(409, "NOT_CANCELLABLE", "ตั๋วนี้ยกเลิกไม่ได้")
    refund = core.refund_amount(t["amount"], datetime.fromtimestamp(t["start_at"]), datetime.fromtimestamp(now()))
    conn.execute("UPDATE tickets SET status='CANCELLED', refund=?, cancel_reason=? WHERE id=?", (refund, body.reason, tid))
    # Production: request the refund from the payment gateway here.
    return {"ok": True, "refund": refund}


# ---------------------------------------------------------------- payments (BKG_03, TKT_03)

def crc16(data: str) -> str:
    crc = 0xFFFF
    for b in data.encode():
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def promptpay_payload(amount: int, payment_id: str) -> str:
    """Thai QR Payment (EMVCo) when a PromptPay ID is configured, otherwise an unpayable demo payload."""
    if not PROMPTPAY_ID:
        return f"PARKQ-DEMO|{payment_id}|{amount}.00THB"
    def f(tag, val):
        return f"{tag}{len(val):02d}{val}"
    target = "0066" + PROMPTPAY_ID[1:] if len(PROMPTPAY_ID) == 10 else PROMPTPAY_ID
    acct = f("00", "A000000677010111") + f("01" if len(PROMPTPAY_ID) == 10 else "02", target)
    body = f("00", "01") + f("01", "12") + f("29", acct) + f("53", "764") + f("54", f"{amount:.2f}") + f("58", "TH") + "6304"
    return body + crc16(body)


class PaymentIn(BaseModel):
    ticket_id: str
    method: str = "promptpay"   # promptpay | card
    card_number: str = ""


def payment_json(p) -> dict:
    d = dict(p)
    d["qr_payload"] = promptpay_payload(p["amount"], p["id"]) if p["method"] == "promptpay" else None
    d["demo"] = not PROMPTPAY_ID
    return d


def mark_paid(conn, pay):
    t = now()
    conn.execute("UPDATE payments SET status='PAID', paid_at=? WHERE id=?", (t, pay["id"]))
    tk = conn.execute("SELECT * FROM tickets WHERE id=?", (pay["ticket_id"],)).fetchone()
    if pay["kind"] == "booking" and tk["status"] == "PENDING":
        token = core.make_ticket_token(tk["id"], tk["lot_id"], datetime.fromtimestamp(tk["start_at"]),
                                       datetime.fromtimestamp(tk["end_at"]), SECRET)
        conn.execute("UPDATE tickets SET status='WAITING', token=?, hold_until=NULL WHERE id=?", (token, tk["id"]))
    elif pay["kind"] == "overstay":
        conn.execute("UPDATE tickets SET overstay_fee=overstay_fee+? WHERE id=?", (pay["amount"], tk["id"]))
        finish_exit(conn, tk, "qr")


@app.post("/api/payments")
def create_payment(body: PaymentIn, user=Depends(current_user), conn=Depends(get_db)):
    tk = my_ticket(conn, user, body.ticket_id)
    if tk["status"] != "PENDING":
        raise ApiError(409, "NOT_PAYABLE", "หมดเวลาทำรายการ กรุณาทำรายการใหม่")
    pid = "PM-" + secrets.token_hex(4).upper()
    conn.execute("INSERT INTO payments VALUES (?,?,?,?,?,?,?,?,?)",
                 (pid, tk["id"], "booking", body.method, tk["amount"], "PENDING", now(), None, tk["hold_until"]))
    pay = conn.execute("SELECT * FROM payments WHERE id=?", (pid,)).fetchone()
    if body.method == "card":
        # Card data goes to the gateway's hosted form in production; the test card 4242 4242 4242 4242 succeeds.
        if body.card_number.replace(" ", "") != "4242424242424242":
            conn.execute("UPDATE payments SET status='DECLINED' WHERE id=?", (pid,))
            raise ApiError(402, "CARD_DECLINED", "การชำระเงินไม่สำเร็จ กรุณาลองใหม่หรือเปลี่ยนวิธีชำระ")
        mark_paid(conn, pay)
    return payment_json(conn.execute("SELECT * FROM payments WHERE id=?", (pid,)).fetchone())


@app.get("/api/payments/{pid}")
def payment(pid: str, conn=Depends(get_db)):
    p = conn.execute("SELECT * FROM payments WHERE id=?", (pid,)).fetchone()
    if not p:
        raise ApiError(404, "PAYMENT_NOT_FOUND", "ไม่พบรายการชำระเงิน")
    return payment_json(p)


@app.post("/api/payments/{pid}/simulate")
def simulate_payment(pid: str, conn=Depends(get_db)):
    """Stands in for the payment gateway webhook during development."""
    if not DEV_MODE:
        raise ApiError(404, "NOT_FOUND", "ไม่พบ")
    p = conn.execute("SELECT * FROM payments WHERE id=? AND status='PENDING'", (pid,)).fetchone()
    if not p:
        raise ApiError(409, "NOT_PENDING", "รายการนี้ชำระแล้วหรือหมดอายุ")
    mark_paid(conn, p)
    return payment_json(conn.execute("SELECT * FROM payments WHERE id=?", (pid,)).fetchone())


@app.get("/api/qr.svg")
def qr_svg(data: str):
    img = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage, border=2,
                      error_correction=qrcode.constants.ERROR_CORRECT_M)
    buf = io.BytesIO()
    img.save(buf)
    return Response(buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "max-age=3600"})


# ---------------------------------------------------------------- gate kiosk / ESP32 (TKT_02, TKT_03)

MESSAGES = {
    "OK": "ยินดีต้อนรับ", "INVALID_QR": "QR ไม่ถูกต้อง", "WRONG_LOT": "ตั๋วนี้ไม่ใช่ของลานจอดนี้",
    "ALREADY_USED": "QR นี้ถูกใช้แล้ว", "TOO_EARLY": "ยังไม่ถึงเวลาเข้า (เข้าได้ก่อนเวลา 30 นาที)",
    "NO_SHOW_RELEASED": "หมดเวลาเข้า (No-show)", "EXPIRED": "ตั๋วหมดอายุ", "NOT_PAID": "ตั๋วยังไม่ได้ชำระเงิน",
    "NOT_ENTERED": "ตั๋วนี้ยังไม่ได้สแกนเข้า", "ALREADY_EXITED": "ตั๋วนี้ออกจากลานแล้ว",
    "PAY_OVERSTAY": "จอดเกินเวลา กรุณาชำระค่าส่วนเกิน", "BYE": "ขอบคุณที่ใช้บริการ",
}


class ScanIn(BaseModel):
    token: str
    device_key: str = ""


def open_gate(conn, lot_id, gate):
    conn.execute("INSERT INTO gate_commands(lot_id,gate,command,created_at) VALUES (?,?,'OPEN',?)", (lot_id, gate, now()))


def set_demo_slot(conn, lot, occupied: bool):
    """Without a real sensor, mark one slot so availability follows cars through the gates."""
    if lot["device_id"]:
        return
    row = conn.execute("SELECT slot_no FROM slots WHERE lot_id=? AND occupied=? ORDER BY slot_no LIMIT 1",
                       (lot["id"], 0 if occupied else 1)).fetchone()
    if row:
        twin_record(conn, lot["id"], row["slot_no"], int(occupied))
        conn.execute("UPDATE slots SET occupied=?, updated_at=? WHERE lot_id=? AND slot_no=?",
                     (int(occupied), now(), lot["id"], row["slot_no"]))


def finish_exit(conn, tk, method, staff_id=None, reason=None):
    lot = get_lot(conn, tk["lot_id"])
    conn.execute("UPDATE tickets SET status='DONE', exited_at=? WHERE id=?", (now(), tk["id"]))
    set_demo_slot(conn, lot, False)
    open_gate(conn, lot["id"], "out")
    log(conn, lot["id"], "out", tk["id"], "OK", method, staff_id, reason)


def plate_of(conn, tk):
    v = conn.execute("SELECT plate FROM vehicles WHERE id=?", (tk["vehicle_id"],)).fetchone()
    return v["plate"] if v else ""


def log(conn, lot_id, gate, tid, result, method, staff_id=None, reason=None):
    plate = ""
    if tid:
        tk = conn.execute("SELECT * FROM tickets WHERE id=?", (tid,)).fetchone()
        plate = plate_of(conn, tk) if tk else ""
    conn.execute("INSERT INTO gate_logs(lot_id,gate,ticket_id,plate,result,method,staff_id,reason,at) VALUES (?,?,?,?,?,?,?,?,?)",
                 (lot_id, gate, tid, plate, result, method, staff_id, reason, now()))


@app.get("/api/gate/{lot_id}/info")
def gate_info(lot_id: str, conn=Depends(get_db)):
    lot = get_lot(conn, lot_id)
    return {"id": lot["id"], "name": lot["name"], **lot_counts(conn, lot), "capacity": lot["capacity"],
            "online": not lot_counts(conn, lot)["stale"], "rate": lot["rate"],
            "open_time": lot["open_time"], "close_time": lot["close_time"]}


@app.post("/api/gate/{lot_id}/in/scan")
def scan_in(lot_id: str, body: ScanIn, conn=Depends(get_db)):
    lot = get_lot(conn, lot_id)
    info = core.verify_token(body.token, SECRET)
    tk = conn.execute("SELECT * FROM tickets WHERE id=?", (info["ticket_id"],)).fetchone() if info else None
    used = {tk["id"]} if tk and tk["status"] in ("PARKED", "DONE") else set()
    result = core.check_entry(body.token.strip(), lot_id, datetime.fromtimestamp(now()), SECRET, used)
    if result == "OK" and (not tk or tk["status"] != "WAITING"):
        result = "NOT_PAID" if tk and tk["status"] == "PENDING" else ("NO_SHOW_RELEASED" if tk and tk["status"] == "NO_SHOW" else "INVALID_QR")
    res = {"result": result, "message": MESSAGES[result], "open": result == "OK"}
    if result == "OK":
        conn.execute("UPDATE tickets SET status='PARKED', entered_at=? WHERE id=?", (now(), tk["id"]))
        set_demo_slot(conn, lot, True)
        open_gate(conn, lot_id, "in")
        res["plate"] = plate_of(conn, tk)
        res["end_at"] = tk["end_at"]
    log(conn, lot_id, "in", tk["id"] if tk else None, result, "qr")
    return res


@app.post("/api/gate/{lot_id}/out/scan")
def scan_out(lot_id: str, body: ScanIn, conn=Depends(get_db)):
    lot = get_lot(conn, lot_id)
    info = core.verify_token(body.token, SECRET)
    tk = conn.execute("SELECT * FROM tickets WHERE id=?", (info["ticket_id"],)).fetchone() if info else None
    status = {"WAITING": "WAITING", "PARKED": "PARKED", "DONE": "DONE"}.get(tk["status"] if tk else "", "NONE")
    result, fee = core.check_exit(body.token.strip(), lot_id, status, datetime.now(timezone.utc), lot["rate"], SECRET)
    res = {"result": result, "message": MESSAGES[result], "open": False, "fee": fee}
    if result == "OK":
        finish_exit(conn, tk, "qr")
        res.update(open=True, message=MESSAGES["BYE"], plate=plate_of(conn, tk))
        return res
    if result == "PAY_OVERSTAY":
        pid = "PM-" + secrets.token_hex(4).upper()
        conn.execute("INSERT INTO payments VALUES (?,?,?,?,?,?,?,?,?)",
                     (pid, tk["id"], "overstay", "promptpay", fee, "PENDING", now(), None, now() + HOLD_SECONDS))
        res["payment"] = payment_json(conn.execute("SELECT * FROM payments WHERE id=?", (pid,)).fetchone())
        res["over_minutes"] = (now() - tk["end_at"]) // 60
        res["plate"] = plate_of(conn, tk)
    log(conn, lot_id, "out", tk["id"] if tk else None, result, "qr")
    return res


@app.post("/api/gate/{lot_id}/{gate}/call")
def call_staff(lot_id: str, gate: str, conn=Depends(get_db)):
    get_lot(conn, lot_id)
    conn.execute("INSERT INTO alerts(lot_id,gate,message,at) VALUES (?,?,?,?)",
                 (lot_id, gate, "ผู้ใช้กดเรียกพนักงานที่ตู้" + ("ทางเข้า" if gate == "in" else "ทางออก"), now()))
    return {"ok": True}


# ---------------------------------------------------------------- IoT device API (ESP32 gate controller / slot sensors)

class SlotsIn(BaseModel):
    device_key: str
    slots: list[int]          # 1 = occupied, index 0 = slot 1


def check_device(lot, key):
    if not lot["device_key"] or not secrets.compare_digest(lot["device_key"], key):
        raise ApiError(403, "BAD_DEVICE_KEY", "device key ไม่ถูกต้อง")


def record_slot(conn, lot_id: str, slot_no: int, occupied: int) -> None:
    """Digital twin history: one row per real change of a slot (heartbeats with the same value add nothing)."""
    row = conn.execute("SELECT occupied FROM slots WHERE lot_id=? AND slot_no=?", (lot_id, slot_no)).fetchone()
    if row is not None and int(row["occupied"]) == int(occupied):
        return
    conn.execute("INSERT INTO slot_history(lot_id,slot_no,occupied,at) VALUES (?,?,?,?)",
                 (lot_id, slot_no, int(occupied), now()))


def twin_record(conn, lot_id: str, slot_no: int, occupied: int) -> None:
    """Guarded call used on the sensor path: the twin must never be able to break it."""
    try:
        record_slot(conn, lot_id, slot_no, occupied)
    except Exception as e:      # noqa: BLE001
        print(f"TWIN_HISTORY_FAILED: {e}", flush=True)


TWIN_MAX_WINDOW = 1800


@app.get("/api/twin/{lot_id}")
def twin_state(lot_id: str, window: int = 600, conn=Depends(get_db)):
    """Public, read-only state for the 3D digital twin. No plates, ticket ids or e-mails."""
    lot = get_lot(conn, lot_id)
    window = max(1, min(window, TWIN_MAX_WINDOW))
    t = now()
    since = t - window
    counts = lot_counts(conn, lot)
    slots = [{"no": r["slot_no"], "occupied": int(r["occupied"]), "updated_at": r["updated_at"]}
             for r in conn.execute("SELECT slot_no, occupied, updated_at FROM slots WHERE lot_id=? ORDER BY slot_no", (lot_id,))]
    events = []
    for r in conn.execute("SELECT slot_no, occupied, at FROM slot_history WHERE lot_id=? AND at>=?", (lot_id, since)):
        events.append({"at": r["at"], "kind": "slot", "slot_no": r["slot_no"], "occupied": int(r["occupied"])})
    for r in conn.execute("SELECT gate, created_at FROM gate_commands WHERE lot_id=? AND command='OPEN' AND created_at>=?", (lot_id, since)):
        events.append({"at": r["created_at"], "kind": "gate_open", "gate": r["gate"]})
    for r in conn.execute("SELECT gate, at FROM gate_logs WHERE lot_id=? AND result='OK' AND at>=?", (lot_id, since)):
        if r["gate"] in ("in", "out"):
            events.append({"at": r["at"], "kind": "car_in" if r["gate"] == "in" else "car_out", "gate": r["gate"]})
    events.sort(key=lambda e: e["at"])
    return {"now": t, "window": window,
            "lot": {"id": lot["id"], "name": lot["name"], "capacity": lot["capacity"],
                    "online": bool(lot["device_id"]) and not counts["stale"]},
            "slots": slots, "free": counts["free"], "events": events}


@app.post("/api/iot/{lot_id}/slots")
def iot_slots(lot_id: str, body: SlotsIn, conn=Depends(get_db)):
    lot = get_lot(conn, lot_id)
    check_device(lot, body.device_key)
    for i, occ in enumerate(body.slots[: lot["capacity"]], 1):
        twin_record(conn, lot_id, i, int(bool(occ)))
        conn.execute("UPDATE slots SET occupied=?, updated_at=? WHERE lot_id=? AND slot_no=?", (int(bool(occ)), now(), lot_id, i))
    conn.execute("UPDATE lots SET last_seen=? WHERE id=?", (now(), lot_id))
    return lot_counts(conn, get_lot(conn, lot_id))


@app.get("/api/iot/{lot_id}/commands")
def iot_commands(lot_id: str, device_key: str, conn=Depends(get_db)):
    """ESP32 polls this every second and drives the relay/servo for each OPEN command."""
    lot = get_lot(conn, lot_id)
    check_device(lot, device_key)
    conn.execute("UPDATE lots SET last_seen=? WHERE id=?", (now(), lot_id))
    cmds = [dict(r) for r in conn.execute("SELECT id, gate, command FROM gate_commands WHERE lot_id=? AND done=0", (lot_id,))]
    conn.execute("UPDATE gate_commands SET done=1 WHERE lot_id=? AND done=0", (lot_id,))
    return cmds


# ---------------------------------------------------------------- staff (TKT_04)

class OpenIn(BaseModel):
    lot_id: str
    gate: str
    reason: str
    ticket_id: str | None = None


@app.get("/api/staff/search")
def staff_search(q: str, user=Depends(require_role("attendant", "admin")), conn=Depends(get_db)):
    rows = conn.execute("""SELECT t.* FROM tickets t JOIN vehicles v ON v.id=t.vehicle_id
        WHERE (t.id LIKE ? OR REPLACE(v.plate,' ','') LIKE ?) AND t.status IN ('WAITING','PARKED','PENDING')
        ORDER BY t.start_at DESC LIMIT 20""", (f"%{q.strip()}%", f"%{q.replace(' ', '')}%")).fetchall()
    out = []
    for r in rows:
        d = ticket_json(conn, r)
        d["due"] = core.overstay_fee(datetime.fromtimestamp(r["end_at"]), datetime.fromtimestamp(now()), r["rate"]) if r["status"] == "PARKED" else 0
        out.append(d)
    return out


@app.post("/api/staff/open")
def staff_open(body: OpenIn, user=Depends(require_role("attendant", "admin")), conn=Depends(get_db)):
    if not body.reason:
        raise ApiError(400, "REASON_REQUIRED", "กรุณาเลือกเหตุผลการเปิดไม้กั้น")
    lot = get_lot(conn, body.lot_id)
    tk = conn.execute("SELECT * FROM tickets WHERE id=?", (body.ticket_id,)).fetchone() if body.ticket_id else None
    if tk and body.gate == "in" and tk["status"] == "WAITING":
        conn.execute("UPDATE tickets SET status='PARKED', entered_at=? WHERE id=?", (now(), tk["id"]))
        set_demo_slot(conn, lot, True)
    if tk and body.gate == "out" and tk["status"] == "PARKED":
        finish_exit(conn, tk, "staff", user["id"], body.reason)
        return {"ok": True}
    open_gate(conn, lot["id"], body.gate)
    log(conn, lot["id"], body.gate, tk["id"] if tk else None, "OK", "staff", user["id"], body.reason)
    conn.execute("UPDATE alerts SET resolved=1 WHERE lot_id=? AND gate=?", (lot["id"], body.gate))
    return {"ok": True}


@app.get("/api/staff/alerts")
def staff_alerts(user=Depends(require_role("attendant", "admin")), conn=Depends(get_db)):
    return [dict(r) for r in conn.execute(
        "SELECT a.*, l.name lot_name FROM alerts a JOIN lots l ON l.id=a.lot_id WHERE resolved=0 ORDER BY at DESC LIMIT 10")]


# ---------------------------------------------------------------- admin (ADM_01..03)

class LotIn(BaseModel):
    name: str
    address: str
    lat: float
    lng: float
    capacity: int
    open_time: str = "00:00"
    close_time: str = "24:00"
    device_id: str = ""
    online: bool = True


class RatesIn(BaseModel):
    rate: int
    advance_ratio: int


def admin_lot(conn, user, lot_id):
    lot = conn.execute("SELECT * FROM lots WHERE id=? AND owner_id=?", (lot_id, user["id"])).fetchone()
    if not lot:
        raise ApiError(404, "LOT_NOT_FOUND", "ไม่พบลานจอดของคุณ")
    return lot


@app.get("/api/admin/lots")
def admin_lots(user=Depends(require_role("admin")), conn=Depends(get_db)):
    return [lot_json(conn, r) for r in conn.execute("SELECT * FROM lots WHERE owner_id=? ORDER BY id", (user["id"],))]


def validate_lot(body: LotIn):
    if not 1 <= len(body.name.strip()) <= 100:
        raise ApiError(400, "NAME_REQUIRED", "กรุณากรอกชื่อลานจอด (1–100 ตัวอักษร)")
    if not body.address.strip():
        raise ApiError(400, "ADDRESS_REQUIRED", "กรุณากรอกที่อยู่")
    if not 1 <= body.capacity <= 5000:
        raise ApiError(400, "INVALID_CAPACITY", "จำนวนช่องจอดต้องอยู่ระหว่าง 1–5,000")
    if body.close_time != "24:00" and body.close_time <= body.open_time:
        raise ApiError(400, "INVALID_HOURS", "เวลาปิดต้องหลังเวลาเปิด")


def resize_slots(conn, lot_id, capacity):
    have = conn.execute("SELECT COUNT(*) FROM slots WHERE lot_id=?", (lot_id,)).fetchone()[0]
    for n in range(have + 1, capacity + 1):
        conn.execute("INSERT INTO slots VALUES (?,?,?,0,?)", (lot_id, n, "ABCD"[min(3, (n - 1) * 4 // capacity)], now()))
    conn.execute("DELETE FROM slots WHERE lot_id=? AND slot_no > ?", (lot_id, capacity))


@app.post("/api/admin/lots")
def admin_add_lot(body: LotIn, user=Depends(require_role("admin")), conn=Depends(get_db)):
    validate_lot(body)
    if conn.execute("SELECT 1 FROM lots WHERE owner_id=? AND name=?", (user["id"], body.name.strip())).fetchone():
        raise ApiError(409, "DUPLICATE_NAME", "มีลานจอดชื่อนี้แล้ว")
    n = conn.execute("SELECT COUNT(*) FROM lots").fetchone()[0] + 1
    lid = f"LOT{n:02d}"
    conn.execute("""INSERT INTO lots(id,name,address,lat,lng,capacity,rate,open_time,close_time,online,device_id,device_key,owner_id)
                    VALUES (?,?,?,?,?,?,20,?,?,?,?,?,?)""",
                 (lid, body.name.strip(), body.address, body.lat, body.lng, body.capacity, body.open_time, body.close_time,
                  int(body.online), body.device_id or None, ("dev-key-" + secrets.token_hex(4)) if body.device_id else None, user["id"]))
    resize_slots(conn, lid, body.capacity)
    return {"ok": True, "id": lid}


@app.put("/api/admin/lots/{lot_id}")
def admin_edit_lot(lot_id: str, body: LotIn, user=Depends(require_role("admin")), conn=Depends(get_db)):
    lot = admin_lot(conn, user, lot_id)
    validate_lot(body)
    active = conn.execute("SELECT COUNT(*) FROM tickets WHERE lot_id=? AND status IN ('PENDING','WAITING','PARKED')",
                          (lot_id,)).fetchone()[0]
    if body.capacity < active:
        raise ApiError(409, "CAPACITY_BELOW_BOOKINGS", f"มีการจองอยู่ {active} ช่อง ลดจำนวนช่องไม่ได้")
    conn.execute("""UPDATE lots SET name=?, address=?, lat=?, lng=?, capacity=?, open_time=?, close_time=?, online=?,
                    device_id=? WHERE id=?""",
                 (body.name.strip(), body.address, body.lat, body.lng, body.capacity, body.open_time, body.close_time,
                  int(body.online), body.device_id or None, lot_id))
    if body.device_id and not lot["device_key"]:
        conn.execute("UPDATE lots SET device_key=? WHERE id=?", ("dev-key-" + secrets.token_hex(4), lot_id))
    resize_slots(conn, lot_id, body.capacity)
    return {"ok": True}


@app.put("/api/admin/lots/{lot_id}/online")
def admin_toggle_online(lot_id: str, online: bool, user=Depends(require_role("admin")), conn=Depends(get_db)):
    admin_lot(conn, user, lot_id)
    conn.execute("UPDATE lots SET online=? WHERE id=?", (int(online), lot_id))
    return {"ok": True}


@app.put("/api/admin/lots/{lot_id}/rates")
def admin_rates(lot_id: str, body: RatesIn, user=Depends(require_role("admin")), conn=Depends(get_db)):
    admin_lot(conn, user, lot_id)
    if not 0 <= body.rate <= 1000:
        raise ApiError(400, "INVALID_RATE", "ค่าจอดต้องอยู่ระหว่าง 0–1,000 บาท")
    if not 0 <= body.advance_ratio <= 100:
        raise ApiError(400, "INVALID_RATIO", "สัดส่วนต้องอยู่ระหว่าง 0–100%")
    conn.execute("UPDATE lots SET rate=?, advance_ratio=? WHERE id=?", (body.rate, body.advance_ratio, lot_id))
    return {"ok": True}


@app.get("/api/admin/dashboard")
def admin_dashboard(lot_id: str, user=Depends(require_role("admin")), conn=Depends(get_db)):
    lot = admin_lot(conn, user, lot_id)
    day0 = int(datetime.now(BKK).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    revenue = conn.execute("""SELECT COALESCE(SUM(p.amount),0) FROM payments p JOIN tickets t ON t.id=p.ticket_id
                              WHERE t.lot_id=? AND p.status='PAID' AND p.paid_at>=?""", (lot_id, day0)).fetchone()[0]
    bookings = conn.execute("SELECT COUNT(*) FROM tickets WHERE lot_id=? AND created_at>=? AND status NOT IN ('EXPIRED')",
                            (lot_id, day0)).fetchone()[0]
    reserved_now = conn.execute(
        "SELECT COUNT(*) FROM tickets WHERE lot_id=? AND status IN ('WAITING','PENDING') AND start_at<=?",
        (lot_id, now() + 1800)).fetchone()[0]
    slots = [dict(r) for r in conn.execute("SELECT slot_no, zone, occupied, updated_at FROM slots WHERE lot_id=? ORDER BY slot_no", (lot_id,))]
    logs = [dict(r) for r in conn.execute("SELECT * FROM gate_logs WHERE lot_id=? ORDER BY id DESC LIMIT 20", (lot_id,))]
    return {"lot": lot_json(conn, lot), "revenue_today": revenue, "bookings_today": bookings,
            "reserved_now": reserved_now, "slots": slots, "logs": logs}


@app.post("/api/admin/lots/{lot_id}/slots/{slot_no}/toggle")
def admin_toggle_slot(lot_id: str, slot_no: int, user=Depends(require_role("admin")), conn=Depends(get_db)):
    """Sensor simulator for demos without hardware."""
    admin_lot(conn, user, lot_id)
    cur = conn.execute("SELECT occupied FROM slots WHERE lot_id=? AND slot_no=?", (lot_id, slot_no)).fetchone()
    if cur is not None:
        twin_record(conn, lot_id, slot_no, 1 - int(cur["occupied"]))
    conn.execute("UPDATE slots SET occupied=1-occupied, updated_at=? WHERE lot_id=? AND slot_no=?", (now(), lot_id, slot_no))
    conn.execute("UPDATE lots SET last_seen=? WHERE id=?", (now(), lot_id))
    return {"ok": True}


@app.get("/api/admin/report")
def admin_report(lot_id: str, date_from: str, date_to: str, format: str = "json",
                 user=Depends(require_role("admin")), conn=Depends(get_db)):
    lot = admin_lot(conn, user, lot_id)
    try:
        d0 = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=BKK)
        d1 = datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=BKK)
    except ValueError:
        raise ApiError(400, "INVALID_DATE", "รูปแบบวันที่ไม่ถูกต้อง")
    if d1 < d0:
        raise ApiError(400, "INVALID_RANGE", "วันที่สิ้นสุดต้องไม่ก่อนวันที่เริ่ม")
    if (d1 - d0).days > 366:
        raise ApiError(400, "RANGE_TOO_LONG", "เลือกช่วงวันที่ได้ไม่เกิน 1 ปี")
    rows = conn.execute("""SELECT p.amount, p.kind, p.paid_at, t.mode, t.hours FROM payments p JOIN tickets t ON t.id=p.ticket_id
                           WHERE t.lot_id=? AND p.status='PAID' AND p.paid_at>=? AND p.paid_at<?""",
                        (lot_id, int(d0.timestamp()), int((d1 + timedelta(days=1)).timestamp()))).fetchall()
    days = {}
    for k in range((d1 - d0).days + 1):
        key = (d0 + timedelta(days=k)).strftime("%Y-%m-%d")
        days[key] = {"date": key, "count": 0, "now": 0, "advance": 0, "overstay": 0, "revenue": 0, "hours": 0}
    for r in rows:
        key = datetime.fromtimestamp(r["paid_at"], BKK).strftime("%Y-%m-%d")
        d = days.get(key)
        if not d:
            continue
        bucket = "overstay" if r["kind"] == "overstay" else r["mode"]
        d[bucket] += r["amount"]
        d["revenue"] += r["amount"]
        if r["kind"] == "booking":
            d["count"] += 1
            d["hours"] += r["hours"]
    out = list(days.values())
    for d in out:
        d["occupancy"] = round(100 * d.pop("hours") / (lot["capacity"] * 24), 1)
    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["วันที่", "จำนวนรายการ", "จอดเลย", "จองล่วงหน้า", "ค่าส่วนเกิน", "รายได้รวม", "อัตราการใช้ช่อง(%)"])
        for d in out:
            w.writerow([d["date"], d["count"], d["now"], d["advance"], d["overstay"], d["revenue"], d["occupancy"]])
        w.writerow(["รวม", sum(d["count"] for d in out), "", "", "", sum(d["revenue"] for d in out), ""])
        return Response("﻿" + buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": f"attachment; filename=parkq-{lot_id}-{date_from}-{date_to}.csv"})
    return {"days": out, "total": sum(d["revenue"] for d in out), "count": sum(d["count"] for d in out)}


# ---------------------------------------------------------------- pages

@app.get("/api/config")
def config():
    return {"dev": DEV_MODE, "demo_payment": not PROMPTPAY_ID}


@app.get("/api/dev/login")
def dev_login(role: str, conn=Depends(get_db)):
    """Development only: sign in as a seed user (used by demos and documentation screenshots)."""
    if not DEV_MODE or PUBLIC:
        raise ApiError(404, "NOT_FOUND", "ไม่พบ")
    user = conn.execute("SELECT * FROM users WHERE role=? ORDER BY id LIMIT 1", (role,)).fetchone()
    if not user:
        raise ApiError(404, "NO_SEED_USER", "ไม่พบผู้ใช้ทดสอบ")
    token = secrets.token_urlsafe(24)
    conn.execute("INSERT INTO sessions VALUES (?,?,?)", (token, user["id"], now()))
    return {"token": token, "user": dict(user)}


for page, file in (("gate", "gate.html"), ("staff", "admin.html"), ("admin", "admin.html"), ("twin", "twin.html")):
    app.add_api_route(f"/{page}", (lambda f=file: FileResponse(STATIC / f)), methods=["GET"], include_in_schema=False)
app.add_api_route("/", lambda: FileResponse(STATIC / "index.html"), methods=["GET"], include_in_schema=False)
app.mount("/static", StaticFiles(directory=STATIC), name="static")

db.init(reset=os.environ.get("PARKQ_RESET") == "1")
