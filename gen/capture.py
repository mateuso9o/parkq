"""Capture annotated screenshots of the real ParkQ web app for W6/W7.

Needs a fresh dev server:  PARKQ_RESET=1 python -m uvicorn server:app --app-dir app --host 127.0.0.1 --port 8000
Then:                      python gen/capture.py
"""
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from screens_data import SCREENS

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:8000"
CLEAN = os.environ.get("PARKQ_CLEAN") == "1"           # screenshots without element markers (for slides)
IMG = ROOT / "build" / ("clean" if CLEAN else "img")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DB = ROOT / "app" / "parkq.db"


def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or b"null")


def fixtures() -> dict:
    """Create the tickets each screenshot needs, through the same API the app uses."""
    tok = call("GET", "/api/dev/login?role=driver")["token"]
    vid = call("GET", "/api/vehicles", token=tok)[0]["id"]

    def book(mode="now", hours=2, start=None, pay=True):
        t = call("POST", "/api/bookings", {"lot_id": "LOT01", "mode": mode, "hours": hours, "vehicle_id": vid, "start_at": start}, tok)
        if pay:
            p = call("POST", "/api/payments", {"ticket_id": t["id"], "method": "promptpay"}, tok)
            call("POST", f"/api/payments/{p['id']}/simulate")
        return call("GET", f"/api/tickets/{t['id']}", token=tok)

    f = {}
    overdue = book(hours=1)
    call("POST", "/api/gate/LOT01/in/scan", {"token": overdue["token"]})
    # Pretend this car arrived on a 1-hour ticket that ended 70 minutes ago, so the exit kiosk asks for the overstay fee.
    # The ticket times live inside the signed QR, so the fixture re-issues the token with the dev secret.
    sys.path.insert(0, str(ROOT / "code"))
    import parkq_core
    from datetime import datetime
    now = int(time.time())
    start, end = now - 7800, now - 4200
    token = parkq_core.make_ticket_token(overdue["id"], "LOT01", datetime.fromtimestamp(start), datetime.fromtimestamp(end), b"parkq-dev-secret")
    con = sqlite3.connect(DB)
    con.execute("UPDATE tickets SET start_at=?, end_at=?, entered_at=?, token=? WHERE id=?", (start, end, start + 100, token, overdue["id"]))
    con.commit()
    con.close()
    f["overdue"] = token
    f["entry"] = book()["token"]
    f["waiting"] = book()["id"]
    f["advance"] = book("advance", 3, int(time.time()) // 900 * 900 + 3 * 3600)["id"]
    pending = book(pay=False)
    f["pending"] = pending["id"]
    f["payment"] = call("POST", "/api/payments", {"ticket_id": pending["id"], "method": "promptpay"}, tok)["id"]
    f["plate"] = urllib.parse.quote("กข1234")
    call("POST", "/api/gate/LOT01/in/call")
    return f


def with_annotate(url: str) -> str:
    if CLEAN:
        return BASE + url
    path, _, frag = url.partition("#")
    path += ("&" if "?" in path else "?") + "annotate=1"
    return BASE + path + (("#" + frag) if frag else "")


PHONE_W = 480   # the driver app column (max-width of .shell)


def shoot(code, url, size):
    """Headless Chrome cannot go narrower than ~500px, so phone screens render at 600px and are cropped to the app column."""
    out = IMG / f"{code}.png"
    if size[0] < 500:
        size = (600, 1040 if CLEAN else size[1])   # slides use a real phone aspect (about 9:19.5)
    profile = ROOT / "build" / "chrome" / code
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
           f"--user-data-dir={profile}", f"--window-size={size[0]},{size[1]}", f"--screenshot={out}",
           "--virtual-time-budget=6000", "--run-all-compositor-stages-before-draw", url]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    import urllib.parse  # noqa: F401
    IMG.mkdir(parents=True, exist_ok=True)
    f = fixtures()
    only = set(sys.argv[1:])
    procs = []
    # The gate success shot consumes its ticket and the overstay shot creates a payment, so they run one at a time.
    for s in SCREENS:
        if only and s["code"] not in only:
            continue
        url = with_annotate(s["url"].format(**f))
        procs.append(shoot(s["code"], url, s["size"]))
        if len(procs) >= 4 or "token=" in url:
            for p in procs:
                p.wait()
            procs = []
    for p in procs:
        p.wait()
    from PIL import Image
    for s in SCREENS:
        if s["size"][0] < 500 and (not only or s["code"] in only):
            path = IMG / f"{s['code']}.png"
            im = Image.open(path)
            x0 = (im.width - PHONE_W * 2) // 2
            im.crop((x0, 0, x0 + PHONE_W * 2, im.height)).save(path)
    print("captured", len(list(IMG.glob("SC-*.png"))), "screens")
