// ParkQ back office: lot admin (ADM_01..03) and gate attendant (TKT_04).
import { api, getToken, setToken, devLogin, esc, baht, fmtTime, fmtDateTime, lotBadge, ticketBadge, toast, modal, fieldError, startAnnotations } from "./common.js";

const $app = document.getElementById("app");
let me = null, lots = [], lotId = sessionStorage.getItem("parkq_admin_lot") || "LOT01";
let timers = [];
const every = (ms, fn) => timers.push(setInterval(fn, ms));
const err = (e) => { if (e.status === 401) { setToken(null); route(); } else toast(e.message || "เกิดข้อผิดพลาด", true); };

const MENU = [
  ["dashboard", "แดชบอร์ด", ["admin"]], ["lots", "ลานจอด", ["admin"]], ["rates", "ราคา", ["admin"]],
  ["report", "รายงาน", ["admin"]], ["gate", "ตรวจสอบตั๋ว / เปิดไม้กั้น", ["admin", "attendant"]],
];

function shell(active, title, body, menuEl) {
  $app.innerHTML = `<div class="bo">
    <nav class="side" ${menuEl ? `data-el="${menuEl}"` : ""}><div class="logo"><span>P</span>ParkQ Admin</div>
      ${MENU.filter((m) => m[2].includes(me.role)).map(([k, t]) => `<a href="#/${k}" class="${k === active ? "on" : ""}">${t}</a>`).join("")}
      <div class="who">${esc(me.name)}<br><span class="small">${me.role === "admin" ? "ผู้ดูแลลานจอด" : "พนักงานหน้าลาน"}</span><br><a href="#" id="logout" style="padding:6px 0;color:#93c5fd">ออกจากระบบ</a></div></nav>
    <main class="main"><div class="head"><h1>${title}</h1><div id="headRight"></div></div>${body}</main></div>`;
  $app.querySelector("#logout").addEventListener("click", async (e) => { e.preventDefault(); await api("/api/auth/logout", { method: "POST" }).catch(() => {}); setToken(null); route(); });
}

function lotSelect(el) {
  return `<label class="field" style="min-width:300px" ${el ? `data-el="${el}"` : ""}><span class="label">ลานจอด <span class="req">*</span></span>
    <select id="lotSel" class="input">${lots.map((l) => `<option value="${l.id}" ${l.id === lotId ? "selected" : ""}>${esc(l.name)}</option>`).join("")}</select></label>`;
}
function bindLotSelect() {
  $app.querySelector("#lotSel")?.addEventListener("change", (e) => { lotId = e.target.value; sessionStorage.setItem("parkq_admin_lot", lotId); route(); });
}

// ------------------------------------------------------------------ login (same OTP flow as drivers)
function screenLogin() {
  $app.innerHTML = `<div class="login-wrap"><div class="card stack">
    <div class="row"><span class="badge blue">ParkQ Admin</span></div>
    <h1 style="font-size:22px">เข้าสู่ระบบหลังบ้าน</h1>
    <p class="muted small" style="margin:0">สำหรับผู้ดูแลลานจอดและพนักงานหน้าลาน</p>
    <label class="field"><span class="label">เบอร์โทรศัพท์</span><input id="phone" class="input" inputmode="numeric" maxlength="10" placeholder="08x-xxx-xxxx"><div class="err"></div></label>
    <div id="otpBox" class="hidden stack"><label class="field"><span class="label">รหัส OTP</span><input id="otp" class="input otp-input num" inputmode="numeric" maxlength="6" placeholder="••••••"><div class="err"></div></label><div id="dev"></div></div>
    <button class="btn block" id="go">ขอรหัส OTP</button>
    <p class="small muted" style="margin:0">ทดสอบ: ผู้ดูแล 0800000001 • พนักงาน 0800000002</p></div></div>`;
  const phone = $app.querySelector("#phone"), otp = $app.querySelector("#otp"), go = $app.querySelector("#go");
  let stage = "phone";
  go.addEventListener("click", async () => {
    try {
      if (stage === "phone") {
        const r = await api("/api/auth/otp", { method: "POST", body: { phone: phone.value, accept: true } });
        stage = "otp"; $app.querySelector("#otpBox").classList.remove("hidden"); go.textContent = "เข้าสู่ระบบ"; otp.focus();
        if (r.dev_code) $app.querySelector("#dev").innerHTML = `<div class="dev-box">โหมดทดสอบ: รหัสคือ <b>${r.dev_code}</b></div>`;
      } else {
        const r = await api("/api/auth/verify", { method: "POST", body: { phone: phone.value, code: otp.value } });
        if (!["admin", "attendant"].includes(r.user.role)) { toast("บัญชีนี้ไม่มีสิทธิ์เข้าระบบหลังบ้าน", true); return; }
        setToken(r.token); route();
      }
    } catch (e) { fieldError(stage === "phone" ? phone : otp, e.message); }
  });
}

