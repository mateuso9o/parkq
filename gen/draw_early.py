"""Draw W2-W4 figures: use case diagrams (Level 1 and 2) and the Gantt chart, via headless Chrome."""
import html
from datetime import timedelta

from draw import ARROW_DEF, svg_page, shoot, text_block
from early_data import (ACTOR_ADMIN, ACTOR_DRIVER, ACTOR_STAFF, INCLUDES, PLAN, PLAN_START, PLAN_WEEKS,
                        UC_LEVEL1, UC_LEVEL2)

ACTOR_SIDE = {ACTOR_DRIVER: "left", ACTOR_STAFF: "right", ACTOR_ADMIN: "right"}


def stick(x, y, label):
    return (f"<g stroke='#13203f' stroke-width='2.2' fill='none'><circle cx='{x}' cy='{y}' r='13'/>"
            f"<path d='M{x},{y + 13} v34 M{x - 22},{y + 26} h44 M{x},{y + 47} l-18,30 M{x},{y + 47} l18,30'/></g>"
            + text_block(x, y + 98, label, 15, 20, 700))


def usecase_diagram(title, cases, actors):
    """cases: [(id, name)], actors: [name]; actors on the left/right of a system boundary, ellipses inside."""
    W, row_h = 1100, 92
    H = max(420, 150 + len(cases) * row_h)
    bx, by, bw, bh = 250, 70, 600, H - 100
    out = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}'>{ARROW_DEF}<rect width='{W}' height='{H}' fill='#fff'/>",
           text_block(W / 2, 30, title, 19, 200, 700),
           f"<rect x='{bx}' y='{by}' width='{bw}' height='{bh}' rx='14' fill='#f6f8fd' stroke='#1e5eff' stroke-width='2'/>",
           text_block(bx + bw / 2, by + 22, "ระบบ ParkQ", 15, 40, 700, "#1e5eff")]
    pos = {}
    for i, (cid, name) in enumerate(cases):
        cx, cy = bx + bw / 2, by + 70 + i * row_h
        pos[cid] = (cx, cy)
    left = [a for a in actors if ACTOR_SIDE[a] == "left"]
    right = [a for a in actors if ACTOR_SIDE[a] == "right"]
    apos = {}
    for side, group, x in (("left", left, 110), ("right", right, W - 110)):
        for k, a in enumerate(group):
            apos[a] = (x, by + (k + 1) * bh / (len(group) + 1) - 50)
    links = []
    for cid, name in cases:
        for a in actor_of(cid):
            if a in apos:
                links.append((a, cid))
    for a, cid in links:
        ax, ay = apos[a]
        cx, cy = pos[cid]
        sx = ax + 30 if ACTOR_SIDE[a] == "left" else ax - 30
        ex = cx - 185 if ACTOR_SIDE[a] == "left" else cx + 185
        out.append(f"<line x1='{sx}' y1='{ay + 30}' x2='{ex}' y2='{cy}' stroke='#64748b' stroke-width='1.6'/>")
    for a, b in INCLUDES:
        if a in pos and b in pos:
            (x1, y1), (x2, y2) = pos[a], pos[b]
            out.append(f"<path d='M{x1 + 185},{y1} C{x1 + 260},{y1} {x2 + 260},{y2} {x2 + 188},{y2}' fill='none' stroke='#b45309' "
                       f"stroke-width='1.6' stroke-dasharray='6 5' marker-end='url(#a)'/>")
            out.append(f"<text x='{max(x1, x2) + 262}' y='{(y1 + y2) / 2}' font-size='12' fill='#b45309' text-anchor='middle'>&lt;&lt;include&gt;&gt;</text>")
    for cid, name in cases:
        cx, cy = pos[cid]
        out.append(f"<ellipse cx='{cx}' cy='{cy}' rx='185' ry='34' fill='#fff' stroke='#13203f' stroke-width='1.8'/>")
        out.append(text_block(cx, cy - 8, cid, 12, 40, 700, "#1e5eff"))
        out.append(text_block(cx, cy + 11, name, 14, 60, 600))
    for a, (x, y) in apos.items():
        out.append(stick(x, y, a))
    out.append("</svg>")
    return "".join(out), W, H


def actor_of(cid):
    for u in UC_LEVEL1:
        if u["id"] == cid:
            return u["actors"]
    for u in UC_LEVEL2:
        if u[0] == cid:
            return u[3]
    return []


