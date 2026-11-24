"""W13 Gantt chart: reads the real project plan (W2) and adds actual status as of TODAY.
python gen/make_gantt.py  ->  ส่งงาน/W13_Gantt_Chart_ParkQ.xlsx  +  build/img/gantt.png
Progress numbers are the team's own assessment (see STATUS); edit them there and re-run."""
import re
from datetime import date, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "ส่งงาน" / "W2_Project_Plan_ParkQ.xlsx"
OUT = ROOT / "ส่งงาน" / "W13_Gantt_Chart_ParkQ.xlsx"
PNG = ROOT / "build" / "img" / "gantt.png"
FONT_TTF = ROOT / "parkq-film" / "fonts" / "Anuphan.ttf"

TODAY = date(2026, 11, 24)            # 24 พ.ย. 2569
BE = 543
OWNER = {"PM": "พีรพัฒน์", "SA": "สงกรานต์", "Dev": "ภูริภัทร", "QA": "พีรพัฒน์"}

# actual progress per task number: (percent, status, note). Anything not listed is "not started".
STATUS = {
    1: (100, "เสร็จ", "Kick-off และเก็บ Requirement ครบ"),
    2: (100, "เสร็จ", "ส่งเอกสาร W3"),
    3: (100, "เสร็จ", "ส่งเอกสาร W4"),
    4: (100, "เสร็จ", "ส่งเอกสาร W5 (SRS)"),
    5: (100, "เสร็จ", "อนุมัติ Requirement"),
    6: (100, "เสร็จ", "Screen Flow W6 (ปรับตาม UI ใหม่)"),
    7: (100, "เสร็จ", "Screen Attributes W7 (ปรับตาม UI ใหม่)"),
    8: (100, "เสร็จ", "SQA และ Traceability W8"),
    9: (100, "เสร็จ", "Test Plan และ Test Case W9"),
    10: (100, "เสร็จ", "เว็บผู้ขับขี่ใช้งานจริงบน Render"),
    11: (100, "เสร็จ", "ตู้ประตู หลังบ้าน และ Device API"),
    12: (100, "เสร็จ", "เทสต์อัตโนมัติ 67 ตัว ผ่านทั้งหมด"),
    13: (60, "กำลังทำ", "ออกแบบและสั่งผลิต PCB แล้ว รอรับบอร์ดและเครื่องอ่าน QR"),
    14: (35, "กำลังทำ", "มี Wokwi, อุปกรณ์จำลอง /device และ Digital Twin แล้ว ยังไม่ได้ทดสอบบนบอร์ดจริง"),
    15: (0, "ยังไม่เริ่ม", ""),
    16: (0, "ยังไม่เริ่ม", "คู่มือ W11 ทำล่วงหน้าแล้ว"),
    17: (50, "กำลังทำ", "ใช้งานบน Render (แพ็กเกจฟรี) แล้ว ยังต้องต่อฐานข้อมูลถาวร"),
    18: (0, "ยังไม่เริ่ม", ""),
}
# work added after the original plan: (task, who-letters, start, end, pct, status, note)
EXTRA = [
    ("Digital Twin 3 มิติ + อุปกรณ์จำลอง (งานเพิ่ม)", ["Dev"], date(2026, 11, 22), date(2026, 11, 24), 100, "เสร็จ", "หน้า /twin และ /device ใช้งานจริงบน Render"),
    ("W13: Gantt Chart และจัดการ Task บน Trello", ["PM", "SA", "Dev"], date(2026, 11, 11), date(2026, 11, 17), 100, "เสร็จ", "กำหนดส่ง 17/11/2569 (ครั้งที่ 13) ส่งช้า เสร็จ 24/11/2569"),
    ("รูปเล่มสมบูรณ์ (PDF + Word) และวิดีโอพิตช์ 5 นาที", ["PM", "SA", "Dev"], date(2026, 11, 18), date(2026, 11, 24), 60, "กำลังทำ", "กำหนดส่ง 24/11/2569 (ครั้งที่ 14) รูปเล่มเสร็จ รอบันทึกวิดีโอพิตช์"),
]
PHASE = {  # task number -> phase colour key (matches the legend of the W2 plan)
    **{n: "plan" for n in (1, 2)}, 3: "analyze", 4: "analyze", 5: "analyze", 6: "design", 7: "design", 8: "quality", 9: "quality",
    10: "dev", 11: "dev", 12: "test", 13: "dev", 14: "test", 15: "test", 16: "test", 17: "deliver", 18: "deliver",
}
COLORS = {  # (planned, done)
    "plan": ("FCE5CD", "E69138"), "analyze": ("D9EAD3", "6AA84F"), "design": ("D9D2E9", "8E7CC3"), "quality": ("FFF2CC", "F1C232"),
    "dev": ("CFE2F3", "3D85C6"), "test": ("F4CCCC", "CC4125"), "deliver": ("D0E0E3", "45818E"), "extra": ("EAD1DC", "A64D79"),
}
PHASE_NAME = {"plan": "วางแผน", "analyze": "วิเคราะห์", "design": "ออกแบบ", "quality": "คุณภาพ", "dev": "พัฒนา", "test": "ทดสอบ", "deliver": "ส่งมอบ", "extra": "งานเพิ่ม"}


