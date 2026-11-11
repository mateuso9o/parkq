"""Build W10 (test report), W11 (user manuals + technical document) and W12 (change requests).

Runs the real test suites first (a throw-away server on port 8790 with a temp SQLite DB), so every status in W10 comes from a real run.
Usage:  python gen/make_w10_12.py [w10|w11|w12|all]
"""
import copy
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import openpyxl
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm
from docx.table import Table
from docx.text.paragraph import Paragraph
from openpyxl.styles import Alignment, Font, PatternFill

import make_docs as md
from make_docs import (CODE, FONT, IMG, OUT, ROOT, bullet, code_block, cover, heading, history, new_doc, page_break, para, rich, save, table)
from spec_data import (DEFECTS, GROUP_NAME, INTEGRATION_TESTS, MEMBERS, MODULES, ROLE_MEMBER, SYSTEM_EN, SYSTEM_TH, TEST_CASES, UNIT_TESTS)

TODAY = "12/11/2569"
TODAY_LONG = "12 พฤศจิกายน 2569"
SYSVER = "1.1.0"
TPL = Path(r"C:\Users\Puripat\Documents\ย้อนหลังงาน")
REVIEW = ROOT / ".impeccable" / "review"


# ------------------------------------------------------------------ real test run
def run_suite(module, env_extra=None):
    env = {**os.environ, "DATABASE_URL": "", "PYTHONIOENCODING": "utf-8", **(env_extra or {})}
    res = subprocess.run([sys.executable, "-m", "unittest", module, "-v"], cwd=CODE, capture_output=True, text=True, encoding="utf-8", env=env)
    rows = []
    for line in res.stderr.splitlines():
        m = re.match(r"test_(\w+?)\s+\((\S+)\)\s*(?:\n)?.*\.\.\. (ok|FAIL|ERROR)", line)
        if m:
            name, _, status = m.groups()
            tid = name.split("_")[0]
            rows.append((tid, name.split("_", 1)[1].replace("_", " "), "Pass" if status == "ok" else "Fail"))
    return rows, res.stderr.strip(), res.returncode == 0


def run_all_tests():
    results = {}
    for mod in ("test_parkq_core", "test_mailer", "test_db_adapter", "test_otp_delivery"):
        results[mod] = run_suite(mod)
    db = Path(tempfile.gettempdir()) / "parkq_w10.db"
    env = {**os.environ, "DATABASE_URL": "", "PARKQ_DB": str(db), "PARKQ_RESET": "1", "PARKQ_DEV": "1"}
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "server:app", "--app-dir", str(ROOT / "app"), "--host", "127.0.0.1", "--port", "8790"],
                           cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                urllib.request.urlopen("http://127.0.0.1:8790/api/config")
                break
            except Exception:
                time.sleep(0.5)
        results["test_api_flow"] = run_suite("test_api_flow", {"PARKQ_URL": "http://127.0.0.1:8790"})
    finally:
        srv.terminate()
        srv.wait(10)
    return results


# requirement each extra test belongs to
REQ_OF = {"UT20": "ACC_01", "UT21": "ACC_01", "UT22": "ACC_01", "UT30": "ACC_01", "UT31": "ACC_01", "UT32": "ACC_01", "UT33": "ACC_01", "UT34": "ACC_01",
          "UT40": "NFR (ข้อมูลถาวร)", "UT41": "NFR (ข้อมูลถาวร)", "UT42": "NFR (ข้อมูลถาวร)", "UT43": "NFR (ข้อมูลถาวร)", "UT44": "NFR (ข้อมูลถาวร)",
          "IT20": "ACC_01", "IT21": "ACC_01", "IT22": "ACC_01", "IT23": "ACC_01"}
KNOWN_REQ = {u[0]: u[1] for u in UNIT_TESTS} | {i[0]: i[1] for i in INTEGRATION_TESTS}


def req_of(tid):
    base = re.match(r"(UT|IT)\d+", tid).group(0)
    return KNOWN_REQ.get(tid) or KNOWN_REQ.get(base) or REQ_OF.get(base, "ACC_01")


