"""Build W2 (project plan + meeting reports), W3 (SOW + workflow) and W4 (use cases) in the same style as W5-W9.

Run after draw.py and draw_early.py:  python gen/make_early_docs.py
"""
from datetime import timedelta

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from early_data import (CUSTOMER, INCLUDES, MEETINGS, PLAN, PLAN_START, PLAN_WEEKS, SOW_DELIVERABLES, SOW_OBJECTIVES,
                        SOW_RISKS, SOW_SCOPE, TEAM, UC_LEVEL1, UC_LEVEL2)
from make_docs import (FONT, IMG, OUT, Cm, bullet, cell_text, cover, heading, history, image, new_doc, page_break, para,
                       rich, save, shade, table, toc)
from spec_data import MEMBERS, MODULES, ROLE_MEMBER, SYSTEM_EN, SYSTEM_TH

ROLE_NAME = {r: f"{r} – {title}" for r, title, _ in TEAM}


def attendees(roles):
    """One line per member present (a member with two roles is listed once), then the customer if present."""
    lines = [f"{n} ({' / '.join(ROLE_NAME[r] for r in rs if r in roles)})" for n, _, rs in MEMBERS if any(r in roles for r in rs)]
    return "\n".join(lines + [CUSTOMER for a in roles if a not in ROLE_NAME])


def kv_table(d, rows, widths=(4, 12.5)):
    """Two-column description table (Use Case Description style): bold shaded label column."""
    t = d.add_table(rows=0, cols=2)
    t.style = "Table Grid"
    for label, value in rows:
        cells = t.add_row().cells
        cell_text(cells[0], label, True, 10)
        shade(cells[0], "EEF2FB")
        cell_text(cells[1], value, size=10)
    for row in t.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = Cm(w)
    d.add_paragraph()
    return t


def numbered_text(items):
    return "\n".join(f"{i}. {s}" for i, s in enumerate(items, 1))


# ---------------------------------------------------------------- W2
def build_w2_xlsx():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Project Plan"
    weeks = [PLAN_START + timedelta(weeks=k) for k in range(PLAN_WEEKS)]
    first_week_col = 10
    head = ["ลำดับ", "รายงาน Task", "ผู้เกี่ยวข้อง", "PM", "SA", "Dev", "QA", "ระยะเวลา", "จำนวนวัน"]
    for c, h in enumerate(head, 1):
        ws.cell(1, c, h)
        ws.merge_cells(start_row=1, start_column=c, end_row=2, end_column=c)
    ws.cell(1, first_week_col, "ระยะเวลาดำเนินการ (สัปดาห์ที่เริ่มวันจันทร์) ปี 2569")
    ws.merge_cells(start_row=1, start_column=first_week_col, end_row=1, end_column=first_week_col + PLAN_WEEKS - 1)
    th_month = {8: "ส.ค.", 9: "ก.ย.", 10: "ต.ค.", 11: "พ.ย.", 12: "ธ.ค."}
    for k, w in enumerate(weeks):
        ws.cell(2, first_week_col + k, f"{w.day} {th_month[w.month]}")
    colors = {"วางแผน": "64748B", "วิเคราะห์": "1E5EFF", "ออกแบบ": "7C3AED", "คุณภาพ": "0891B2", "พัฒนา": "16A34A", "ทดสอบ": "D97706", "ส่งมอบ": "DC2626"}
    thin = Side(style="thin", color="D6DBE6")
    for i, (task, who, roles, s, e, phase) in enumerate(PLAN, 1):
        r = i + 2
        values = [i, task, who] + ["Y" if x in roles else "" for x in ("PM", "SA", "Dev", "QA")] + \
                 [f"{s.day}/{s.month}/{s.year + 543} – {e.day}/{e.month}/{e.year + 543}", (e - s).days + 1]
        for c, v in enumerate(values, 1):
            ws.cell(r, c, v)
        for k, w in enumerate(weeks):
            if w <= e and w + timedelta(days=6) >= s:
                ws.cell(r, first_week_col + k).fill = PatternFill("solid", fgColor=colors[phase])
    legend_row = len(PLAN) + 4
    ws.cell(legend_row, 2, "สีแท่ง = ช่วงงาน:")
    for k, (p, c) in enumerate(colors.items()):
        ws.cell(legend_row + 1 + k, 2, p).fill = PatternFill("solid", fgColor=c)
        ws.cell(legend_row + 1 + k, 2).font = Font(name=FONT, color="FFFFFF", bold=True)
    for row in ws.iter_rows(min_row=1, max_row=len(PLAN) + 2, max_col=first_week_col + PLAN_WEEKS - 1):
        for cell in row:
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
            cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center" if cell.column != 2 and cell.column != 3 else "left")
            if cell.row <= 2:
                cell.font = Font(name=FONT, bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="13203F")
            elif not cell.font.bold:
                cell.font = Font(name=FONT, size=10)
    widths = {1: 6, 2: 52, 3: 30, 4: 5, 5: 5, 6: 5, 7: 5, 8: 24, 9: 9}
    for c, w in widths.items():
        ws.column_dimensions[openpyxl.utils.get_column_letter(c)].width = w
    for k in range(PLAN_WEEKS):
        ws.column_dimensions[openpyxl.utils.get_column_letter(first_week_col + k)].width = 6.5
    ws.row_dimensions[2].height = 30
    ws.freeze_panes = "D3"
    wb.save(OUT / "W2_Project_Plan_ParkQ.xlsx")
    print("saved W2_Project_Plan_ParkQ.xlsx")


