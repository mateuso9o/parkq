// ParkQ driver web app (hash router). Each screen marks its documented elements with data-el="n".
import { api, getToken, setToken, devLogin, qs, esc, baht, fmtTime, fmtRange, fmtDuration, fmtDateTime, lotBadge, ticketBadge,
  qrSrc, toast, modal, fieldError, provinceOptions, startAnnotations, TICKET_STATUS } from "./common.js";

const $app = document.getElementById("app");
const $tab = document.getElementById("tabbar");
let config = { dev: false, demo_payment: true };
let me = null;
let timers = [];
const every = (ms, fn) => timers.push(setInterval(fn, ms));
const clearTimers = () => { timers.forEach(clearInterval); timers = []; };

const ICON = {
  back: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>`,
  search: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>`,
  home: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 11l9-7 9 7v9a1 1 0 01-1 1h-5v-6H9v6H4a1 1 0 01-1-1z"/></svg>`,
  ticket: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 8a2 2 0 002-2h14a2 2 0 002 2v2a2 2 0 000 4v2a2 2 0 00-2 2H5a2 2 0 00-2-2v-2a2 2 0 000-4z"/><path d="M14 6v12" stroke-dasharray="2 2"/></svg>`,
  user: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/></svg>`,
  check: `<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>`,
  nav: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M3 11l18-8-8 18-2-8z"/></svg>`,
};

function topbar(title, back) {
  return `<header class="topbar">${back ? `<button class="icon-btn" data-el="${back.el ?? ""}" onclick="${back.href ? `location.hash='${back.href}'` : "history.back()"}" aria-label="ย้อนกลับ">${ICON.back}</button>` : ""}<h1>${esc(title)}</h1></header>`;
}

function showTabs(active, el) {
  $tab.classList.remove("hidden");
  $tab.dataset.el = el;
  $tab.innerHTML = [["#/", "หน้าแรก", ICON.home, "home"], ["#/tickets", "ตั๋วของฉัน", ICON.ticket, "tickets"], ["#/account", "บัญชี", ICON.user, "account"]]
    .map(([h, t, i, k]) => `<a href="${h}" class="${k === active ? "on" : ""}">${i}${t}</a>`).join("");
}

function err(e) {
  if (e.status === 401) { setToken(null); sessionStorage.setItem("parkq_next", location.hash); location.hash = "#/login"; return; }
  toast(e.message || "เกิดข้อผิดพลาด", true);
}

// ------------------------------------------------------------------ ACC_01 login / OTP / register
let pendingPhone = sessionStorage.getItem("parkq_phone") || "";

function screenLogin() {
  $app.innerHTML = `
    <div class="hero">
      <div class="logo" data-el="1"><span class="mark">P</span>ParkQ</div>
      <p data-el="2">จอดง่าย จองไว ด้วย QR<br><span class="small">เช็กที่ว่าง ซื้อสิทธิ์จอด แล้วสแกนเข้าได้ทันที</span></p>
    </div>
    <div class="card float-card stack">
      <h2 style="font-size:19px">เข้าสู่ระบบ / สมัครสมาชิก</h2>
      <label class="field" data-el="3"><span class="label">เบอร์โทรศัพท์ <span class="req">*</span></span>
        <input id="phone" class="input" inputmode="numeric" maxlength="10" placeholder="08x-xxx-xxxx" value="${esc(pendingPhone)}" autocomplete="tel">
        <div class="err"></div></label>
      <label class="check" data-el="4"><input type="checkbox" id="accept">
        <span>ฉันยอมรับ <a href="#" onclick="event.preventDefault()">เงื่อนไขการใช้บริการ</a> และ <a href="#" onclick="event.preventDefault()">นโยบายความเป็นส่วนตัว</a></span></label>
      <button id="send" class="btn block" data-el="5" disabled>ขอรหัส OTP</button>
      <p class="small muted" style="text-align:center;margin:4px 0 0">ไม่ต้องจำรหัสผ่าน เราจะส่งรหัส 6 หลักทาง SMS</p>
    </div>
    <p style="text-align:center"><a href="/admin" data-el="6" class="small">สำหรับผู้ดูแลลานจอด / พนักงาน →</a></p>`;
  const phone = $app.querySelector("#phone"), accept = $app.querySelector("#accept"), send = $app.querySelector("#send");
  const valid = () => /^0[689]\d{8}$/.test(phone.value);
  const sync = () => { send.disabled = !(valid() && accept.checked); };
  phone.addEventListener("input", () => { phone.value = phone.value.replace(/\D/g, ""); fieldError(phone, phone.value.length >= 10 && !valid() ? "กรุณากรอกเบอร์โทรศัพท์ให้ถูกต้อง" : ""); sync(); });
  phone.addEventListener("blur", () => fieldError(phone, phone.value && !valid() ? "กรุณากรอกเบอร์โทรศัพท์ให้ถูกต้อง" : ""));
  accept.addEventListener("change", sync);
  send.addEventListener("click", async () => {
    send.disabled = true;
    try {
      const r = await api("/api/auth/otp", { method: "POST", body: { phone: phone.value, accept: accept.checked } });
      pendingPhone = phone.value; sessionStorage.setItem("parkq_phone", pendingPhone);
      sessionStorage.setItem("parkq_otp", JSON.stringify({ masked: r.masked, sentAt: Date.now(), dev: r.dev_code }));
      location.hash = "#/otp";
    } catch (e) { err(e); sync(); }
  });
}

