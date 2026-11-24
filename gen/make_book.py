"""ParkQ complete project book (one volume): front matter + W2..W13 chapters + conclusion, as DOCX and PDF.
  python gen/make_book.py parts      builds W13 doc, front matter and back matter (python-docx)
  python gen/make_book.py assemble   merges everything with Microsoft Word (COM) and exports the PDF
  python gen/make_book.py            both
Needs Microsoft Word on this PC (the course PDFs were exported from it the same way)."""
import json
import sys
from pathlib import Path

from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.shared import Cm, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_docs as md                      # noqa: E402  (shared styling helpers)
import make_gantt as mg                     # noqa: E402
from make_docs import (para, rich, bullet, heading, table, image, page_break, new_doc, set_font, SYSTEM_TH, SYSTEM_EN, MEMBERS,  # noqa: E402,F401
                       ROLE_MEMBER, GROUP_NAME)

ROOT = md.ROOT
OUT = md.OUT
BUILD = ROOT / "build" / "book"
BOOK_DATE = "24/11/2569"
BOOK_VERSION = "1.0 (รูปเล่มสมบูรณ์)"
TRELLO_IMG = ROOT / "build" / "img" / "trello_board.png"

# (chapter title, file, strip the document's own cover/history/TOC)
CHAPTERS = [
    ("แผนโครงการและรายงานการประชุม (Project Plan & Meeting Report)", "W2_Project_Plan_Meeting_Report_ParkQ.docx", True),
    ("ขอบเขตการดำเนินงาน (Statement of Work)", "W3_Statement_of_Work_ParkQ.docx", True),
    ("กระบวนการทำงาน (Workflow Process)", "W3_Workflow_Process_ParkQ.docx", True),
    ("Use Case Diagram และ Use Case Description", "W4_Use_Case_ParkQ.docx", True),
    ("ข้อกำหนดความต้องการของระบบ (SRS)", "W5_SRS_ParkQ.docx", True),
    ("Screen Flow", "W6_Screen_Flow_ParkQ.docx", True),
    ("Screen Attributes", "W7_Screen_Attributes_ParkQ.docx", True),
    ("แผนประกันคุณภาพ (SQA) และ Traceability", "W8_SQA_Traceability_ParkQ.docx", True),
    ("Test Plan และ Test Case", "W9_Test_Plan_Test_Cases_ParkQ.docx", True),
    ("รายงานผลการทดสอบ (Test Report)", "W10_Test_Report_ParkQ.docx", True),
    ("คู่มือการใช้งานสำหรับผู้ใช้", "W11_User_Manual_User_ParkQ.docx", False),
    ("คู่มือการใช้งานสำหรับผู้ดูแลลานจอด", "W11_User_Manual_Admin_ParkQ.docx", False),
    ("เอกสารทางเทคนิค (Technical Document)", "W11_Technical_Document_ParkQ.docx", True),
    ("แบบคำขอเปลี่ยนแปลง CR-001: ส่งรหัส OTP ทางอีเมล", "W12_Change_Request_CR-001_Email_OTP_ParkQ.docx", False),
    ("แบบคำขอเปลี่ยนแปลง CR-002: ฐานข้อมูลบนคลาวด์", "W12_Change_Request_CR-002_Cloud_Database_ParkQ.docx", False),
    ("แบบคำขอเปลี่ยนแปลง CR-003: ปรับ UI และธีม", "W12_Change_Request_CR-003_UI_Redesign_Theme_ParkQ.docx", False),
    ("แบบคำขอเปลี่ยนแปลง CR-004: หน้าจอผู้ขับขี่แบบมินิมอล", "W12_Change_Request_CR-004_Driver_App_Minimal_UI_ParkQ.docx", False),
    ("การบริหารโครงการ: Gantt Chart และ Trello", "W13_Gantt_Trello_ParkQ.docx", True),
    ("บทสรุป ข้อเสนอแนะ และภาคผนวก", "back.docx", False),
]


