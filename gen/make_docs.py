"""Build the W5-W9 Word documents (and the W9 test-case workbook) from spec_data."""
import subprocess
import sys
from pathlib import Path

import openpyxl
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from openpyxl.styles import Alignment, Font, PatternFill

from spec_data import *  # noqa: F401,F403

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "build" / "img"
OUT = ROOT / "ส่งงาน"
CODE = ROOT / "code"
FONT = "Leelawadee UI"
BLUE = RGBColor(0x1E, 0x5E, 0xFF)
SCREEN_BY_CODE = {s["code"]: s for s in SCREENS}
ALL_REQS = [(m, r) for m in MODULES for r in m["reqs"]]


# ---------------- low-level helpers ----------------

def set_font(rpr_parent, size=None, bold=None, color=None, font=FONT):
    """Apply font to a run or style, including the complex-script (Thai) slots."""
    rpr = rpr_parent._element.get_or_add_rPr() if hasattr(rpr_parent, "_element") and hasattr(rpr_parent._element, "get_or_add_rPr") else rpr_parent.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(attr), font)
    if size:
        for tag in ("w:sz", "w:szCs"):
            el = rpr.find(qn(tag))
            if el is None:
                el = OxmlElement(tag)
                rpr.append(el)
            el.set(qn("w:val"), str(int(size * 2)))
    if bold is not None:
        for tag in ("w:b", "w:bCs"):
            el = rpr.find(qn(tag))
            if el is None:
                el = OxmlElement(tag)
                rpr.append(el)
            el.set(qn("w:val"), "1" if bold else "0")
    if color is not None:
        el = rpr.find(qn("w:color"))
        if el is None:
            el = OxmlElement("w:color")
            rpr.append(el)
        el.set(qn("w:val"), str(color))


def new_doc(doc_code, landscape=False):
    d = Document()
    sec = d.sections[0]
    if landscape:
        sec.orientation = WD_ORIENT.LANDSCAPE
        sec.page_width, sec.page_height = sec.page_height, sec.page_width
    for side in ("left_margin", "right_margin"):
        setattr(sec, side, Cm(2))
    sec.top_margin, sec.bottom_margin = Cm(2), Cm(1.8)
    set_font(d.styles["Normal"], 11)
    d.styles["Normal"].paragraph_format.space_after = Pt(4)
    d.styles["Normal"].paragraph_format.line_spacing = 1.15
    for lvl, size in ((1, 16), (2, 13.5), (3, 12)):
        st = d.styles[f"Heading {lvl}"]
        set_font(st, size, True, "1E5EFF" if lvl == 1 else "13203F")
        st.paragraph_format.space_before = Pt(12 if lvl == 1 else 8)
        st.paragraph_format.space_after = Pt(4)
    hp = sec.header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = hp.add_run(f"{SYSTEM_SHORT} – {SYSTEM_TH}    |    {doc_code}")
    set_font(r, 8.5, color="5B6475")
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run("หน้า ")
    set_font(r, 8.5, color="5B6475")
    page_field(fp)
    return d


def page_field(p):
    r = p.add_run()
    set_font(r, 8.5, color="5B6475")
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        r._element.append(el)


def para(d, text="", bold=False, size=None, align=None, color=None, style=None, space_after=None):
    p = d.add_paragraph(style=style)
    if text:
        r = p.add_run(text)
        set_font(r, size, bold if bold else None, color)
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if space_after is not None:
        p.paragraph_format.space_after = Pt(space_after)
    return p


def rich(d, parts, style=None):
    """parts: list of (text, bold)."""
    p = d.add_paragraph(style=style)
    for text, bold in parts:
        set_font(p.add_run(text), bold=bold or None)
    return p


def bullet(d, text, bold_prefix=None):
    p = d.add_paragraph(style="List Bullet")
    if bold_prefix:
        set_font(p.add_run(bold_prefix), bold=True)
    set_font(p.add_run(text))
    p.paragraph_format.space_after = Pt(2)
    return p


def numbered(d, text, n):
    p = d.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.6)
    set_font(p.add_run(f"{n}. {text}"))
    p.paragraph_format.space_after = Pt(2)
    return p


def heading(d, text, level=1):
    h = d.add_heading(level=level)
    set_font(h.add_run(text))
    return h


def shade(cell, hex_color):
    tcpr = cell._element.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcpr.append(shd)


