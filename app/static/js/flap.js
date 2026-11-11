// Split-flap cells: the signature of ParkQ's board look.
// A value is shown as one cell per character (a Thai base letter and its marks share a cell). When the value changes,
// only the cells whose character changed flip, left to right. The container carries the real text in aria-label.
const seg = typeof Intl !== "undefined" && Intl.Segmenter ? new Intl.Segmenter("th", { granularity: "grapheme" }) : null;
const chars = (s) => (seg ? [...seg.segment(String(s))].map((x) => x.segment) : [...String(s)]);
const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const BLANK = " ";

function pad(text, cells, align) {
  const cs = chars(text);
  if (!cells || cs.length >= cells) return cs;
  const fill = Array(cells - cs.length).fill(BLANK);
  return align === "left" ? [...cs, ...fill] : [...fill, ...cs];
}

const cellHtml = (c) => `<i class="cell" data-c="${esc(c)}" aria-hidden="true"><b class="h up">${esc(c)}</b><b class="h dn">${esc(c)}</b></i>`;

// HTML string for a flap display. tone: "" | "warn" | "bad" | "dim". size: font-size in px.
export function flapHtml(text, { cells = 0, tone = "", size = 0, align = "right", label } = {}) {
  const cs = pad(text, cells, align);
  return `<span class="flap ${tone}" role="img" aria-label="${esc(label ?? text)}" data-cells="${cells}" data-align="${align}"${size ? ` style="--fs:${size}px"` : ""}>${cs.map(cellHtml).join("")}</span>`;
}

function flipCell(cell, to, delay) {
  const from = cell.dataset.c;
  if (from === to) return;
  if (reduced()) { setCell(cell, to); return; }
  cell.classList.remove("flip");
  cell.querySelectorAll(".ft, .fb").forEach((n) => n.remove());
  const top = cell.querySelector(".up"), bot = cell.querySelector(".dn");
  top.textContent = to;                                           // upper half underneath already shows the new char
  const ft = Object.assign(document.createElement("b"), { className: "h ft", textContent: from });   // old upper half folds down
  const fb = Object.assign(document.createElement("b"), { className: "h fb", textContent: to });     // new lower half falls into place
  ft.style.animationDelay = delay + "ms";
  fb.style.animationDelay = delay + 170 + "ms";                  // the lower half lands after the upper half has folded
  cell.append(ft, fb);
  cell.classList.add("flip");
  cell.dataset.c = to;
  setTimeout(() => { bot.textContent = to; ft.remove(); fb.remove(); cell.classList.remove("flip"); }, delay + 360);
}

function setCell(cell, c) {
  cell.dataset.c = c;
  cell.querySelectorAll(".h").forEach((n) => (n.textContent = c));
  cell.querySelectorAll(".ft, .fb").forEach((n) => n.remove());
}

// Update an existing flap element in place (cascade flip). Re-renders cells when the cell count must change.
export function setFlap(el, text, { tone, label } = {}) {
  if (!el) return;
  const cells = Number(el.dataset.cells) || 0, align = el.dataset.align || "right";
  const next = pad(text, cells, align);
  let nodes = [...el.querySelectorAll(".cell")];
  if (nodes.length !== next.length) {
    el.innerHTML = next.map(cellHtml).join("");
    nodes = [...el.querySelectorAll(".cell")];
  } else {
    nodes.forEach((n, i) => flipCell(n, next[i], i * 40));
  }
  el.setAttribute("aria-label", label ?? text);
  if (tone !== undefined) el.className = "flap " + tone;
}

// Cascade a word in from blank (used once on the login board).
export function flapIn(el, text, stepMs = 110) {
  const cs = chars(text);
  el.innerHTML = cs.map(() => cellHtml(BLANK)).join("");
  el.setAttribute("aria-label", text);
  [...el.querySelectorAll(".cell")].forEach((n, i) => setTimeout(() => flipCell(n, cs[i], 0), i * stepMs + 250));
}