def gantt():
    weeks = [PLAN_START + timedelta(weeks=k) for k in range(PLAN_WEEKS)]
    months = {}
    for w in weeks:
        months.setdefault(w.strftime("%m"), 0)
        months[w.strftime("%m")] += 1
    th_names = {"08": "ส.ค. 69", "09": "ก.ย. 69", "10": "ต.ค. 69", "11": "พ.ย. 69", "12": "ธ.ค. 69"}
    colors = {"วางแผน": "#64748b", "วิเคราะห์": "#1e5eff", "ออกแบบ": "#7c3aed", "คุณภาพ": "#0891b2", "พัฒนา": "#16a34a", "ทดสอบ": "#d97706", "ส่งมอบ": "#dc2626"}
    head1 = "".join(f"<th colspan='{n}'>{th_names[m]}</th>" for m, n in months.items())
    head2 = "".join(f"<th class='wk'>{w.day}</th>" for w in weeks)
    rows = []
    for i, (task, who, roles, s, e, phase) in enumerate(PLAN, 1):
        cells = "".join(f"<td class='wk'>{'<i style=background:' + colors[phase] + '></i>' if w <= e and w + timedelta(days=6) >= s else ''}</td>" for w in weeks)
        rows.append(f"<tr><td class='n'>{i}</td><td class='task'>{html.escape(task)}</td>"
                    + "".join(f"<td class='r'>{'●' if r in roles else ''}</td>" for r in ("PM", "SA", "Dev", "QA"))
                    + f"<td class='d'>{s.day}/{s.month}–{e.day}/{e.month}</td>{cells}</tr>")
    legend = "".join(f"<span><i style='background:{c}'></i>{p}</span>" for p, c in colors.items())
    doc = f"""<!doctype html><html><head><meta charset='utf-8'><style>
      body{{font-family:'Leelawadee UI',Tahoma,sans-serif;margin:16px;color:#1d2433;width:1560px}}
      h1{{font-size:20px;margin:0 0 10px}} table{{border-collapse:collapse;font-size:12.5px;width:100%}}
      th,td{{border:1px solid #d6dbe6;padding:4px 6px}} th{{background:#13203f;color:#fff}}
      td.task{{min-width:420px}} td.n,td.r{{text-align:center;width:26px}} td.d{{white-space:nowrap;width:80px}}
      .wk{{width:34px;padding:0;text-align:center}} td.wk i{{display:block;height:14px;margin:0 1px;border-radius:3px}}
      .legend{{display:flex;gap:14px;margin-top:10px;font-size:13px}} .legend i{{display:inline-block;width:14px;height:12px;border-radius:3px;margin-right:5px}}
    </style></head><body><h1>Project Plan (Gantt Chart) – ParkQ ระบบซื้อสิทธิ์และจองที่จอดรถออนไลน์ด้วย QR Code</h1>
    <table><tr><th rowspan='2'>#</th><th rowspan='2'>งาน (Task)</th><th rowspan='2'>PM</th><th rowspan='2'>SA</th><th rowspan='2'>Dev</th><th rowspan='2'>QA</th>
    <th rowspan='2'>ช่วงวันที่</th>{head1}</tr><tr>{head2}</tr>{''.join(rows)}</table><div class='legend'>{legend}</div></body></html>"""
    return doc, 1600, 140 + 34 * len(PLAN)


if __name__ == "__main__":
    jobs = []
    svg, w, h = usecase_diagram("Use Case Diagram Level 1: ภาพรวมระบบ ParkQ", [(u["id"], u["name"]) for u in UC_LEVEL1],
                                [ACTOR_DRIVER, ACTOR_STAFF, ACTOR_ADMIN])
    jobs.append(("uc_level1", svg_page(svg, w, h), w, h))
    for u in UC_LEVEL1:
        cases = [(c[0], c[2]) for c in UC_LEVEL2 if c[0].startswith(u["id"] + "-")]
        if u["id"] == "UC-ACC":
            actors = [ACTOR_DRIVER, ACTOR_STAFF, ACTOR_ADMIN]
        else:
            actors = sorted({a for c in UC_LEVEL2 if c[0].startswith(u["id"] + "-") for a in c[3]}, key=[ACTOR_DRIVER, ACTOR_STAFF, ACTOR_ADMIN].index)
        svg, w, h = usecase_diagram(f"Use Case Diagram Level 2: {u['name']} ({u['id']})", cases, actors)
        jobs.append((f"uc_{u['id']}", svg_page(svg, w, h), w, h))
    doc, w, h = gantt()
    jobs.append(("gantt", doc, w, h))
    shoot(jobs)
    print("drawn", len(jobs))