def build_w2_docx():
    d = new_doc("Project Plan & Meeting Report")
    cover(d, "Project Plan & Meeting Report", "แผนการดำเนินโครงการและรายงานการประชุม", "Assignment สัปดาห์ที่ 2")
    heading(d, "1. Project Plan")
    heading(d, "1.1 ข้อมูลโครงการ", 2)
    table(d, ["หัวข้อ", "รายละเอียด"], [
        ("ชื่อโครงการ", f"{SYSTEM_TH}\n{SYSTEM_EN}"),
        ("ผู้ว่าจ้าง", CUSTOMER),
        ("ระยะเวลา", "25 สิงหาคม – 18 ธันวาคม 2569 (17 สัปดาห์)"),
        ("กระบวนการพัฒนา", "Incremental Model: วิเคราะห์และออกแบบทั้งระบบก่อน แล้วพัฒนา 2 Phase "
                          "(Phase 1 เว็บผู้ขับขี่, Phase 2 ตู้ประตู/หลังบ้าน/IoT) แต่ละ Phase ผ่าน Internal Test ก่อนส่งมอบ"),
        ("เหตุผลที่เลือก", "ลูกค้าเห็นและทดลองฟีเจอร์หลัก (ดูสถานะ–จอง–QR) ได้เร็ว ส่วนฮาร์ดแวร์ที่ใช้เวลาผลิตนานพัฒนาคู่ขนานใน Phase 2"),
    ], [4, 12.5])
    heading(d, "1.2 ทีมงานและบทบาท", 2)
    table(d, ["บทบาท", "ชื่อ-นามสกุล", "หน้าที่ความรับผิดชอบ"],
          [(f"{r}\n{title}", ROLE_MEMBER[r], duty) for r, title, duty in TEAM] +
          [("ลูกค้า", CUSTOMER, "ให้ความต้องการ อนุมัติเอกสาร ทดสอบ UAT ตรวจรับงาน")], [4.2, 4.5, 7.8])
    heading(d, "1.3 แผนงาน (Gantt Chart)", 2)
    para(d, "แผนงานละเอียดพร้อมผู้รับผิดชอบ (Y = เกี่ยวข้อง) อยู่ในไฟล์ W2_Project_Plan_ParkQ.xlsx", size=10, color="5B6475")
    image(d, IMG / "gantt.png", 17, "Gantt Chart แผนการดำเนินโครงการ ParkQ")
    heading(d, "1.4 จุดตรวจรับงาน (Milestones)", 2)
    table(d, ["Milestone", "วันที่", "สิ่งที่ส่งมอบ"], [
        ("M1 อนุมัติ Requirement", "22 ก.ย. 2569", "SOW, Workflow, Use Case, SRS"),
        ("M2 อนุมัติการออกแบบ", "5 ต.ค. 2569", "Screen Flow, Screen Attributes, Prototype"),
        ("M3 แผนคุณภาพและการทดสอบ", "19 ต.ค. 2569", "SQA Plan, Traceability, Test Plan, Test Case"),
        ("M4 ส่งมอบ Phase 1–2", "13 พ.ย. 2569", "เว็บผู้ขับขี่ ตู้ประตู หลังบ้าน ผล Unit/Integration Test"),
        ("M5 Go-live และตรวจรับ", "18 ธ.ค. 2569", "ระบบออนไลน์ บอร์ด IoT ลานนำร่อง คู่มือ ซอร์สโค้ด"),
    ], [5, 3.5, 8])

    for m in MEETINGS:
        page_break(d)
        heading(d, f"2.{m['no']} Meeting Report ครั้งที่ {m['no']}: {m['title']}")
        para(d, f"รายงานการประชุม {SYSTEM_TH}", True, 12)
        kv_table(d, [("วันที่ / เวลา", f"{m['date']}  เวลา {m['time']}"), ("สถานที่ประชุม", m["place"]),
                     ("ผู้เข้าร่วมประชุม", attendees(m["attendees"]))])
        heading(d, "วาระการประชุม", 3)
        for i, a in enumerate(m["agenda"], 1):
            para(d, f"{i}. {a}", space_after=1)
        heading(d, "สรุปการหารือ", 3)
        for x in m["discussion"]:
            bullet(d, x)
        heading(d, "มติที่ประชุม", 3)
        for x in m["resolutions"]:
            bullet(d, x)
        heading(d, "งานที่ต้องดำเนินการ (Action Items)", 3)
        table(d, ["งาน", "ผู้รับผิดชอบ", "กำหนดเสร็จ"], m["actions"], [9.5, 3.5, 3.5])
        para(d, f"ผู้บันทึกการประชุม {ROLE_MEMBER['SA']} (SA)          ผู้รับรอง {ROLE_MEMBER['PM']} (PM)", size=10)
    save(d, "W2_Project_Plan_Meeting_Report_ParkQ.docx")