# ---------------------------------------------------------------- Trello plan (also read by the board-building step)
def trello_cards(rows):
    cards = []
    for r in rows:
        lst = {"เสร็จ": "Done", "กำลังทำ": "Doing"}.get(r["status"], "To Do" if r["start"] <= mg.TODAY.replace(day=mg.TODAY.day) or (r["start"] - mg.TODAY).days <= 14 else "Backlog")
        steps = ["จัดทำ", "ตรวจทานโดย QA", "ส่ง/อนุมัติ"]
        done_n = {"Done": 3, "Doing": 1, "To Do": 0, "Backlog": 0}[lst]
        extra = {
            13: ["ออกแบบ PCB และ BOM", "สั่งผลิตที่ JLCPCB", "รับบอร์ดและเครื่องอ่าน QR", "ประกอบและทดสอบ"],
            14: ["เฟิร์มแวร์ build ผ่าน", "ทดสอบบน Wokwi", "อุปกรณ์จำลอง /device", "ทดสอบกับ ESP32 จริงบนเบรดบอร์ด"],
            17: ["Deploy บน Render", "ต่อฐานข้อมูล PostgreSQL ถาวร", "ปิดโหมดทดสอบ (PARKQ_DEV) ก่อนใช้จริง"],
        }
        items = extra.get(r["no"], steps)
        n_done = {13: 2, 14: 3, 17: 1}.get(r["no"], done_n if r["no"] not in extra else 0)
        cards.append({
            "list": lst, "no": r["no"], "title": f"{r['no']}. {r['name']}", "members": mg.owners(r["who"]).split(", "),
            "due": f"{r['end'].isoformat()}", "due_th": mg.thai(r["end"]), "label": mg.PHASE_NAME[r["phase"]], "status": r["status"],
            "pct": r["pct"], "note": r["note"], "checklist": [{"item": it, "done": i < n_done} for i, it in enumerate(items)],
        })
    return cards