def parse_th(s: str) -> date:
    d, m, y = (int(x) for x in s.strip().split("/"))
    return date(y - BE, m, d)


def thai(d: date, short=True) -> str:
    return f"{d.day}/{d.month}/{d.year + BE}"


def load_tasks():
    ws = openpyxl.load_workbook(PLAN)["Project Plan"]
    tasks = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not isinstance(r[0], int):
            continue
        a, b = re.split(r"\s*[–-]\s*", str(r[7]))
        who = [k for k, v in zip(("PM", "SA", "Dev", "QA"), r[3:7]) if v]
        tasks.append({"no": r[0], "name": r[1], "who": who, "start": parse_th(a), "end": parse_th(b)})
    return tasks


def build_rows():
    rows = []
    for t in load_tasks():
        pct, st, note = STATUS.get(t["no"], (0, "ยังไม่เริ่ม", ""))
        rows.append({**t, "pct": pct, "status": st, "note": note, "phase": PHASE.get(t["no"], "dev")})
    n = rows[-1]["no"]
    for i, (name, who, s, e, pct, st, note) in enumerate(EXTRA, 1):
        rows.append({"no": n + i, "name": name, "who": who, "start": s, "end": e, "pct": pct, "status": st, "note": note, "phase": "extra"})
    return rows


def owners(who):
    seen = []
    for w in who:
        o = OWNER[w]
        if o not in seen:
            seen.append(o)
    return ", ".join(seen)


def done_until(r):
    span = (r["end"] - r["start"]).days + 1
    return r["start"] + timedelta(days=round(span * r["pct"] / 100) - 1) if r["pct"] else None


def monday(d):
    return d - timedelta(days=d.weekday())