function screenOtp(params) {
  if (params?.get("phone")) pendingPhone = params.get("phone");   // deep link used by demos / doc screenshots
  const info = JSON.parse(sessionStorage.getItem("parkq_otp") || "{}");
  if (!pendingPhone) return (location.hash = "#/login");
  $app.innerHTML = `${topbar("ยืนยันรหัส OTP", { href: "#/login", el: 1 })}
    <div class="page">
      <div class="card stack">
        <p data-el="2" style="margin:0">ส่งรหัส 6 หลักไปที่ <b>${esc(info.masked || pendingPhone)}</b> แล้ว</p>
        <div class="field" data-el="3"><span class="label">รหัส OTP <span class="req">*</span></span>
          <input id="otp" class="input otp-input num" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="••••••">
          <div class="err" id="otpErr"></div></div>
        <div class="row between">
          <span class="small muted" data-el="4">รหัสหมดอายุใน <b id="left" class="num">05:00</b></span>
          <button id="resend" class="btn ghost sm" data-el="5" disabled>ขอรหัสใหม่ (<span id="cool">60</span>)</button>
        </div>
        <button id="verify" class="btn block" data-el="6" disabled>ยืนยัน</button>
        ${info.dev ? `<div class="dev-box">โหมดทดสอบ (ยังไม่ต่อ SMS Gateway): รหัสคือ <b>${info.dev}</b></div>` : ""}
      </div>
    </div>`;
  const box = $app.querySelector("#otp"), verify = $app.querySelector("#verify"), errEl = $app.querySelector("#otpErr");
  const code = () => box.value;
  box.addEventListener("input", () => { box.value = box.value.replace(/\D/g, "").slice(0, 6); verify.disabled = box.value.length !== 6; errEl.textContent = ""; });
  box.addEventListener("keydown", (e) => { if (e.key === "Enter" && !verify.disabled) verify.click(); });
  box.focus();
  const tick = () => {
    const age = (Date.now() - (info.sentAt || Date.now())) / 1000;
    const left = Math.max(0, 300 - age), cool = Math.max(0, Math.ceil(60 - age));
    $app.querySelector("#left").textContent = `${String(Math.floor(left / 60)).padStart(2, "0")}:${String(Math.floor(left % 60)).padStart(2, "0")}`;
    $app.querySelector("#cool").textContent = cool;
    $app.querySelector("#resend").disabled = cool > 0;
    if (!left) errEl.textContent = "รหัส OTP หมดอายุ กรุณาขอใหม่";
  };
  tick(); every(1000, tick);
  $app.querySelector("#resend").addEventListener("click", async () => {
    try {
      const r = await api("/api/auth/otp", { method: "POST", body: { phone: pendingPhone, accept: true } });
      sessionStorage.setItem("parkq_otp", JSON.stringify({ masked: r.masked, sentAt: Date.now(), dev: r.dev_code }));
      toast("ส่งรหัสใหม่แล้ว"); route();
    } catch (e) { err(e); }
  });
  verify.addEventListener("click", async () => {
    verify.disabled = true;
    try {
      const r = await api("/api/auth/verify", { method: "POST", body: { phone: pendingPhone, code: code() } });
      setToken(r.token); me = r.user;
      sessionStorage.removeItem("parkq_otp");
      location.hash = r.is_new ? "#/register" : (sessionStorage.getItem("parkq_next") || "#/");
    } catch (e) {
      errEl.textContent = e.message; box.value = ""; box.focus(); verify.disabled = true;
      if (e.code === "OTP_LOCKED" || e.code === "OTP_EXPIRED") $app.querySelector("#resend").disabled = false;
    }
  });
}

function screenRegister() {
  $app.innerHTML = `${topbar("สมัครสมาชิก")}
    <div class="page"><div class="card stack">
      <p class="muted" style="margin:0">อีกนิดเดียว กรอกชื่อและรถคันแรกของคุณ</p>
      <label class="field" data-el="1"><span class="label">ชื่อ-นามสกุล <span class="req">*</span></span><input id="name" class="input" maxlength="100" placeholder="เช่น สมชาย ใจดี"><div class="err"></div></label>
      <label class="field" data-el="2"><span class="label">อีเมล (ใช้รับใบเสร็จ)</span><input id="email" class="input" type="email" placeholder="name@example.com"><div class="err"></div></label>
      <label class="field" data-el="3"><span class="label">ทะเบียนรถ <span class="req">*</span></span><input id="plate" class="input" placeholder="เช่น กข 1234"><div class="err"></div></label>
      <label class="field" data-el="4"><span class="label">จังหวัด <span class="req">*</span></span><select id="prov" class="input">${provinceOptions()}</select></label>
      <button id="go" class="btn block" data-el="5">เริ่มใช้งาน</button>
    </div></div>`;
  $app.querySelector("#go").addEventListener("click", async () => {
    const f = (id) => $app.querySelector("#" + id);
    try {
      await api("/api/auth/register", { method: "POST", body: { name: f("name").value, email: f("email").value, plate: f("plate").value, province: f("prov").value } });
      toast("สมัครสมาชิกเรียบร้อย"); location.hash = "#/";
    } catch (e) {
      const map = { NAME_REQUIRED: "name", INVALID_EMAIL: "email", INVALID_PLATE: "plate" };
      map[e.code] ? fieldError(f(map[e.code]), e.message) : err(e);
    }
  });
}