# ---------------------------------------------------------------- W13 document
def build_w13():
    rows = mg.build_rows()
    cards = trello_cards(rows)
    (ROOT / "se-work").mkdir(exist_ok=True)
    (ROOT / "se-work" / "trello_cards.json").write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")

    d = new_doc("W13 – Gantt Chart และการจัดการ Task บน Trello")
    md.cover(d, "ParkQ", SYSTEM_TH, "W13 – Gantt Chart และการจัดการ Task บน Trello")
    md.history(d, "เอกสาร Gantt Chart และ Trello")
    page_break(d)

    heading(d, "1. วัตถุประสงค์และขอบเขต", 1)
    para(d, "เอกสารนี้แสดงตารางเวลาโครงการเป็น Gantt Chart เทียบแผนเดิม (W2) กับความคืบหน้าจริง ณ วันที่ "
            f"{mg.thai(mg.TODAY)} และอธิบายวิธีจัดการงานของทีมบน Trello ตามแนวทาง ISO/IEC 29110 สำหรับกิจการขนาดเล็กมาก (VSE) "
            "ที่ให้มีการวางแผน ติดตาม และควบคุมงานโดยมีบทบาท PM, SA, Dev และ QA ชัดเจน")
    bullet(d, "ไฟล์ Excel ต้นฉบับ: ส่งงาน/W13_Gantt_Chart_ParkQ.xlsx (แก้ไขและคำนวณซ้ำได้)")
    bullet(d, "เปอร์เซ็นต์ความคืบหน้าเป็นการประเมินของทีม ไม่ได้วัดจากเครื่องมืออัตโนมัติ")

    # landscape section for the chart
    sec = d.add_section(WD_SECTION.NEW_PAGE)
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = sec.page_height, sec.page_width
    heading(d, "2. Gantt Chart", 1)
    image(d, mg.PNG, 24.8, f"รูปที่ 13-1 Gantt Chart ของโครงงาน ParkQ ณ {mg.thai(mg.TODAY)} (สีเข้ม = ส่วนที่ทำเสร็จ, เส้นแดง = วันนี้)")
    page_break(d)
    heading(d, "3. ตารางสถานะงานเทียบแผน", 1)
    table(d, ["ลำดับ", "รายการงาน", "ผู้รับผิดชอบ", "ช่วงเวลา", "% เสร็จ", "สถานะ"],
          [(r["no"], r["name"], mg.owners(r["who"]), f"{mg.thai(r['start'])} – {mg.thai(r['end'])}", f"{r['pct']}%", r["status"] + (f" · {r['note']}" if r["note"] else "")) for r in rows],
          [1.2, 9.2, 3.6, 4.6, 1.6, 5.5], size=9, center_cols=(0, 4))
    para(d, "หมายเหตุ: งานที่ 13 เลยกำหนดเดิม (23/11/2569) เพราะรอรับบอร์ดจากผู้ผลิต จึงเลื่อนการทดสอบกับอุปกรณ์จริง (งานที่ 14) ออกไปด้วย", size=10, color="5B6475")

    sec = d.add_section(WD_SECTION.NEW_PAGE)
    sec.orientation = WD_ORIENT.PORTRAIT
    sec.page_width, sec.page_height = sec.page_height, sec.page_width
    heading(d, "4. การจัดการ Task บน Trello", 1)
    heading(d, "4.1 โครงสร้างบอร์ด", 2)
    para(d, "บอร์ดชื่อ “ParkQ – SE Project” ใช้ Kanban 5 คอลัมน์ ตามสถานะงาน")
    table(d, ["คอลัมน์", "ความหมาย", "กติกา"], [
        ("Backlog", "งานที่ยังไม่ถึงกำหนดเริ่ม", "ไม่ต้องมีผู้รับผิดชอบ"),
        ("To Do", "งานที่ต้องเริ่มภายใน 2 สัปดาห์", "ต้องมีผู้รับผิดชอบและวันครบกำหนดก่อนย้ายเข้า"),
        ("Doing", "งานที่กำลังทำ", "จำกัดไม่เกิน 5 การ์ดพร้อมกัน (WIP limit)"),
        ("Review / QA", "งานที่ทำเสร็จรอตรวจ", "QA ตรวจทานตามรายการในการ์ดก่อนปิด"),
        ("Done", "งานที่ตรวจและส่งแล้ว", "แนบไฟล์หรือลิงก์ผลงานในการ์ด"),
    ], [3.2, 5.8, 8], size=10)
    heading(d, "4.2 โครงสร้างการ์ด", 2)
    bullet(d, "ชื่อการ์ด = ลำดับและชื่องานตรงกับตาราง Gantt", "ชื่อ: ")
    bullet(d, "บทบาท/ผู้รับผิดชอบ (Members) และวันครบกำหนด (Due) ตรงกับแผน", "สมาชิกและวันที่: ")
    bullet(d, "ป้ายสีตามเฟสงาน (วางแผน วิเคราะห์ ออกแบบ คุณภาพ พัฒนา ทดสอบ ส่งมอบ งานเพิ่ม)", "ป้าย: ")
    bullet(d, "จัดทำ → ตรวจทานโดย QA → ส่ง/อนุมัติ (งานที่ 13, 14, 17 มีรายการย่อยเฉพาะ)", "Checklist: ")
    heading(d, "4.3 บอร์ดจริงของทีม", 2)
    if TRELLO_IMG.exists():
        image(d, TRELLO_IMG, 16.5, "รูปที่ 13-2 บอร์ด Trello “ParkQ – SE Project” ณ " + mg.thai(mg.TODAY))
    else:
        para(d, "[ภาพบอร์ด Trello จะใส่เมื่อสร้างบอร์ดเสร็จ]", color="B00020")
    para(d, "สรุปจำนวนการ์ดตามคอลัมน์ (ตรงกับตารางสถานะ):")
    counts = {}
    for c in cards:
        counts[c["list"]] = counts.get(c["list"], 0) + 1
    table(d, ["คอลัมน์", "จำนวนการ์ด"], [(k, str(counts.get(k, 0))) for k in ("Backlog", "To Do", "Doing", "Review / QA", "Done")], [6, 4], size=10, center_cols=(1,))
    heading(d, "4.4 วิธีติดตามงานของทีม", 2)
    for t in ("ประชุมสั้น ๆ ทุกสัปดาห์เพื่อย้ายการ์ดและปรับ % ใน Gantt ให้ตรงกัน",
              "ความเสี่ยงที่พบ (ฮาร์ดแวร์ล่าช้า ซิมจำลองไม่เสถียร ฐานข้อมูลบน Render ฟรีรีเซ็ต) ถูกบันทึกเป็นการ์ดและติดตามจนปิด",
              "การเปลี่ยนแปลงขอบเขตทำผ่านแบบฟอร์ม Change Request (บท CR-001 ถึง CR-004) และเพิ่มการ์ดใหม่ทุกครั้ง"):
        bullet(d, t)
    md.save(d, "W13_Gantt_Trello_ParkQ.docx")


