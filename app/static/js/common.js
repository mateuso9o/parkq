// Shared helpers for every ParkQ page: API calls, formatting, toasts, modals, auth and doc annotations.
export const qs = new URLSearchParams(location.search);
const TOKEN_KEY = "parkq_token";

export function getToken() { try { return localStorage.getItem(TOKEN_KEY); } catch { return null; } }
export function setToken(t) { try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch {} }

export async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = "Bearer " + token;
  let res;
  try {
    res = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  } catch {
    throw { code: "NETWORK", message: "ไม่สามารถเชื่อมต่อเครือข่ายได้" };
  }
  const data = res.headers.get("content-type")?.includes("json") ? await res.json() : await res.text();
  if (!res.ok) throw { status: res.status, ...(typeof data === "object" ? data : { message: data }) };
  return data;
}

// Dev-only deep links used by the documentation screenshots: ?as=driver|admin|attendant logs in automatically.
export async function devLogin() {
  const role = qs.get("as");
  if (!role) return;
  const r = await api("/api/dev/login?role=" + role);
  setToken(r.token);
}

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const baht = (n) => Number(n).toLocaleString("th-TH") + " บาท";
const TZ = { timeZone: "Asia/Bangkok" };
export const fmtTime = (ts) => new Date(ts * 1000).toLocaleTimeString("th-TH", { ...TZ, hour: "2-digit", minute: "2-digit" });
export const fmtDate = (ts) => new Date(ts * 1000).toLocaleDateString("th-TH", { ...TZ, day: "numeric", month: "short" });
export const fmtDateTime = (ts) => `${fmtDate(ts)} ${fmtTime(ts)} น.`;
export const fmtRange = (a, b) => fmtDate(a) === fmtDate(b) ? `${fmtDate(a)} • ${fmtTime(a)}–${fmtTime(b)} น.` : `${fmtDateTime(a)} – ${fmtDateTime(b)}`;
export const fmtDuration = (sec) => { sec = Math.max(0, sec); const h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60); return h ? `${h} ชม. ${m} นาที` : `${m} นาที`; };

export const LOT_STATUS = { AVAILABLE: "ว่าง", NEARLY_FULL: "ใกล้เต็ม", FULL: "เต็ม", STALE: "ข้อมูลไม่เป็นปัจจุบัน" };
export const TICKET_STATUS = {
  PENDING: ["รอชำระเงิน", "warn"], WAITING: ["รอเข้า", "blue"], PARKED: ["จอดอยู่", "ok"], DONE: ["เสร็จสิ้น", "gray"],
  CANCELLED: ["ยกเลิก", "gray"], NO_SHOW: ["ไม่มาตามนัด", "bad"], EXPIRED: ["หมดเวลาชำระ", "gray"],
};
export const lotBadge = (s) => `<span class="badge ${s}">${LOT_STATUS[s]}</span>`;
export const ticketBadge = (s) => `<span class="badge ${TICKET_STATUS[s][1]}">${TICKET_STATUS[s][0]}</span>`;
export const qrSrc = (data) => "/api/qr.svg?data=" + encodeURIComponent(data);

let toastTimer;
export function toast(msg, bad = false) {
  let el = document.getElementById("toast");
  if (!el) { el = document.createElement("div"); el.id = "toast"; document.body.append(el); }
  el.textContent = msg; el.className = "show" + (bad ? " bad" : "");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => (el.className = ""), 2800);
}

export function modal(html, { onClose } = {}) {
  const back = document.createElement("div");
  back.className = "modal-back";
  back.innerHTML = `<div class="modal" role="dialog" aria-modal="true">${html}</div>`;
  const close = () => { back.remove(); onClose?.(); };
  back.addEventListener("click", (e) => { if (e.target === back) close(); });
  document.body.append(back);
  return { el: back.querySelector(".modal"), close };
}

export function fieldError(input, msg) {
  input.classList.toggle("invalid", !!msg);
  let err = input.closest(".field")?.querySelector(".err");
  if (err) err.textContent = msg || "";
}

export const PROVINCES = ["กรุงเทพมหานคร","กระบี่","กาญจนบุรี","กาฬสินธุ์","กำแพงเพชร","ขอนแก่น","จันทบุรี","ฉะเชิงเทรา","ชลบุรี","ชัยนาท","ชัยภูมิ","ชุมพร","เชียงราย","เชียงใหม่","ตรัง","ตราด","ตาก","นครนายก","นครปฐม","นครพนม","นครราชสีมา","นครศรีธรรมราช","นครสวรรค์","นนทบุรี","นราธิวาส","น่าน","บึงกาฬ","บุรีรัมย์","ปทุมธานี","ประจวบคีรีขันธ์","ปราจีนบุรี","ปัตตานี","พระนครศรีอยุธยา","พะเยา","พังงา","พัทลุง","พิจิตร","พิษณุโลก","เพชรบุรี","เพชรบูรณ์","แพร่","ภูเก็ต","มหาสารคาม","มุกดาหาร","แม่ฮ่องสอน","ยโสธร","ยะลา","ร้อยเอ็ด","ระนอง","ระยอง","ราชบุรี","ลพบุรี","ลำปาง","ลำพูน","เลย","ศรีสะเกษ","สกลนคร","สงขลา","สตูล","สมุทรปราการ","สมุทรสงคราม","สมุทรสาคร","สระแก้ว","สระบุรี","สิงห์บุรี","สุโขทัย","สุพรรณบุรี","สุราษฎร์ธานี","สุรินทร์","หนองคาย","หนองบัวลำภู","อ่างทอง","อำนาจเจริญ","อุดรธานี","อุตรดิตถ์","อุทัยธานี","อุบลราชธานี"];
export const provinceOptions = (sel = "กรุงเทพมหานคร") => PROVINCES.map((p) => `<option ${p === sel ? "selected" : ""}>${p}</option>`).join("");

// ---- Documentation mode: ?annotate=1 draws numbered markers on every [data-el] element ----
export function startAnnotations() {
  if (qs.get("annotate") !== "1") return;
  document.documentElement.classList.add("doc-mode");   // hides developer-only helpers in screenshots
  const draw = () => {
    document.querySelectorAll(".anno").forEach((a) => a.remove());
    document.querySelectorAll("[data-el]").forEach((el) => {
      const r = el.getBoundingClientRect();
      if (!r.width && !r.height) return;
      // skip elements covered by a modal or overlay
      const top = document.elementFromPoint(Math.min(innerWidth - 1, r.left + Math.min(r.width / 2, 20)), Math.min(innerHeight - 1, Math.max(0, r.top + Math.min(r.height / 2, 12))));
      if (top && !el.contains(top) && !top.contains(el) && r.top < innerHeight) return;
      const a = document.createElement("div");
      a.className = "anno";
      a.textContent = el.dataset.el;
      a.style.left = Math.max(2, r.left + scrollX - 9) + "px";
      a.style.top = Math.max(2, r.top + scrollY - 9) + "px";
      document.body.append(a);
    });
  };
  let t;
  new MutationObserver((m) => { if (m.some((x) => ![...x.addedNodes].every((n) => n.classList?.contains("anno")))) { clearTimeout(t); t = setTimeout(draw, 60); } })
    .observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
  addEventListener("resize", draw);
  setTimeout(draw, 300);
}