// ------------------------------------------------------------------ LOT_01 home / LOT_02 detail
let filter = "all";
function lotCard(l, first) {
  const pct = l.capacity ? (l.capacity - l.free) / l.capacity : 1;
  const color = { AVAILABLE: "var(--ok)", NEARLY_FULL: "#d97706", FULL: "var(--bad)", STALE: "var(--stale)" }[l.status];
  return `<article class="card lot-card" onclick="location.hash='#/lot/${l.id}'">
    <div><h3>${esc(l.name)}</h3><div class="meta">${l.rate} บาท/ชม. • ${l.open_time}–${l.close_time} น.${l.open_now ? "" : " • ปิดอยู่"}</div>
      <div style="margin-top:6px" ${first ? 'data-el="5"' : ""}>${lotBadge(l.status)}</div></div>
    <div class="free"><b class="num">${l.stale ? "–" : l.free}</b><span class="small muted">ว่าง / ${l.capacity}</span></div>
    <div class="meter"><i style="width:${Math.round(pct * 100)}%;background:${color}"></i></div>
    <div class="actions" onclick="event.stopPropagation()">
      <button class="btn sm" ${first ? 'data-el="6"' : ""} ${l.sellable && l.free > 0 ? "" : "disabled"} onclick="location.hash='#/book/${l.id}?mode=now'">จอดเลย</button>
      <button class="btn ghost sm" ${l.sellable ? "" : "disabled"} onclick="location.hash='#/book/${l.id}?mode=advance'">จองล่วงหน้า</button>
    </div></article>`;
}

async function screenHome() {
  $app.innerHTML = `${topbar("ค้นหาที่จอดรถ")}
    <div class="page">
      <div class="search" data-el="1">${ICON.search}<input id="q" class="input" placeholder="ค้นหาชื่อสถานที่หรือลานจอด"></div>
      <div class="map" id="map" data-el="2"></div>
      <div class="chips" data-el="3">${[["all", "ทั้งหมด"], ["free", "มีที่ว่าง"], ["advance", "จองล่วงหน้าได้"]]
        .map(([k, t]) => `<button class="chip ${filter === k ? "on" : ""}" data-f="${k}">${t}</button>`).join("")}</div>
      <div id="list" class="stack" data-el="4"></div>
    </div>`;
  showTabs("home", 7);
  const q = $app.querySelector("#q");
  const load = async () => {
    let lots;
    try { lots = await api("/api/lots?q=" + encodeURIComponent(q.value)); } catch (e) { return err(e); }
    if (filter === "free") lots = lots.filter((l) => l.sellable && l.free > 0);
    if (filter === "advance") lots = lots.filter((l) => l.sellable);
    const list = $app.querySelector("#list");
    if (!list) return;
    list.innerHTML = lots.length ? lots.map((l, i) => lotCard(l, i === 0)).join("") : `<div class="empty">ไม่พบลานจอดที่ค้นหา</div>`;
    drawMap(lots);
  };
  $app.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => { filter = c.dataset.f; $app.querySelectorAll(".chip").forEach((x) => x.classList.toggle("on", x === c)); load(); }));
  let t; q.addEventListener("input", () => { clearTimeout(t); t = setTimeout(load, 250); });
  await load();
  every(5000, load);
}

function drawMap(lots) {
  const map = $app.querySelector("#map");
  if (!map) return;
  const lat0 = 13.850, lat1 = 13.892, lng0 = 100.578, lng1 = 100.608;
  const pos = (lat, lng) => [((lng - lng0) / (lng1 - lng0)) * 100, (1 - (lat - lat0) / (lat1 - lat0)) * 100];
  const [mx, my] = pos(13.8560, 100.5838);
  map.innerHTML = `<span class="me" style="left:${mx}%;top:${my}%" title="ตำแหน่งของคุณ"></span>` +
    lots.map((l) => { const [x, y] = pos(l.lat, l.lng); return `<button class="pin ${l.status}" style="left:${x}%;top:${y}%" onclick="location.hash='#/lot/${l.id}'" title="${esc(l.name)}"><span class="dot num">${l.stale ? "?" : l.free}</span></button>`; }).join("") +
    `<div class="map-legend">${["AVAILABLE", "NEARLY_FULL", "FULL"].map(lotBadge).join("")}</div>`;
}

async function screenLot(id) {
  let l;
  try { l = await api("/api/lots/" + id); } catch (e) { return err(e); }
  $app.innerHTML = `${topbar("รายละเอียดลานจอด", { href: "#/" })}
    <div class="page">
      <div class="lot-photo" data-el="1"><span class="small" style="opacity:.85">${l.id}</span></div>
      <div class="card" data-el="2"><h2 style="font-size:19px">${esc(l.name)}</h2><p class="muted small" style="margin:4px 0 10px">${esc(l.address)}</p>
        <a class="btn soft sm" target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1&destination=${l.lat},${l.lng}">${ICON.nav} นำทาง</a></div>
      <div class="card row between" data-el="3"><div>${lotBadge(l.status)}<div class="small muted" style="margin-top:6px">อัปเดตอัตโนมัติทุก 5 วินาที</div></div>
        <div style="text-align:right"><b class="num" style="font-size:30px" id="free">${l.stale ? "–" : l.free}</b><span class="muted"> / ${l.capacity} ช่องว่าง</span></div></div>
      <div data-el="4"><div class="section-title" style="margin-bottom:10px">ช่องว่างแยกโซน</div>
        <div class="zones">${l.zones.map((z) => `<div class="zone"><span class="small muted">โซน ${z.zone}</span><b class="num">${z.total - z.occupied}</b><span class="small muted">/ ${z.total}</span></div>`).join("")}</div></div>
      <div class="card" data-el="5"><dl class="kv"><dt>อัตราค่าบริการ</dt><dd>${l.rate} บาท / ชั่วโมง</dd><dt>เวลาเปิด–ปิด</dt><dd>${l.open_time}–${l.close_time} น.</dd>
        <dt>จองล่วงหน้า</dt><dd>สูงสุด ${l.advance_ratio}% ของช่อง</dd></dl>
        <p class="small muted" style="margin:10px 0 0">จอดไม่เกิน 15 นาทีไม่คิดเงิน • ยกเลิกก่อนเวลาเริ่ม 60 นาที คืนเงินเต็มจำนวน</p></div>
      ${!l.sellable ? `<div class="demo-note">${l.stale ? "อุปกรณ์ของลานขาดการเชื่อมต่อ ปิดการขายชั่วคราว" : l.open_now ? "ลานจอดปิดการขายออนไลน์ชั่วคราว" : "ลานจอดปิดอยู่ในขณะนี้"}</div>` : ""}
      <div class="row">
        <button class="btn grow" data-el="6" ${l.sellable && l.free > 0 ? "" : "disabled"} onclick="location.hash='#/book/${l.id}?mode=now'">จอดเลย</button>
        <button class="btn ghost grow" data-el="7" ${l.online && !l.stale ? "" : "disabled"} onclick="location.hash='#/book/${l.id}?mode=advance'">จองล่วงหน้า</button>
      </div>
    </div>`;
  every(5000, async () => { try { const x = await api("/api/lots/" + id); const f = $app.querySelector("#free"); if (f) f.textContent = x.stale ? "–" : x.free; } catch {} });
}