# ---------------------------------------------------------------- front and back matter
def build_front():
    d = new_doc("รายงานโครงงานฉบับสมบูรณ์")
    for lvl, size in ((4, 11.5), (5, 11)):
        set_font(d.styles[f"Heading {lvl}"], size, True, "13203F")
    sec = d.sections[0]
    sec.left_margin = sec.right_margin = sec.top_margin = sec.bottom_margin = Cm(0)
    sec.header_distance = sec.footer_distance = Cm(0)
    cp = d.add_paragraph()
    cp.paragraph_format.space_after = Pt(0)
    cp.paragraph_format.line_spacing = 1.0
    cp.add_run().add_picture(str(ROOT / "build" / "img" / "cover.png"), width=sec.page_width, height=sec.page_height - Cm(0.05))
    sec2 = d.add_section(WD_SECTION.NEW_PAGE)
    for side in ("left_margin", "right_margin"):
        setattr(sec2, side, Cm(2))
    sec2.top_margin, sec2.bottom_margin = Cm(2), Cm(1.8)
    sec2.header_distance = sec2.footer_distance = Cm(1.25)
    heading(d, "คำนำ", 1)
    para(d, "เล่มนี้รวมงานของ ParkQ ไว้ในที่เดียว ParkQ คือระบบที่ให้คนขับรถดูว่าลานจอดยังว่างเท่าไร ซื้อสิทธิ์หรือจองล่วงหน้า แล้วรับตั๋ว QR "
            "ไปสแกนให้ไม้กั้นเปิดที่หน้าลาน ตั้งแต่แผนโครงการ การวิเคราะห์และออกแบบ การทดสอบ คู่มือ ไปจนถึง Gantt Chart และบอร์ด Trello ที่ใช้คุมงานในช่วงท้าย")
    para(d, "ทีมทำงานตามแนวทาง ISO/IEC 29110 สำหรับทีมขนาดเล็ก โดยแบ่งบทบาทเป็น PM, SA, Dev และ QA เอกสารแต่ละบทคือชุดที่ส่งในแต่ละสัปดาห์ (W2 ถึง W13) "
            "นำมาเรียงตามลำดับของงาน และบทท้ายเล่มบอกตรง ๆ ว่าอะไรใช้งานได้จริงแล้ว อะไรยังเป็นการจำลองเพราะบอร์ดและอุปกรณ์ยังมาไม่ครบ")
    para(d, "คณะผู้จัดทำ", True)
    for n, sid, roles in MEMBERS:
        para(d, f"{n}  รหัส {sid} ({' / '.join(roles)})", space_after=0)
    page_break(d)

    para(d, "สารบัญ", True, 18, None, "1C2530", space_after=8)
    para(d, "[[TOC]]")
    page_break(d)

    heading(d, "บทสรุปสำหรับผู้บริหาร", 1)
    para(d, "คนขับเปิดแอป ดูว่าลานจอดไหนว่าง ซื้อหรือจองที่ ชำระเงิน แล้วได้ตั๋ว QR ไปสแกนที่ตู้หน้าประตู ไม้กั้นก็เปิด "
            "ฝั่งเจ้าของลานมีหน้าจัดการลานจอด ตั้งอัตราค่าบริการ และดูรายงานรายได้ ส่วนหน้าประตูใช้ ESP32 ต่อเซนเซอร์ IR กับเซอร์โวคุมไม้กั้น")
    para(d, "ตารางนี้สรุปว่าอะไรเสร็จแล้ว และอะไรยังรอ")
    table(d, ["หัวข้อ", "สถานะ ณ " + BOOK_DATE], [
        ("เว็บแอปและ API", "ใช้งานจริงบน Render (แพ็กเกจฟรี) ล็อกอินด้วยอีเมล + รหัส OTP ส่งทางอีเมลจริง"),
        ("เอกสารตลอดวงจร SDLC", "ครบ W2 ถึง W13 รวมในเล่มนี้"),
        ("การทดสอบ", "เทสต์อัตโนมัติ 67 ตัวผ่านทั้งหมด (รายงาน W10 บันทึกผล ณ 12/11/2569 จำนวน 51 ตัว ภายหลังเพิ่มเทสต์อีก)"),
        ("Digital Twin 3 มิติ", "ใช้งานจริง (งานเพิ่มเติมนอกแผนเดิม)"),
        ("บอร์ด ESP32", "ได้รับแล้ว ยังไม่ได้ทดสอบบนฮาร์ดแวร์จริง (ทดสอบบนซิม Wokwi และอุปกรณ์จำลอง)"),
        ("PCB และเครื่องอ่าน QR", "ยังไม่ได้รับ ใช้เบรดบอร์ดและกล้องมือถือสแกนแทนระหว่างรอ"),
    ], [5, 11], size=10)
    para(d, "ข้อจำกัดและสิ่งที่ยังไม่ได้ทดสอบ อยู่ในบทที่ 19", size=10, color="5B6475")
    d.save(BUILD / "front.docx")
    print("saved front.docx")