// ------------------------------------------------------------------ ADM_03 dashboard
async function screenDashboard() {
  shell("dashboard", "แดชบอร์ดลานจอด", `
    <div class="row" style="margin-bottom:16px">${lotSelect(1)}</div>
    <div class="stats" id="stats" data-el="2"></div>
    <div class="grid2">
      <div class="card" data-el="3"><div class="row between" style="margin-bottom:12px"><h3>ผังช่องจอด (เรียลไทม์)</h3><span class="legend"><span><i style="background:#22c55e"></i>ว่าง</span><span><i style="background:#ef4444"></i>มีรถ</span></span></div>
        <div class="slots" id="slots"></div><p class="small muted" style="margin:12px 0 0">คลิกช่องเพื่อจำลองสัญญาณเซ็นเซอร์ (ใช้ระหว่างที่ยังไม่ได้ติดตั้งอุปกรณ์)</p></div>
      <div class="card" data-el="4"><h3 style="margin-bottom:10px">รายการเข้า-ออกล่าสุด</h3><div style="max-height:420px;overflow:auto"><table class="t" id="logs"></table></div></div>
    </div>`, 5);
  bindLotSelect();
  const load = async () => {
    let d;
    try { d = await api("/api/admin/dashboard?lot_id=" + lotId); } catch (e) { return err(e); }
    const s = $app.querySelector("#stats"); if (!s) return;
    s.innerHTML = [["ช่องว่าง", `${d.lot.stale ? "–" : d.lot.free} <span class="small muted">/ ${d.lot.capacity}</span>`, lotBadge(d.lot.status)],
      ["รถจอดอยู่", d.lot.occupied, ""], ["การจองวันนี้", d.bookings_today, `<span class="small muted">กันช่องไว้ ${d.lot.reserved}</span>`], ["รายได้วันนี้", baht(d.revenue_today), ""]]
      .map(([l, v, x]) => `<div class="card stat"><div class="label">${l}</div><b class="num">${v}</b>${x}</div>`).join("");
    $app.querySelector("#slots").innerHTML = d.slots.map((x) => `<button class="slot ${x.occupied ? "busy" : "free"}" data-n="${x.slot_no}" title="โซน ${x.zone}">${x.zone}${x.slot_no}</button>`).join("");
    $app.querySelectorAll(".slot").forEach((b) => b.addEventListener("click", async () => { await api(`/api/admin/lots/${lotId}/slots/${b.dataset.n}/toggle`, { method: "POST" }).catch(err); load(); }));
    $app.querySelector("#logs").innerHTML = `<tr><th>เวลา</th><th>ทะเบียน</th><th>ประตู</th><th>ผล</th><th>วิธี</th></tr>` +
      (d.logs.map((l) => `<tr><td class="num">${fmtTime(l.at)}</td><td>${esc(l.plate || "-")}</td><td>${l.gate === "in" ? "เข้า" : "ออก"}</td>
        <td>${l.result === "OK" ? '<span class="badge ok">ผ่าน</span>' : `<span class="badge bad">${esc(l.result)}</span>`}</td><td>${l.method === "qr" ? "QR" : "พนักงาน"}</td></tr>`).join("")
        || `<tr><td colspan="5" class="muted">ยังไม่มีรายการ</td></tr>`);
  };
  await load(); every(5000, load);
}