// ------------------------------------------------------------------ BKG_01/02 booking, BKG_03 payment
async function screenBook(id, params) {
  let l, vehicles;
  try { [l, vehicles] = await Promise.all([api("/api/lots/" + id), api("/api/vehicles")]); } catch (e) { return err(e); }
  let mode = params.get("mode") === "advance" ? "advance" : "now", hours = 2;
  const next = new Date(Date.now() + 3600e3); next.setMinutes(0, 0, 0);
  const bkkDate = (d) => d.toLocaleDateString("en-CA", { timeZone: "Asia/Bangkok" });
  const bkkTime = (d) => d.toLocaleTimeString("en-GB", { timeZone: "Asia/Bangkok", hour: "2-digit", minute: "2-digit" });
  const maxDate = bkkDate(new Date(Date.now() + 7 * 864e5));
  $app.innerHTML = `${topbar("ซื้อสิทธิ์จอด", { href: "#/lot/" + id })}
    <div class="page">
      <div class="card row between" data-el="1"><div class="grow"><b>${esc(l.name)}</b><div class="small muted">${l.rate} บาท/ชม.</div></div>${lotBadge(l.status)}</div>
      <div class="seg" data-el="2"><button data-m="now">จอดเลย</button><button data-m="advance">จองล่วงหน้า</button></div>
      <div id="when" class="card stack">
        <label class="field" data-el="3"><span class="label">วันที่เริ่มจอด <span class="req">*</span></span><input id="date" type="date" class="input" min="${bkkDate(new Date())}" max="${maxDate}" value="${bkkDate(next)}"></label>
        <label class="field" data-el="4"><span class="label">เวลาเริ่มจอด <span class="req">*</span></span><input id="time" type="time" step="900" class="input" value="${bkkTime(next)}"><div class="err"></div></label>
      </div>
      <div id="nowInfo" class="card small muted">เริ่มนับเวลาทันทีที่ชำระเงินสำเร็จ • เข้าลานได้ภายใน 30 นาที</div>
      <div class="card stack">
        <div class="field" data-el="5"><span class="label">จำนวนชั่วโมง <span class="req">*</span></span>
          <div class="stepper"><button id="minus" aria-label="ลด">−</button><div class="val num"><span id="hrs">2</span> ชม.</div><button id="plus" aria-label="เพิ่ม">+</button></div>
          <div class="small muted" style="margin-top:6px" id="endAt"></div></div>
        <label class="field" data-el="6"><span class="label">รถที่จะเข้าจอด <span class="req">*</span></span>
          ${vehicles.length ? `<select id="veh" class="input">${vehicles.map((v) => `<option value="${v.id}">${esc(v.plate)} ${esc(v.province)}${v.is_primary ? " (คันหลัก)" : ""}</option>`).join("")}</select>`
            : `<a class="btn soft block" href="#/account?add=1">+ เพิ่มรถก่อนจอง</a>`}</label>
      </div>
      <div class="sticky-cta">
        <div class="card"><div class="total" data-el="7"><span class="muted">ราคารวม</span><b class="num" id="total"></b></div>
          <button id="next" class="btn block" style="margin-top:12px" data-el="8" ${vehicles.length ? "" : "disabled"}>ดำเนินการต่อ</button></div>
      </div>
    </div>`;
  const $ = (s) => $app.querySelector(s);
  const startTs = () => mode === "now" ? Date.now() / 1000 : new Date(`${$("#date").value}T${$("#time").value}:00+07:00`).getTime() / 1000;
  const sync = () => {
    $app.querySelectorAll(".seg button").forEach((b) => b.classList.toggle("on", b.dataset.m === mode));
    $("#when").classList.toggle("hidden", mode === "now");
    $("#nowInfo").classList.toggle("hidden", mode !== "now");
    $("#hrs").textContent = hours;
    $("#minus").disabled = hours <= 1; $("#plus").disabled = hours >= 24;
    $("#total").textContent = baht(hours * l.rate);
    const s = startTs();
    $("#endAt").textContent = isNaN(s) ? "" : `จอดได้ถึง ${fmtDateTime(s + hours * 3600)}`;
    fieldError($("#time"), mode === "advance" && s < Date.now() / 1000 - 60 ? "กรุณาเลือกเวลาในอนาคต" : "");
  };
  $app.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => { mode = b.dataset.m; sync(); }));
  $("#minus").addEventListener("click", () => { hours = Math.max(1, hours - 1); sync(); });
  $("#plus").addEventListener("click", () => { hours = Math.min(24, hours + 1); sync(); });
  $("#date").addEventListener("change", sync); $("#time").addEventListener("change", sync);
  sync();
  $("#next").addEventListener("click", async () => {
    $("#next").disabled = true;
    try {
      const t = await api("/api/bookings", { method: "POST", body: { lot_id: id, mode, hours, vehicle_id: Number($("#veh").value), start_at: mode === "advance" ? Math.round(startTs()) : null } });
      summaryModal(t);
    } catch (e) { err(e); } finally { $("#next") && ($("#next").disabled = false); }
  });
  if (params.get("summary")) { try { summaryModal(await api("/api/tickets/" + params.get("summary"))); } catch {} }
}