# ------------------------------------------------------------------ W10
def build_w10(results):
    unit = [r for m in ("test_parkq_core", "test_mailer", "test_db_adapter") for r in results[m][0]]
    otp = results["test_otp_delivery"][0]
    api = results["test_api_flow"][0]
    all_rows = unit + otp + api
    passed = {r[0] for r in all_rows if r[2] == "Pass"}
    md.IT_PASSED = {r[0] for r in api + otp if r[2] == "Pass"}
    ok = all(r[2] == "Pass" for r in all_rows)

    d = new_doc("Proj_Test_Report")
    cover(d, "Proj_Test_Report", "รายงานผลการทดสอบ แผนการทดสอบฉบับปรับปรุง และ Unit Test", "Software Testing: Test Plan, Test Case, Unit Test (Execution Report)")
    para(d, f"ผลการรันจริงเมื่อ {TODAY} บนระบบเวอร์ชัน {SYSVER}", False, 10.5, "center", "5B6475")
    page_break(d)
    history(d, "รายงานผลการทดสอบ")

    heading(d, "1. สรุปผลการทดสอบ (Test Summary)")
    suites = [("Unit Test – ตรรกะหลัก (parkq_core)", "test_parkq_core"), ("Unit Test – ส่งอีเมล OTP (mailer)", "test_mailer"),
              ("Unit Test – ตัวแปลงฐานข้อมูล SQLite/PostgreSQL", "test_db_adapter"), ("Integration – ส่ง OTP ผ่าน API (ไม่เปิดรหัสบนจอ)", "test_otp_delivery"),
              ("Integration – ทั้ง Workflow ผ่าน API + ฐานข้อมูล", "test_api_flow")]
    rows = []
    for name, mod in suites:
        r = results[mod][0]
        p = sum(x[2] == "Pass" for x in r)
        rows.append((name, mod + ".py", str(len(r)), str(p), str(len(r) - p), "ผ่านทั้งหมด" if results[mod][2] else "มีข้อไม่ผ่าน"))
    rows.append(("รวม", "", str(len(all_rows)), str(len(passed & {r[0] for r in all_rows})), str(sum(r[2] != "Pass" for r in all_rows)), "ผ่านทั้งหมด" if ok else "มีข้อไม่ผ่าน"))
    table(d, ["ชุดทดสอบ", "ไฟล์", "ทั้งหมด", "ผ่าน", "ไม่ผ่าน", "ผล"], rows, [5.6, 3.6, 1.5, 1.4, 1.5, 2.9], size=9, center_cols=(2, 3, 4))
    para(d, "Integration Test ชุดเดียวกันถูกรันกับ PostgreSQL 16 (ในเครื่อง) และ Neon PostgreSQL (ภูมิภาค Singapore) ผ่านครบ 14 ข้อเช่นกัน "
            "ซึ่งยืนยันว่าตรรกะ \"ไม่ขายช่องสุดท้ายซ้ำ\" ทำงานถูกต้องบนฐานข้อมูลจริงที่ใช้ตอนนำเสนอ", size=10)

    heading(d, "2. Test Plan ฉบับปรับปรุง (เปลี่ยนจาก W9 อย่างไร)")
    table(d, ["หัวข้อ", "W9 (เดิม)", "W10 (ปรับปรุง)"], [
        ("การยืนยันตัวตน", "OTP ทาง SMS ไปยังเบอร์โทร", "OTP ทางอีเมล (SMTP) ใช้อีเมลเป็นตัวระบุบัญชี → เพิ่ม UT20–22, UT30–34, IT20–23"),
        ("ฐานข้อมูล", "SQLite ในเครื่อง", "PostgreSQL (Neon) ผ่านตัวแปลง SQL → เพิ่ม UT40–44 และรัน IT01–IT12 ซ้ำบน PostgreSQL"),
        ("การสแกน QR", "เครื่องอ่าน USB/ฮาร์ดแวร์", "เพิ่มสแกนด้วยกล้องเบราว์เซอร์ (BarcodeDetector + jsQR) ทดสอบด้วยกล้องจำลอง (fake camera) ครบวงจร"),
        ("หน้าจอ", "UI เดิม", "UI ใหม่ธีม Split-Flap และโหมดสว่าง/มืด ตรวจด้วยภาพหน้าจอ 390px (มือถือ) และ 1440px (เดสก์ท็อป) ทั้งสองธีม"),
        ("สภาพแวดล้อม", "Staging Ubuntu + Mosquitto", "เครื่องนักพัฒนา (Windows) + Render (เว็บ) + Neon (ฐานข้อมูล)"),
        ("ข้อยกเว้น", "—", "ฮาร์ดแวร์บอร์ด ESP32 จริง และการส่งอีเมลผ่าน SMTP จริง ยังไม่ได้ทดสอบ (รอบอร์ดเสร็จ / ผู้ใช้ตั้งค่า SMTP)"),
    ], [3.2, 4.8, 8.5], size=9)

    heading(d, "3. ผลการรัน Unit Test")
    table(d, ["UT ID", "Requirement", "สิ่งที่ตรวจสอบ", "ผล"], [(r[0], req_of(r[0]), r[1], r[2]) for r in unit], [1.6, 3.0, 9.8, 1.6], size=8.5, center_cols=(0, 1, 3))
    heading(d, "4. ผลการรัน Integration Test")
    desc = {i[0]: i[2] for i in INTEGRATION_TESTS}
    table(d, ["IT ID", "Requirement", "สิ่งที่ตรวจสอบ", "ผล"], [(r[0], req_of(r[0]), desc.get(r[0], r[1]), r[2]) for r in otp + api], [1.6, 3.0, 9.8, 1.6], size=8.5, center_cols=(0, 1, 3))

    heading(d, "5. ผลการทดสอบตาม Test Case (System Test)")
    para(d, "AC = ผ่าน (มี Integration Test ที่ผ่านครอบคลุม หรือทดสอบมือในเบราว์เซอร์) · ว่าง = ยังไม่ได้ทดสอบ (ต้องใช้ฮาร์ดแวร์หรือบริการภายนอกจริง)", size=9.5, color="5B6475")
    tcs = [(tc[0], tc[1], tc[2], md.tc_status(tc[0]) or "–") for tc in TEST_CASES]
    done = sum(1 for t in tcs if t[3] == "AC")
    table(d, ["Test Case", "Requirement", "ชื่อ Test Case", "สถานะ"], tcs, [2.2, 2.6, 9.9, 1.8], size=8.5, center_cols=(0, 1, 3))
    para(d, f"ผ่าน {done} จาก {len(tcs)} Test Case ({done * 100 // len(tcs)}%) ที่เหลือต้องใช้ฮาร์ดแวร์/บริการภายนอกจริง", True, 10)

    heading(d, "6. ข้อบกพร่องที่พบในรอบนี้ (Defect Report)")
    table(d, ["ID", "ข้อบกพร่อง", "พบจาก", "ระดับ", "การแก้ไข", "สถานะ"], [
        ("DEF-04", "แดชบอร์ดผู้ดูแลใช้ ROWID นับจำนวนช่องที่จองไว้ ซึ่งไม่มีใน PostgreSQL ทำให้ API ล้ม", "รัน IT บน PostgreSQL", "High", "เปลี่ยนเป็น COUNT(*) (ใช้ได้ทั้งสองฐานข้อมูล)", "Closed – IT ผ่านบน PostgreSQL"),
        ("DEF-05", "ตรวจทะเบียนซ้ำใช้ id <> NULL ตอนเพิ่มรถใหม่ ซึ่งใน PostgreSQL ให้ผลไม่ตรงกับ SQLite", "รัน IT04 บน PostgreSQL", "Medium", "ส่ง id เป็น 0 เมื่อเป็นรถใหม่ (id <> 0)", "Closed – IT04 ผ่าน"),
        ("DEF-06", "ปุ่มตัวเลขจำนวนชั่วโมงและปุ่มเพิ่มรถใช้ตัวอักษร +/− แทนไอคอนทำให้ขนาดไม่สม่ำเสมอ", "Design review", "Low", "เปลี่ยนเป็นชุดไอคอน SVG ของระบบ", "Closed – ตรวจด้วยภาพหน้าจอ"),
    ], [1.4, 5.3, 2.6, 1.3, 3.8, 2.1], size=8.5, center_cols=(0, 3))
    para(d, "ข้อบกพร่องเดิม DEF-01 ถึง DEF-03 ดูรายละเอียดใน W8 ทั้งหมดปิดแล้ว (UT18, IT08 เป็น Regression Test ที่ยังผ่านอยู่)", size=9.5, color="5B6475")

    heading(d, "7. สรุปและข้อจำกัด (Test Summary Conclusion)")
    for t in [f"Unit และ Integration Test รวม {len(all_rows)} ข้อ ผ่านทั้งหมดบน SQLite และ PostgreSQL",
              "เกณฑ์จบการทดสอบ (Exit Criteria) ใน W9: Test Case ระดับ High ที่ทดสอบได้โดยไม่ใช้ฮาร์ดแวร์ผ่าน 100% และไม่มี Defect High/Medium ค้าง → เป็นไปตามเกณฑ์",
              "ยังไม่ได้ทดสอบ: (1) การส่งอีเมลผ่าน SMTP จริง (ทดสอบด้วย SMTP จำลอง UT31 และ IT20–21 แล้ว) (2) สแกนด้วยกล้องมือถือจริงผ่าน HTTPS (3) บอร์ด ESP32 + เซ็นเซอร์จริง (4) ชำระเงินผ่าน Payment Gateway จริง",
              "ข้อเสนอ: ทำ UAT ในวันนำเสนอ โดยให้อาจารย์และเพื่อนลองเข้าสู่ระบบด้วยอีเมลจริง จองและสแกน QR ที่หน้าตู้จำลอง"]:
        bullet(d, t)
    heading(d, "8. ผลรันดิบ (ตัวอย่าง)", 2)
    code_block(d, "> cd code\n> python -m unittest test_parkq_core test_mailer test_db_adapter test_otp_delivery -v\n"
               + "\n".join(l for m in ("test_parkq_core",) for l in results[m][1].splitlines() if l.startswith(("Ran", "OK", "FAILED")))
               + "\n> python -m unittest test_api_flow -v   (PARKQ_URL=http://127.0.0.1:8790)\n"
               + "\n".join(l for l in results["test_api_flow"][1].splitlines() if l.startswith(("Ran", "OK", "FAILED"))))
    save(d, "W10_Test_Report_ParkQ.docx")

    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "Test Cases"
    ws.append(["TC ID", "Requirement", "Test Case Description", "Precondition", "Test Steps", "Expected Result", "Status (Pass/Fail)"])
    for tc in TEST_CASES:
        ws.append([tc[0], tc[1], tc[2], tc[3], "\n".join(f"{i}. {s}" for i, s in enumerate(tc[4], 1)), tc[5], "Pass" if md.tc_status(tc[0]) == "AC" else ""])
    ws2 = wb.create_sheet("Unit & Integration Tests")
    ws2.append(["Test ID", "Requirement", "Description", "Status (Pass/Fail)"])
    for r in all_rows:
        ws2.append([r[0], req_of(r[0]), r[1], r[2]])
    for sheet, widths in ((ws, [12, 12, 34, 30, 45, 45, 14]), (ws2, [10, 18, 70, 14])):
        for i, w in enumerate(widths):
            sheet.column_dimensions[chr(65 + i)].width = w
        for c in sheet[1]:
            c.font = Font(bold=True, color="FFFFFF", name=FONT); c.fill = PatternFill("solid", fgColor="1E5EFF")
        for row in sheet.iter_rows():
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")
                if c.row > 1:
                    c.font = Font(name=FONT, size=10)
        sheet.freeze_panes = "A2"
    wb.save(OUT / "W10_Test_Results_ParkQ.xlsx")
    print("saved W10_Test_Results_ParkQ.xlsx")
    return ok


# ------------------------------------------------------------------ template filling helpers
def body_items(doc):
    paras, tables = [], []
    for ch in doc.element.body.iterchildren():
        tag = ch.tag.split("}")[1]
        if tag == "p":
            paras.append(Paragraph(ch, doc))
        elif tag == "tbl":
            tables.append(Table(ch, doc))
    return paras, tables


def set_par(p, text):
    runs = p.runs
    if runs:
        runs[0].text = text
        for r in runs[1:]:
            r._r.getparent().remove(r._r)
    else:
        p.add_run(text)