def build_back():
    d = new_doc("บทสรุป ข้อเสนอแนะ และภาคผนวก")
    heading(d, "1. สรุปผลการดำเนินงาน", 1)
    para(d, "เอกสารครบทุกสัปดาห์ (W2–W13) ระบบเว็บและ Device API ใช้งานจริงบน Render "
            "และมีเทสต์อัตโนมัติ 67 ตัว แบ่งเป็น Unit Test ตรรกะหลัก 23 ตัว Integration Test ผ่าน API 14 ตัว ตัวส่งอีเมล 9 ตัว ตัวแปลงฐานข้อมูล 6 ตัว "
            "การส่ง OTP 4 ตัว และ Digital Twin 11 ตัว")
    heading(d, "2. เปรียบเทียบกับแผนเดิม", 1)
    table(d, ["ประเด็น", "แผนเดิม", "ผลจริง"], [
        ("เอกสาร W2–W12", "ตามตารางสัปดาห์", "ส่งครบ ปรับ W6/W7 ตาม UI ใหม่ (CR-003, CR-004)"),
        ("การส่งรหัสยืนยัน", "แสดงรหัสบนจอในโหมดทดสอบ", "ส่ง OTP ทางอีเมลจริง (CR-001) ผ่าน SMTP relay"),
        ("ฐานข้อมูล", "SQLite", "รองรับ PostgreSQL (CR-002) แต่เว็บบน Render ฟรียังใช้ SQLite ที่รีเซ็ตเมื่อ deploy"),
        ("บอร์ด IoT", "ประกอบและทดสอบสัปดาห์ที่ 10–13", "ล่าช้า รอรับ PCB/เครื่องอ่าน QR ใช้ Wokwi และอุปกรณ์จำลองแทน"),
        ("Digital Twin", "ไม่อยู่ในแผน", "เพิ่มเป็นงานเสริม ใช้ได้จริง"),
    ], [3.6, 5.2, 8.2], size=9.5)
    heading(d, "3. สิ่งที่ยังไม่ได้ทำหรือทดสอบ", 1)
    for t in ("ยังไม่ได้ทดสอบเฟิร์มแวร์กับบอร์ด ESP32 จริง ผลทดสอบฝั่งอุปกรณ์มาจากซิมและอุปกรณ์จำลองเท่านั้น",
              "ซิม Wokwi จับมือ HTTPS ไม่เสถียร (พบข้อผิดพลาด -80) จึงไม่ใช่ตัวแทนที่ดีของพฤติกรรมบนบอร์ดจริง",
              "การชำระเงินเป็นการจำลอง ไม่ได้เชื่อมผู้ให้บริการจริง และเว็บยังอยู่ในโหมดทดสอบ",
              "ข้อมูลบน Render แพ็กเกจฟรีไม่ถาวร ต้องต่อฐานข้อมูล PostgreSQL ก่อนใช้งานจริง",
              "โหมดเดโมของเฟิร์มแวร์ข้ามการตรวจใบรับรอง TLS ต้องปักใบรับรอง CA ก่อนใช้งานจริง"):
        bullet(d, t)
    heading(d, "4. สิ่งที่เรียนรู้", 1)
    for t in ("เอกสารที่สร้างจากข้อมูลชุดเดียวกับโค้ด (single source of truth) ช่วยให้ข้อกำหนด ตารางเทียบเทสต์ และคู่มือไม่ขัดกัน",
              "การเลือกใช้บริการภายนอกควรตรวจข้อจำกัดก่อน เช่น แพ็กเกจฟรีของผู้ให้บริการโฮสต์บล็อกพอร์ต SMTP ทำให้ต้องเปลี่ยนวิธีส่งอีเมล",
              "ซิมเมเตอร์ช่วยตรวจตรรกะได้ แต่ต้องมีแผนทดสอบกับฮาร์ดแวร์จริงเสมอ และควรบอกผู้ตรวจตรง ๆ ว่าส่วนใดจริง ส่วนใดจำลอง",
              "ควรเขียนตัวป้องกันในโค้ดสำหรับคำสั่งที่ทำลายข้อมูล เช่นการรีเซ็ตฐานข้อมูล แทนการพึ่งความระมัดระวังของผู้ใช้"):
        bullet(d, t)
    heading(d, "5. งานที่จะทำต่อ", 1)
    for t in ("ทดสอบเฟิร์มแวร์บนบอร์ดจริงเมื่อได้รับอุปกรณ์ครบ และเก็บผลเป็นเอกสาร Test Report ฉบับเพิ่มเติม",
              "ต่อฐานข้อมูล PostgreSQL ถาวร และเชื่อมผู้ให้บริการชำระเงินจริง",
              "ปักใบรับรอง CA ในเฟิร์มแวร์ และพิจารณาย้ายการสื่อสารไปใช้ MQTT เมื่อมีหลายลานจอด",
              "เพิ่มระบบอัปเดตเฟิร์มแวร์ทางอากาศ (OTA) และการแจ้งเตือนเมื่ออุปกรณ์ขาดการติดต่อ"):
        bullet(d, t)
    heading(d, "6. บรรณานุกรม", 1)
    for t in ("ISO/IEC 29110: Systems and software engineering — Lifecycle profiles for Very Small Entities (VSEs)",
              "คู่มือปฏิบัติตามกระบวนการมาตรฐานวิศวกรรมซอฟต์แวร์ ISO/IEC 29110 สำหรับหน่วยงานภาครัฐ (เอกสารประกอบการเรียน)",
              "FastAPI Documentation, https://fastapi.tiangolo.com",
              "Espressif ESP32 Series Datasheet และ Arduino-ESP32 Documentation",
              "three.js Documentation, https://threejs.org (ใช้สร้างหน้า Digital Twin)",
              "Trello Guide, https://trello.com/guide"):
        bullet(d, t)
    heading(d, "7. ภาคผนวก: รายการไฟล์ประกอบ", 1)
    table(d, ["ไฟล์", "เนื้อหา"], [
        ("W2_Project_Plan_ParkQ.xlsx", "แผนโครงการเดิม พร้อม Gantt แบบสี"),
        ("W9_Test_Cases_ParkQ.xlsx", "Test Case ทั้งหมดพร้อมผลรัน"),
        ("W10_Test_Results_ParkQ.xlsx", "ผลการทดสอบ ณ 12/11/2569"),
        ("W13_Gantt_Chart_ParkQ.xlsx", "Gantt Chart และสรุปสถานะ (ไฟล์ต้นฉบับของบทที่ 18)"),
        ("ParkQ_Pitch / ปิตช์ 5 นาที", "สไลด์และวิดีโอนำเสนอ"),
    ], [7, 10], size=10)
    d.save(BUILD / "back.docx")
    print("saved back.docx")