function summaryModal(t) {
  const m = modal(`<h2>สรุปรายการก่อนชำระเงิน</h2>
    <dl class="kv" data-el="1"><dt>ลานจอด</dt><dd>${esc(t.lot_name)}</dd><dt>ประเภท</dt><dd>${t.mode === "now" ? "จอดเลย" : "จองล่วงหน้า"}</dd>
      <dt>เวลา</dt><dd>${fmtRange(t.start_at, t.end_at)}</dd><dt>ทะเบียนรถ</dt><dd>${esc(t.plate)}</dd><dt>ระยะเวลา</dt><dd>${t.hours} ชั่วโมง</dd></dl>
    <div class="divider"></div>
    <div class="total" data-el="2"><span class="muted">ยอดชำระ</span><b class="num">${baht(t.amount)}</b></div>
    <p class="small muted" data-el="3">ยกเลิกก่อนเวลาเริ่มอย่างน้อย 60 นาที คืนเงินเต็มจำนวน • ถ้าไม่เข้าลานภายใน 30 นาทีหลังเวลาเริ่ม ระบบจะปล่อยช่องคืนและไม่คืนเงิน</p>
    <div class="demo-note" data-el="4">ล็อกช่องจอดไว้ให้ <b class="num" id="hold"></b> นาที</div>
    <div class="stack" style="margin-top:14px"><button class="btn block" id="pay" data-el="5">ชำระเงิน</button><button class="btn ghost block" id="edit" data-el="6">แก้ไข</button></div>`,
    { onClose: () => !paid && api(`/api/tickets/${t.id}/release`, { method: "POST" }).catch(() => {}) });
  let paid = false;
  const tick = () => { const s = Math.max(0, t.hold_until - Date.now() / 1000); const h = m.el.querySelector("#hold"); if (h) h.textContent = `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`; if (!s) { m.close(); toast("หมดเวลาทำรายการ", true); } };
  tick(); every(1000, tick);
  m.el.querySelector("#edit").addEventListener("click", m.close);
  m.el.querySelector("#pay").addEventListener("click", () => { paid = true; m.close(); location.hash = "#/pay/" + t.id; });
}

async function screenPay(tid, params) {
  let t;
  try { t = await api("/api/tickets/" + tid); } catch (e) { return err(e); }
  if (t.status !== "PENDING") return (location.hash = "#/ticket/" + tid);
  let method = "promptpay";
  $app.innerHTML = `${topbar("ชำระเงิน", { href: `#/book/${t.lot_id}` })}
    <div class="page">
      <div class="card"><div class="total" data-el="1"><span class="muted">ยอดชำระ</span><b class="num">${baht(t.amount)}</b></div><div class="small muted">${esc(t.lot_name)} • ${fmtRange(t.start_at, t.end_at)}</div></div>
      <div class="stack" data-el="2">
        <label class="radio-card on" data-m="promptpay"><input type="radio" name="m" checked><div class="grow"><b>QR พร้อมเพย์</b><div class="small muted">สแกนจ่ายด้วยแอปธนาคารใดก็ได้</div></div></label>
        <label class="radio-card" data-m="card"><input type="radio" name="m"><div class="grow"><b>บัตรเครดิต / เดบิต</b><div class="small muted">Visa, Mastercard, JCB</div></div></label>
      </div>
      <div id="cardBox" class="card stack hidden" data-el="3">
        <label class="field"><span class="label">หมายเลขบัตร <span class="req">*</span></span><input id="cardNo" class="input" inputmode="numeric" placeholder="xxxx xxxx xxxx xxxx"></label>
        <div class="row"><label class="field grow"><span class="label">หมดอายุ</span><input class="input" placeholder="MM/YY"></label><label class="field grow"><span class="label">CVV</span><input class="input" placeholder="•••"></label></div>
        <p class="small muted" style="margin:0">ข้อมูลบัตรส่งตรงถึงผู้ให้บริการชำระเงิน ParkQ ไม่เก็บเลขบัตร${config.dev ? " • ทดสอบด้วย 4242 4242 4242 4242" : ""}</p>
      </div>
      <button id="go" class="btn block" data-el="4">ชำระ ${baht(t.amount)}</button>
    </div>`;
  $app.querySelectorAll(".radio-card").forEach((c) => c.addEventListener("click", () => {
    method = c.dataset.m; $app.querySelectorAll(".radio-card").forEach((x) => { x.classList.toggle("on", x === c); x.querySelector("input").checked = x === c; });
    $app.querySelector("#cardBox").classList.toggle("hidden", method !== "card");
  }));
  if (params?.get("method") === "card") $app.querySelector('.radio-card[data-m="card"]').click();
  $app.querySelector("#go").addEventListener("click", async () => {
    try {
      const p = await api("/api/payments", { method: "POST", body: { ticket_id: tid, method, card_number: $app.querySelector("#cardNo").value } });
      if (p.status === "PAID") successModal(tid); else location.hash = `#/pay/${tid}/qr/${p.id}`;
    } catch (e) { err(e); }
  });
}