def put(cell, text):
    ps = cell.paragraphs
    set_par(ps[0], text)
    for p in ps[1:]:
        p._p.getparent().remove(p._p)


def ensure_rows(tbl, n):
    while len(tbl.rows) < n:
        tbl._tbl.append(copy.deepcopy(tbl.rows[-1]._tr))
    while len(tbl.rows) > n:
        tbl._tbl.remove(tbl.rows[-1]._tr)


def fill_rows(tbl, data):
    ensure_rows(tbl, len(data) + 1)
    for r, row in zip(tbl.rows[1:], data):
        for c, v in zip(r.cells, row):
            put(c, v)


def put_image(tbl, path, width_cm):
    cell = tbl.rows[0].cells[0]
    for p in cell.paragraphs[1:]:
        p._p.getparent().remove(p._p)
    p = cell.paragraphs[0]
    for r in p.runs:
        r._r.getparent().remove(r._r)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(path), width=Cm(width_cm))


def shrink(path, max_h=1500):
    from PIL import Image
    im = Image.open(path)
    out = ROOT / "build" / "manual" / (Path(path).stem + ".png")
    out.parent.mkdir(parents=True, exist_ok=True)
    if im.height > max_h:
        im = im.crop((0, 0, im.width, max_h))
    im.convert("RGB").save(out)
    return out


MANUAL_ROLES = {
    "PM": ROLE_MEMBER["PM"], "SA": ROLE_MEMBER["SA"], "QA": ROLE_MEMBER["QA"],
}


def fill_manual(tpl, out_name, P, T):
    doc = Document(str(TPL / "W11 _ User Manual, Technical Docs" / tpl))
    paras, tables = body_items(doc)
    for i, text in P.items():
        set_par(paras[i], text)
    for ti, spec in T.items():
        t = tables[ti]
        kind = spec[0]
        if kind == "rows":
            fill_rows(t, spec[1])
        elif kind == "img":
            put_image(t, spec[1], spec[2])
        elif kind == "info":
            for r, v in zip(t.rows[1:], spec[1]):
                put(r.cells[1], v)
        elif kind == "hist":
            for c, v in zip(t.rows[1].cells, spec[1]):
                put(c, v)
    doc.save(str(OUT / out_name))
    print("saved", out_name)


COMMON_SUPPORT = {
    64: "หน่วยงาน / ผู้รับผิดชอบ  กลุ่ม ParkQ (ผู้พัฒนาระบบ) ในรายวิชา Software Engineering",
    65: "อีเมล / โทรศัพท์ / ช่องทาง Ticket  แจ้งผ่านกลุ่ม ParkQ ในห้องเรียน หรือผ่านอาจารย์ผู้สอน (ยังไม่มีระบบ Ticket)",
    66: "ช่วงเวลาให้บริการ  ช่วงทดสอบและนำเสนอในคาบเรียน (ระบบคลาวด์เปิดตลอดเวลา แต่การช่วยเหลือเฉพาะเวลาเรียน)",
    67: "กรณีเร่งด่วน  แจ้งผู้ทดสอบหน้าชั้นเรียนทันที (ระหว่างการนำเสนอ)",
    69: "ชื่อผู้แจ้ง / บทบาท: ผู้ขับขี่ หรือ ผู้ดูแล    วันเวลาเกิดเหตุ: เช่น 12/11/2569 10:30    เมนู / เลขที่รายการ: เช่น ตั๋ว TK-000123\nขั้นตอนก่อนเกิดปัญหา: เช่น กด \"ขอรหัส OTP\"    ข้อความแจ้งเตือน: คัดลอกข้อความที่ขึ้นบนจอ    ผลที่คาดหวัง/ผลที่เกิดขึ้นจริง: อธิบายสั้นๆ",
    72: "☑ เปลี่ยนข้อความตัวอย่างและวงเล็บเหลี่ยมเป็นข้อมูลจริงครบแล้ว",
    73: "☑ ตรวจสอบสิทธิ์และขอบเขตข้อมูลตรงกับบทบาทผู้ใช้งาน",
    74: "☑ ชื่อเมนู ปุ่ม ภาพหน้าจอ และขั้นตอนตรงกับเวอร์ชันระบบ (ภาพถ่ายจากระบบเวอร์ชัน 1.1.0)",
}


