"""SQLite storage for ParkQ (PostgreSQL in production; the schema is plain SQL so it ports directly)."""
import os
import random
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(os.environ.get("PARKQ_DB", Path(__file__).resolve().parent / "parkq.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, phone TEXT UNIQUE NOT NULL, name TEXT, email TEXT,
  role TEXT NOT NULL DEFAULT 'driver', created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS otps (
  id INTEGER PRIMARY KEY, phone TEXT NOT NULL, code TEXT NOT NULL, created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, used INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS vehicles (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, plate TEXT NOT NULL, province TEXT NOT NULL,
  type TEXT NOT NULL DEFAULT 'car', is_primary INTEGER NOT NULL DEFAULT 0, UNIQUE(user_id, plate));
CREATE TABLE IF NOT EXISTS lots (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, address TEXT NOT NULL, lat REAL, lng REAL,
  capacity INTEGER NOT NULL, rate INTEGER NOT NULL, open_time TEXT NOT NULL DEFAULT '00:00',
  close_time TEXT NOT NULL DEFAULT '24:00', advance_ratio INTEGER NOT NULL DEFAULT 50,
  online INTEGER NOT NULL DEFAULT 1, device_id TEXT, device_key TEXT, last_seen INTEGER,
  owner_id INTEGER, photo TEXT);
CREATE TABLE IF NOT EXISTS slots (
  lot_id TEXT NOT NULL, slot_no INTEGER NOT NULL, zone TEXT NOT NULL, occupied INTEGER NOT NULL DEFAULT 0,
  updated_at INTEGER, PRIMARY KEY(lot_id, slot_no));
CREATE TABLE IF NOT EXISTS tickets (
  id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, vehicle_id INTEGER NOT NULL, lot_id TEXT NOT NULL,
  mode TEXT NOT NULL, start_at INTEGER NOT NULL, end_at INTEGER NOT NULL, hours INTEGER NOT NULL,
  rate INTEGER NOT NULL, amount INTEGER NOT NULL, status TEXT NOT NULL, hold_until INTEGER,
  token TEXT, entered_at INTEGER, exited_at INTEGER, overstay_fee INTEGER NOT NULL DEFAULT 0,
  refund INTEGER NOT NULL DEFAULT 0, cancel_reason TEXT, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS payments (
  id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL, kind TEXT NOT NULL, method TEXT NOT NULL,
  amount INTEGER NOT NULL, status TEXT NOT NULL, created_at INTEGER NOT NULL, paid_at INTEGER, expires_at INTEGER);
CREATE TABLE IF NOT EXISTS gate_logs (
  id INTEGER PRIMARY KEY, lot_id TEXT NOT NULL, gate TEXT NOT NULL, ticket_id TEXT, plate TEXT,
  result TEXT NOT NULL, method TEXT NOT NULL, staff_id INTEGER, reason TEXT, at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS gate_commands (
  id INTEGER PRIMARY KEY, lot_id TEXT NOT NULL, gate TEXT NOT NULL, command TEXT NOT NULL,
  created_at INTEGER NOT NULL, done INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY, lot_id TEXT NOT NULL, gate TEXT NOT NULL, message TEXT, at INTEGER NOT NULL,
  resolved INTEGER NOT NULL DEFAULT 0);
"""

LOTS = [
    # id, name, address, lat, lng, capacity, rate, open, close, occupied, device
    ("LOT01", "ลานจอด ParkQ – ม.ศรีปทุม บางเขน", "2410/2 ถ.พหลโยธิน แขวงเสนานิคม เขตจตุจักร กรุงเทพฯ",
     13.8566, 100.5850, 50, 20, "00:00", "24:00", 27, None),
    ("LOT02", "โมเดลลานจอด IoT (บอร์ด ParkQ Gate)", "ห้องปฏิบัติการ อาคาร 11 ม.ศรีปทุม",
     13.8628, 100.5905, 4, 10, "00:00", "24:00", 1, "ESP32-GATE-01"),
    ("LOT03", "อาคารจอดรถ ตลาดบางเขน", "ถ.พหลโยธิน แขวงอนุสาวรีย์ เขตบางเขน กรุงเทพฯ",
     13.8730, 100.5960, 120, 30, "05:00", "22:00", 112, None),
    ("LOT04", "ลานจอด สถานีรถไฟฟ้าพหลโยธิน 59", "ถ.พหลโยธิน แขวงอนุสาวรีย์ เขตบางเขน กรุงเทพฯ",
     13.8840, 100.6010, 80, 25, "05:30", "24:00", 80, None),
]

SEED_USERS = [  # phone, name, role
    ("0800000001", "ผู้ดูแล ParkQ", "admin"),
    ("0800000002", "พนักงานหน้าลาน", "attendant"),
    ("0891234567", "สมชาย ใจดี", "driver"),
]


def connect() -> sqlite3.Connection:
    # Each request owns its connection, but FastAPI may open it and use it on different worker threads (DEF-05).
    conn = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init(reset: bool = False):
    if reset:
        for suffix in ("", "-wal", "-shm"):
            Path(str(DB_PATH) + suffix).unlink(missing_ok=True)
    conn = connect()
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM lots").fetchone()[0] == 0:
        seed(conn)
    conn.close()


def seed(conn):
    now = int(time.time())
    rnd = random.Random(7)
    for phone, name, role in SEED_USERS:
        conn.execute("INSERT INTO users(phone,name,role,created_at) VALUES (?,?,?,?)", (phone, name, role, now))
    admin_id = conn.execute("SELECT id FROM users WHERE role='admin'").fetchone()[0]
    driver_id = conn.execute("SELECT id FROM users WHERE phone='0891234567'").fetchone()[0]
    conn.execute("INSERT INTO vehicles(user_id,plate,province,type,is_primary) VALUES (?,?,?,?,1)",
                 (driver_id, "กข 1234", "กรุงเทพมหานคร", "car"))
    for lid, name, addr, lat, lng, cap, rate, op, cl, occ, dev in LOTS:
        conn.execute("""INSERT INTO lots(id,name,address,lat,lng,capacity,rate,open_time,close_time,
                        device_id,device_key,last_seen,owner_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (lid, name, addr, lat, lng, cap, rate, op, cl, dev, "dev-key-" + lid if dev else None,
                      now if dev else None, admin_id))
        taken = set(rnd.sample(range(1, cap + 1), occ))
        zones = "ABCD"
        per_zone = max(1, -(-cap // (4 if cap >= 20 else 1)))
        for n in range(1, cap + 1):
            conn.execute("INSERT INTO slots VALUES (?,?,?,?,?)",
                         (lid, n, zones[(n - 1) // per_zone], 1 if n in taken else 0, now))
    # revenue history for the admin report (last 14 days)
    for day in range(14, 0, -1):
        for k in range(rnd.randint(6, 18)):
            start = now - day * 86400 + rnd.randint(7, 20) * 3600
            hours = rnd.randint(1, 4)
            tid = f"TK-H{day:02d}{k:02d}"
            mode = rnd.choice(["now", "now", "advance"])
            conn.execute("""INSERT INTO tickets(id,user_id,vehicle_id,lot_id,mode,start_at,end_at,hours,rate,amount,
                            status,entered_at,exited_at,created_at) VALUES (?,?,1,'LOT01',?,?,?,?,20,?,'DONE',?,?,?)""",
                         (tid, driver_id, mode, start, start + hours * 3600, hours, hours * 20, start,
                          start + hours * 3600, start - 600))
            conn.execute("INSERT INTO payments VALUES (?,?,?,?,?,?,?,?,?)",
                         ("PM-" + tid[3:], tid, "booking", "promptpay", hours * 20, "PAID", start - 600, start - 590, None))