async function screenPayQr(tid, pid) {
  let p;
  try { p = await api("/api/payments/" + pid); } catch (e) { return err(e); }
  $app.innerHTML = `${topbar("สแกนเพื่อชำระเงิน", { href: "#/pay/" + tid })}
    <div class="page">
      <div class="card stack" style="text-align:center">
        <div class="qr-box" data-el="1"><img alt="QR พร้อมเพย์" src="${qrSrc(p.qr_payload)}"></div>
        <div data-el="2"><span class="muted">ยอดชำระ</span><div style="font-size:28px;font-weight:700" class="num">${baht(p.amount)}</div></div>
        ${p.demo ? `<div class="demo-note">QR ทดสอบ – ไม่ใช่การชำระเงินจริง</div>` : ""}
        <a class="btn ghost block" data-el="3" download="parkq-${pid}.svg" href="${qrSrc(p.qr_payload)}">บันทึก QR</a>
        <div data-el="4" id="st" class="row" style="justify-content:center"><span class="badge warn">รอชำระเงิน…</span><span class="small muted" id="exp"></span></div>
      </div>
      ${config.dev ? `<div class="dev-box">โหมดทดสอบ: ยังไม่ได้ต่อ Payment Gateway <button class="btn sm" id="sim" style="margin-top:8px;width:100%">จำลองว่าชำระเงินสำเร็จ</button></div>` : ""}
    </div>`;
  const check = async () => {
    try {
      const x = await api("/api/payments/" + pid);
      const left = Math.max(0, x.expires_at - Date.now() / 1000);
      const exp = $app.querySelector("#exp"); if (exp) exp.textContent = `QR หมดอายุใน ${Math.floor(left / 60)}:${String(Math.floor(left % 60)).padStart(2, "0")}`;
      if (x.status === "PAID") { clearTimers(); successModal(tid); }
      if (x.status === "EXPIRED") { clearTimers(); $app.querySelector("#st").innerHTML = `<span class="badge bad">QR หมดอายุ</span>`; }
    } catch {}
  };
  check(); every(2000, check);
  $app.querySelector("#sim")?.addEventListener("click", async () => { try { await api(`/api/payments/${pid}/simulate`, { method: "POST" }); check(); } catch (e) { err(e); } });
}

function successModal(tid) {
  const m = modal(`<div style="text-align:center"><div class="success-icon" data-el="1">${ICON.check}</div>
    <h2 data-el="2">ชำระเงินสำเร็จ</h2><p class="muted">ตั๋วของคุณพร้อมใช้งาน รหัส <b>${esc(tid)}</b><br>นำ QR ไปสแกนที่ตู้หน้าประตูลานจอดได้เลย</p>
    <button class="btn block" id="view" data-el="3">ดูตั๋ว QR</button></div>`);
  m.el.querySelector("#view").addEventListener("click", () => { m.close(); location.hash = "#/ticket/" + tid; });
}

// ------------------------------------------------------------------ TKT_01 tickets, BKG_04 cancel
let ticketTab = "active";
async function screenTickets() {
  $app.innerHTML = `${topbar("ตั๋วของฉัน")}<div class="page">
    <div class="seg" data-el="1"><button data-t="active">ใช้งานได้</button><button data-t="history">ประวัติ</button></div>
    <div id="list" class="stack" data-el="2"></div></div>`;
  showTabs("tickets", 3);
  let all;
  try { all = await api("/api/tickets"); } catch (e) { return err(e); }
  const draw = () => {
    $app.querySelectorAll(".seg button").forEach((b) => b.classList.toggle("on", b.dataset.t === ticketTab));
    const rows = all.filter((t) => (["WAITING", "PARKED", "PENDING"].includes(t.status)) === (ticketTab === "active"));
    const list = $app.querySelector("#list");
    list.innerHTML = rows.length ? rows.map((t) => `<article class="card ticket-item" onclick="location.hash='${t.status === "PENDING" ? "#/pay/" + t.id : "#/ticket/" + t.id}'">
        <h3>${esc(t.lot_name)}</h3>${ticketBadge(t.status)}
        <div class="small muted">${fmtRange(t.start_at, t.end_at)}</div><div class="small muted num">${esc(t.plate.split(" ").slice(0, 2).join(" "))}</div>
        <div class="small muted">${t.id}</div><div class="small num"><b>${baht(t.amount + t.overstay_fee)}</b></div></article>`).join("")
      : `<div class="empty">ยังไม่มีตั๋ว<br><a class="btn soft sm" style="margin-top:12px" href="#/">ค้นหาลานจอดเลย</a></div>`;
    if (rows.length) list.removeAttribute("data-el-empty");
  };
  $app.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => { ticketTab = b.dataset.t; draw(); }));
  draw();
}