// ------------------------------------------------------------------ ADM_01 lots
async function screenLots(params) {
  shell("lots", "ลานจอดของฉัน", `<div class="card" style="padding:0;overflow:hidden" data-el="2"><table class="t" id="tbl"></table></div>`);
  $app.querySelector("#headRight").innerHTML = `<button class="btn" id="add" data-el="1">+ เพิ่มลานจอด</button>`;
  $app.querySelector("#add").addEventListener("click", () => lotModal());
  $app.querySelector("#tbl").innerHTML = `<tr><th>รหัส</th><th>ชื่อลานจอด</th><th>ช่องจอด</th><th>เวลาเปิด</th><th>สถานะ</th><th>อุปกรณ์ IoT</th><th>ขายออนไลน์</th><th></th></tr>` +
    lots.map((l, i) => `<tr><td>${l.id}</td><td><b>${esc(l.name)}</b><div class="small muted">${esc(l.address)}</div></td><td class="num">${l.capacity}</td>
      <td class="num">${l.open_time}–${l.close_time}</td><td>${lotBadge(l.status)}</td><td>${l.device_id ? `<span class="badge ${l.stale ? "gray" : "ok"}">${esc(l.device_id)}</span>` : '<span class="muted small">จำลอง</span>'}</td>
      <td><label class="toggle" ${i === 0 ? 'data-el="3"' : ""}><input type="checkbox" data-online="${l.id}" ${l.online ? "checked" : ""}><span></span></label></td>
      <td><button class="btn ghost sm" data-edit="${l.id}" ${i === 0 ? 'data-el="4"' : ""}>แก้ไข</button></td></tr>`).join("");
  $app.querySelectorAll("[data-online]").forEach((c) => c.addEventListener("change", async () => {
    try { await api(`/api/admin/lots/${c.dataset.online}/online?online=${c.checked}`, { method: "PUT" }); toast(c.checked ? "เปิดขายออนไลน์แล้ว" : "ปิดขายออนไลน์แล้ว"); } catch (e) { err(e); }
  }));
  $app.querySelectorAll("[data-edit]").forEach((b) => b.addEventListener("click", () => lotModal(lots.find((l) => l.id === b.dataset.edit))));
  if (params.get("edit")) lotModal(lots.find((l) => l.id === params.get("edit")));
}

function lotModal(l) {
  const v = l || { name: "", address: "", lat: 13.8566, lng: 100.585, capacity: 20, open_time: "06:00", close_time: "22:00", device_id: "", online: 1 };
  const m = modal(`<h2>${l ? "แก้ไขลานจอด " + l.id : "เพิ่มลานจอด"}</h2><div class="form2">
    <label class="field full" data-el="1"><span class="label">ชื่อลานจอด <span class="req">*</span></span><input id="f_name" class="input" maxlength="100" value="${esc(v.name)}"><div class="err"></div></label>
    <label class="field full" data-el="2"><span class="label">ที่อยู่ <span class="req">*</span></span><input id="f_address" class="input" value="${esc(v.address)}"><div class="err"></div></label>
    <div class="field full" data-el="3"><span class="label">พิกัด (ละติจูด, ลองจิจูด) <span class="req">*</span></span><div class="row"><input id="f_lat" class="input" type="number" step="0.0001" value="${v.lat}"><input id="f_lng" class="input" type="number" step="0.0001" value="${v.lng}"></div></div>
    <label class="field" data-el="4"><span class="label">จำนวนช่องจอด <span class="req">*</span></span><input id="f_capacity" class="input" type="number" min="1" max="5000" value="${v.capacity}"><div class="err"></div></label>
    <div class="field" data-el="5"><span class="label">เวลาเปิด – ปิด <span class="req">*</span></span><div class="row"><input id="f_open" class="input" type="time" value="${v.open_time}"><input id="f_close" class="input" value="${v.close_time}" placeholder="24:00"></div><div class="err" id="hoursErr"></div></div>
    <label class="field full" data-el="6"><span class="label">รหัสอุปกรณ์ IoT (Gate Controller)</span><input id="f_device" class="input" placeholder="เช่น ESP32-GATE-02 (ว่าง = ใช้ตัวจำลอง)" value="${esc(v.device_id || "")}"></label>
    <div class="full row" style="justify-content:flex-end;margin-top:6px"><button class="btn ghost" id="x">ยกเลิก</button><button class="btn" id="save" data-el="7">บันทึก</button></div></div>`);
  const f = (k) => m.el.querySelector("#f_" + k);
  m.el.querySelector("#x").addEventListener("click", m.close);
  m.el.querySelector("#save").addEventListener("click", async () => {
    const body = { name: f("name").value, address: f("address").value, lat: +f("lat").value, lng: +f("lng").value, capacity: +f("capacity").value,
      open_time: f("open").value, close_time: f("close").value || "24:00", device_id: f("device").value, online: !!v.online };
    try {
      await api(l ? "/api/admin/lots/" + l.id : "/api/admin/lots", { method: l ? "PUT" : "POST", body });
      m.close(); toast("บันทึกข้อมูลลานจอดแล้ว"); lots = await api("/api/admin/lots"); route();
    } catch (e) {
      const map = { NAME_REQUIRED: "name", DUPLICATE_NAME: "name", ADDRESS_REQUIRED: "address", INVALID_CAPACITY: "capacity", CAPACITY_BELOW_BOOKINGS: "capacity" };
      if (map[e.code]) fieldError(f(map[e.code]), e.message); else if (e.code === "INVALID_HOURS") m.el.querySelector("#hoursErr").textContent = e.message; else err(e);
    }
  });
}