# ---------------------------------------------------------------- W3
def build_w3_sow():
    d = new_doc("Proj_Statement_of_Work")
    cover(d, "Statement of Work", "ขอบเขตการดำเนินงาน", "Statement of Work (SOW)")
    history(d, "ขอบเขตการดำเนินงาน (Statement of Work)")
    toc(d, [("1. วัตถุประสงค์ของการจัดทำ Statement of Work", 0), ("2. วัตถุประสงค์ของโครงการ", 0), ("3. ขอบเขตของโครงการ", 0),
            ("3.1 ขอบเขตของการดำเนินงาน", 1), ("3.2 ระยะเวลาในการดำเนินโครงการ", 1), ("3.3 งวดงานและงวดเงิน", 1),
            ("3.4 การรายงานความคืบหน้าของโครงการ", 1), ("3.5 ปัจจัยที่มีผลกระทบต่อโครงการ (และงานนอกขอบเขตโครงการ)", 1),
            ("4. ข้อตกลงร่วมกัน", 0), ("5. การบริหารการเปลี่ยนแปลง", 0), ("6. รายการเอกสารที่เกี่ยวข้อง", 0)])
    para(d, "ขอบเขตการทำงาน", True, 18, "center", "1E5EFF")
    para(d, SYSTEM_TH, True, 13, "center")
    para(d, SYSTEM_EN, False, 11, "center", "5B6475")
    heading(d, "1. วัตถุประสงค์ของการจัดทำ Statement of Work")
    para(d, "เอกสารฉบับนี้จัดทำขึ้นเพื่อกำหนดขอบเขตของโครงการ ParkQ ระหว่างผู้ว่าจ้าง (เจ้าของลานจอดนำร่อง) และผู้รับจ้าง (ทีมพัฒนา) "
            "ใช้เป็นข้อตกลงในการวางแผนและบริหารจัดการโครงการ โดยมีกรอบดังนี้")
    for t in ["1.1 ศึกษา วิเคราะห์ความต้องการ ให้สอดคล้องกับวัตถุประสงค์ของโครงการ",
              "1.2 กำหนดขอบเขต ระยะเวลา สิ่งที่ต้องส่งมอบ และรายละเอียดที่จำเป็น เพื่อให้เข้าใจตรงกันก่อนเริ่มโครงการ",
              "1.3 กำหนดข้อตกลงร่วมกัน แนวทางการบริหารจัดการ และการแก้ไขปัญหาร่วมกันของโครงการ"]:
        para(d, t)
    heading(d, "2. วัตถุประสงค์ของโครงการ")
    for i, t in enumerate(SOW_OBJECTIVES, 1):
        para(d, f"2.{i} {t}")
    heading(d, "3. ขอบเขตของโครงการ")
    heading(d, "3.1 ขอบเขตของการดำเนินงาน ประกอบด้วย", 2)
    table(d, ["ข้อ", "ระบบย่อย", "รายละเอียด"], [(f"3.1.{i}", a, b) for i, (a, b) in enumerate(SOW_SCOPE, 1)], [1.6, 5, 9.9], center_cols=(0,))
    para(d, "ผู้ใช้งานระบบ: ผู้ขับขี่ (ผ่านเว็บบนมือถือ), พนักงานหน้าลาน และผู้ดูแลลานจอด (ผ่านระบบหลังบ้าน)", size=10.5)
    heading(d, "3.2 ระยะเวลาในการดำเนินโครงการ", 2)
    para(d, "17 สัปดาห์ ตั้งแต่ 25 สิงหาคม ถึง 18 ธันวาคม 2569 (Work Schedule Overview)")
    image(d, IMG / "gantt.png", 17, "Work Schedule Overview (รายละเอียดใน Project Plan)")
    heading(d, "3.3 งวดงานและงวดเงิน", 2)
    table(d, ["ลำดับ", "รายละเอียดของงาน", "งวดเงิน"], SOW_DELIVERABLES, [1.6, 11, 3.9], center_cols=(0,))
    heading(d, "3.4 การรายงานความคืบหน้าของโครงการ", 2)
    para(d, "ผู้บริหารโครงการ (Project Manager) จัดส่งรายงานความคืบหน้า (Progress Report) ให้ผู้ว่าจ้างทุก 2 สัปดาห์ "
            "และรายงานสรุปเดือนละ 1 ครั้ง นับตั้งแต่ Project Kick-off พร้อมสาธิตระบบเมื่อจบแต่ละ Phase")
    heading(d, "3.5 ปัจจัยที่มีผลกระทบต่อโครงการ (และงานนอกขอบเขตโครงการ)", 2)
    for i, t in enumerate(SOW_RISKS, 1):
        para(d, f"3.5.{i} {t}")
    heading(d, "4. ข้อตกลงร่วมกัน")
    para(d, "4.1 ความต้องการจะถูกบริหารจัดการผ่านกิจกรรมการบริหารจัดการความต้องการ (System and Software Requirement Management) "
            "ซึ่งเป็นหนึ่งในกระบวนการพัฒนาระบบ โดยทุก Requirement มีรหัสอ้างอิง (เช่น BKG_01) ที่ตรวจสอบย้อนกลับไปยัง Use Case หน้าจอ และ Test Case ได้")
    para(d, "4.2 การปรับปรุงและเปลี่ยนแปลงขอบเขตของงานจะถูกบริหารจัดการอย่างเป็นระบบภายใต้กรอบของ IT Service Desk ตามข้อ 5")
    para(d, "4.3 ผู้ว่าจ้างจัดหาบัญชี SMS Gateway, Payment Gateway (บัญชีร้านค้าพร้อมเพย์) และพื้นที่ติดตั้งอุปกรณ์ที่ประตูลานจอด")
    heading(d, "5. การบริหารการเปลี่ยนแปลง")
    para(d, "การเปลี่ยนแปลงของโครงการใช้กระบวนการบริการ IT ผ่านโต๊ะบริการ (Service Desk) โดยผู้ขอเปลี่ยนแปลงยื่น Change Request (CR) "
            "ระบุสิ่งที่ต้องการเปลี่ยนและเหตุผล ทีมวิเคราะห์ผลกระทบต่อขอบเขต เวลา ค่าใช้จ่าย และเอกสาร ก่อนให้ PM และผู้ว่าจ้างอนุมัติ")
    table(d, ["ขั้นตอน", "ผู้รับผิดชอบ"], [("1. ยื่น Change Request ผ่าน Service Desk", "ผู้ว่าจ้าง / ทีมงาน"),
                                          ("2. วิเคราะห์ผลกระทบ (Requirement, หน้าจอ, Test Case, แผนงาน)", "SA, QA"),
                                          ("3. อนุมัติหรือปฏิเสธ", "PM + ผู้ว่าจ้าง"),
                                          ("4. ปรับเอกสารที่เกี่ยวข้องและพัฒนา", "SA, Dev"),
                                          ("5. ทดสอบซ้ำ (Regression) และปิด CR", "QA")], [11, 5.5])
    heading(d, "6. รายการเอกสารที่เกี่ยวข้อง")
    table(d, ["ลำดับ", "รายการ"], [("6.1", "แผนการดำเนินโครงการ (Project Plan) และรายงานการประชุม"), ("6.2", "Workflow Process"),
                                  ("6.3", "Use Case Diagram และ Use Case Description"), ("6.4", "เอกสารสรุปความต้องการของระบบงาน (SRS)"),
                                  ("6.5", "Screen Flow และ Screen Attributes"), ("6.6", "แผนประกันคุณภาพ (SQA) และ Traceability Record"),
                                  ("6.7", "Test Plan และ Test Case"), ("6.8", "คู่มือสำหรับผู้ใช้งาน และคู่มือผู้ดูแลลานจอด")], [1.6, 14.9], center_cols=(0,))
    save(d, "W3_Statement_of_Work_ParkQ.docx")


