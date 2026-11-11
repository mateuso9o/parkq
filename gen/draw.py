"""Render wireframes, screen flows, workflows and the architecture diagram to PNG via headless Chrome."""
import hashlib
import html
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from spec_data import SCREENS, FLOWS, MAIN_FLOW, MODULES

ROOT = Path(__file__).resolve().parent.parent
HTML_DIR = ROOT / "build" / "html"
IMG_DIR = ROOT / "build" / "img"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

FRAME_SIZE = {"phone": (390, 800), "modal": (390, 800), "kiosk": (800, 480),
              "desktop": (1200, 760), "dmodal": (1200, 760)}

BASE_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Leelawadee UI','Tahoma',sans-serif;background:#fff;color:#1d2433;font-size:15px}
.n{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;
   background:#e5484d;color:#fff;font-size:11px;font-weight:700;flex:none;margin-right:6px}
.el{display:flex;align-items:flex-start;margin:8px 0}
.el>.body{flex:1;min-width:0}
.cap{font-size:12px;color:#5b6475;margin-bottom:3px}
.input{border:1.5px solid #c9d1e0;border-radius:8px;padding:9px 11px;color:#8a93a5;background:#fff;
       display:flex;justify-content:space-between;font-size:14px}
.btn{background:#1e5eff;color:#fff;border-radius:10px;padding:11px;text-align:center;font-weight:600}
.btn.sec{background:#fff;color:#1e5eff;border:1.5px solid #1e5eff}
.lbl{font-size:14px}
.lbl b{font-weight:600}
.link{color:#1e5eff;text-decoration:underline;font-size:14px}
.img{background:#e8ecf4;border-radius:10px;height:90px;display:flex;align-items:center;justify-content:center;color:#7b859a;font-size:13px}
.map{background:repeating-linear-gradient(0deg,#eef2f8 0 22px,#e2e8f2 22px 23px),repeating-linear-gradient(90deg,transparent 0 22px,#e2e8f2 22px 23px);
     background-blend-mode:multiply;border-radius:10px;height:150px;position:relative;overflow:hidden}
.pin{position:absolute;width:16px;height:16px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);border:2px solid #fff}
.pill{display:inline-block;padding:6px 12px;border-radius:999px;background:#eef2fb;color:#3b4a66;font-size:13px;margin:0 4px 4px 0}
.pill.on{background:#1e5eff;color:#fff}
.badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600;margin-right:4px}
.g{background:#dff6e7;color:#137a3a}.o{background:#fff0d9;color:#a35a00}.r{background:#fde2e2;color:#b42318}
.card{border:1px solid #dde3ee;border-radius:10px;padding:9px 11px;margin-bottom:6px;font-size:13px}
.card b{font-size:14px}
table{border-collapse:collapse;width:100%;font-size:12px}
th{background:#eef2fb;text-align:left;padding:6px;border:1px solid #dde3ee}
td{padding:6px;border:1px solid #dde3ee;color:#8a93a5}
.qr{display:grid;gap:0;margin:0 auto;border:8px solid #fff;outline:1px solid #dde3ee}
.qr i{display:block}
.chk{display:flex;align-items:center;font-size:14px}.box{width:18px;height:18px;border:1.5px solid #8a93a5;border-radius:4px;margin-right:8px}
.radio{display:flex;gap:16px;font-size:14px}.radio span:before{content:'';display:inline-block;width:14px;height:14px;border-radius:50%;
       border:1.5px solid #8a93a5;margin-right:6px;vertical-align:-2px}.radio span.on:before{border:5px solid #1e5eff}
.toggle{width:44px;height:24px;border-radius:12px;background:#1e5eff;position:relative}.toggle:after{content:'';position:absolute;right:3px;top:3px;width:18px;height:18px;border-radius:50%;background:#fff}
.bars{display:flex;align-items:flex-end;gap:8px;height:120px;border-bottom:1px solid #c9d1e0;padding:0 6px}
.bars i{flex:1;background:#1e5eff;border-radius:4px 4px 0 0;opacity:.85}
.scanner{border:2px dashed #8a93a5;border-radius:12px;padding:14px;text-align:center;color:#5b6475}
"""


def qr_html(seed: str, size: int = 160, n: int = 25) -> str:
    """Deterministic fake QR pattern with three finder squares."""
    h = hashlib.sha256(seed.encode()).digest() * 40
    cell = size // n
    cells = []
    for y in range(n):
        for x in range(n):
            finder = None
            for fx, fy in ((0, 0), (n - 7, 0), (0, n - 7)):
                if fx <= x < fx + 7 and fy <= y < fy + 7:
                    dx, dy = x - fx, y - fy
                    finder = dx in (0, 6) or dy in (0, 6) or (2 <= dx <= 4 and 2 <= dy <= 4)
            on = finder if finder is not None else (h[y * n + x] & 1)
            cells.append(f"<i style='background:{'#111' if on else '#fff'}'></i>")
    return (f"<div class='qr' style='grid-template-columns:repeat({n},{cell}px);grid-auto-rows:{cell}px;"
            f"width:{cell * n + 16}px'>{''.join(cells)}</div>")


def clean_btn(name: str) -> str:
    return name.replace("ปุ่ม", "").replace("\"", "").replace("บนการ์ด", "").strip()


def render_element(i: int, el, frame: str, code: str) -> str:
    name, typ, req, domain, _ = el
    e = html.escape
    num = f"<span class='n'>{i}</span>"
    star = " <span style='color:#e5484d'>*</span>" if req.startswith("Y") else ""
    opts = [o.strip() for o in domain.split("/")] if "/" in domain else []
    if typ == "Label":
        text = domain.strip("\"") if domain else name
        if domain.startswith("\"") or not domain:
            inner = f"<div class='lbl'>{e(text)}</div>"
        else:
            inner = f"<div class='lbl'><b>{e(name)}:</b> {e(domain)}</div>"
    elif typ in ("Text Input", "Number Input", "Date Picker", "Time Picker", "Dropdown List"):
        icon = {"Dropdown List": "▾", "Date Picker": "▦", "Time Picker": "◷", "Number Input": "−  +"}.get(typ, "")
        inner = f"<div class='cap'>{e(name)}{star}</div><div class='input'><span>{e(domain or name)}</span><span>{icon}</span></div>"
    elif typ == "Button":
        label = clean_btn(name)
        sec = " sec" if any(k in label for k in ("ยกเลิก", "แก้ไข", "ไม่", "ลบ", "ย้อน", "บันทึก QR", "นำทาง", "เรียก", "ขอรหัสใหม่", "จองล่วงหน้า")) else ""
        inner = f"<div class='btn{sec}'>{e(label)}</div>"
    elif typ == "Link":
        inner = f"<div class='link'>{e(clean_btn(name))}</div>"
    elif typ == "Checkbox":
        inner = f"<div class='chk'><span class='box'></span>{e(name)}{star}</div>"
    elif typ == "Radio Button":
        inner = f"<div class='cap'>{e(name)}{star}</div><div class='radio'>" + "".join(
            f"<span class='{'on' if k == 0 else ''}'>{e(o)}</span>" for k, o in enumerate(opts)) + "</div>"
    elif typ == "Tab":
        inner = "".join(f"<span class='pill{' on' if k == 0 else ''}'>{e(o)}</span>" for k, o in enumerate(opts))
    elif typ == "Badge":
        if opts:
            inner = "".join(f"<span class='badge {'gor'[k % 3]}'>{e(o)}</span>" for k, o in enumerate(opts))
        else:
            inner = f"<span class='lbl'><b>{e(name)}:</b></span> <span class='badge g'>{e(domain)}</span>"
    elif typ == "Image":
        inner = f"<div class='img' style='height:{60 if 'ไอคอน' in name or 'โลโก้' in name else 90}px'>{e(name)}</div>"
    elif typ == "QR Code":
        inner = qr_html(code + name, 150 if frame == "kiosk" else 190) + f"<div class='cap' style='text-align:center;margin-top:4px'>{e(name)}</div>"
    elif typ == "QR Scanner":
        inner = f"<div class='scanner'>▣ {e(name)} – {e(domain)}</div>"
    elif typ == "Map":
        h = 150 if frame in ("phone", "modal") else 220
        pins = "".join(f"<span class='pin' style='left:{x}%;top:{y}%;background:{c}'></span>"
                       for x, y, c in ((20, 30, '#22a35a'), (55, 50, '#f59f0b'), (75, 25, '#e5484d'), (35, 70, '#22a35a'), (85, 70, '#9aa3b2')))
        inner = f"<div class='map' style='height:{h}px'>{pins}</div>"
    elif typ == "List":
        fields = [f.strip() for f in domain.split(",")]
        inner = "".join(f"<div class='card'><b>{e(fields[0])} {k + 1}</b><br>{e(' • '.join(fields[1:]))}</div>" for k in range(2))
    elif typ == "Table":
        cols = [c.strip() for c in domain.split(",")][:6]
        rows = "".join("<tr>" + "".join("<td>…</td>" for _ in cols) + "</tr>" for _ in range(3))
        inner = f"<div class='cap'>{e(name)}</div><table><tr>{''.join(f'<th>{e(c)}</th>' for c in cols)}</tr>{rows}</table>"
    elif typ == "Toggle":
        inner = f"<div class='chk'><span class='toggle'></span>&nbsp; {e(name)}</div>"
    elif typ == "Chart":
        bars = "".join(f"<i style='height:{h}%'></i>" for h in (40, 65, 52, 80, 70, 95, 60, 75, 88, 50))
        inner = f"<div class='cap'>{e(name)}</div><div class='bars'>{bars}</div>"
    else:  # System Action: not visible
        return ""
    return f"<div class='el'>{num}<div class='body'>{inner}</div></div>"


def screen_html(s) -> str:
    frame = s["frame"]
    w, h = FRAME_SIZE[frame]
    els = s["elements"]
    bottom_tab = [i for i, el in enumerate(els) if "เมนูล่าง" in el[0]]
    side_tab = [i for i, el in enumerate(els) if "เมนูด้านข้าง" in el[0]]
    body_items = [render_element(i + 1, el, frame, s["code"]) for i, el in enumerate(els)
                  if i not in bottom_tab and i not in side_tab]
    title = html.escape(s["name"])
    if frame in ("phone", "modal"):
        content = (f"<div style='background:#1e5eff;color:#fff;padding:14px 16px;font-weight:600'>ParkQ · {title}</div>"
                   f"<div style='padding:6px 16px'>{''.join(body_items)}</div>")
        if bottom_tab:
            content += (f"<div style='position:absolute;bottom:0;left:0;right:0;border-top:1px solid #dde3ee;padding:8px;background:#fff'>"
                        f"{render_element(bottom_tab[0] + 1, els[bottom_tab[0]], frame, s['code'])}</div>")
        page = f"<div style='position:relative;width:{w}px;height:{h}px;overflow:hidden'>{content}</div>"
        if frame == "modal":
            page = (f"<div style='position:relative;width:{w}px;height:{h}px;background:#5d6577'>"
                    f"<div style='position:absolute;left:18px;right:18px;top:90px;background:#fff;border-radius:16px;overflow:hidden;"
                    f"box-shadow:0 10px 30px rgba(0,0,0,.3)'><div style='padding:14px 16px;font-weight:700;border-bottom:1px solid #dde3ee'>{title}</div>"
                    f"<div style='padding:6px 16px 14px'>{''.join(body_items)}</div></div></div>")
    elif frame == "kiosk":
        page = (f"<div style='width:{w}px;height:{h}px;background:#0f1a33;padding:16px'>"
                f"<div style='background:#fff;border-radius:12px;height:100%;padding:12px 20px;display:grid;grid-template-columns:1fr 1fr;gap:0 24px;align-content:start'>"
                f"<div style='grid-column:1/3;font-weight:700;font-size:18px;color:#1e5eff;margin-bottom:4px'>ตู้ ParkQ Gate · {title}</div>"
                f"{''.join(body_items)}</div></div>")
    else:  # desktop / dmodal
        side = ""
        menu_num = f"<span class='n' style='margin-left:8px'>{side_tab[0] + 1}</span>" if side_tab else ""
        menu ="".join(f"<div style='padding:10px 14px;border-radius:8px;{'background:#1e5eff;color:#fff' if k == 0 else 'color:#c9d3ea'}'>{m}</div>"
                       for k, m in enumerate(["แดชบอร์ด", "ลานจอด", "ราคา", "รายงาน"]))
        main = (f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:0 28px'>{''.join(body_items)}</div>")
        page = (f"<div style='display:flex;width:{w}px;height:{h}px'>"
                f"<div style='width:200px;background:#13203f;color:#fff;padding:16px'><div style='font-weight:700;font-size:18px;margin-bottom:16px'>ParkQ Admin{menu_num}</div>{menu}{side}</div>"
                f"<div style='flex:1;background:#f5f7fb;padding:18px 24px'><div style='font-size:20px;font-weight:700;margin-bottom:8px'>{title}</div>"
                f"<div style='background:#fff;border-radius:12px;padding:12px 18px'>{main}</div></div></div>")
        if frame == "dmodal":
            page = (f"<div style='position:relative;width:{w}px;height:{h}px;background:#5d6577'>"
                    f"<div style='position:absolute;left:300px;right:300px;top:40px;background:#fff;border-radius:16px;padding:6px 22px 16px'>"
                    f"<div style='padding:12px 0;font-weight:700;font-size:18px;border-bottom:1px solid #dde3ee'>{title}</div>{''.join(body_items)}</div></div>")
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{BASE_CSS}</style></head><body>{page}</body></html>"


# ---------------- generic SVG diagram helpers ----------------

def svg_page(svg: str, w: int, h: int) -> str:
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{BASE_CSS} text{{font-family:'Leelawadee UI'}}</style></head>"
            f"<body style='width:{w}px;height:{h}px'>{svg}</body></html>")


ARROW_DEF = ("<defs><marker id='a' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='8' markerHeight='8' orient='auto'>"
             "<path d='M0,0 L10,5 L0,10 z' fill='#33415c'/></marker></defs>")


def wrap_text(text: str, width_chars: int):
    words, lines, cur = text.split(" "), [], ""
    for wd in words:
        if len(cur) + len(wd) + 1 > width_chars and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = (cur + " " + wd).strip()
    lines.append(cur)
    return lines


def text_block(cx, cy, text, size=14, chars=22, weight=400, fill="#1d2433"):
    lines = wrap_text(text, chars)
    lh = size * 1.35
    y0 = cy - (len(lines) - 1) * lh / 2
    return "".join(f"<text x='{cx}' y='{y0 + k * lh}' font-size='{size}' font-weight='{weight}' fill='{fill}' "
                   f"text-anchor='middle' dominant-baseline='middle'>{html.escape(l)}</text>" for k, l in enumerate(lines))


def flowchart(nodes, edges, title):
    """nodes: id -> (shape, text, col, row). shapes: term, proc, dec, io. edges: (a, b, label, side)."""
    CW, RH, NW, NH, PAD = 270, 105, 210, 62, 30
    cols = max(n[2] for n in nodes.values()) + 1
    rows = max(n[3] for n in nodes.values()) + 1
    W, H = PAD * 2 + cols * CW, PAD * 2 + 40 + rows * RH
    pos = {k: (PAD + c * CW + CW / 2, PAD + 40 + r * RH + RH / 2) for k, (_, _, c, r) in nodes.items()}
    out = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}'>{ARROW_DEF}"
           f"<rect width='{W}' height='{H}' fill='#fff'/>{text_block(W / 2, PAD + 6, title, 18, 200, 700)}"]
    for a, b, label, *rest in edges:
        (x1, y1), (x2, y2) = pos[a], pos[b]
        sa = nodes[a][0]
        if rest and rest[0] == "downleft":
            sx, sy = x1, y1 + NH / 2
            d = f"M{sx},{sy} L{sx},{y2} L{x2 + NW / 2},{y2}"
            lx, ly = sx + 26, sy + 14
        elif rest and rest[0] == "right" and abs(y2 - y1) < 1:
            sx, sy = x1 + NW / 2, y1
            d = f"M{sx},{sy} L{x2 - NW / 2},{y2}"
            lx, ly = sx + 26, sy - 10
        elif rest and rest[0] == "right":
            sx, sy = x1 + NW / 2, y1
            ex, ey = (x2, y2 - NH / 2) if y2 > y1 else (x2 + NW / 2, y2)
            if y2 > y1:
                d = f"M{sx},{sy} L{ex},{sy} L{ex},{ey}"
            else:
                mx = max(sx, ex) + 24
                d = f"M{sx},{sy} L{mx},{sy} L{mx},{ey} L{ex},{ey}"
            lx, ly = sx + 26, sy - 10
        elif rest and rest[0] == "left":
            sx, sy = x1 - NW / 2, y1
            mx = min(sx, x2 - NW / 2) - 24
            d = f"M{sx},{sy} L{mx},{sy} L{mx},{y2} L{x2 - NW / 2},{y2}"
            lx, ly = sx - 26, sy - 10
        elif abs(x1 - x2) < 1:
            d = f"M{x1},{y1 + NH / 2} L{x2},{y2 - NH / 2}"
            lx, ly = x1 + 22, y1 + NH / 2 + 14
        else:
            my = (y1 + NH / 2 + y2 - NH / 2) / 2
            d = f"M{x1},{y1 + NH / 2} L{x1},{my} L{x2},{my} L{x2},{y2 - NH / 2}"
            lx, ly = x1 + 22, y1 + NH / 2 + 14
        out.append(f"<path d='{d}' fill='none' stroke='#33415c' stroke-width='1.6' marker-end='url(#a)'/>")
        if label:
            out.append(f"<text x='{lx}' y='{ly}' font-size='13' font-weight='700' fill='#b42318' text-anchor='middle'>{html.escape(label)}</text>")
    for k, (shape, text, _, _) in nodes.items():
        x, y = pos[k]
        if shape == "term":
            out.append(f"<rect x='{x - NW / 2}' y='{y - NH / 2}' width='{NW}' height='{NH}' rx='31' fill='#dff6e7' stroke='#137a3a' stroke-width='1.6'/>")
        elif shape == "dec":
            out.append(f"<polygon points='{x},{y - NH / 2 - 8} {x + NW / 2},{y} {x},{y + NH / 2 + 8} {x - NW / 2},{y}' fill='#fff0d9' stroke='#a35a00' stroke-width='1.6'/>")
        elif shape == "io":
            out.append(f"<polygon points='{x - NW / 2 + 16},{y - NH / 2} {x + NW / 2},{y - NH / 2} {x + NW / 2 - 16},{y + NH / 2} {x - NW / 2},{y + NH / 2}' fill='#eef2fb' stroke='#1e5eff' stroke-width='1.6'/>")
        else:
            out.append(f"<rect x='{x - NW / 2}' y='{y - NH / 2}' width='{NW}' height='{NH}' rx='6' fill='#fff' stroke='#1e5eff' stroke-width='1.6'/>")
        out.append(text_block(x, y, text, 13, 30 if shape != "dec" else 24))
    out.append("</svg>")
    return "".join(out), W, H


WORKFLOWS = {
    "wf1_booking": ("Workflow 1: ค้นหาลานจอด ซื้อสิทธิ์/จองที่จอด และชำระเงิน", {
        "s": ("term", "ผู้ใช้เปิด ParkQ", 0, 0),
        "d1": ("dec", "เข้าสู่ระบบแล้ว?", 0, 1),
        "login": ("proc", "เข้าสู่ระบบด้วยอีเมล + OTP (ACC_01)", 1, 1),
        "find": ("proc", "ค้นหาลานจอดและดูสถานะ ว่าง/ใกล้เต็ม/เต็ม (LOT_01)", 0, 2),
        "d2": ("dec", "ลานมีช่องว่าง?", 0, 3),
        "other": ("proc", "เลือกลานอื่นหรือเปลี่ยนเวลา", 1, 3),
        "sel": ("io", "เลือก จอดเลย/จองล่วงหน้า รถ และจำนวนชั่วโมง", 0, 4),
        "lock": ("proc", "ระบบตรวจช่องว่างและล็อกช่อง 10 นาที", 0, 5),
        "pay": ("io", "ชำระเงิน QR พร้อมเพย์ / บัตร (BKG_03)", 0, 6),
        "d3": ("dec", "ชำระสำเร็จภายในเวลา?", 0, 7),
        "cancel": ("proc", "ยกเลิกรายการ คืนช่องให้ลาน", 1, 7),
        "ticket": ("proc", "ออกตั๋ว QR (E-Ticket) ส่งให้ผู้ใช้", 0, 8),
        "e": ("term", "สิ้นสุด", 0, 9),
    }, [("s", "d1", ""), ("d1", "login", "ไม่", "right"), ("login", "find", "", "downleft"), ("d1", "find", "ใช่"),
        ("find", "d2", ""), ("d2", "other", "ไม่", "right"), ("other", "find", "", "right"), ("d2", "sel", "ใช่"),
        ("sel", "lock", ""), ("lock", "pay", ""), ("pay", "d3", ""), ("d3", "cancel", "ไม่", "right"),
        ("d3", "ticket", "ใช่"), ("cancel", "e", "", "downleft"), ("ticket", "e", "")]),
    "wf2_gate": ("Workflow 2: เข้า-ออกลานจอดด้วย QR Code", {
        "s": ("term", "ผู้ใช้มาถึงประตูทางเข้า", 0, 0),
        "scan": ("io", "สแกน QR ตั๋วที่ตู้ ParkQ Gate (TKT_02)", 0, 1),
        "chk": ("proc", "ตรวจลายมือชื่อ ลาน เวลา การใช้ซ้ำ", 0, 2),
        "d1": ("dec", "QR ถูกต้อง?", 0, 3),
        "why": ("proc", "แสดงเหตุผล ผู้ใช้กดเรียกพนักงาน", 1, 3),
        "staff": ("proc", "พนักงานตรวจสอบตั๋วและเปิดไม้กั้น (TKT_04)", 1, 4),
        "open": ("proc", "เปิดไม้กั้นทางเข้า ตั๋ว = จอดอยู่", 0, 4),
        "park": ("proc", "จอดรถ เซ็นเซอร์อัปเดตสถานะช่อง", 0, 5),
        "out": ("io", "สแกน QR เดิมที่ประตูทางออก (TKT_03)", 0, 6),
        "d2": ("dec", "เกินเวลาเกิน 15 นาที?", 0, 7),
        "fee": ("io", "ชำระค่าส่วนเกินด้วย QR พร้อมเพย์ที่ตู้", 1, 7),
        "exit": ("proc", "เปิดไม้กั้นทางออก ตั๋ว = เสร็จสิ้น", 0, 8),
        "e": ("term", "สิ้นสุด", 0, 9),
    }, [("s", "scan", ""), ("scan", "chk", ""), ("chk", "d1", ""), ("d1", "why", "ไม่", "right"), ("why", "staff", ""),
        ("staff", "park", "", "downleft"), ("d1", "open", "ใช่"), ("open", "park", ""), ("park", "out", ""), ("out", "d2", ""),
        ("d2", "fee", "ใช่", "right"), ("fee", "exit", "", "downleft"), ("d2", "exit", "ไม่"), ("exit", "e", "")]),
    "wf3_iot": ("Workflow 3: อัปเดตสถานะช่องจอดจากเซ็นเซอร์ IoT", {
        "s": ("term", "เซ็นเซอร์ตรวจพบรถเข้า/ออกช่องจอด", 0, 0),
        "led": ("proc", "ESP32 เปลี่ยนไฟ LED ช่อง (เขียว/แดง)", 0, 1),
        "mqtt": ("io", "ส่งสถานะช่องผ่าน Device API (POST /api/iot/{lot}/slots)", 0, 2),
        "d1": ("dec", "Server ได้รับข้อมูลภายใน 2 นาที?", 0, 3),
        "stale": ("proc", "ทำเครื่องหมาย \"ข้อมูลไม่เป็นปัจจุบัน\" ปิดการขายชั่วคราว", 1, 3),
        "calc": ("proc", "คำนวณช่องว่าง (BR-03) และสถานะ (BR-04)", 0, 4),
        "push": ("proc", "บันทึกฐานข้อมูล หน้าเว็บดึงข้อมูลใหม่ทุก 5 วินาที", 0, 5),
        "ui": ("proc", "หน้าแรกผู้ใช้ / แดชบอร์ดผู้ดูแล / จอที่ตู้ อัปเดตทันที", 0, 6),
        "e": ("term", "สิ้นสุด", 0, 7),
    }, [("s", "led", ""), ("led", "mqtt", ""), ("mqtt", "d1", ""), ("d1", "stale", "ไม่", "right"), ("stale", "ui", "", "downleft"),
        ("d1", "calc", "ใช่"), ("calc", "push", ""), ("push", "ui", ""), ("ui", "e", "")]),
}


WORKFLOWS["wf4_admin"] = ("Workflow 4: ผู้ดูแลตั้งค่าลานจอดและติดตามรายได้", {
    "s": ("term", "ผู้ดูแลเข้าสู่ระบบหลังบ้าน", 0, 0),
    "d1": ("dec", "มีลานจอดในระบบแล้ว?", 0, 1),
    "add": ("io", "เพิ่มลานจอด: ชื่อ ที่อยู่ พิกัด จำนวนช่อง เวลาเปิด รหัสอุปกรณ์", 1, 1),
    "rate": ("io", "กำหนดราคาต่อชั่วโมงและสัดส่วนช่องจองล่วงหน้า", 0, 2),
    "online": ("proc", "เปิดขายออนไลน์ ลานแสดงในแอปผู้ขับขี่", 0, 3),
    "dash": ("proc", "ติดตามแดชบอร์ด: ช่องว่าง รถจอดอยู่ รายการเข้า-ออก", 0, 4),
    "d2": ("dec", "ต้องการสรุปรายได้?", 0, 5),
    "rep": ("io", "เลือกช่วงวันที่ ดูกราฟ/ตาราง และส่งออก CSV", 1, 5),
    "e": ("term", "สิ้นสุด", 0, 6),
}, [("s", "d1", ""), ("d1", "add", "ไม่", "right"), ("add", "rate", "", "downleft"), ("d1", "rate", "ใช่"), ("rate", "online", ""),
    ("online", "dash", ""), ("dash", "d2", ""), ("d2", "rep", "ใช่", "right"), ("rep", "e", "", "downleft"), ("d2", "e", "ไม่")])


def architecture():
    W, H = 1100, 560
    boxes = {
        "user": (40, 60, "ผู้ใช้บริการ", "มือถือ · Web App / PWA"),
        "admin": (40, 220, "ผู้ดูแลลานจอด / พนักงาน", "เว็บหลังบ้าน"),
        "api": (420, 140, "ParkQ Backend (FastAPI)", "REST API + หน้าเว็บ · Linux"),
        "db": (420, 320, "SQLite / PostgreSQL", "ผู้ใช้ ลาน ช่องจอด ตั๋ว ชำระเงิน log"),
        "mqtt": (420, 450, "Device API (HTTP)", "device key · slots / commands / scan"),
        "pay": (800, 40, "Payment Gateway", "QR พร้อมเพย์ / บัตร"),
        "sms": (800, 150, "Email (SMTP)", "ส่ง OTP ทางอีเมล"),
        "map": (800, 260, "Map Service", "แผนที่ / นำทาง"),
        "gate": (40, 420, "Gate Controller (PCB)", "ESP32 · QR Reader · OLED · Relay/Servo"),
        "sensor": (800, 420, "Slot Sensors", "Ultrasonic / ToF + LED WS2812B"),
    }
    BW, BH = 260, 76
    out = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}'>{ARROW_DEF}<rect width='{W}' height='{H}' fill='#fff'/>"]
    links = [("user", "api"), ("admin", "api"), ("api", "db"), ("api", "pay"), ("api", "sms"), ("api", "map"),
             ("api", "mqtt"), ("gate", "mqtt"), ("sensor", "mqtt")]
    c = {k: (x + BW / 2, y + BH / 2) for k, (x, y, _, _) in boxes.items()}
    for a, b in links:
        out.append(f"<line x1='{c[a][0]}' y1='{c[a][1]}' x2='{c[b][0]}' y2='{c[b][1]}' stroke='#8a93a5' stroke-width='1.6'/>")
    for k, (x, y, t, sub) in boxes.items():
        fill = "#1e5eff" if k == "api" else ("#13203f" if k in ("gate", "sensor") else "#fff")
        fg = "#fff" if fill != "#fff" else "#1d2433"
        out.append(f"<rect x='{x}' y='{y}' width='{BW}' height='{BH}' rx='10' fill='{fill}' stroke='#1e5eff' stroke-width='1.6'/>")
        out.append(text_block(x + BW / 2, y + 28, t, 15, 40, 700, fg))
        out.append(text_block(x + BW / 2, y + 52, sub, 12, 50, 400, fg))
    out.append("</svg>")
    return "".join(out), W, H


def img_size(code):
    from PIL import Image
    with Image.open(IMG_DIR / f"{code}.png") as im:
        return im.size


def screen_flow(module_code, edges):
    """Thumbnails of screens laid out by BFS depth with labelled arrows."""
    screens = {s["code"]: s for s in SCREENS if s["code"].startswith(f"SC-{module_code}-")}
    order = list(screens)
    depth = {}
    for a, b, _ in edges:
        depth.setdefault(a, 0)
        if b:
            depth[b] = max(depth.get(b, 0), depth[a] + 1)
    for code in order:
        depth.setdefault(code, 0)
    cols = defaultdict(list)
    for code in order:
        cols[depth[code]].append(code)
    TW = {"phone": 170, "kiosk": 300, "desktop": 340}
    COLW = max(TW[screens[c]["frame"]] for c in order) + 120
    pos, H = {}, 0
    for d, codes in cols.items():
        y = 50
        for code in codes:
            fw, fh = img_size(code)
            tw = TW[screens[code]["frame"]]
            th = tw * fh / fw
            pos[code] = (30 + d * COLW, y, tw, th)
            y += th + 60
        H = max(H, y)
    W = 30 + len(cols) * COLW
    out = [f"<svg xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink' width='{W}' height='{H}'>{ARROW_DEF}<rect width='{W}' height='{H}' fill='#fff'/>"]
    for code, (x, y, tw, th) in pos.items():
        out.append(f"<rect x='{x - 1}' y='{y - 1}' width='{tw + 2}' height='{th + 2}' fill='none' stroke='#8a93a5'/>")
        out.append(f"<image x='{x}' y='{y}' width='{tw}' height='{th}' href='{(IMG_DIR / (code + '.png')).as_uri()}'/>")
        out.append(f"<text x='{x + tw / 2}' y='{y - 12}' font-size='13' font-weight='700' text-anchor='middle'>{code}</text>")
    for a, b, label in edges:
        if not b:
            continue
        xa, ya, wa, ha = pos[a]
        xb, yb, wb, hb = pos[b]
        sx, sy, ex, ey = xa + wa, ya + ha / 2, xb, yb + hb / 2
        mx = (sx + ex) / 2
        out.append(f"<path d='M{sx},{sy} L{mx},{sy} L{mx},{ey} L{ex - 2},{ey}' fill='none' stroke='#e5484d' stroke-width='2' marker-end='url(#a)'/>")
        out.append(f"<rect x='{mx - 52}' y='{(sy + ey) / 2 - 12}' width='104' height='22' rx='11' fill='#fff' stroke='#e5484d'/>")
        out.append(f"<text x='{mx}' y='{(sy + ey) / 2 + 3}' font-size='12' text-anchor='middle' dominant-baseline='middle' fill='#b42318'>{html.escape(label)}</text>")
    out.append("</svg>")
    return "".join(out), W, H


def main_flow():
    chain = [MAIN_FLOW[0][0]] + [b for _, b in MAIN_FLOW]
    names = {s["code"]: s for s in SCREENS}
    per_row, tw = 6, 150
    out_items = []
    W = 40 + per_row * (tw + 60)
    rows = (len(chain) + per_row - 1) // per_row
    H = 40 + rows * 380
    out = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}'>{ARROW_DEF}<rect width='{W}' height='{H}' fill='#fff'/>"]
    for i, code in enumerate(chain):
        r, cidx = divmod(i, per_row)
        fw, fh = img_size(code)
        th = min(tw * fh / fw, 330)
        x, y = 30 + cidx * (tw + 60), 50 + r * 380
        out.append(f"<rect x='{x - 1}' y='{y - 1}' width='{tw + 2}' height='{th + 2}' fill='none' stroke='#8a93a5'/>")
        out.append(f"<image x='{x}' y='{y}' width='{tw}' height='{th}' href='{(IMG_DIR / (code + '.png')).as_uri()}'/>")
        out.append(f"<text x='{x + tw / 2}' y='{y - 12}' font-size='12' font-weight='700' text-anchor='middle'>{i + 1}. {code}</text>")
        if i < len(chain) - 1 and cidx < per_row - 1:
            out.append(f"<line x1='{x + tw + 4}' y1='{y + 120}' x2='{x + tw + 54}' y2='{y + 120}' stroke='#e5484d' stroke-width='2.5' marker-end='url(#a)'/>")
    out.append("</svg>")
    return "".join(out), W, H


def shoot(jobs):
    """jobs: list of (name, html, w, h). Renders in parallel with headless Chrome."""
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    procs = []
    for name, doc, w, h in jobs:
        hp = HTML_DIR / f"{name}.html"
        hp.write_text(doc, encoding="utf-8")
        cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
               "--allow-file-access-from-files", f"--user-data-dir={ROOT / 'build' / 'chrome' / name}",
               f"--screenshot={IMG_DIR / (name + '.png')}", f"--window-size={int(w)},{int(h)}",
               "--default-background-color=FFFFFFFF", "--virtual-time-budget=2000", hp.as_uri()]
        procs.append(subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        if len(procs) >= 6:
            procs.pop(0).wait()
    for p in procs:
        p.wait()


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    # Screen images now come from the real web app (gen/capture.py); this script draws the diagrams only.
    if stage in ("diagrams", "all"):
        jobs = []
        for key, (title, nodes, edges) in WORKFLOWS.items():
            svg, w, h = flowchart(nodes, edges, title)
            jobs.append((key, svg_page(svg, w, h), w, h))
        svg, w, h = architecture()
        jobs.append(("architecture", svg_page(svg, w, h), w, h))
        for m in MODULES:
            svg, w, h = screen_flow(m["code"], FLOWS[m["code"]])
            jobs.append((f"flow_{m['code']}", svg_page(svg, w, h), w, h))
        svg, w, h = main_flow()
        jobs.append(("flow_main", svg_page(svg, w, h), w, h))
        shoot(jobs)
    print("done", len(list(IMG_DIR.glob("*.png"))), "images")