// ------------------------------------------------------------------ ADM_02 rates
async function screenRates() {
  const l = lots.find((x) => x.id === lotId) || lots[0];
  shell("rates", "กำหนดอัตราค่าบริการ", `<div class="row" style="margin-bottom:16px">${lotSelect()}</div>
    <div class="card" style="max-width:620px"><div class="stack">
      <label class="field" data-el="1"><span class="label">ค่าจอดต่อชั่วโมง (บาท) <span class="req">*</span></span><input id="rate" class="input" type="number" min="0" max="1000" value="${l.rate}"><div class="err"></div></label>
      <label class="field" data-el="2"><span class="label">สัดส่วนช่องที่เปิดให้จองล่วงหน้า (%) <span class="req">*</span></span><input id="ratio" class="input" type="number" min="0" max="100" value="${l.advance_ratio}"><div class="err"></div>
        <div class="small muted" style="margin-top:6px" id="ratioHint"></div></label>
      <div class="card flat" data-el="3"><dl class="kv"><dt>จอดฟรี</dt><dd>15 นาทีแรก</dd><dt>จอดเกินเวลา</dt><dd>คิดตามชั่วโมงที่เริ่มนับ (เกิน 15 นาที)</dd><dt>ยกเลิกฟรี</dt><dd>ก่อนเวลาเริ่ม ≥ 60 นาที</dd></dl></div>
      <div class="demo-note">ราคาใหม่มีผลกับรายการใหม่เท่านั้น ตั๋วที่ชำระแล้วใช้ราคาเดิม</div>
      <div class="row" style="justify-content:flex-end"><button class="btn" id="save" data-el="4">บันทึก</button></div></div></div>`);
  bindLotSelect();
  const hint = () => { $app.querySelector("#ratioHint").textContent = `= เปิดจองล่วงหน้าได้สูงสุด ${Math.floor(l.capacity * (+$app.querySelector("#ratio").value || 0) / 100)} จาก ${l.capacity} ช่อง ที่เหลือสงวนไว้สำหรับ "จอดเลย"`; };
  $app.querySelector("#ratio").addEventListener("input", hint); hint();
  $app.querySelector("#save").addEventListener("click", async () => {
    if (!confirm("ยืนยันบันทึกราคา? ราคานี้มีผลกับรายการใหม่เท่านั้น")) return;
    try { await api(`/api/admin/lots/${l.id}/rates`, { method: "PUT", body: { rate: +$app.querySelector("#rate").value, advance_ratio: +$app.querySelector("#ratio").value } });
      toast("บันทึกราคาแล้ว"); lots = await api("/api/admin/lots"); } catch (e) { fieldError($app.querySelector(e.code === "INVALID_RATIO" ? "#ratio" : "#rate"), e.message); }
  });
}