async function screenTicket(id, params) {
  let t;
  try { t = await api("/api/tickets/" + id); } catch (e) { return err(e); }
  const live = ["WAITING", "PARKED"].includes(t.status);
  $app.innerHTML = `${topbar("ตั๋ว QR", { href: "#/tickets" })}
    <div class="page">
      <div class="ticket">
        <div class="head"><div class="code" data-el="2">รหัสตั๋ว ${esc(t.id)}</div><div style="font-size:18px;font-weight:700">${esc(t.lot_name)}</div></div>
        <div class="body" style="text-align:center">
          ${live ? `<div class="qr-box" data-el="1"><img alt="QR ตั๋ว" src="${qrSrc(t.token)}"></div>
            <p class="small muted" style="margin:10px 0 0">${t.status === "WAITING" ? "สแกนที่ตู้ประตูทางเข้า" : "สแกน QR เดิมที่ตู้ประตูทางออก"}</p>`
            : `<div class="empty" data-el="1">${t.status === "DONE" ? "ใช้งานเสร็จสิ้นแล้ว" : "ตั๋วนี้ใช้งานไม่ได้แล้ว"}</div>`}
        </div>
        <div class="tear"></div>
        <div class="body stack">
          <div class="row between"><span class="muted">สถานะ</span><span data-el="4" id="status">${ticketBadge(t.status)}</span></div>
          <dl class="kv" data-el="3"><dt>ทะเบียนรถ</dt><dd>${esc(t.plate)}</dd><dt>เวลา</dt><dd>${fmtRange(t.start_at, t.end_at)}</dd>
            <dt>ชำระแล้ว</dt><dd>${baht(t.amount + t.overstay_fee)}</dd>${t.refund ? `<dt>เงินคืน</dt><dd>${baht(t.refund)}</dd>` : ""}</dl>
          <div class="row between" data-el="5"><span class="muted">${t.status === "WAITING" ? "เข้าลานได้ถึง" : "เวลาคงเหลือ"}</span><span class="countdown num" id="left">–</span></div>
        </div>
      </div>
      <a class="btn soft block" data-el="6" target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1&destination=${t.lat},${t.lng}">${ICON.nav} นำทางไปลานจอด</a>
      ${t.status === "WAITING" ? `<button class="btn danger ghost block" id="cancel" data-el="7">ยกเลิกการจอง</button>` : ""}
      ${config.dev && live ? `<div class="dev-box">โหมดทดสอบ (ไม่มีเครื่องสแกน): <a target="_blank" href="/gate?lot=${t.lot_id}&dir=${t.status === "WAITING" ? "in" : "out"}&token=${encodeURIComponent(t.token)}">เปิดหน้าตู้${t.status === "WAITING" ? "ทางเข้า" : "ทางออก"}แล้วสแกนตั๋วนี้ →</a></div>` : ""}
    </div>`;
  const tick = () => {
    const el = $app.querySelector("#left"); if (!el) return;
    const now = Date.now() / 1000;
    if (t.status === "WAITING") el.textContent = fmtTime(t.start_at + 1800) + " น.";
    else if (t.status === "PARKED") { const s = t.end_at - now; el.textContent = s >= 0 ? fmtDuration(s) : "เกิน " + fmtDuration(-s); el.style.color = s < 0 ? "var(--bad)" : ""; }
    else el.textContent = "–";
  };
  tick(); every(1000, tick);
  if (live) every(4000, async () => { try { const x = await api("/api/tickets/" + id); if (x.status !== t.status) route(); } catch {} });
  $app.querySelector("#cancel")?.addEventListener("click", () => cancelModal(t));
  if (params.get("cancel") === "1" && t.status === "WAITING") cancelModal(t);
}

function cancelModal(t) {
  const m = modal(`<h2>ยกเลิกการจอง</h2>
    <p data-el="1" style="margin-top:0">ต้องการยกเลิกการจอง <b>${esc(t.lot_name)}</b><br><span class="muted small">${fmtRange(t.start_at, t.end_at)}</span></p>
    <div class="card flat total" data-el="2"><span class="muted">ยอดเงินคืน</span><b class="num">${baht(t.refund_if_cancel)}</b></div>
    ${t.refund_if_cancel ? "" : `<p class="small" style="color:var(--bad)">ยกเลิกน้อยกว่า 60 นาทีก่อนเวลาเริ่ม จะไม่ได้รับเงินคืน</p>`}
    <label class="field" data-el="3" style="margin-top:12px"><span class="label">เหตุผล (ไม่บังคับ)</span><select id="why" class="input"><option value="">– เลือก –</option><option>เปลี่ยนแผน</option><option>จองผิด</option><option>อื่น ๆ</option></select></label>
    <div class="stack" style="margin-top:16px"><button class="btn danger block" id="yes" data-el="4">ยืนยันยกเลิก</button><button class="btn ghost block" id="no" data-el="5">ไม่ยกเลิก</button></div>`);
  m.el.querySelector("#no").addEventListener("click", m.close);
  m.el.querySelector("#yes").addEventListener("click", async () => {
    try { const r = await api(`/api/tickets/${t.id}/cancel`, { method: "POST", body: { reason: m.el.querySelector("#why").value } });
      m.close(); toast(r.refund ? `ยกเลิกแล้ว เงินคืน ${baht(r.refund)} ภายใน 7 วันทำการ` : "ยกเลิกแล้ว"); route(); } catch (e) { err(e); }
  });
}

