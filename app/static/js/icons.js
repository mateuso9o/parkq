// ParkQ icon set: authored for this product, 24px grid, 2px stroke, round caps. Decorative by default (aria-hidden).
const P = {
  back: '<path d="M15 5l-7 7 7 7"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/>',
  board: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 12h18M9 4v16"/>',
  ticket: '<path d="M3 8a2 2 0 002-2h14a2 2 0 002 2v2a2 2 0 000 4v2a2 2 0 00-2 2H5a2 2 0 00-2-2v-2a2 2 0 000-4z"/><path d="M15 6v2M15 11v2M15 16v2"/>',
  user: '<circle cx="12" cy="8" r="3.8"/><path d="M4.5 20c1.4-3.6 4.2-5.4 7.5-5.4s6.1 1.8 7.5 5.4"/>',
  check: '<path d="M4.5 12.5l5 5 10-11"/>',
  nav: '<path d="M4 11l16-7-7 16-2.2-6.8z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4L7 17M17 7l1.4-1.4"/>',
    moon: '<path d="M20 14.5A8 8 0 019.5 4a8 8 0 1010.5 10.5z"/>',
  camera: '<path d="M4 8h3l1.5-2h7L17 8h3a1 1 0 011 1v9a1 1 0 01-1 1H4a1 1 0 01-1-1V9a1 1 0 011-1z"/><circle cx="12" cy="13" r="3.5"/>',
  bell: '<path d="M6 17V11a6 6 0 1112 0v6l1.5 2h-15z"/><path d="M10 21h4"/>',
  car: '<path d="M5 16V11l1.8-4.5A2 2 0 018.7 5h6.6a2 2 0 011.9 1.5L19 11v5"/><path d="M3.5 16h17M7 16v2.5M17 16v2.5"/><circle cx="8" cy="12.5" r=".6"/><circle cx="16" cy="12.5" r=".6"/>',
  gate: '<path d="M4 20V9M20 20V9M4 12h16"/><path d="M8 12v5M12 12v5M16 12v5" stroke-dasharray="2 2"/>',
  lock: '<rect x="5" y="11" width="14" height="9" rx="1.5"/><path d="M8 11V8a4 4 0 018 0v3"/>',
  alert: '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17v.2"/>',
  out: '<path d="M10 4H5v16h5M14 8l4 4-4 4M18 12H9"/>',
};

export const icon = (name, size = 22) =>
  `<svg class="ico" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${P[name]}</svg>`;