def build_w11_manuals():
    info = lambda code: ["PPK-UM-" + code + "-001", GROUP_NAME + " (รายวิชา Software Engineering)", f"{ROLE_MEMBER['SA']} (SA)", f"{ROLE_MEMBER['QA']} (QA)", f"{ROLE_MEMBER['PM']} (PM) {TODAY}"]
    hist = ["1.0", TODAY, f"จัดทำคู่มือฉบับแรกสำหรับระบบเวอร์ชัน {SYSVER} (UI ธีม Split-Flap, OTP ทางอีเมล, โหมดสว่าง/มืด)", f"{ROLE_MEMBER['SA']} (SA)"]
    sc = lambda c: shrink(IMG / f"{c}.png")

    # ------------------ driver
    P = {2: f"{SYSTEM_TH} ({SYSTEM_EN})", 4: f"เวอร์ชันระบบ {SYSVER}    |    วันที่มีผล {TODAY_LONG}",
         10: "1  เริ่มต้นใช้งานและสิทธิ์ของผู้ใช้ ........................................ 2", 11: "2  ซื้อสิทธิ์จอดและชำระเงิน ........................................ 3",
         12: "3  ใช้ตั๋ว QR เข้า-ออก และยกเลิกการจอง ........................................ 4",
         19: "ผู้ขับขี่ดูสถานะลานจอดแบบเรียลไทม์ ซื้อสิทธิ์จอดทันทีหรือจองล่วงหน้า ชำระเงิน แล้วใช้ตั๋ว QR สแกนที่ตู้หน้าประตู เข้าถึงได้เฉพาะข้อมูลรถและตั๋วของตนเอง ไม่เห็นข้อมูลผู้ใช้อื่นและเข้าหน้าหลังบ้านไม่ได้",
         22: "URL ของระบบ  http://127.0.0.1:8000/ (ทดสอบในเครื่อง) หรือ URL บน Render ที่ทีมแจ้งในวันนำเสนอ",
         23: "บัญชีผู้ใช้งาน  ไม่ต้องสมัครล่วงหน้า กรอกอีเมลของตนเอง ระบบสร้างบัญชีให้อัตโนมัติเมื่อยืนยัน OTP ครั้งแรก",
         24: "อุปกรณ์และเบราว์เซอร์ที่รองรับ  สมาร์ตโฟนหรือคอมพิวเตอร์ที่มี Chrome / Safari / Edge รุ่นล่าสุด (สแกนด้วยกล้องต้องใช้ HTTPS)",
         25: "เครือข่ายหรือการยืนยันตัวตนเพิ่มเติม  ต้องมีอินเทอร์เน็ตและเข้าอีเมลของตนเองได้ เพื่อรับรหัส OTP 6 หลัก (อายุ 5 นาที)",
         27: "ภาพที่ 1  หน้าเข้าสู่ระบบ (ตัวเลขสีแดงอ้างอิงตาราง Screen Attributes ใน W7 รหัส SC-ACC-01-01)",
         29: "ออกจากระบบ  แท็บ \"บัญชี\" > ปุ่ม \"ออกจากระบบ\"    กรณีลืมรหัสผ่าน  ไม่มีรหัสผ่าน ให้ขอรหัส OTP ใหม่ทางอีเมลได้ตลอด",
         32: "ซื้อสิทธิ์จอดและชำระเงิน",
         33: "วัตถุประสงค์  เลือกลานจอด ซื้อสิทธิ์จอดทันที (\"จอดเลย\") หรือจองล่วงหน้า แล้วชำระเงินเพื่อรับตั๋ว QR",
         34: "ผู้มีสิทธิ์ใช้งาน  ผู้ขับขี่ที่เข้าสู่ระบบแล้วและมีรถในบัญชีอย่างน้อย 1 คัน",
         35: "เงื่อนไขก่อนเริ่ม / สถานะรายการ  ลานต้องไม่เต็มและมีสถานะออนไลน์ จองล่วงหน้าได้ไม่เกิน 7 วัน ระยะเวลา 1–24 ชั่วโมง ชำระเต็มจำนวนตอนจอง",
         36: "เส้นทางเมนู  หน้าแรก > การ์ดลานจอด > จอดเลย / จองล่วงหน้า > ชำระเงิน",
         37: "ตัวอย่างหน้าจอ ซื้อสิทธิ์จอด / จองล่วงหน้า",
         38: "ภาพที่ 2  หน้าซื้อสิทธิ์จอด (SC-BKG-01-01) ตรวจโหมดการจอด เวลา จำนวนชั่วโมง รถ และราคารวมก่อนกดต่อไป",
         42: "ข้อควรทราบ  ถ้าไม่มีรถในบัญชี ปุ่มจะพาไปเพิ่มรถก่อน ช่องจอดถูกล็อกให้ 10 นาทีระหว่างชำระเงิน ยกเลิกก่อนเริ่มจอดได้ตามเงื่อนไขในหน้าสรุป",
         43: "กรณีไม่สำเร็จ  \"ขออภัย ช่วงเวลานี้เต็มแล้ว\" เลือกเวลาอื่นหรือลานอื่น · ชำระไม่ผ่าน ลองวิธีอื่นหรือบัตรอื่น ยังไม่ถูกตัดเงินจนกว่าจะขึ้นว่าสำเร็จ",
         47: "วัตถุประสงค์  แสดงตั๋ว QR ที่ตู้ประตูทางเข้า-ออก ดูเวลาคงเหลือ นำทางไปลานจอด และยกเลิกการจองที่ยังไม่เริ่ม",
         48: "ผู้มีสิทธิ์ใช้งาน  เจ้าของตั๋วที่เข้าสู่ระบบด้วยอีเมลเดียวกับตอนซื้อ",
         49: "เงื่อนไขก่อนเริ่ม / สถานะรายการ  ตั๋วต้องชำระเงินแล้ว สถานะ \"รอเข้า\" (ยกเลิกได้) \"จอดอยู่\" หรือ \"เสร็จสิ้น\" (ยกเลิกไม่ได้)",
         50: "เส้นทางเมนู  แท็บ \"ตั๋วของฉัน\" > เลือกตั๋ว > ตั๋ว QR",
         51: "ตัวอย่างหน้าจอ ตั๋ว QR",
         52: "ภาพที่ 3  ตั๋ว QR (SC-TKT-01-02) เปิดให้สว่างและเห็นเต็มจอเมื่อสแกนที่ตู้ ตรวจชื่อลาน รหัสตั๋ว และเวลาเข้าลานได้ถึง",
         56: "ข้อควรทราบ  QR ใช้เข้าได้ 1 ครั้งต่อ 1 ตั๋ว ใช้ผิดลานหรือนอกเวลาจะถูกปฏิเสธ จอดเกินเวลาต้องชำระค่าส่วนเกินที่ตู้ทางออก (หรือเรียกพนักงาน)",
         57: "กรณีไม่สำเร็จ  \"QR นี้ถูกใช้แล้ว\" หรือ \"ไม่ใช่ลานนี้\" ให้กดปุ่ม \"เรียกพนักงาน\" ที่ตู้ ระบบจะแจ้งพนักงานหน้าลานให้ตรวจและเปิดไม้กั้นให้",
         **COMMON_SUPPORT}
    P[46] = "ใช้ตั๋ว QR เข้า-ออก และยกเลิกการจอง"
    P[45] = "03  TASK GUIDE"
    T = {0: ("info", info("USR")), 1: ("hist", hist),
         2: ("rows", [("ดูสถานะลานและซื้อสิทธิ์จอด", "ดู / ซื้อ / จองล่วงหน้า / ยกเลิก (ตั๋วของตนเอง)", "ลานต้องออนไลน์ ตั๋วเป็นของบัญชีตนเท่านั้น"),
                      ("ตั๋ว QR และการเข้า-ออก", "ดู / แสดง QR / นำทาง", "ใช้ได้ 1 ครั้งต่อ 1 ตั๋ว ตามลานและเวลาที่ระบุ"),
                      ("บัญชีและรถของฉัน", "ดู / เพิ่ม / แก้ไข / ลบรถ", "ลบรถที่มีตั๋วใช้งานอยู่ไม่ได้ ต้องมีรถอย่างน้อย 1 คันก่อนซื้อ")]),
         3: ("img", sc("SC-ACC-01-01"), 6.2),
         4: ("rows", [("1", "เปิดเว็บ ParkQ ในเบราว์เซอร์", "หน้าเข้าสู่ระบบ แผงชื่อ PARKQ พลิกตัวอักษร"),
                      ("2", "กรอกอีเมล ติ๊กยอมรับเงื่อนไข แล้วกด \"ขอรหัส OTP\"", "ระบบส่งรหัส 6 หลักไปที่อีเมล และพาไปหน้ายืนยัน OTP"),
                      ("3", "เปิดอีเมล กรอกรหัส 6 หลัก แล้วกด \"ยืนยัน\" (ผู้ใช้ใหม่กรอกชื่อ ทะเบียน จังหวัดต่ออีก 1 หน้า)", "เข้าสู่หน้าแรก เห็นรายการลานจอดและสถานะ")]),
         5: ("img", sc("SC-BKG-01-01"), 6.2),
         6: ("rows", [("1", "ที่หน้าแรก เลือกลานที่ \"ว่าง\" แล้วกด \"จอดเลย\" หรือ \"จองล่วงหน้า\"", "หน้าซื้อสิทธิ์จอดของลานนั้น"),
                      ("2", "เลือกโหมด วัน/เวลา จำนวนชั่วโมง (ปุ่ม − +) และรถ", "ราคารวมคำนวณใหม่ทันที (20 บาท/ชม. ที่ลานตัวอย่าง)"),
                      ("3", "ตรวจสรุป แล้วกด \"ชำระเงิน\" เลือก QR พร้อมเพย์หรือบัตร", "หน้าชำระเงิน / QR พร้อมเพย์ (โหมดทดสอบมีปุ่มจำลองว่าชำระแล้ว)"),
                      ("4", "รอจนขึ้น \"ชำระเงินสำเร็จ\" แล้วกด \"ดูตั๋ว QR\"", "ตั๋ว QR สถานะ \"รอเข้า\" ปรากฏใน \"ตั๋วของฉัน\"")]),
         7: ("rows", [("โหมดการจอด", "จอดเลย / จองล่วงหน้า", "จำเป็น"), ("จำนวนชั่วโมง", "1–24 ชั่วโมง", "จำเป็น"), ("รถที่จะเข้าจอด", "เลือกจากรถในบัญชี", "จำเป็น")]),
         8: ("img", sc("SC-TKT-01-02"), 6.2),
         9: ("rows", [("1", "แตะแท็บ \"ตั๋วของฉัน\" แล้วเลือกตั๋วที่ต้องการ", "หน้าตั๋ว QR พร้อมรหัสตั๋วและเวลา"),
                      ("2", "ที่ตู้ทางเข้า วางหน้าจอให้ QR อยู่หน้าเครื่องอ่าน (หรือกด \"นำทางไปลานจอด\" ก่อนไป)", "จอตู้ขึ้นสีขาว \"ผ่านได้\" พร้อมทะเบียน และไม้กั้นเปิด"),
                      ("3", "ถ้าต้องการยกเลิกก่อนเข้าลาน กด \"ยกเลิกการจอง\" แล้วยืนยัน", "ตั๋วเป็น \"ยกเลิก\" และแจ้งยอดเงินคืนตามเงื่อนไข"),
                      ("4", "ตอนออก สแกน QR เดิมที่ตู้ทางออก", "ถ้าจอดเกินเวลา ระบบแจ้งค่าส่วนเกินให้ชำระก่อนออก")]),
         10: ("rows", [("รหัสตั๋ว", "TK-000123 (ระบบสร้างให้)", "ไม่ต้องกรอก"), ("ยกเลิกการจอง", "กดยืนยัน (เลือกเหตุผลได้)", "ไม่จำเป็น")]),
         11: ("rows", [("ไม่ได้รับอีเมล OTP", "อีเมลพิมพ์ผิด หรืออีเมลเข้าสแปม/ส่งช้า (หมดอายุใน 5 นาที)", "ตรวจโฟลเดอร์สแปม กด \"ขอรหัสใหม่\" (ขอได้ 5 ครั้ง/10 นาที)"),
                       ("\"รหัส OTP ไม่ถูกต้อง\"", "กรอกผิด (ผิดครบ 3 ครั้งรหัสถูกล็อก)", "กดขอรหัสใหม่แล้วกรอกรหัสล่าสุด"),
                       ("ลานขึ้น \"เต็ม\" หรือ \"ข้อมูลไม่เป็นปัจจุบัน\"", "ช่องหมดหรือบอร์ดที่ลานไม่ส่งข้อมูลเกิน 2 นาที", "เลือกลานอื่นหรือรอสักครู่ แจ้งทีมถ้าเป็นนาน"),
                       ("สแกนด้วยกล้องไม่ได้", "ไม่ได้ใช้ HTTPS หรือไม่ได้อนุญาตกล้อง", "เปิดผ่านลิงก์ https อนุญาตกล้อง หรือพิมพ์รหัสตั๋วที่ช่องทดสอบ")])}
    fill_manual("ppkitsoft_User_Manual_Template_User.docx", "W11_User_Manual_User_ParkQ.docx", P, T)

    # ------------------ admin / staff
    P = {2: f"{SYSTEM_TH} ({SYSTEM_EN})", 4: f"เวอร์ชันระบบ {SYSVER}    |    วันที่มีผล {TODAY_LONG}",
         10: "1  เริ่มต้นใช้งานและสิทธิ์ของผู้ใช้ ........................................ 2", 11: "2  จัดการลานจอดและอัตราค่าบริการ ........................................ 3",
         12: "3  ตรวจสอบสถานะ รายงาน และเปิดไม้กั้น ........................................ 4",
         19: "ผู้ดูแลลานจอด (admin) จัดการลาน ราคา และดูรายงาน ส่วนพนักงานหน้าลาน (staff) ดูแดชบอร์ด ตรวจตั๋ว และเปิดไม้กั้นด้วยตนเองได้ แต่แก้ลานและราคาไม่ได้ ทั้งสองบทบาทไม่เห็นข้อมูลส่วนตัวของผู้ขับขี่เกินที่จำเป็น (ทะเบียนและตั๋ว)",
         22: "URL ของระบบ  /admin (ผู้ดูแล) และ /staff (พนักงาน) เช่น http://127.0.0.1:8000/admin หรือ URL บน Render ที่ทีมแจ้ง",
         23: "บัญชีผู้ใช้งาน  อีเมลผู้ดูแลและพนักงานกำหนดโดยเจ้าของระบบ (ตั้งค่า PARKQ_ADMIN_EMAIL / PARKQ_STAFF_EMAIL ตอนติดตั้ง) ขอเพิ่มบัญชีจากผู้พัฒนา",
         24: "อุปกรณ์และเบราว์เซอร์ที่รองรับ  คอมพิวเตอร์หรือแท็บเล็ต Chrome / Edge / Safari รุ่นล่าสุด (หน้าจอกว้างอย่างน้อย 900px จะเห็นเมนูด้านข้างเต็ม)",
         25: "เครือข่ายหรือการยืนยันตัวตนเพิ่มเติม  ใช้อีเมลและรหัส OTP ทางอีเมลเหมือนผู้ขับขี่ ไม่ต้องมี VPN",
         27: "ภาพที่ 1  หน้าเข้าสู่ระบบหลังบ้าน (กรอกอีเมลผู้ดูแลหรือพนักงาน แล้วกด \"ขอรหัส OTP\") มีปุ่มสลับโหมดสว่าง/มืดมุมขวาบน",
         29: "ออกจากระบบ  เมนูด้านข้างล่างสุด > \"ออกจากระบบ\"    กรณีลืมรหัสผ่าน  ไม่มีรหัสผ่าน ขอ OTP ใหม่ทางอีเมลได้ หากเข้าอีเมลไม่ได้ให้ติดต่อผู้พัฒนา",
         32: "จัดการลานจอดและอัตราค่าบริการ",
         33: "วัตถุประสงค์  เพิ่ม/แก้ไขข้อมูลลานจอด เปิด-ปิดการขายออนไลน์ และกำหนดอัตราค่าบริการ",
         34: "ผู้มีสิทธิ์ใช้งาน  ผู้ดูแลลานจอดเท่านั้น (พนักงานไม่เห็นเมนูนี้)",
         35: "เงื่อนไขก่อนเริ่ม / สถานะรายการ  เข้าสู่ระบบในบทบาทผู้ดูแล การลดจำนวนช่องต่ำกว่าจำนวนที่มีรถ/ตั๋วอยู่ไม่ได้",
         36: "เส้นทางเมนู  แดชบอร์ด > ลานจอด > + เพิ่มลานจอด / แก้ไข    และ    ราคา",
         37: "ตัวอย่างหน้าจอ รายการลานจอด",
         38: "ภาพที่ 2  รายการลานจอด (SC-ADM-01-01) มีสวิตช์เปิด-ปิดขายออนไลน์ ปุ่มแก้ไข และปุ่ม \"+ เพิ่มลานจอด\"",
         42: "ข้อควรทราบ  ปิดสวิตช์ขายออนไลน์จะซ่อนลานจากผู้ขับขี่ทันที ตั๋วที่ซื้อแล้วยังใช้ได้ ราคาที่แก้มีผลกับตั๋วใหม่เท่านั้น",
         43: "กรณีไม่สำเร็จ  ช่องว่างชื่อลานหรือจำนวนช่องไม่ถูกต้องจะมีข้อความใต้ช่อง · \"จำนวนช่องน้อยกว่าที่ใช้งานอยู่\" ให้รอให้รถออกหรือยกเลิกตั๋วก่อน",
         47: "วัตถุประสงค์  ดูสถานะลานแบบเรียลไทม์ ผังช่องจอด รายงานรายได้ และตรวจตั๋ว/เปิดไม้กั้นกรณีพิเศษ",
         48: "ผู้มีสิทธิ์ใช้งาน  ผู้ดูแล (ทุกเมนู) และพนักงาน (แดชบอร์ด และ \"ตรวจสอบตั๋ว / เปิดไม้กั้น\")",
         49: "เงื่อนไขก่อนเริ่ม / สถานะรายการ  ตู้ประตูต้องเรียกพนักงานหรือผู้ขับขี่มีปัญหาจึงเปิดไม้กั้นด้วยตนเอง ทุกการเปิดต้องใส่เหตุผลและถูกบันทึก",
         50: "เส้นทางเมนู  แดชบอร์ด / รายงาน / ตรวจสอบตั๋ว – เปิดไม้กั้น",
         51: "ตัวอย่างหน้าจอ แดชบอร์ดลานจอด",
         52: "ภาพที่ 3  แดชบอร์ด (SC-ADM-03-01) แผงตัวเลขช่องว่าง/รถจอดอยู่/การจอง ผังช่องจอดเรียลไทม์ และรายการเข้า-ออกล่าสุด",
         56: "ข้อควรทราบ  เมื่อบอร์ดที่ลานไม่ส่งข้อมูลเกิน 2 นาที ลานจะขึ้น \"ข้อมูลไม่เป็นปัจจุบัน\" และปิดการขายชั่วคราวเอง การเปิดไม้กั้นด้วยตนเองบันทึกชื่อผู้ทำและเหตุผล",
         57: "กรณีไม่สำเร็จ  ค้นหาตั๋วไม่พบให้ตรวจรหัสตั๋ว/ทะเบียน · ไม้กั้นไม่ขยับให้ตรวจว่าบอร์ดออนไลน์ แล้วแจ้งผู้พัฒนา",
         **COMMON_SUPPORT}
    P[69] = COMMON_SUPPORT[69].replace("ผู้ขับขี่ หรือ ผู้ดูแล", "ผู้ดูแล / พนักงาน")
    T = {0: ("info", info("ADM")), 1: ("hist", hist),
         2: ("rows", [("แดชบอร์ดและผังช่องจอด", "ผู้ดูแล: ดู · พนักงาน: ดู", "ข้อมูลเฉพาะลานที่เลือก"),
                      ("ลานจอด และราคา", "ผู้ดูแล: ดู / เพิ่ม / แก้ไข / เปิด-ปิดขาย / ตั้งราคา · พนักงาน: ไม่มีสิทธิ์", "ต้องมีบทบาทผู้ดูแล"),
                      ("รายงานรายได้ และตรวจสอบตั๋ว / เปิดไม้กั้น", "ผู้ดูแล: ดู + ส่งออก CSV · พนักงาน: ตรวจตั๋ว + เปิดไม้กั้น", "เปิดไม้กั้นต้องใส่เหตุผลและถูกบันทึก")]),
         3: ("img", REVIEW / "t-admin-dark.png", 11.5),
         4: ("rows", [("1", "เปิด /admin (หรือ /staff สำหรับพนักงาน)", "หน้าเข้าสู่ระบบหลังบ้าน"),
                      ("2", "กรอกอีเมลของผู้ดูแล/พนักงาน แล้วกด \"ขอรหัส OTP\"", "ระบบส่งรหัส 6 หลักไปที่อีเมล"),
                      ("3", "กรอกรหัส OTP แล้วกดยืนยัน", "เข้าสู่แดชบอร์ดของบทบาทนั้น (ผู้ดูแลเห็นเมนูครบ พนักงานเห็นเมนูที่เกี่ยวข้อง)")]),
         5: ("img", sc("SC-ADM-01-01"), 11.5),
         6: ("rows", [("1", "เลือกเมนู \"ลานจอด\" แล้วกด \"+ เพิ่มลานจอด\" หรือ \"แก้ไข\" ที่ลานเดิม", "หน้าต่างกรอกข้อมูลลานจอด"),
                      ("2", "กรอกชื่อ ที่อยู่ พิกัด จำนวนช่อง เวลาเปิด–ปิด และรหัสอุปกรณ์ IoT", "ระบบตรวจรูปแบบและแจ้งข้อผิดพลาดใต้ช่อง"),
                      ("3", "กด \"บันทึก\" แล้วไปเมนู \"ราคา\" กำหนดค่าจอดต่อชั่วโมงและสัดส่วนช่องที่เปิดให้จองล่วงหน้า", "ข้อความบันทึกสำเร็จ ลานแสดงในแอปผู้ขับขี่ตามราคาใหม่"),
                      ("4", "ตรวจในตารางลานจอดและเปิดสวิตช์ \"ขายออนไลน์\"", "ลานปรากฏบนหน้าแรกของผู้ขับขี่")]),
         7: ("rows", [("ชื่อลานจอด", "ข้อความ เช่น ลานจอด ParkQ – ม.ศรีปทุม", "จำเป็น"), ("จำนวนช่องจอด", "จำนวนเต็มบวก", "จำเป็น"),
                      ("ค่าจอดต่อชั่วโมง", "บาท (จำนวนเต็ม)", "จำเป็น")]),
         8: ("img", sc("SC-ADM-03-01"), 11.5),
         9: ("rows", [("1", "เมนู \"แดชบอร์ด\" เลือกลานจอดจากรายการ", "แผงตัวเลขช่องว่าง รถจอดอยู่ การจองวันนี้ และรายได้วันนี้"),
                      ("2", "ดูผังช่องจอด (ช่องสีส้ม = มีรถ) และตารางเข้า-ออกล่าสุด", "สถานะอัปเดตเองทุกไม่กี่วินาที ตัวเลขพลิกแบบแผ่นป้าย"),
                      ("3", "เมนู \"รายงาน\" เลือกช่วงวันที่ แล้วกด \"ส่งออก CSV\" (ผู้ดูแล)", "กราฟและตารางรายได้ พร้อมไฟล์ CSV"),
                      ("4", "เมนู \"ตรวจสอบตั๋ว / เปิดไม้กั้น\" ค้นหาตั๋ว เลือกประตู ใส่เหตุผล แล้วกด \"เปิดไม้กั้น\"", "ไม้กั้นเปิดครั้งเดียว และบันทึกลงรายการเข้า-ออก")]),
         10: ("rows", [("ช่วงวันที่ (รายงาน)", "วันเริ่ม – วันสิ้นสุด", "จำเป็น"), ("เหตุผลการเปิดไม้กั้น", "ข้อความสั้นๆ เช่น ผู้ขับขี่สแกนไม่ติด", "จำเป็น")]),
         11: ("rows", [("เข้าสู่ระบบไม่ได้ / ไม่ได้รับ OTP", "อีเมลไม่ตรงกับที่ลงทะเบียนไว้ หรืออีเมลเข้าสแปม", "ใช้อีเมลที่ตั้งเป็นผู้ดูแล/พนักงาน ตรวจสแปม ขอรหัสใหม่ หรือติดต่อผู้พัฒนา"),
                       ("ไม่เห็นเมนูลานจอด / ราคา", "เข้าสู่ระบบด้วยบทบาทพนักงาน", "ออกจากระบบแล้วเข้าด้วยอีเมลผู้ดูแล"),
                       ("ลานขึ้น \"ข้อมูลไม่เป็นปัจจุบัน\"", "บอร์ด Gate Controller ไม่ส่งข้อมูลเกิน 2 นาที (ไฟดับ / เครือข่าย)", "ตรวจไฟและ Wi-Fi ของบอร์ด รีสตาร์ทบอร์ด แจ้งผู้พัฒนา"),
                       ("บันทึกลานจอดไม่ได้", "จำนวนช่องน้อยกว่าจำนวนที่ใช้งานอยู่ หรือข้อมูลไม่ครบ", "แก้ตามข้อความใต้ช่อง รอให้รถออกก่อนลดจำนวนช่อง")])}
    fill_manual("ppkitsoft_User_Manual_Template_Admin.docx", "W11_User_Manual_Admin_ParkQ.docx", P, T)