def cell_text(cell, text, bold=False, size=9.5, color=None, align=None):
    cell.text = ""
    lines = str(text).split("\n")
    p = cell.paragraphs[0]
    for k, line in enumerate(lines):
        if k:
            p = cell.add_paragraph()
        r = p.add_run(line)
        set_font(r, size, bold or None, color)
        p.paragraph_format.space_after = Pt(0)
        if align == "center":
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def table(d, headers, rows, widths_cm, size=9.5, header_fill="1E5EFF", center_cols=()):
    t = d.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        cell_text(c, h, True, size, "FFFFFF", "center")
        shade(c, header_fill)
    # repeat header row on each page
    trpr = t.rows[0]._tr.get_or_add_trPr()
    th = OxmlElement("w:tblHeader")
    th.set(qn("w:val"), "true")
    trpr.append(th)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cell_text(cells[i], v, size=size, align="center" if i in center_cols else None)
    for row in t.rows:
        for i, w in enumerate(widths_cm):
            row.cells[i].width = Cm(w)
    d.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def compact(path):
    """Collapse tall blank horizontal bands in a wireframe so the page has no empty gap."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    w, h = im.size
    px = im.load()
    rows = [all(px[x, y] == px[0, y] for x in range(0, w, 4)) for y in range(h)]
    keep, run = [], 0
    for y, blank in enumerate(rows):
        run = run + 1 if blank else 0
        if run <= 60:
            keep.append(y)
    if len(keep) == h:
        return path
    out = Image.new("RGB", (w, len(keep)))
    for i, y in enumerate(keep):
        out.paste(im.crop((0, y, w, y + 1)), (0, i))
    dst = path.parent.parent / "img_compact" / path.name
    dst.parent.mkdir(exist_ok=True)
    out.save(dst)
    return dst


def image(d, path, width_cm, caption=None):
    if path.name.startswith("SC-"):
        path = compact(path)
    p = d.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(path), width=Cm(width_cm))
    if caption:
        c = para(d, caption, size=9, align="center", color="5B6475")
        c.paragraph_format.space_after = Pt(8)


def page_break(d):
    d.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def cover(d, proj_name, th_desc, doc_title):
    for _ in range(5):
        para(d)
    para(d, proj_name, True, 26, "center", "1E5EFF")
    para(d, f"({th_desc})", False, 16, "center")
    para(d)
    para(d, doc_title, True, 15, "center")
    para(d, SYSTEM_TH, False, 13, "center")
    para(d, SYSTEM_EN, False, 12, "center", "5B6475")
    for _ in range(4):
        para(d)
    t = table(d, ["รายการ", "รายละเอียด"], [
        ("ชื่อกลุ่ม", "...................................................."),
        ("สมาชิก / บทบาท", "1. ............................ (PM)\n2. ............................ (SA)\n3. ............................ (Developer)\n4. ............................ (QA)"),
        ("รายวิชา", "Software Engineering (ทฤษฎี + ปฏิบัติ)"),
        ("เวอร์ชันเอกสาร / วันที่", f"{VERSION} / {DOC_DATE}"),
    ], [5, 10], size=10.5)
    page_break(d)


def history(d, purpose):
    heading(d, "ประวัติการจัดทำเอกสาร", 2)
    table(d, ["ลำดับ", "เวอร์ชัน", "รายละเอียดการดำเนินการ", "ผู้ดำเนินการ (วันที่)", "ผู้อนุมัติ (วันที่)"], [
        ("1", "0.1", f"จัดทำ{purpose}", f"SA ({DOC_DATE})", ""),
        ("2", "1.0", f"ทบทวนและอนุมัติ{purpose}", f"QA ({DOC_DATE})", f"PM ({DOC_DATE})"),
    ], [1.3, 1.7, 6.3, 3.6, 3.6], center_cols=(0, 1))


def toc(d, items):
    heading(d, "สารบัญ", 2)
    for text, level in items:
        p = para(d, ("      " * level) + text, size=10.5, space_after=1)
    page_break(d)


def req_detail(rid):
    for m, r in ALL_REQS:
        if r[0] == rid:
            return m, r


# ---------------- W5 SRS ----------------

def build_w5():
    d = new_doc("Proj_Requirement_Spec")
    cover(d, "Proj_Requirement_Spec", "เอกสารสรุปความต้องการของระบบงาน", "Software Requirements Specification (SRS)")
    history(d, " Requirement Specification")
    toc(d, [("1. Introduction", 0), ("2. System Requirement", 0), ("2.1 System Requirement Overview", 1),
            ("2.2 Requirements Functionality", 1), ("2.3 External Interfaces", 1), ("3. Software Requirement", 0),
            ("3.1 Software Requirement Overview (Workflow)", 1), ("3.2 Requirements Functionality", 1),
            ("3.3 External Interfaces", 1), ("3.4 Business Rules", 1), ("4. Non-functional Requirements", 0)])

    para(d, "Requirement Specification", True, 18, "center", "1E5EFF")
    para(d, SYSTEM_TH, True, 13, "center")
    para(d, SYSTEM_EN, False, 11, "center", "5B6475")

    heading(d, "1. Introduction")
    para(d, INTRO)
    rich(d, [("วัตถุประสงค์ของระบบ", True)])
    for t in ["ลดเวลาวนหาที่จอดโดยแสดงสถานะลานจอด ว่าง / ใกล้เต็ม / เต็ม แบบเรียลไทม์",
              "ให้ผู้ใช้ซื้อสิทธิ์จอดหรือจองล่วงหน้าและชำระเงินออนไลน์ได้ในไม่เกิน 60 วินาที",
              "ใช้ QR Code เปิดไม้กั้นเข้า-ออกได้ทันที ไม่ต้องรับบัตรหรือต่อคิวจ่ายเงิน",
              "ให้เจ้าของลานจอดเพิ่มรายได้จากการจองล่วงหน้า และเห็นข้อมูลการใช้งานเพื่อบริหารลาน"]:
        bullet(d, t)
    rich(d, [("ผู้ใช้งานระบบ (Actors)", True)])
    table(d, ["Actor", "คำอธิบาย"], ACTORS, [5, 11.5])
    rich(d, [("ขอบเขตที่ไม่รวมในเวอร์ชันนี้ (Out of scope)", True)])
    for t in ["ระบบอ่านป้ายทะเบียนอัตโนมัติด้วยกล้อง (LPR) – วางแผนในเวอร์ชัน 2",
              "การเชื่อมต่อระบบไม้กั้นของผู้ผลิตรายอื่นนอกจาก Gate Controller ของ ParkQ",
              "แอปพลิเคชัน Native (iOS/Android) – ใช้ Web App/PWA แทน"]:
        bullet(d, t)

    heading(d, "2. System Requirement")
    heading(d, "2.1 System Requirement Overview", 2)
    para(d, "ระบบประกอบด้วย Web Application ฝั่งผู้ใช้และผู้ดูแล, Backend API บน Linux, ฐานข้อมูล PostgreSQL, "
            "MQTT Broker สำหรับสื่อสารกับอุปกรณ์ IoT และ Gate Controller ที่หน้าประตูลานจอด ดังแผนภาพ")
    image(d, IMG / "architecture.png", 16, "ภาพที่ 1 สถาปัตยกรรมระบบ ParkQ")
    heading(d, "2.2 Requirements Functionality", 2)
    para(d, "ระบบ ParkQ ต้องมีองค์ประกอบด้านระบบและฮาร์ดแวร์ดังต่อไปนี้")
    table(d, ["Requirement ID", "องค์ประกอบ", "รายละเอียด"], SYSTEM_REQ, [2.6, 4.2, 9.7], center_cols=(0,))
    heading(d, "2.3 External Interfaces", 2)
    table(d, ["ระบบภายนอก", "การเชื่อมต่อ"], EXTERNAL_IF, [4, 12.5])

    heading(d, "3. Software Requirement")
    heading(d, "3.1 Software Requirement Overview", 2)
    para(d, "ระบบแบ่งเป็น 5 โมดูล ได้แก่ " + ", ".join(m["name"] for m in MODULES) +
         " โดยมี Workflow หลักของระบบ 3 กระบวนการดังนี้")
    for k, (key, cap) in enumerate((("wf1_booking", "Workflow 1 ค้นหา ซื้อสิทธิ์/จอง และชำระเงิน"),
                                     ("wf2_gate", "Workflow 2 เข้า-ออกลานจอดด้วย QR Code"),
                                     ("wf3_iot", "Workflow 3 อัปเดตสถานะช่องจอดจากเซ็นเซอร์ IoT")), start=2):
        image(d, IMG / f"{key}.png", 11.5, f"ภาพที่ {k} {cap}")
    heading(d, "3.2 Requirements Functionality", 2)
    para(d, "ระบบ ParkQ ต้องมีความสามารถดังต่อไปนี้ (Requirement ID อ้างอิงจาก Use Case ที่ออกแบบไว้ในสัปดาห์ที่ 4)")
    for m in MODULES:
        heading(d, f"โมดูล {m['code']} : {m['name']}", 3)
        table(d, ["Requirement ID", "ชื่อความต้องการ", "รายละเอียด", "Actor", "Priority"],
              [(r[0], r[1], r[2], r[3], r[4]) for r in m["reqs"]], [2.4, 3.6, 7, 2, 1.5], size=9, center_cols=(0, 4))
    heading(d, "3.3 External Interfaces", 2)
    table(d, ["Interface", "Method / Topic", "ใช้โดย Requirement"], [
        ("ขอ OTP / ยืนยัน OTP", "POST /api/auth/otp, POST /api/auth/verify", "ACC_01"),
        ("ลานจอดและสถานะ", "GET /api/lots, GET /api/lots/{id}, WebSocket /ws/lots", "LOT_01, LOT_02"),
        ("การจอง", "POST /api/bookings, POST /api/bookings/{id}/cancel", "BKG_01, BKG_02, BKG_04"),
        ("ชำระเงิน", "POST /api/payments, POST /api/payments/webhook", "BKG_03, TKT_03"),
        ("ตู้ประตู (IoT)", "MQTT parkq/{lot}/gate/{in|out}/scan และ /cmd, parkq/{lot}/slots", "TKT_02, TKT_03, LOT_01"),
        ("หลังบ้าน", "/api/admin/lots, /rates, /dashboard, /reports", "ADM_01–ADM_03, TKT_04"),
    ], [4, 8.5, 4], size=9)
    heading(d, "3.4 Business Rules", 2)
    table(d, ["Rule ID", "กฎทางธุรกิจ"], BUSINESS_RULES, [2, 14.5], size=9.5, center_cols=(0,))

    heading(d, "4. Non-functional Requirements")
    for title, items in NFR:
        heading(d, title, 2)
        for t in items:
            bullet(d, t)
    save(d, "W5_SRS_ParkQ.docx")


# ---------------- W6 Screen Flow ----------------

def screen_table_rows(module_code):
    rows = []
    for i, s in enumerate([s for s in SCREENS if s["code"].startswith(f"SC-{module_code}-")], 1):
        rows.append((f"{i:02d}", s["type"], s["code"], s["name"], s["desc"]))
    return rows


def screen_grid(d, screens, per_row=3, width=5.0):
    t = d.add_table(rows=0, cols=per_row)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for k in range(0, len(screens), per_row):
        cells = t.add_row().cells
        for j, s in enumerate(screens[k:k + per_row]):
            p = cells[j].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            wide = s["frame"] in ("desktop", "dmodal", "kiosk")
            p.add_run().add_picture(str(compact(IMG / f"{s['code']}.png")), width=Cm(width))
            cp = cells[j].add_paragraph()
            cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            set_font(cp.add_run(f"{s['code']}\n{s['name']}"), 8.5, True)
    d.add_paragraph()


def build_w6():
    d = new_doc("Proj_Screen_Flow")
    cover(d, "Proj_Screen_Flow", "เอกสารออกแบบหน้าจอและลำดับการทำงานของหน้าจอ", "Prototyping & UI-UX : Screen Flow")
    history(d, "เอกสาร Screen Flow")
    heading(d, "หลักการตั้งรหัสหน้าจอ (Naming Convention)")
    para(d, "รหัสหน้าจอใช้รูปแบบ SC-[โมดูล]-[ลำดับ Use Case]-[ลำดับหน้าจอ] เช่น SC-BKG-03-02 = หน้าจอที่ 2 ของ "
            "Requirement BKG_03 (ชำระเงินออนไลน์) ทำให้ตรวจสอบย้อนกลับ (Traceability) จากหน้าจอไปยัง Use Case/Requirement ได้ทุกหน้าจอ")
    table(d, ["โมดูล", "ชื่อ", "Requirement", "จำนวนหน้าจอ"],
          [(m["code"], m["name"], ", ".join(r[0] for r in m["reqs"]),
            str(sum(s["code"].startswith(f"SC-{m['code']}-") for s in SCREENS))) for m in MODULES]
          + [("รวม", "", "", str(len(SCREENS)))], [2, 6.5, 5.5, 2.5], center_cols=(0, 3))
    heading(d, "ภาพรวม Screen Flow หลัก (ซื้อสิทธิ์จอด → สแกนเข้าลาน)", 2)
    image(d, IMG / "flow_main.png", 16.5, "ภาพรวมเส้นทางหลักของผู้ใช้ตั้งแต่เข้าสู่ระบบจนสแกน QR เข้าลานจอด")
    for m in MODULES:
        page_break(d)
        heading(d, f"FN-{m['code']}: {m['name']}")
        para(d, m["desc"])
        heading(d, "Business Constraint", 3)
        for c in m["constraints"]:
            bullet(d, c)
        heading(d, "Screen Flow", 3)
        img = IMG / f"flow_{m['code']}.png"
        image(d, img, 16.5, f"Screen Flow โมดูล {m['code']}")
        heading(d, "Summary of Screens", 3)
        table(d, ["#", "TYPE", "CODE", "SCREEN NAME", "DESCRIPTION"], screen_table_rows(m["code"]),
              [1, 1.6, 3.2, 4.4, 6.3], size=9, center_cols=(0, 1))
        heading(d, "Screen Design", 3)
        screens = [s for s in SCREENS if s["code"].startswith(f"SC-{m['code']}-")]
        wide = any(s["frame"] in ("desktop", "dmodal", "kiosk") for s in screens)
        screen_grid(d, screens, per_row=2 if wide else 3, width=7.8 if wide else 5.0)
    save(d, "W6_Screen_Flow_ParkQ.docx")


# ---------------- W7 Screen Attributes ----------------

def build_w7():
    d = new_doc("Proj_Screen_Attributes")
    cover(d, "Proj_Screen_Attributes", "เอกสารรายละเอียดองค์ประกอบหน้าจอ", "Screen Attributes Specification")
    history(d, "เอกสาร Screen Attributes")
    heading(d, "คำอธิบายตาราง Screen Attributes")
    table(d, ["คอลัมน์", "ความหมาย"], [
        ("#", "ลำดับ Element ตรงกับหมายเลขสีแดงบนภาพหน้าจอ"),
        ("ELEMENT", "ชื่อช่อง / ปุ่ม / ตาราง / ข้อความบนหน้าจอ"),
        ("TYPE", "Label, Text Input, Number Input, Button, Dropdown List, Radio Button, Checkbox, Date/Time Picker, Tab, List, Table, QR Code, Map, Badge, Modal ฯลฯ"),
        ("REQ", "Y = ต้องกรอก (Required), N = ไม่บังคับ, Y* = บังคับเฉพาะเงื่อนไข, - = ไม่ใช่ช่องกรอก"),
        ("DOMAIN / VALUE", "ค่าที่ยอมรับได้ รูปแบบ หรือรายการตัวเลือก"),
        ("DESCRIPTION", "พฤติกรรมเมื่อใช้งาน กฎการตรวจสอบ (Validation Rules) และข้อความแจ้งเตือน"),
    ], [3.3, 13.2])
    for m in MODULES:
        for k, s in enumerate([s for s in SCREENS if s["code"].startswith(f"SC-{m['code']}-")]):
            page_break(d)
            if k == 0:
                heading(d, f"FN-{m['code']}: {m['name']}")
            heading(d, f"{s['code']} : {s['name']}" + (" (Modal)" if s["type"] == "Modal" else ""), 2)
            rich(d, [("Requirement: ", True), (s["req"], False), ("    ประเภท: ", True), (s["type"], False)])
            wide = s["frame"] in ("desktop", "dmodal", "kiosk")
            image(d, IMG / f"{s['code']}.png", 14 if wide else 7.0)
            para(d, "Screen Attributes Table", True, 10.5)
            t = d.add_table(rows=2, cols=6)
            t.style = "Table Grid"
            t.alignment = WD_TABLE_ALIGNMENT.CENTER
            for i, h in enumerate(["#", "ELEMENT", "TYPE", "REQ", "DOMAIN / VALUE", "DESCRIPTION"]):
                cell_text(t.rows[0].cells[i], h, True, 9, "FFFFFF", "center")
                shade(t.rows[0].cells[i], "1E5EFF")
            merged = t.rows[1].cells[0].merge(t.rows[1].cells[5])
            cell_text(merged, s["desc"], size=9)
            shade(merged, "EEF2FB")
            for i, (name, typ, req, dom, desc) in enumerate(s["elements"], 1):
                cells = t.add_row().cells
                for j, v in enumerate((f"{i:02d}", name, typ, req, dom, desc)):
                    cell_text(cells[j], v, size=9, align="center" if j in (0, 3) else None)
            for row in t.rows:
                for i, w in enumerate((1, 3.2, 2.3, 1.1, 3.6, 5.3)):
                    if i < len(row.cells):
                        row.cells[i].width = Cm(w)
            d.add_paragraph()
    save(d, "W7_Screen_Attributes_ParkQ.docx")


# ---------------- unit test run (shared by W8/W9) ----------------

def run_tests(module):
    """Run one test module: (output, ids that passed, all ok). Integration tests need the ParkQ server running."""
    res = subprocess.run([sys.executable, "-m", "unittest", module, "-v"], cwd=CODE, capture_output=True, text=True, encoding="utf-8")
    out = res.stderr.strip()
    passed = {line.split()[0].replace("test_", "").split("_")[0] for line in out.splitlines() if line.endswith("... ok")}
    return out, passed, res.returncode == 0


def run_unit_tests():
    return run_tests("test_parkq_core")


IT_OUT, IT_PASSED, IT_OK = "", set(), False


def tc_status(tc_id):
    """AC when a passing integration test covers the case or it was verified by hand in the browser; blank = not run yet."""
    if tc_id in MANUAL_VERIFIED or any(tc_id in covered and it in IT_PASSED for it, _, _, covered in INTEGRATION_TESTS):
        return "AC"
    return ""


def tests_for(rid):
    tcs = [tc[0] for tc in TEST_CASES if rid in tc[1]]
    uts = [u[0] for u in UNIT_TESTS if u[1] == rid] + [i[0] for i in INTEGRATION_TESTS if rid in i[1]]
    return tcs, uts


# ---------------- W8 SQA + Traceability ----------------

def build_w8(ut_out, passed, all_ok):
    d = new_doc("Proj_SQA_Traceability_Record")
    cover(d, "Proj_SQA", "แผนประกันคุณภาพ ผลการทดสอบ รายงานข้อผิดพลาด และบันทึกการตรวจสอบย้อนกลับ",
          "Software Quality Assurance & Traceability Record")
    history(d, "เอกสาร SQA และ Traceability Record")

    heading(d, "1. แผนคุณภาพ (Quality Plan)")
    heading(d, "1.1 วัตถุประสงค์", 2)
    para(d, "ให้ระบบ ParkQ ทำงานถูกต้องตาม SRS โดยเฉพาะการคิดเงิน การนับช่องว่าง และการตรวจ QR ที่ประตู "
            "ซึ่งหากผิดพลาดจะกระทบรายได้ของลูกค้าและทำให้ผู้ใช้เข้าลานไม่ได้")
    heading(d, "1.2 มาตรฐานและเกณฑ์คุณภาพ (อ้างอิง ISO/IEC 25010)", 2)
    table(d, ["คุณลักษณะ", "เกณฑ์ที่ยอมรับ", "วิธีวัด"], [
        ("Functional Suitability", "Test Case ระดับ High ผ่าน 100%, ทั้งหมดผ่าน ≥ 95%", "System Test / UAT ตาม W9"),
        ("Correctness ของตรรกะหลัก", "Unit Test ผ่าน 100% ครอบคลุมทุกฟังก์ชันใน parkq_core", "python -m unittest"),
        ("Performance Efficiency", "สแกน QR → เปิดไม้กั้น ≤ 2 วินาที, หน้าแรก ≤ 3 วินาที (4G)", "จับเวลาจาก log / Lighthouse"),
        ("Reliability", "Availability ≥ 99.5%, ตู้ประตูทำงานออฟไลน์ได้", "Uptime monitor, TC-TKT-07"),
        ("Security", "QR ปลอมแปลงไม่ได้, HTTPS ทุกจุด, ไม่เก็บเลขบัตร", "UT15, TC-TKT-06, Security review"),
        ("Usability", "ผู้ใช้ใหม่ซื้อสิทธิ์จอดสำเร็จ ≤ 60 วินาที", "ทดสอบกับผู้ใช้ 5 คน"),
    ], [4, 6.8, 5.7], size=9.5)
    heading(d, "1.3 บทบาทและความรับผิดชอบ", 2)
    table(d, ["บทบาท", "ความรับผิดชอบด้านคุณภาพ"], [
        ("PM (Project Manager)", "อนุมัติแผนคุณภาพ ติดตามสถานะ Defect และตัดสินใจ Go-Live"),
        ("SA (System Analyst)", "เขียน SRS/Screen Spec ให้ทดสอบได้ ร่วม Review เอกสาร ตอบคำถาม Requirement"),
        ("Developer", "เขียน Unit Test (AAA) ทุกฟังก์ชันตรรกะ, Code Review ก่อน merge, แก้ Defect"),
        ("QA (Tester)", "เขียน Test Plan/Test Case, ทดสอบ System/Integration, บันทึก Defect และ Regression"),
        ("ลูกค้า (เจ้าของลานจอด)", "ทดสอบ UAT ตาม Workflow จริงและลงนามรับมอบ"),
    ], [4.5, 12])
    heading(d, "1.4 กิจกรรมประกันคุณภาพ", 2)
    for a in ["Requirement Review: ตรวจ SRS ว่าครบ ชัดเจน ทดสอบได้ และไม่ขัดแย้งกัน (Static)",
              "Design Review: ตรวจ Workflow, Screen Flow, Screen Attributes และสถาปัตยกรรม (Static)",
              "Code Review: ทุก Pull Request ต้องมีผู้ตรวจ 1 คน และ Unit Test ผ่านทั้งหมด (Static)",
              "Unit Test → Integration Test (API + MQTT + Gate Controller) → System Test → UAT (Dynamic)",
              "Traceability Record: ทุก Requirement ต้องมี Design, Component และ Test Case รองรับ"]:
        bullet(d, a)

    heading(d, "2. ผลการทดสอบ (Test Results)")
    heading(d, "2.1 Static Testing – ผลการทบทวนเอกสารและการออกแบบ", 2)
    table(d, ["รายการตรวจ", "เกณฑ์", "ผล", "หมายเหตุ"], [
        ("ทุก Requirement มี ID และอ้างอิง Use Case", "15/15", "ผ่าน", ""),
        ("ทุก Requirement มีหน้าจอรองรับ (Traceability)", f"15/15 ({len(SCREENS)} หน้าจอ)", "ผ่าน", ""),
        ("ทุกช่องกรอกมี Validation Rule และข้อความ Error", "ทุกหน้าจอใน W7", "ผ่าน", ""),
        ("Requirement ไม่กำกวม", "ไม่มีจุดตีความได้หลายแบบ", "พบ 1 จุด", "DEF-02 แก้แล้ว"),
        ("การออกแบบรองรับผู้ใช้พร้อมกัน", "ไม่ขายช่องเกิน", "พบ 1 จุด", "DEF-03 แก้แล้ว"),
        ("การออกแบบครอบคลุมขาออก", "มีสถานะตั๋วครบวงจร", "พบ 1 จุด", "DEF-04 แก้แล้ว"),
        ("หน้าจอในเอกสารตรงกับเว็บจริง", "ภาพทุกหน้าจับจากเว็บที่รันอยู่", "ผ่าน", "gen/capture.py"),
    ], [6, 4, 2.2, 4.3], size=9.5, center_cols=(2,))
    heading(d, "2.2 Dynamic Testing – ผล Unit Test (รันจริง)", 2)
    total = len(UNIT_TESTS)
    para(d, f"รันคำสั่ง python -m unittest test_parkq_core -v ในโฟลเดอร์ code ผลรวม: ผ่าน {len(passed)}/{total} "
            f"({'ผ่านทั้งหมด' if all_ok else 'มีรายการไม่ผ่าน'}) วันที่ {DOC_DATE}")
    table(d, ["UT ID", "Requirement", "ฟังก์ชันที่ทดสอบ", "สิ่งที่ตรวจสอบ", "ผล"],
          [(u[0], u[1], u[2], u[3], "AC" if u[0] in passed else "RJ") for u in UNIT_TESTS],
          [1.5, 2.3, 3.5, 7.7, 1.5], size=9, center_cols=(0, 1, 4))
    heading(d, "2.3 Dynamic Testing – ผล Integration Test (รันจริงกับเซิร์ฟเวอร์)", 2)
    para(d, f"รันคำสั่ง python -m unittest test_api_flow -v ขณะเซิร์ฟเวอร์ ParkQ ทำงาน ผลรวม: ผ่าน {len(IT_PASSED)}/{len(INTEGRATION_TESTS)} "
            f"({'ผ่านทั้งหมด' if IT_OK else 'มีรายการไม่ผ่าน'})")
    table(d, ["IT ID", "Requirement", "สิ่งที่ตรวจสอบ", "Test Case ที่ครอบคลุม", "ผล"],
          [(i[0], i[1], i[2], ", ".join(i[3]), "AC" if i[0] in IT_PASSED else "RJ") for i in INTEGRATION_TESTS],
          [1.4, 2.6, 6.8, 4.2, 1.5], size=9, center_cols=(0, 4))
    n_ac = sum(tc_status(tc[0]) == "AC" for tc in TEST_CASES)
    para(d, f"System Test Case ใน W9 ผ่านแล้ว {n_ac}/{len(TEST_CASES)} ข้อ (จาก Integration Test และการทดสอบในเบราว์เซอร์) "
            "ข้อที่เหลือต้องใช้ฮาร์ดแวร์จริง, SMS/Payment Gateway จริง หรือการรอเวลาจริง จะทดสอบในรอบ System Test/UAT",
         size=9.5, color="5B6475")

    heading(d, "3. รายงานข้อผิดพลาด (Defect Report)")
    table(d, ["ระดับ", "ความหมาย"], [("High", "ระบบใช้งานหลักไม่ได้ / เสียเงิน / เข้าลานไม่ได้"),
                                      ("Medium", "ทำงานผิดบางกรณี มีทางเลี่ยง"), ("Low", "ความสวยงาม / ข้อความ")], [2.5, 14])
    for df in DEFECTS:
        heading(d, f"{df['id']}: {df['title']}", 2)
        table(d, ["หัวข้อ", "รายละเอียด"], [
            ("พบจาก", df["found"]), ("ระดับความรุนแรง", df["severity"]),
            ("Requirement / Component", f"{df['req']} / {df['component']}"),
            ("ขั้นตอนที่ทำให้เกิด", "\n".join(f"{i}. {s}" for i, s in enumerate(df["steps"], 1))),
            ("ผลที่เกิดขึ้นจริง (หลักฐาน)", df["actual"]), ("ผลที่คาดหวัง", df["expected"]),
            ("สาเหตุ", df["cause"]), ("การแก้ไข", df["fix"]), ("สถานะ", df["status"]),
        ], [4.3, 12.2], size=9.5)

    heading(d, "4. ข้อเสนอปรับปรุง (Improvement Suggestions)")
    table(d, ["Defect", "สาเหตุราก (Root Cause)", "แผนป้องกัน"], [
        ("DEF-01", "ไม่มีมาตรฐานการจัดการเวลาระหว่างอุปกรณ์", "กำหนดให้ทุกส่วนส่งเวลาเป็น Epoch/UTC, ESP32 ซิงก์เวลา NTP, เพิ่ม Test Case เขตเวลาใน Checklist"),
        ("DEF-02", "Requirement ไม่ระบุขอบเขตเวลา", "เพิ่มข้อ \"ระบุหน่วยและช่วงเวลา\" ใน Requirement Review Checklist"),
        ("DEF-03", "ไม่ได้พิจารณาการทำงานพร้อมกันตั้งแต่ออกแบบ", "Design Review ต้องมีหัวข้อ Concurrency, ทำ Load Test กรณีช่องสุดท้าย"),
        ("DEF-04", "ออกแบบเฉพาะ Happy Path ขาเข้า", "เขียน State Diagram ของตั๋วก่อนเขียนโค้ด และให้ QA ตรวจทุกสถานะ"),
    ], [2, 5.5, 9], size=9.5, center_cols=(0,))
    bullet(d, "รัน Unit Test อัตโนมัติทุกครั้งที่ push (GitHub Actions) และห้าม merge ถ้าไม่ผ่าน")
    bullet(d, "วัด Code Coverage ของ parkq_core ให้ ≥ 90%")

    page_break(d)
    heading(d, "5. Traceability Record (เอกสารบันทึกการตรวจสอบย้อนกลับของระบบ)")
    para(d, "✔ = ฟังก์ชันที่เขียนโค้ดและผ่าน Unit Test แล้ว, ส่วนที่ไม่มีเครื่องหมาย = ออกแบบแล้ว รอพัฒนา", size=9.5, color="5B6475")
    rows = []
    for m, r in ALL_REQS:
        screens = [s["code"] for s in SCREENS if r[0] in s["req"]]
        tcs, uts = tests_for(r[0])
        rows.append((r[0], f"{r[1]}\n{r[2]}", f"Use Case: UC-{r[0]}\nWorkflow + Screens:\n" + "\n".join(screens),
                     COMPONENTS[r[0]].replace("; ", "\n"), "\n".join(tcs + uts)))
    table(d, ["เลขที่ความต้องการ", "สรุปสาระสำคัญความต้องการของระบบ", "Software Design", "Software Components", "Test Cases"],
          rows, [2.5, 4.6, 3.2, 4, 2.2], size=8.5, center_cols=(0,))
    save(d, "W8_SQA_Traceability_ParkQ.docx")


# ---------------- W9 Test Plan / Cases / Unit Test ----------------

def build_w9(ut_out, passed, all_ok):
    d = new_doc("Proj_Test_Plan_Test_Cases")
    cover(d, "Proj_Test_Cases", "แผนการทดสอบ ชุดข้อมูลทดสอบ และ Unit Test", "Software Testing: Test Plan, Test Case, Unit Test")
    history(d, "เอกสาร Test Plan และ Test Cases")

    heading(d, "1. Test Plan (แผนการทดสอบ)")
    table(d, ["หัวข้อ", "รายละเอียด"], [
        ("ขอบเขต (In scope)", "ทุก Requirement ใน SRS: ACC, LOT, BKG, TKT, ADM รวมการทำงานร่วมกับ Gate Controller (IoT) และ Payment Gateway (Sandbox)"),
        ("ไม่ทดสอบ (Out of scope)", "ระบบภายในของธนาคาร/Payment Gateway, LPR, แอป Native"),
        ("ระดับการทดสอบ", "1) Unit Test – Developer, AAA, unittest\n2) Integration Test – API + DB + MQTT + Gate Controller\n3) System Test – QA ตาม Test Case หัวข้อ 2\n4) UAT – เจ้าของลานจอดทดสอบ Workflow จริง"),
        ("ผู้รับผิดชอบ", "Developer: Unit/Integration · QA: System Test + Defect · ลูกค้า: UAT · PM: อนุมัติผล"),
        ("สภาพแวดล้อม", "Staging Server (Ubuntu 24.04, PostgreSQL 16, Mosquitto), Chrome/Safari บน Android และ iPhone, "
                        "โมเดลลานจอด 4 ช่องพร้อม Gate Controller PCB, Payment Gateway โหมด Test"),
        ("ข้อมูลทดสอบ", "ลานทดสอบ LOT01 (50 ช่อง, 20 บาท/ชม.), LOT02 (4 ช่อง โมเดล IoT), เบอร์โทรทดสอบ 3 เบอร์, บัตรทดสอบของ Gateway"),
        ("กำหนดการ", "สัปดาห์ที่ 1: Unit Test · สัปดาห์ที่ 2: Integration + System Test · สัปดาห์ที่ 3: แก้ Defect + Regression + UAT"),
        ("เกณฑ์เริ่มทดสอบ (Entry)", "Build ติดตั้งบน Staging ได้, Unit Test ผ่าน 100%, มีข้อมูลทดสอบพร้อม"),
        ("เกณฑ์หยุดชั่วคราว (Suspension)", "พบ Defect High ที่ขวาง Workflow หลัก (เข้าสู่ระบบ/ชำระเงิน/สแกนเข้า) หรือ Staging ล่ม > 1 ชั่วโมง"),
        ("เกณฑ์จบการทดสอบ (Exit)", "Test Case High ผ่าน 100%, ทั้งหมดผ่าน ≥ 95%, ไม่มี Defect High/Medium ค้าง, UAT ลงนาม"),
        ("สิ่งที่ส่งมอบ", "Test Plan, Test Cases, ผล Unit Test, Defect Report, Test Summary Report"),
        ("ความเสี่ยง", "PCB/ฮาร์ดแวร์มาช้า → ใช้ตัวจำลอง MQTT แทนชั่วคราว · Gateway Sandbox ล่ม → Mock Webhook"),
    ], [4.2, 12.3], size=9.5)

    heading(d, "2. Test Cases and Test Procedures")
    rich(d, [("โครงการ: ", True), (f"{SYSTEM_TH} ({SYSTEM_SHORT})", False)])
    rich(d, [("สถานะ: ", True), ("AC (Accepted, ผ่าน), RJ (Reject, ไม่ผ่าน), ว่าง = ยังไม่ได้ทดสอบ (ต้องใช้ฮาร์ดแวร์หรือบริการภายนอกจริง) "
             "ช่องหมายเหตุระบุ Integration Test (IT) ที่ใช้ยืนยันผล", False)])
    purposes = {
        "ACC": "ตรวจสอบการเข้าสู่ระบบด้วย OTP การสมัครสมาชิก และการจัดการข้อมูลรถ ตาม BR-01, BR-02",
        "LOT": "ตรวจสอบการแสดงสถานะลานจอดแบบเรียลไทม์จากเซ็นเซอร์ IoT ตาม BR-03, BR-04",
        "BKG": "ตรวจสอบการซื้อสิทธิ์จอด การจองล่วงหน้า การชำระเงิน และการยกเลิก ตาม BR-05, BR-06, BR-08",
        "TKT": "ตรวจสอบตั๋ว QR การสแกนเข้า-ออก ค่าส่วนเกิน และการเปิดไม้กั้นโดยพนักงาน ตาม BR-07, BR-09, BR-10",
        "ADM": "ตรวจสอบการจัดการลานจอด ราคา และรายงานของผู้ดูแล",
    }
    for m in MODULES:
        heading(d, f"2.{MODULES.index(m) + 1} {m['code']} : {m['name']}", 2)
        rich(d, [("จุดประสงค์ของการทดสอบ: ", True), (purposes[m["code"]], False)])
        rich(d, [("ขั้นตอนการทดสอบ", True)])
        steps_no = 0
        for s in ["เตรียมข้อมูลตาม Precondition ของแต่ละ Test Case", "ทำตาม Test Steps บนอุปกรณ์ทดสอบ",
                  "เทียบผลกับความคาดหวัง บันทึกสถานะ AC/RJ และแนบภาพหน้าจอเมื่อไม่ผ่าน", "เปิด Defect สำหรับรายการ RJ"]:
            numbered(d, s, steps_no := steps_no + 1)
        rich(d, [("วิธีการทดสอบ: ", True), ("Black-box (Equivalence Partitioning, Boundary Value Analysis, State Transition)", False)])
        rows = [(tc[0], f"{tc[2]}\nเงื่อนไขก่อนทดสอบ: {tc[3]}\nขั้นตอน: " + " → ".join(tc[4]), tc[5], tc_status(tc[0]),
                 tc[1] + "".join("\n" + i[0] for i in INTEGRATION_TESTS if tc[0] in i[3]) + ("\nทดสอบในเบราว์เซอร์" if tc[0] in MANUAL_VERIFIED else ""))
                for tc in TEST_CASES if tc[0].startswith(f"TC-{m['code']}")]
        table(d, ["Test Case ID", "Test Conditions", "ความคาดหวัง", "สถานะ", "หมายเหตุ"], rows,
              [2.0, 6.6, 4.6, 1.2, 2.3], size=8.5, center_cols=(0, 3, 4))

    page_break(d)
    heading(d, "3. Unit Test (AAA: Arrange – Act – Assert)")
    para(d, "ตรรกะหลักที่ใช้ร่วมกันระหว่าง Backend และ Gate Controller ถูกแยกไว้ในโมดูล parkq_core.py "
            "และทดสอบด้วย unittest ของ Python ทุก Test เขียนตามโครงสร้าง AAA")
    table(d, ["UT ID", "Requirement", "ฟังก์ชัน", "สิ่งที่ตรวจสอบ", "สถานะ"],
          [(u[0], u[1], u[2], u[3], "AC" if u[0] in passed else "RJ") for u in UNIT_TESTS],
          [1.5, 2.3, 3.5, 7.7, 1.5], size=9, center_cols=(0, 1, 4))
    heading(d, "3.1 ตัวอย่างโค้ด Unit Test", 2)
    src = (CODE / "test_parkq_core.py").read_text(encoding="utf-8")
    start = src.index("class TestFees")
    end = src.index("class TestLotStatus")
    code_block(d, src[start:end].rstrip())
    start = src.index("class TestTicketQR")
    code_block(d, src[start:src.index("    def test_UT15")].rstrip())
    heading(d, "3.2 ผลการรัน Unit Test", 2)
    code_block(d, "> python -m unittest -v\n" + "\n".join(l for l in ut_out.splitlines() if "... ok" in l or l.startswith(("Ran", "OK", "FAILED"))))
    para(d, "ไฟล์โค้ดเต็มแนบมาในโฟลเดอร์ code: parkq_core.py และ test_parkq_core.py", size=9.5, color="5B6475")
    save(d, "W9_Test_Plan_Test_Cases_ParkQ.docx")


def code_block(d, text):
    t = d.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    c = t.rows[0].cells[0]
    shade(c, "F5F7FB")
    c.text = ""
    for k, line in enumerate(text.splitlines()):
        p = c.paragraphs[0] if k == 0 else c.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        set_font(p.add_run(line if line else " "), 7.5, font="Consolas")
    c.width = Cm(16.5)
    d.add_paragraph()


def build_w9_xlsx(passed):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Test Cases"
    head = ["TC ID", "Requirement", "Test Case Description", "Precondition", "Test Steps", "Expected Result", "Status (Pass/Fail)"]
    ws.append(head)
    for tc in TEST_CASES:
        ws.append([tc[0], tc[1], tc[2], tc[3], "\n".join(f"{i}. {s}" for i, s in enumerate(tc[4], 1)), tc[5], "Pass" if tc_status(tc[0]) == "AC" else ""])
    ws2 = wb.create_sheet("Unit Tests")
    ws2.append(["UT ID", "Requirement", "Function", "Description", "Status (Pass/Fail)"])
    for u in UNIT_TESTS:
        ws2.append([u[0], u[1], u[2], u[3], "Pass" if u[0] in passed else "Fail"])
    for sheet, widths in ((ws, [12, 12, 34, 30, 45, 45, 14]), (ws2, [8, 12, 20, 60, 14])):
        for i, w in enumerate(widths):
            sheet.column_dimensions[chr(65 + i)].width = w
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF", name=FONT)
            cell.fill = PatternFill("solid", fgColor="1E5EFF")
        for row in sheet.iter_rows():
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                if cell.row > 1:
                    cell.font = Font(name=FONT, size=10)
        sheet.freeze_panes = "A2"
    wb.save(OUT / "W9_Test_Cases_ParkQ.xlsx")


def save(d, name):
    OUT.mkdir(exist_ok=True)
    d.save(OUT / name)
    print("saved", name)


if __name__ == "__main__":
    ut_out, passed, all_ok = run_unit_tests()
    IT_OUT, IT_PASSED, IT_OK = run_tests("test_api_flow")
    print(f"integration tests: {len(IT_PASSED)} passed, ok={IT_OK}")
    print(f"unit tests: {len(passed)} passed, ok={all_ok}")
    build_w5()
    build_w6()
    build_w7()
    build_w8(ut_out, passed, all_ok)
    build_w9(ut_out, passed, all_ok)
    build_w9_xlsx(passed)