# ---------------------------------------------------------------- assemble with Word
HEAD_MAP = {"Heading 1": "Heading 2", "Heading 2": "Heading 3", "Heading 3": "Heading 4", "Heading 4": "Heading 5"}

INK = "1C2530"
AMBER_RGB = 0x00B0FF            # Word BGR for #FFB000


def recolor(src: Path) -> Path:
    """Copy a weekly DOCX with the old template blue swapped for the book's ink colour."""
    import zipfile
    dst = BUILD / "src" / src.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zo:
        for item in zi.infolist():
            data = zi.read(item.filename)
            if item.filename.startswith("word/") and item.filename.endswith(".xml"):
                data = data.replace(b"1E5EFF", INK.encode()).replace(b"1e5eff", INK.encode())
            zo.writestr(item, data)
    return dst


def assemble():
    import pythoncom
    import win32com.client as wc
    from docx import Document

    BUILD.mkdir(parents=True, exist_ok=True)
    out_docx = (OUT / "ParkQ_Project_Book.docx").resolve()
    out_pdf = (OUT / "ParkQ_Project_Book.pdf").resolve()
    pythoncom.CoInitialize()
    word = wc.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        doc = word.Documents.Open(str((BUILD / "front.docx").resolve()))
        # footer page numbers, header text
        sec1 = doc.Sections(1)
        sec1.PageSetup.DifferentFirstPageHeaderFooter = True
        sel = word.Selection
        chapter_starts = []
        for n, (title, fname, strip) in enumerate(CHAPTERS, 1):
            path = recolor((BUILD / fname) if fname == "back.docx" else (OUT / fname))
            src = Document(str(path))
            landscape = src.sections[0].orientation == WD_ORIENT.LANDSCAPE
            sel.EndKey(6)                                   # wdStory
            sel.InsertBreak(2)                              # section break (next page)
            ps = doc.Sections(doc.Sections.Count).PageSetup
            ps.DifferentFirstPageHeaderFooter = False
            ps.Orientation = 1 if landscape else 0
            sel.Style = doc.Styles("Heading 1")
            sel.TypeText(f"บทที่ {n}  {title}")
            sel.TypeParagraph()
            sel.Style = doc.Styles("Normal")
            start = sel.Start
            sel.InsertFile(str(path.resolve()))
            end = doc.Content.End
            rng = doc.Range(start, end)
            if strip:                                       # drop the document's own cover / history / TOC
                for para_ in rng.Paragraphs:
                    if para_.Style.NameLocal == "Heading 1":
                        if para_.Range.Start > start:
                            doc.Range(start, para_.Range.Start).Delete()
                        break
            rng = doc.Range(start, doc.Content.End)
            for para_ in rng.Paragraphs:                    # nest the document's own headings under the chapter title
                nm = para_.Style.NameLocal
                if nm in HEAD_MAP:
                    para_.Style = doc.Styles(HEAD_MAP[nm])
                    para_.Range.Font.Reset()                # drop inherited direct formatting so the book style (Leelawadee UI) applies
            chapter_starts.append(start)
        # book-wide heading and TOC styles: set Latin and complex-script (Thai) sizes/weights explicitly
        rgb = lambda h: int(h[0:2], 16) + int(h[2:4], 16) * 256 + int(h[4:6], 16) * 65536
        for name, size, color in (("Heading 1", 20, "1C2530"), ("Heading 2", 15, "1C2530"), ("Heading 3", 13, "13203F"),
                                  ("Heading 4", 12, "13203F"), ("Heading 5", 11.5, "13203F"), ("TOC 1", 11.5, "000000"), ("TOC 2", 10.5, "000000")):
            f = doc.Styles(name).Font
            f.Name = "Leelawadee UI"; f.NameBi = "Leelawadee UI"
            f.Size = size; f.SizeBi = size
            heading_like = name.startswith("Heading") or name == "TOC 1"
            f.Bold = heading_like; f.BoldBi = heading_like
            f.Italic = False; f.ItalicBi = False
            f.Color = rgb(color)
        b = doc.Styles("Heading 1").ParagraphFormat.Borders(-3)      # amber rule under each chapter title
        b.LineStyle = 1; b.LineWidth = 18; b.Color = AMBER_RGB
        doc.Styles("Heading 1").ParagraphFormat.Borders.DistanceFromBottom = 4
        # table of contents
        for para_ in doc.Paragraphs:
            if para_.Range.Text.strip() == "[[TOC]]":
                r = para_.Range
                r.Text = ""
                doc.TablesOfContents.Add(Range=r, UseHeadingStyles=True, UpperHeadingLevel=1, LowerHeadingLevel=2, UseFields=False,
                                         IncludePageNumbers=True, RightAlignPageNumbers=True, UseHyperlinks=False, UseOutlineLevels=False)
                break
        # header / footer for every section after the cover
        for s in list(doc.Sections)[1:]:
            for idx in (1,):
                hdr = s.Headers(idx)
                hdr.LinkToPrevious = False
                hdr.Range.Text = f"ParkQ – รายงานโครงงานฉบับสมบูรณ์    |    Software Engineering"
                hdr.Range.ParagraphFormat.Alignment = 2
                hdr.Range.Font.Size = 8.5
                ftr = s.Footers(idx)
                ftr.LinkToPrevious = False
                ftr.Range.Text = "หน้า "
                ftr.Range.ParagraphFormat.Alignment = 1
                ftr.Range.Font.Size = 8.5
                ftr.Range.Collapse(0)
                doc.Fields.Add(ftr.Range, 33)               # wdFieldPage
        for kind in (1, 2):
            doc.Sections(1).Headers(kind).Range.Text = ""
            doc.Sections(1).Footers(kind).Range.Text = ""
        for t in doc.TablesOfContents:
            t.Update()
        doc.Fields.Update()
        for t in doc.TablesOfContents:                      # TOC entries copy odd Thai fonts from the headings: pin them
            for para_ in t.Range.Paragraphs:
                size = 11.5 if para_.Style.NameLocal == "TOC 1" else 10.5
                para_.Range.Font.NameBi = "Leelawadee UI"
                para_.Range.Font.SizeBi = size
                para_.Range.Font.Size = size
                para_.Range.Font.Name = "Leelawadee UI"
        doc.BuiltInDocumentProperties("Title").Value = "ParkQ – รายงานโครงงานฉบับสมบูรณ์"
        doc.SaveAs2(str(out_docx), 16)                      # wdFormatXMLDocument
        doc.ExportAsFixedFormat(str(out_pdf), 17, False, 0, 0, 1, 1, 0, True, True, 1)   # PDF with heading bookmarks
        pages = doc.ComputeStatistics(2)
        doc.Close(False)
        print(f"book saved: {out_docx.name}, {out_pdf.name}, {pages} pages")
    finally:
        word.Quit()


def parts():
    BUILD.mkdir(parents=True, exist_ok=True)
    mg.make_xlsx(mg.build_rows())
    build_w13()
    build_front()
    build_back()


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("parts", "all"):
        parts()
    if what in ("assemble", "all"):
        assemble()