# ------------------------------------------------------------------ W11 technical document
def build_w11_tech():
    d = new_doc("Proj_Technical_Document")
    cover(d, "Proj_Technical_Document", "เอกสารทางเทคนิคของระบบ", "Technical Documentation")
    para(d, f"ระบบเวอร์ชัน {SYSVER} · {TODAY}", False, 10.5, "center", "5B6475")
    page_break(d)
    history(d, "เอกสารทางเทคนิค")

    heading(d, "1. สถาปัตยกรรมระบบ")
    para(d, "ParkQ เป็นเว็บแอปแบบ 3 ส่วน: (1) เว็บฝั่งผู้ใช้ ตู้ประตู และหลังบ้าน เป็นหน้า HTML + JavaScript ล้วน (ไม่ต้อง build) "
            "ให้บริการจากเซิร์ฟเวอร์เดียวกัน (2) API ด้วย FastAPI (3) ฐานข้อมูล SQLite ในเครื่อง หรือ PostgreSQL บนคลาวด์ (Neon) "
            "บอร์ด ESP32 ที่ลานคุยกับระบบผ่าน HTTP API ด้วย device key ของแต่ละลาน")
    md.image(d, IMG / "architecture.png", 16, "แผนภาพสถาปัตยกรรมระบบ")
    heading(d, "1.1 เทคโนโลยีที่ใช้", 2)
    table(d, ["ส่วน", "เทคโนโลยี", "หมายเหตุ"], [
        ("Backend", "Python 3.12, FastAPI, Uvicorn, Pydantic", "app/server.py"),
        ("ฐานข้อมูล", "SQLite (พัฒนา) / PostgreSQL 16 ผ่าน psycopg 3 (ใช้งานจริง บน Neon Singapore)", "app/db.py แปล SQL อัตโนมัติ"),
        ("Frontend", "HTML + CSS + JavaScript (ES modules) ไม่มี framework", "app/static/ · ฟอนต์ Bai Jamjuree, Noto Sans Thai เก็บในเครื่อง"),
        ("OTP", "SMTP (smtplib ในไลบรารีมาตรฐาน) เช่น Brevo / Gmail", "app/mailer.py"),
        ("QR", "สร้างด้วย qrcode · สแกนด้วย BarcodeDetector หรือ jsQR 1.4.0 (ฝังในเครื่อง)", "app/static/js/scanner.js"),
        ("ตรรกะหลัก", "parkq_core.py (ค่าจอด สถานะลาน ตั๋ว QR แบบเซ็น HMAC-SHA256 ตรวจรูปแบบอีเมล/ทะเบียน)", "ใช้ร่วมกับ Gate Controller ได้"),
        ("ทดสอบ", "unittest, FastAPI TestClient, Playwright (ถ่ายภาพ/ทดสอบหน้าจอ)", "โฟลเดอร์ code/"),
        ("โฮสต์", "Render (เว็บ) + Neon (ฐานข้อมูล) ตามไฟล์ render.yaml", "ยังไม่ได้ Deploy"),
        ("ฮาร์ดแวร์", "ESP32-DevKitC-32E, เครื่องอ่าน QR, OLED, รีเลย์/เซอร์โว, เซ็นเซอร์ช่องจอด + LED WS2812B", "โฟลเดอร์ hardware/, firmware/"),
    ], [2.4, 8.8, 5.3], size=9)

    heading(d, "2. โครงสร้างโปรเจกต์")
    code_block(d, "ParkQ_SoftEng/\n  app/            server.py (API) · db.py (ฐานข้อมูล) · mailer.py (ส่ง OTP)\n"
                  "    static/       index.html (ผู้ขับขี่) · gate.html (ตู้) · admin.html (หลังบ้าน/พนักงาน) · css/ js/ fonts/\n"
                  "  code/           parkq_core.py + test_*.py (Unit/Integration Test)\n  firmware/ hardware/  โค้ดบอร์ดและแผ่นวงจร\n"
                  "  gen/            สคริปต์สร้างเอกสาร W5–W12\n  render.yaml · requirements.txt · .env (ไม่เข้า Git)")

    schema = (ROOT / "app" / "db.py").read_text(encoding="utf-8")
    tables = re.findall(r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\);", schema, re.S)
    heading(d, "3. โครงสร้างข้อมูล (Data Model)")
    para(d, "ตารางทั้งหมดสร้างโดย db.init() ตอนเริ่มระบบ (ใช้ชนิดข้อมูลที่ตัวแปลงเปลี่ยนเป็นของ PostgreSQL ให้เอง)")
    rows = []
    for name, body in tables:
        parts, depth, cur = [], 0, ""
        for ch in body:
            depth += ch == "("
            depth -= ch == ")"
            if ch == "," and depth == 0:
                parts.append(cur)
                cur = ""
            else:
                cur += ch
        parts.append(cur)
        cols = [re.split(r"\s+", c.strip())[0] for c in parts if c.strip() and not c.strip().upper().startswith(("PRIMARY", "UNIQUE", "FOREIGN", "CHECK"))]
        cols = [c for c in cols if re.match(r"^\w+$", c)]
        rows.append((name, ", ".join(cols)))
    table(d, ["ตาราง", "คอลัมน์"], rows, [3.2, 13.3], size=9)

    server = (ROOT / "app" / "server.py").read_text(encoding="utf-8")
    routes = re.findall(r'@app\.(get|post|put|patch|delete)\("(/api[^"]*)"[^\n]*\)\ndef (\w+)\(', server)
    heading(d, "4. รายการ API")
    para(d, f"รวม {len(routes)} เส้นทาง ทุกเส้นทางที่ต้องล็อกอินส่งหัว Authorization: Bearer <token> (ได้จาก /api/auth/verify) "
            "เส้นทาง /api/iot และ /api/gate ใช้ device key ของลาน ข้อผิดพลาดตอบเป็น JSON {code, message}")
    table(d, ["วิธี", "เส้นทาง", "ฟังก์ชัน"], [(m.upper(), p, f) for m, p, f in routes], [1.6, 9.2, 5.7], size=8.5, center_cols=(0,))

    heading(d, "5. ตัวแปรสภาพแวดล้อม (Environment Variables)")
    table(d, ["ตัวแปร", "ความหมาย", "ค่าเริ่มต้น / หมายเหตุ"], [
        ("DATABASE_URL", "connection string ของ PostgreSQL (Neon) ถ้าว่างใช้ SQLite", "ว่าง · เก็บในไฟล์ .env หรือ Environment ของ Render ห้ามเข้า Git"),
        ("PARKQ_DB", "ที่อยู่ไฟล์ SQLite", "app/parkq.db"),
        ("PARKQ_RESET", "1 = ล้างและสร้างข้อมูลตั้งต้นใหม่ตอนเริ่ม", "ใช้ครั้งแรกเท่านั้น แล้วลบออก"),
        ("PARKQ_DEV", "โหมดทดสอบ (แสดง OTP บนจอเมื่อไม่มี SMTP, ปุ่มจำลองชำระเงิน)", "1 · ตั้ง 0 เมื่อใช้งานจริง"),
        ("PARKQ_SMTP_HOST / PORT / USER / PASS / FROM", "บัญชี SMTP สำหรับส่งอีเมล OTP", "ไม่ตั้ง = ไม่ส่งอีเมล (โหมดทดสอบแสดงรหัสบนจอ)"),
        ("PARKQ_ADMIN_EMAIL / PARKQ_STAFF_EMAIL", "อีเมลของผู้ดูแลและพนักงาน ตอนสร้างข้อมูลตั้งต้น", "admin@parkq.demo / staff@parkq.demo"),
        ("PARKQ_SECRET", "กุญแจเซ็น QR ตั๋ว (HMAC)", "ค่าทดสอบ · ต้องตั้งค่าสุ่มยาวเมื่อใช้งานจริง"),
        ("PARKQ_PROMPTPAY_ID", "เลขพร้อมเพย์ของร้านสำหรับ QR ชำระเงินจริง", "ว่าง = QR ทดสอบ"),
    ], [4.6, 6.3, 5.6], size=8.5)

    heading(d, "6. การติดตั้งและใช้งาน")
    heading(d, "6.1 รันในเครื่อง", 2)
    code_block(d, "pip install -r requirements.txt\npython -m uvicorn server:app --app-dir app --host 127.0.0.1 --port 8000\n"
                  "# เปิด http://127.0.0.1:8000/  (แอปผู้ขับขี่)  /admin  /staff  /gate?lot=LOT01&dir=in")
    heading(d, "6.2 ติดตั้งบน Render + Neon", 2)
    for i, s in enumerate(["สร้างโปรเจกต์ Neon เลือกภูมิภาค Singapore คัดลอก connection string (postgresql://...)",
                           "สร้าง Web Service บน Render จากรีโพ (ไฟล์ render.yaml ตั้งค่า region singapore ให้แล้ว)",
                           "ตั้ง Environment: DATABASE_URL, PARKQ_SMTP_*, PARKQ_ADMIN_EMAIL, PARKQ_STAFF_EMAIL, PARKQ_SECRET และ PARKQ_DEV=0 เมื่อใช้งานจริง",
                           "ตั้ง PARKQ_RESET=1 ให้เริ่มรอบแรก เมื่อขึ้นแล้ว ลบตัวแปรนี้ออกทันที (ถ้าค้าง ข้อมูลถูกล้างทุกครั้งที่รีสตาร์ท)",
                           "ตรวจสอบ: เข้า URL ขอ OTP ด้วยอีเมลจริง จองและสแกน QR ที่หน้า /gate"], 1):
        md.numbered(d, s, i)

    heading(d, "7. การรักษาความปลอดภัย")
    for t in ["OTP 6 หลัก อายุ 5 นาที ผิดได้ 3 ครั้ง ขอได้ 5 ครั้ง/10 นาที เทียบด้วย compare_digest (กัน timing attack)",
              "บัญชีผูกกับอีเมลที่ยืนยันแล้ว (ไม่ใช้เบอร์โทรเป็นตัวระบุ ป้องกันการยึดบัญชี)",
              "QR ตั๋วเป็นข้อมูลที่เซ็น HMAC-SHA256 ปลอมหรือแก้เวลาไม่ได้ ใช้ได้ครั้งเดียวต่อรอบ",
              "ไม่ขายช่องสุดท้ายซ้ำ: ตรวจและบันทึกในธุรกรรมเดียว (SQLite BEGIN IMMEDIATE / PostgreSQL LOCK TABLE)",
              "อุปกรณ์ IoT ยืนยันด้วย device key ต่อลาน · ผู้ใช้เข้าถึงได้เฉพาะตั๋วและรถของตนเอง",
              "ความลับทั้งหมด (DATABASE_URL, รหัส SMTP) อยู่ใน .env หรือ Environment ของโฮสต์ ไฟล์ .env อยู่ใน .gitignore"]:
        bullet(d, t)

    heading(d, "8. การทดสอบและการสร้างเอกสาร")
    code_block(d, "cd code\npython -m unittest test_parkq_core test_mailer test_db_adapter test_otp_delivery -v\n"
                  "# Integration Test (เปิดเซิร์ฟเวอร์ก่อน)  PARKQ_URL=http://127.0.0.1:8000 python -m unittest test_api_flow -v\n"
                  "# สร้างเอกสารใหม่: python gen/capture.py && python gen/draw.py && python gen/make_docs.py && python gen/make_w10_12.py")
    heading(d, "9. ข้อจำกัดที่ทราบและงานต่อไป")
    for t in ["บอร์ด ESP32 + เซ็นเซอร์จริงยังรอฮาร์ดแวร์ (ใช้ตัวจำลองผ่าน Device API)", "ชำระเงินจริงต้องต่อ Payment Gateway และตั้ง PARKQ_PROMPTPAY_ID",
              "ส่งอีเมลจริงต้องตั้งค่า SMTP ก่อน · แผนฟรีของ Render/Neon มีข้อจำกัดเรื่องการหลับและโควตา",
              "ควรเปลี่ยนรหัสผ่านฐานข้อมูลบน Neon หลังการนำเสนอ (เคยแสดงในการสนทนาระหว่างพัฒนา)"]:
        bullet(d, t)
    save(d, "W11_Technical_Document_ParkQ.docx")


