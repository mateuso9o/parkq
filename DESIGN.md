# ParkQ Design System — Rail Concourse Split-Flap

Surfaces: driver app (mobile), gate kiosk, admin/staff back office. Mode: Operate.

## World
A station concourse departure board. Dark "flap black" ground, steel rails and frames, letter-white text. Amber is the single action/attention colour; red means full or failed. Status is always a word plus a colour, never colour alone.

## Tokens (app/static/css/app.css)
- `--flap #0b0b0b` ground, `--panel` / `--panel-2` raised surfaces, `--steel*` frames and dividers
- `--letter #f2f2f2` text, `--amber #ffb000` primary action and attention, `--red #ff5a5f` full / failed
- Type: Bai Jamjuree (board labels, numerals) + Noto Sans Thai (body), self-hosted woff2 in `app/static/fonts/`
- Radius 4–10px, no side stripes, no glyph icons: all icons from `js/icons.js` (24px grid, 2px stroke)

## Light / dark
`<html data-theme="dark|light">`, set before paint by an inline script (saved `parkq_theme`, else the device setting). `initTheme()` in `js/common.js` adds the round sun/moon switch on every surface. Light tokens: ground `#f3f4f7`, white panels, ink `#14171c`, amber `#b25a00` (white text on it), red `#c4262e`. Flap boards stay dark in both themes. Shapes are rounder (14px cards, pill buttons and badges) with soft shadows and a blurred top/tab bar.

## Signature
Per-character flap cells (`js/flap.js`): `flapHtml` renders, `setFlap` flips only changed characters left to right (40ms stagger). Used for free-slot counts, times, KPI numbers and the login wordmark. Honors `prefers-reduced-motion`; the real text lives in `aria-label`.

## Components
- Lot row: name and meta left, flap free count right, amber primary action
- Ticket: boarding-line card with QR, flap start/end times, plate chip
- Kiosk: oversized flap count, white pass overlay with plate, red fail overlay, amber pay overlay
- Admin: steel rail nav, board-style KPI rows, flap-style slot grid, amber toggles

## Rules
No eyebrow labels above headings, no emoji or glyph icons, no hard offset shadows, touch targets at least 44px, body text at least 14px on dark with 4.5:1 contrast.