def build_w3_workflow():
    d = new_doc("Workflow Process")
    cover(d, "Workflow Process", "ขั้นตอนการทำงานของระบบ", "Workflow Process")
    heading(d, "Workflow Process คืออะไร")
    para(d, "Workflow Process คือแผนผังขั้นตอนการทำงานที่แสดงว่า \"ใคร\" ทำอะไร \"เมื่อไหร่\" ในลำดับไหน และต้องตัดสินใจอะไรบ้าง "
            "ระบบ ParkQ มีหลายกระบวนการย่อย จึงแยก Workflow ตามงานหลักของระบบ 4 กระบวนการ")
    heading(d, "สัญลักษณ์ที่ใช้", 2)
    table(d, ["สัญลักษณ์", "ชื่อ", "ความหมาย"], [("วงรีสีเขียว", "Terminator", "จุดเริ่มต้น / สิ้นสุด"),
                                              ("สี่เหลี่ยม", "Process", "ขั้นตอนการทำงาน"),
                                              ("สี่เหลี่ยมด้านขนาน", "Input / Output", "ผู้ใช้กรอกข้อมูล สแกน หรือชำระเงิน"),
                                              ("ข้าวหลามตัด", "Decision", "จุดตัดสินใจ (ใช่ / ไม่)"),
                                              ("ลูกศร", "Arrow", "ทิศทางของขั้นตอนถัดไป")], [4.5, 4, 8])
    flows = [
        ("wf1_booking", "Workflow 1: ค้นหาลานจอด ซื้อสิทธิ์/จองที่จอด และชำระเงิน", "ผู้ขับขี่",
         "เริ่มจากผู้ขับขี่เปิดเว็บ ถ้ายังไม่เข้าสู่ระบบจะเข้าสู่ระบบด้วย OTP ก่อน จากนั้นดูสถานะลานจอด ถ้าลานเต็มให้เลือกลานอื่น "
         "ถ้าว่างเลือกจอดเลยหรือจองล่วงหน้า ระบบล็อกช่องไว้ 10 นาทีระหว่างชำระเงิน ชำระสำเร็จได้ตั๋ว QR ไม่สำเร็จระบบคืนช่องให้ลาน"),
        ("wf2_gate", "Workflow 2: เข้า-ออกลานจอดด้วย QR Code", "ผู้ขับขี่, พนักงานหน้าลาน, Gate Controller",
         "ผู้ขับขี่สแกน QR ที่ตู้ประตูทางเข้า ระบบตรวจความถูกต้อง ถ้าผ่านเปิดไม้กั้นทันที ถ้าไม่ผ่านแสดงเหตุผลและให้เรียกพนักงาน "
         "ขาออกสแกน QR เดิม ถ้าจอดเกินเวลาเกิน 15 นาทีต้องชำระค่าส่วนเกินที่ตู้ก่อนไม้กั้นจะเปิด"),
        ("wf3_iot", "Workflow 3: อัปเดตสถานะช่องจอดจากเซ็นเซอร์ IoT", "เซ็นเซอร์ / ESP32, ระบบ",
         "เมื่อเซ็นเซอร์ตรวจพบรถเข้า-ออกช่อง บอร์ดเปลี่ยนไฟสถานะและส่งข้อมูลให้ระบบ ระบบคำนวณช่องว่างและสถานะลาน "
         "แล้วหน้าเว็บทุกจออัปเดตเอง ถ้าบอร์ดเงียบเกิน 2 นาที ระบบปิดการขายลานนั้นชั่วคราว (กระบวนการนี้เป็นงานภายในระบบ ไม่เป็น Use Case)"),
        ("wf4_admin", "Workflow 4: ผู้ดูแลตั้งค่าลานจอดและติดตามรายได้", "ผู้ดูแลลานจอด",
         "ผู้ดูแลเข้าสู่ระบบหลังบ้าน เพิ่มลานจอดถ้ายังไม่มี กำหนดราคาและสัดส่วนช่องจองล่วงหน้า เปิดขายออนไลน์ "
         "จากนั้นติดตามแดชบอร์ด และดูรายงานรายได้ตามช่วงวันที่"),
    ]
    for key, title, who, desc in flows:
        page_break(d)
        heading(d, title)
        rich(d, [("ผู้เกี่ยวข้อง: ", True), (who, False)])
        para(d, desc)
        image(d, IMG / f"{key}.png", 11.5, title)
    save(d, "W3_Workflow_Process_ParkQ.docx")