// ------------------------------------------------------------------ ADM_03 report
async function screenReport() {
  const today = new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Bangkok" });
  const from = new Date(Date.now() - 13 * 864e5).toLocaleDateString("en-CA", { timeZone: "Asia/Bangkok" });
  shell("report", "รายงานรายได้", `<div class="row" style="margin-bottom:16px;align-items:flex-end;flex-wrap:wrap">${lotSelect()}
      <div class="field" data-el="1"><span class="label">ช่วงวันที่ <span class="req">*</span></span><div class="row"><input id="d0" type="date" class="input" value="${from}"> – <input id="d1" type="date" class="input" value="${today}"></div></div>
      <button class="btn soft" id="run">แสดงรายงาน</button><button class="btn ghost" id="csv" data-el="4">ส่งออก CSV</button></div>
    <div class="err" id="rangeErr" style="color:var(--bad);margin-bottom:8px"></div>
    <div class="card" data-el="2"><div class="row between"><h3>รายได้รายวัน</h3><div class="legend"><span><i style="background:#1f5bff"></i>จอดเลย</span><span><i style="background:#93b4ff"></i>จองล่วงหน้า</span><span><i style="background:#f59e0b"></i>ค่าส่วนเกิน</span></div></div>
      <div class="chart" id="chart"></div><div class="xlabels" id="xl"></div></div>
    <div class="card" style="margin-top:16px;padding:0;overflow:hidden" data-el="3"><table class="t" id="tbl"></table></div>`);
  bindLotSelect();
  const q = () => `/api/admin/report?lot_id=${lotId}&date_from=${$app.querySelector("#d0").value}&date_to=${$app.querySelector("#d1").value}`;
  const run = async () => {
    let r; $app.querySelector("#rangeErr").textContent = "";
    try { r = await api(q()); } catch (e) { $app.querySelector("#rangeErr").textContent = e.message; return; }
    const max = Math.max(1, ...r.days.map((d) => d.revenue));
    $app.querySelector("#chart").innerHTML = r.days.map((d) => `<div class="col" data-tip="${d.date}: ${baht(d.revenue)}">
      <i style="height:${d.now / max * 200}px;background:#1f5bff"></i><i style="height:${d.advance / max * 200}px;background:#93b4ff"></i><i style="height:${d.overstay / max * 200}px;background:#f59e0b;border-radius:4px 4px 0 0"></i></div>`).join("");
    $app.querySelector("#xl").innerHTML = r.days.map((d) => `<span>${+d.date.slice(8)}</span>`).join("");
    $app.querySelector("#tbl").innerHTML = `<tr><th>วันที่</th><th>จำนวนรายการ</th><th>จอดเลย</th><th>จองล่วงหน้า</th><th>ค่าส่วนเกิน</th><th>รายได้รวม</th><th>อัตราการใช้ช่อง</th></tr>` +
      r.days.slice().reverse().map((d) => `<tr><td class="num">${d.date}</td><td class="num">${d.count}</td><td class="num">${baht(d.now)}</td><td class="num">${baht(d.advance)}</td><td class="num">${baht(d.overstay)}</td><td class="num"><b>${baht(d.revenue)}</b></td><td class="num">${d.occupancy}%</td></tr>`).join("") +
      `<tr style="background:#f8fafc"><td><b>รวม</b></td><td class="num"><b>${r.count}</b></td><td></td><td></td><td></td><td class="num"><b>${baht(r.total)}</b></td><td></td></tr>`;
  };
  $app.querySelector("#run").addEventListener("click", run);
  $app.querySelector("#csv").addEventListener("click", async () => {
    const res = await fetch(q() + "&format=csv", { headers: { Authorization: "Bearer " + getToken() } });
    if (!res.ok) return toast((await res.json()).message, true);
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(await res.blob()), download: `parkq-${lotId}.csv` }); a.click();
  });
  run();
}