def make_xlsx(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Gantt Chart"
    first = monday(min(r["start"] for r in rows))
    last = monday(max(r["end"] for r in rows))
    weeks = [first + timedelta(days=7 * i) for i in range(((last - first).days // 7) + 1)]
    thin = Side(style="thin", color="BBBBBB")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    head = PatternFill("solid", fgColor="1F2937")
    font = lambda **k: Font(name="Leelawadee UI", size=k.pop("size", 10), **k)

    ws["A1"] = "Gantt Chart โครงงาน ParkQ"
    ws["A1"].font = font(size=16, bold=True)
    ws["A2"] = f"สถานะ ณ วันที่ {thai(TODAY)} · ทีม: พีรพัฒน์ เครือวัลย์ (PM·QA) · สงกรานต์ บุญเสริม (SA) · ภูริภัทร เมตมาตร์ (Dev)"
    ws["A2"].font = font(color="555555")
    ws["A3"] = "สีเข้ม = ส่วนที่ทำเสร็จตามจริง · สีอ่อน = ส่วนที่ยังเหลือ · กรอบแดง = สัปดาห์ปัจจุบัน"
    ws["A3"].font = font(color="555555")

    hdr = ["ลำดับ", "รายการงาน", "ผู้รับผิดชอบ", "เริ่ม", "สิ้นสุด", "% เสร็จ", "สถานะ"]
    top = 5
    for c, h in enumerate(hdr, 1):
        cell = ws.cell(top + 1, c, h)
        cell.font = font(bold=True, color="FFFFFF"); cell.fill = head; cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True); cell.border = box
        ws.merge_cells(start_row=top, start_column=c, end_row=top + 1, end_column=c)
        ws.cell(top, c).fill = head
    for i, w in enumerate(weeks):
        c = len(hdr) + 1 + i
        a = ws.cell(top, c, f"W{i + 1}")
        b = ws.cell(top + 1, c, f"{w.day}/{w.month}")
        for x in (a, b):
            x.font = font(bold=True, color="FFFFFF", size=9); x.fill = head; x.alignment = Alignment(horizontal="center"); x.border = box
        ws.column_dimensions[get_column_letter(c)].width = 5.2
    for c, wd in zip("ABCDEFG", (6, 58, 20, 11, 11, 8, 12)):
        ws.column_dimensions[c].width = wd

    today_col = None
    for i, w in enumerate(weeks):
        if w <= TODAY < w + timedelta(days=7):
            today_col = len(hdr) + 1 + i

    for k, r in enumerate(rows):
        row = top + 2 + k
        vals = [r["no"], r["name"], owners(r["who"]), thai(r["start"]), thai(r["end"]), r["pct"] / 100, r["status"]]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row, c, v)
            cell.font = font(); cell.border = box
            cell.alignment = Alignment(vertical="center", wrap_text=(c == 2), horizontal="left" if c in (2, 3) else "center")
        ws.cell(row, 6).number_format = "0%"
        ws.row_dimensions[row].height = 30
        light, dark = COLORS[r["phase"]]
        du = done_until(r)
        for i, w in enumerate(weeks):
            c = len(hdr) + 1 + i
            we = w + timedelta(days=6)
            cell = ws.cell(row, c)
            cell.border = box
            if r["start"] <= we and r["end"] >= w:
                is_done = du is not None and du >= w
                cell.fill = PatternFill("solid", fgColor=dark if is_done else light)
        if r["note"]:
            ws.cell(row, len(hdr) + len(weeks) + 1, r["note"]).font = font(color="555555", size=9)
    note_col = len(hdr) + len(weeks) + 1
    ws.cell(top + 1, note_col, "หมายเหตุ").font = font(bold=True)
    ws.column_dimensions[get_column_letter(note_col)].width = 70
    if today_col:
        red = Side(style="medium", color="D93025")
        for row in range(top, top + 2 + len(rows)):
            cell = ws.cell(row, today_col)
            cell.border = Border(left=red, right=red, top=red if row == top else cell.border.top, bottom=red if row == top + 1 + len(rows) else cell.border.bottom)
    ws.freeze_panes = ws.cell(top + 2, 3)

    # legend
    lr = top + 3 + len(rows)
    ws.cell(lr, 2, "คำอธิบายสี (เข้ม = เสร็จแล้ว, อ่อน = ที่เหลือ)").font = font(bold=True)
    for j, (k, (light, dark)) in enumerate(COLORS.items()):
        ws.cell(lr + 1 + j, 1).fill = PatternFill("solid", fgColor=dark)
        ws.cell(lr + 1 + j, 2, PHASE_NAME[k]).font = font()
        ws.cell(lr + 1 + j, 3).fill = PatternFill("solid", fgColor=light)

    # summary sheet
    s = wb.create_sheet("สรุปสถานะ")
    total = len(rows)
    done = sum(1 for r in rows if r["pct"] == 100)
    doing = sum(1 for r in rows if 0 < r["pct"] < 100)
    todo = total - done - doing
    avg = sum(r["pct"] for r in rows) / total
    s["A1"] = f"สรุปความคืบหน้า ณ {thai(TODAY)}"; s["A1"].font = font(size=14, bold=True)
    lines = [("งานทั้งหมด", total), ("เสร็จ", done), ("กำลังทำ", doing), ("ยังไม่เริ่ม", todo), ("ความคืบหน้าเฉลี่ย (ถ่วงน้ำหนักเท่ากันทุกงาน)", f"{avg:.0f}%")]
    for i, (a, b) in enumerate(lines, 3):
        s.cell(i, 1, a).font = font(); s.cell(i, 2, b).font = font(bold=True)
    s["A9"] = "ความเสี่ยงที่ติดตามอยู่"; s["A9"].font = font(bold=True)
    risks = [
        "บอร์ด PCB และเครื่องอ่าน QR ยังไม่ได้รับ ทดสอบกับฮาร์ดแวร์จริงยังไม่ได้ (ใช้ Wokwi และอุปกรณ์จำลองแทน)",
        "ซิม Wokwi จับมือ HTTPS ไม่เสถียร ไม่เหมาะเป็นตัวเดโมสดหลัก",
        "ฐานข้อมูลบน Render แพ็กเกจฟรีรีเซ็ตเมื่อ deploy ต้องต่อ PostgreSQL ถาวรก่อนทดสอบกับผู้ใช้จริง",
        "ตัวเลข % เป็นการประเมินของทีม ไม่ได้วัดจากเครื่องมือ",
    ]
    for i, t in enumerate(risks, 10):
        s.cell(i, 1, f"• {t}").font = font()
    s.column_dimensions["A"].width = 100
    wb.save(OUT)
    return weeks


def make_png(rows, weeks):
    from matplotlib.patches import Patch
    PNG.parent.mkdir(parents=True, exist_ok=True)
    font_manager.fontManager.addfont(str(FONT_TTF))
    plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(FONT_TTF)).get_name()
    INKC, AMB, AMB_L, GREY = "#1C2530", "#FFB000", "#FFE4A3", "#9AA1A9"
    fig, ax = plt.subplots(figsize=(20, 0.46 * len(rows) + 2.0))
    first = weeks[0]
    x = lambda d: (d - first).days
    n = len(rows)
    for i, r in enumerate(rows):
        y = n - 1 - i
        s, e = x(r["start"]), x(r["end"]) + 1
        if r["pct"] >= 100:
            ax.barh(y, e - s, left=s, color=INKC, height=0.56)
        elif r["pct"] > 0:
            ax.barh(y, e - s, left=s, color=AMB_L, edgecolor=AMB, height=0.56, linewidth=1.0)
            ax.barh(y, (e - s) * r["pct"] / 100, left=s, color=AMB, height=0.56)
        else:
            ax.barh(y, e - s, left=s, color="white", edgecolor=GREY, height=0.56, linewidth=1.0, linestyle=(0, (3, 2)))
        ax.text(e + 0.7, y, f"{r['pct']}%", va="center", fontsize=8, color="#5B6475")
    ax.set_yticks(range(n))
    ax.set_yticklabels([f"{r['no']}. {r['name'] if len(r['name']) <= 50 else r['name'][:49] + '…'}" for r in reversed(rows)], fontsize=10.5, color=INKC)
    ax.tick_params(axis="y", length=0, pad=8)
    ax.set_xticks([7 * i for i in range(len(weeks))])
    ax.set_xticklabels([f"W{i + 1}\n{w.day}/{w.month}" for i, w in enumerate(weeks)], fontsize=9, color="#5B6475")
    ax.tick_params(axis="x", length=0)
    ax.axvline(x(TODAY), color=INKC, linewidth=1.2, linestyle=(0, (4, 3)))
    ax.text(x(TODAY) + 0.6, n - 0.3, f"วันนี้ {thai(TODAY)}", color=INKC, fontsize=9, va="bottom", fontweight="bold")
    ax.set_xlim(0, (weeks[-1] - first).days + 8)
    ax.set_ylim(-0.7, n - 0.1)
    ax.grid(axis="x", color="#EEF0F2", linewidth=0.8)
    ax.set_axisbelow(True)
    for s_ in ("top", "right", "left", "bottom"):
        ax.spines[s_].set_visible(False)
    ax.legend(handles=[Patch(facecolor=INKC, label="เสร็จแล้ว"), Patch(facecolor=AMB, label="กำลังทำ (ส่วนทึบ = ที่ทำแล้ว)"),
                       Patch(facecolor="white", edgecolor=GREY, linestyle="--", label="ยังไม่เริ่ม")],
              loc="upper center", bbox_to_anchor=(0.5, -0.07), ncol=3, frameon=False, fontsize=9.5)
    ax.set_title("Gantt Chart โครงงาน ParkQ", loc="left", fontsize=14, fontweight="bold", color=INKC, pad=14)
    fig.tight_layout()
    fig.savefig(PNG, dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    rows = build_rows()
    weeks = make_xlsx(rows)
    make_png(rows, weeks)
    print(f"{len(rows)} tasks, {len(weeks)} weeks -> {OUT.name}, {PNG.name}")