# ---------------------------------------------------------------- W4
def build_w4():
    d = new_doc("Use Case Diagram & Description")
    cover(d, "Use Case Diagram", "แผนภาพและคำอธิบาย Use Case", "Use Case Diagram พร้อมคำอธิบาย")
    heading(d, "Use Case Diagram พร้อมคำอธิบาย")
    para(d, "Use Case Diagram แสดงการทำงานระหว่างผู้ใช้ระบบ (Actor) กับระบบย่อยของ ParkQ ทุก Use Case ต้องมี Actor ที่เป็นคน "
            "กระทำผ่านหน้าจอ การประมวลผลภายใน เช่น การอ่านเซ็นเซอร์หรือการคำนวณช่องว่าง จึงไม่นับเป็น Use Case แต่เขียนไว้ใน Main Flow")
    table(d, ["สัญลักษณ์", "ความหมาย"], [("วงรี (Use Case)", "หน้าที่ที่ระบบต้องทำให้ Actor"),
                                       ("รูปคน (Actor)", "ผู้ใช้ระบบที่เป็นมนุษย์: ผู้ขับขี่, พนักงานหน้าลาน, ผู้ดูแลลานจอด"),
                                       ("กรอบสี่เหลี่ยม (System Boundary)", "ขอบเขตของระบบ ParkQ"),
                                       ("เส้นทึบ (Association)", "Actor ใช้งาน Use Case นั้น"),
                                       ("เส้นประ <<include>>", "Use Case หนึ่งต้องเรียกใช้อีก Use Case เสมอ เช่น การจองต้องชำระเงิน")], [5.5, 11])
    rich(d, [("รหัส: ", True), ("Level 1 = UC-โมดูล, Level 2 = UC-โมดูล-ลำดับ ตรงกับ Requirement ID ใน SRS เช่น UC-BKG-01 = BKG_01", False)])

    page_break(d)
    heading(d, "Level 1 แผนภาพการทำงานภาพรวมของผู้ใช้งานในโครงการ")
    image(d, IMG / "uc_level1.png", 16.5, "Use Case Diagram Level 1")
    for u in UC_LEVEL1:
        heading(d, f"Use Case Description: {u['name']}", 2)
        kv_table(d, [("Use Case ID", u["id"]), ("Use Case Name", u["name"]), ("Purpose", u["purpose"]),
                     ("Actor", " , ".join(u["actors"])), ("Precondition", u["pre"]), ("Postcondition", u["post"]),
                     ("Main Flows", numbered_text(u["main"]))])

    for u in UC_LEVEL1:
        page_break(d)
        module = next(m for m in MODULES if m["code"] == u["id"][3:])
        heading(d, f"Level 2 แผนภาพการทำงานของ{u['name']} ({u['id']})")
        image(d, IMG / f"uc_{u['id']}.png", 16.5, f"Use Case Diagram Level 2: {u['name']}")
        for uc in [c for c in UC_LEVEL2 if c[0].startswith(u["id"] + "-")]:
            cid, req, name, actors, purpose, pre, post, main, alts, screens = uc
            inc = [b for a, b in INCLUDES if a == cid]
            heading(d, f"Use Case Description: {name}", 2)
            kv_table(d, [("Use Case ID", cid), ("Use Case Name", name), ("Requirement ID", req), ("Purpose", purpose),
                         ("Actor", " , ".join(actors)), ("Precondition", pre), ("Postcondition", post),
                         ("Main Flows", numbered_text(main) + (f"\n(include {', '.join(inc)})" if inc else "")),
                         ("Alternatives", numbered_text(alts)), ("หน้าจอที่เกี่ยวข้อง", ", ".join(screens))])
    save(d, "W4_Use_Case_ParkQ.docx")


if __name__ == "__main__":
    build_w2_xlsx()
    build_w2_docx()
    build_w3_sow()
    build_w3_workflow()
    build_w4()