// ------------------------------------------------------------------ TKT_04 attendant: check ticket & open gate
async function screenGate(params) {
  shell("gate", "ตรวจสอบตั๋วและเปิดไม้กั้น", `<div class="grid2" style="margin-top:0">
    <div class="card stack">
      <label class="field" data-el="1"><span class="label">ค้นหาด้วยทะเบียนรถ หรือ รหัสตั๋ว <span class="req">*</span></span><div class="row"><input id="q" class="input" placeholder="เช่น กข1234 หรือ TK-000123" value="${esc(params.get("q") || "")}"><button class="btn" id="find">ค้นหา</button></div><div class="err"></div></label>
      <div data-el="2"><table class="t" id="res"></table></div>
      <div class="form2">
        <label class="field" data-el="3"><span class="label">ประตู <span class="req">*</span></span><select id="gate" class="input"><option value="in">ทางเข้า</option><option value="out">ทางออก</option></select></label>
        <label class="field" data-el="4"><span class="label">เหตุผลการเปิดด้วยตนเอง <span class="req">*</span></span><select id="why" class="input"><option value="">– เลือกเหตุผล –</option><option>QR สแกนไม่ได้</option><option>มือถือแบตหมด</option><option>รับชำระเงินสด</option><option>อื่น ๆ</option></select><div class="err"></div></label>
      </div>
      <div class="row between"><span class="small muted" id="sel">ยังไม่ได้เลือกตั๋ว (เปิดได้โดยไม่ผูกตั๋ว)</span><button class="btn" id="open" data-el="5">เปิดไม้กั้น</button></div>
      <div class="row">${lotSelect()}</div>
    </div>
    <div class="card" data-el="6"><h3 style="margin-bottom:10px">การเรียกพนักงานจากตู้</h3><div id="alerts" class="stack"></div></div></div>`);
  bindLotSelect();
  let picked = null;
  const find = async () => {
    const q = $app.querySelector("#q").value.trim(); if (!q) return fieldError($app.querySelector("#q"), "กรุณากรอกทะเบียนรถหรือรหัสตั๋ว");
    fieldError($app.querySelector("#q"), "");
    let rows; try { rows = await api("/api/staff/search?q=" + encodeURIComponent(q)); } catch (e) { return err(e); }
    $app.querySelector("#res").innerHTML = rows.length ? `<tr><th>รหัสตั๋ว</th><th>ทะเบียน</th><th>เวลา</th><th>สถานะ</th><th>ค้างชำระ</th><th></th></tr>` + rows.map((t) =>
      `<tr><td>${t.id}</td><td>${esc(t.plate)}</td><td class="num small">${fmtTime(t.start_at)}–${fmtTime(t.end_at)}</td><td>${ticketBadge(t.status)}</td><td class="num">${t.due ? baht(t.due) : "-"}</td>
        <td><button class="btn ghost sm" data-pick="${t.id}" data-lot="${t.lot_id}" data-st="${t.status}">เลือก</button></td></tr>`).join("")
      : `<tr><td class="muted">ไม่พบตั๋วที่ใช้งานได้</td></tr>`;
    $app.querySelectorAll("[data-pick]").forEach((b) => b.addEventListener("click", () => {
      picked = b.dataset.pick; lotId = b.dataset.lot; $app.querySelector("#lotSel").value = lotId;
      $app.querySelector("#gate").value = b.dataset.st === "PARKED" ? "out" : "in";
      $app.querySelector("#sel").innerHTML = `เลือกตั๋ว <b>${picked}</b>`;
    }));
  };
  $app.querySelector("#find").addEventListener("click", find);
  $app.querySelector("#q").addEventListener("keydown", (e) => e.key === "Enter" && find());
  $app.querySelector("#open").addEventListener("click", async () => {
    const why = $app.querySelector("#why");
    if (!why.value) return fieldError(why, "กรุณาเลือกเหตุผลก่อนเปิดไม้กั้น");
    fieldError(why, "");
    try { await api("/api/staff/open", { method: "POST", body: { lot_id: lotId, gate: $app.querySelector("#gate").value, reason: why.value, ticket_id: picked } });
      toast("ส่งคำสั่งเปิดไม้กั้นแล้ว และบันทึก log"); picked = null; $app.querySelector("#sel").textContent = "ยังไม่ได้เลือกตั๋ว"; if ($app.querySelector("#q").value) find(); loadAlerts(); } catch (e) { err(e); }
  });
  const loadAlerts = async () => {
    const a = await api("/api/staff/alerts").catch(() => []); const box = $app.querySelector("#alerts"); if (!box) return;
    box.innerHTML = a.length ? a.map((x) => `<div class="alert"><b>${esc(x.lot_name)}</b> – ประตู${x.gate === "in" ? "ทางเข้า" : "ทางออก"}<div class="small muted">${esc(x.message)} • ${fmtTime(x.at)} น.</div></div>`).join("") : `<div class="muted small">ไม่มีการเรียก</div>`;
  };
  loadAlerts(); every(5000, loadAlerts);
  if (params.get("q")) find();
}

// ------------------------------------------------------------------ router
async function route() {
  timers.forEach(clearInterval); timers = [];
  document.querySelectorAll(".modal-back").forEach((m) => m.remove());
  if (!getToken()) return screenLogin();
  try { me = await api("/api/me"); } catch { setToken(null); return screenLogin(); }
  if (!["admin", "attendant"].includes(me.role)) { setToken(null); return screenLogin(); }
  const [path, query] = (location.hash.slice(2) || (location.pathname === "/staff" || me.role === "attendant" ? "gate" : "dashboard")).split("?");
  const params = new URLSearchParams(query || "");
  if (me.role === "admin") { try { lots = await api("/api/admin/lots"); } catch (e) { return err(e); } }
  else lots = await api("/api/lots").catch(() => []);
  if (!lots.some((l) => l.id === lotId) && lots[0]) lotId = lots[0].id;
  const allowed = MENU.find((m) => m[0] === path)?.[2].includes(me.role);
  const screen = { dashboard: screenDashboard, lots: () => screenLots(params), rates: screenRates, report: screenReport, gate: () => screenGate(params) }[allowed ? path : "gate"];
  try { await screen(); } catch (e) { err(e); }
}
addEventListener("hashchange", route);
(async () => { try { await devLogin(); } catch {} startAnnotations(); route(); })();