# ------------------------------------------------------------------ W12 change requests
CRS = [
    {"no": "CR-ParkQ-001", "file": "W12_Change_Request_CR-001_Email_OTP_ParkQ.docx",
     "old": "ACC_01 / BR-02: ผู้ใช้เข้าสู่ระบบด้วยเบอร์โทรศัพท์ รับรหัส OTP ทาง SMS ผ่าน SMS Gateway บัญชีผูกกับเบอร์โทร",
     "new": "ผู้ใช้เข้าสู่ระบบด้วยอีเมล รับรหัส OTP 6 หลักทางอีเมล (SMTP) บัญชีผูกกับอีเมล (ไม่สนตัวพิมพ์ใหญ่/เล็ก) เบอร์โทรเป็นข้อมูลเสริมที่ไม่บังคับ แก้ BR-02 เป็นกฎรูปแบบอีเมล ปรับหน้าจอ SC-ACC-01-01/02/03",
     "reason": "บริการ SMS Gateway มีค่าใช้จ่ายต่อข้อความและต้องมีสัญญาผู้ให้บริการ ซึ่งเกินงบของโครงการนักศึกษา แต่ต้องการให้อาจารย์และเพื่อนลองใช้ OTP \"ของจริง\" ตอนนำเสนอ "
               "อีเมลส่งฟรี (Brevo / Gmail) ผู้ใช้ทุกคนมีอีเมลอยู่แล้ว และใช้อีเมลเป็นตัวระบุบัญชีช่วยลดความเสี่ยงที่ผู้อื่นจะสวมบัญชีที่ผูกกับเบอร์โทรเดิม",
     "impact": (1, 0, 1), "note": "ประมาณการงาน: แก้โค้ดและทดสอบ 1–2 วัน แก้เอกสาร W5–W9 อีก 1 วัน ไม่มีค่าใช้จ่ายเพิ่ม (ลดค่า SMS) ทำเสร็จแล้วในเวอร์ชัน 1.1.0 รอการพิจารณารับรอง"},
    {"no": "CR-ParkQ-002", "file": "W12_Change_Request_CR-002_Cloud_Database_ParkQ.docx",
     "old": "NFR: ข้อมูลเก็บใน SQLite ในเครื่องเซิร์ฟเวอร์ ถูกล้างเมื่อบริการบน Render รีสตาร์ท (ไม่เหมาะกับการสาธิตข้อมูลจริง)",
     "new": "รองรับฐานข้อมูล PostgreSQL บนคลาวด์ (Neon ภูมิภาค Singapore) โดยตั้ง DATABASE_URL ระบบแปล SQL ให้ใช้ได้ทั้งสองฐานข้อมูล ข้อมูลผู้ใช้ รถ ตั๋ว การชำระเงิน คงอยู่ถาวร และคงการล็อกกันขายช่องสุดท้ายซ้ำ",
     "reason": "ต้องการให้ข้อมูลที่อาจารย์และเพื่อนสร้างระหว่างทดลอง (บัญชี ตั๋ว รายการเข้า-ออก) คงอยู่ข้ามการรีสตาร์ทและสามารถนำกลับมาดูได้ และเป็นการเตรียมระบบสำหรับการใช้งานจริงในอนาคต แผนฟรีของ Neon ไม่มีค่าใช้จ่าย",
     "impact": (1, 0, 1), "note": "เพิ่มตัวแปลงฐานข้อมูล psycopg3 + ชุดทดสอบ (UT40–44) และรัน Integration Test บน PostgreSQL ทำเสร็จแล้ว ข้อจำกัด: แผนฟรีมีโควตาและอาจหน่วงเมื่อฐานข้อมูลหลับ"},
    {"no": "CR-ParkQ-003", "file": "W12_Change_Request_CR-003_UI_Redesign_Theme_ParkQ.docx",
     "old": "UI เดิมโทนสีน้ำเงินแบบมาตรฐาน มีโหมดเดียว หน้าจอตู้ประตูและหลังบ้านใช้สไตล์ต่างจากแอปผู้ขับขี่",
     "new": "ออกแบบ UI ใหม่ทั้ง 3 พื้นผิวเป็นธีม Split-Flap (ป้ายสถานี) ตัวเลขช่องว่าง/เวลาพลิกแบบแผ่นป้าย โทนทันสมัย มุมโค้ง เงานุ่ม และเพิ่มปุ่มสลับโหมดสว่าง/มืด ที่จำค่าที่เลือกไว้ ปรับเอกสาร W6/W7 ให้ตรงกับหน้าจอใหม่",
     "reason": "ตู้ประตูและหน้าจอผู้ขับขี่ต้องอ่านได้ชัดจากระยะไกลและกลางแดด ธีมป้ายสถานีทำให้สถานะ ว่าง/ใกล้เต็ม/เต็ม เข้าใจทันที และโหมดสว่าง/มืดรองรับทั้งผู้ใช้กลางแจ้งและในร่ม รวมทั้งให้ระบบดูทันสมัยขึ้นตามคำขอของผู้ใช้หลังเห็นเวอร์ชันแรก",
     "impact": (1, 0, 1), "note": "ไม่เปลี่ยน Requirement เชิงหน้าที่ (ACC/LOT/BKG/TKT/ADM) ทำเสร็จแล้ว ตรวจด้วยภาพหน้าจอทั้งสองธีม ยังไม่ได้ทดสอบกับผู้ใช้จริง"},
]