// ------------------------------------------------------------------ ACC_02 account & vehicles
async function screenAccount(params) {
  let vehicles;
  try { [me, vehicles] = await Promise.all([api("/api/me"), api("/api/vehicles")]); } catch (e) { return err(e); }
  $app.innerHTML = `${topbar("บัญชีและรถของฉัน")}<div class="page">
    <div class="card row" data-el="1"><div class="success-icon" style="width:52px;height:52px;margin:0;background:var(--brand-soft);color:var(--brand)">${ICON.user}</div>
      <div class="grow"><b>${esc(me.name || "-")}</b><div class="small muted num">${esc(me.phone)}</div></div></div>
    <div class="section-title">รถของฉัน</div>
    <div class="stack" data-el="2">${vehicles.map((v, i) => `<div class="card vehicle">
      <div class="plate"><b>${esc(v.plate)}</b><span>${esc(v.province)}</span></div>
      <div><b>${v.type === "car" ? "รถยนต์" : "รถจักรยานยนต์"}</b>${v.is_primary ? ` <span class="badge blue">คันหลัก</span>` : ""}</div>
      <div class="row" style="gap:4px"><button class="btn ghost sm" data-edit="${v.id}" ${i === 0 ? 'data-el="3"' : ""}>แก้ไข</button><button class="btn danger ghost sm" data-del="${v.id}" ${i === 0 ? 'data-el="4"' : ""}>ลบ</button></div></div>`).join("")
      || `<div class="empty">ยังไม่มีรถ เพิ่มรถอย่างน้อย 1 คันก่อนจอง</div>`}</div>
    <button class="btn soft block" id="add" data-el="5">+ เพิ่มรถ</button>
    <button class="btn ghost block" id="logout" data-el="6">ออกจากระบบ</button></div>`;
  showTabs("account", 7);
  $app.querySelector("#add").addEventListener("click", () => vehicleModal());
  $app.querySelectorAll("[data-edit]").forEach((b) => b.addEventListener("click", () => vehicleModal(vehicles.find((v) => v.id == b.dataset.edit))));
  $app.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", async () => {
    if (!confirm("ต้องการลบรถคันนี้หรือไม่")) return;
    try { await api("/api/vehicles/" + b.dataset.del, { method: "DELETE" }); toast("ลบรถแล้ว"); route(); } catch (e) { err(e); }
  }));
  $app.querySelector("#logout").addEventListener("click", async () => { await api("/api/auth/logout", { method: "POST" }).catch(() => {}); setToken(null); location.hash = "#/login"; });
  if (params.get("add") === "1") vehicleModal(vehicles[0] && params.get("edit") ? vehicles[0] : undefined);
}

function vehicleModal(v) {
  const m = modal(`<h2>${v ? "แก้ไขรถ" : "เพิ่มรถ"}</h2><div class="stack">
    <label class="field" data-el="1"><span class="label">ทะเบียนรถ <span class="req">*</span></span><input id="plate" class="input" placeholder="เช่น กข 1234" value="${esc(v?.plate || "")}"><div class="err"></div></label>
    <label class="field" data-el="2"><span class="label">จังหวัด <span class="req">*</span></span><select id="prov" class="input">${provinceOptions(v?.province)}</select></label>
    <div class="field" data-el="3"><span class="label">ประเภทรถ <span class="req">*</span></span><div class="seg"><button data-t="car">รถยนต์</button><button data-t="motorcycle">รถจักรยานยนต์</button></div></div>
    <label class="check" data-el="4"><input type="checkbox" id="primary" ${v?.is_primary ? "checked" : ""}><span>ตั้งเป็นรถคันหลัก (เลือกให้อัตโนมัติตอนจอง)</span></label>
    <button class="btn block" id="save" data-el="5">บันทึก</button><button class="btn ghost block" id="x" data-el="6">ยกเลิก</button></div>`);
  let type = v?.type || "car";
  const segs = m.el.querySelectorAll(".seg button");
  const sync = () => segs.forEach((b) => b.classList.toggle("on", b.dataset.t === type));
  segs.forEach((b) => b.addEventListener("click", () => { type = b.dataset.t; sync(); })); sync();
  m.el.querySelector("#x").addEventListener("click", m.close);
  m.el.querySelector("#save").addEventListener("click", async () => {
    const plate = m.el.querySelector("#plate");
    try {
      await api(v ? "/api/vehicles/" + v.id : "/api/vehicles", { method: v ? "PUT" : "POST", body: { plate: plate.value, province: m.el.querySelector("#prov").value, type, is_primary: m.el.querySelector("#primary").checked } });
      m.close(); toast("บันทึกข้อมูลรถแล้ว"); route();
    } catch (e) { e.code === "INVALID_PLATE" || e.code === "DUPLICATE_PLATE" ? fieldError(plate, e.message) : err(e); }
  });
}

// ------------------------------------------------------------------ router
const PUBLIC = ["login", "otp"];
async function route() {
  clearTimers();
  document.querySelectorAll(".modal-back").forEach((m) => m.remove());
  $tab.classList.add("hidden");
  const [path, query] = (location.hash.slice(1) || "/").split("?");
  const params = new URLSearchParams(query || "");
  const parts = path.split("/").filter(Boolean);
  const name = parts[0] || "home";
  if (!getToken() && !PUBLIC.includes(name)) { sessionStorage.setItem("parkq_next", location.hash); return (location.hash = "#/login"); }
  window.scrollTo(0, 0);
  const screens = {
    login: screenLogin, otp: () => screenOtp(params), register: screenRegister, home: screenHome,
    lot: () => screenLot(parts[1]), book: () => screenBook(parts[1], params),
    pay: () => (parts[2] === "qr" ? screenPayQr(parts[1], parts[3]) : screenPay(parts[1], params)),
    paid: async () => { await screenTickets(); successModal(parts[1]); },
    tickets: screenTickets, ticket: () => screenTicket(parts[1], params), account: () => screenAccount(params),
  };
  try { await (screens[name] || screenHome)(); }
  catch (e) { if (e.status === 401) { setToken(null); location.hash = "#/login"; } else err(e); }
}

addEventListener("hashchange", route);
(async () => {
  try { config = await api("/api/config"); } catch {}
  try { await devLogin(); } catch {}
  startAnnotations();
  route();
})();