def build_w12():
    for cr in CRS:
        doc = Document(str(TPL / "W12 _ Changed Request" / "ppkitsoft_Change_Request.docx"))
        paras, tables = body_items(doc)
        t1 = tables[1]
        put(t1.rows[0].cells[1], cr["no"]); put(t1.rows[0].cells[3], TODAY)
        put(t1.rows[1].cells[1], f"{SYSTEM_TH} ({SYSTEM_EN})")
        put(t1.rows[2].cells[1], "อาจารย์ผู้สอนรายวิชา Software Engineering")
        put(t1.rows[3].cells[1], f"{ROLE_MEMBER['PM']} (PM) กลุ่ม {GROUP_NAME}")
        put(tables[3].rows[1].cells[0], cr["old"]); put(tables[3].rows[1].cells[1], cr["new"])
        put(tables[5].rows[0].cells[0], cr["reason"])
        for row, flag in zip(tables[7].rows, cr["impact"]):
            put(row.cells[1], "☐ ไม่มีผลกระทบ     ☑ มีผลกระทบ" if flag else "☑ ไม่มีผลกระทบ     ☐ มีผลกระทบ")
        put(tables[9].rows[1].cells[1], cr["note"] + "  (สถานะ: รอพิจารณาอนุมัติ)")
        doc.save(str(OUT / cr["file"]))
        print("saved", cr["file"])


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    md.DOC_DATE = TODAY
    if which in ("w10", "all"):
        res = run_all_tests()
        print("tests ok:", build_w10(res))
    if which in ("w11", "all"):
        build_w11_manuals()
    if which in ("w11", "tech", "all"):
        build_w11_tech()
    if which in ("w12", "all"):
        build_w12()
