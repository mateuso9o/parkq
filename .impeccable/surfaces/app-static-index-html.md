---
version: 1
slug: "app-static-index-html"
primary_target: "app/static/index.html"
related_targets: ["app/static/gate.html","app/static/admin.html"]
---

# Surface brief: ParkQ web app (driver, gate kiosk, admin and staff)

Scope and visitor mode: Operate. Four working surfaces of one product: driver app (mobile web, hash router), gate kiosk (landscape, no keyboard), admin back office, gate attendant page. Replacement of the earlier blue SaaS look; product truth, copy, routes and `data-el` markers are preserved.

Audience, job, action: Thai drivers booking and entering/leaving with a ticket QR (at the barrier in sun, or planning ahead), attendants opening barriers, owners reading live occupancy and revenue. Constraints: Thai text, small phones first, 44px+ touch targets, no color-only status, QR must stay large and high contrast, camera needs https or localhost, payments are simulated.

Chosen direction and memorable moment: Rail Concourse Split-Flap (catalog challenger signals-instruments-split-flap-concourse). The free-space count and ticket times are split-flap cells that flip when the value changes; the login screen spells PARKQ onto the board.

Unresolved decisions: none blocking; dark world is committed, outdoor glare is mitigated by maximum contrast and large type rather than a light theme.

## Direction contract

THESIS: A parking lot is a row on a departures board. The number a driver needs, free spaces, is a flap cell that visibly changes, and the ticket is read like a boarding line: time, plate, state. It refuses the category default of white cards with a blue button and a pin map as hero.

OWN-WORLD: Flap black ground (#0B0B0B), steel frame and panels (#15171A, #2A2D31, hairline #2E3237), letter white (#F2F2F2) for normal state, amber (#FFB000) for attention and the one primary action, cancel red (#FF5A5F on black) for full or failed. Condensed-feeling Thai/Latin face Bai Jamjuree for board labels and numerals, Noto Sans Thai for reading text, Latin labels uppercase and tracked, Thai never tracked. Square-ish 6px plates with brushed-steel frame lines, flap cells with a centre seam. Status is word plus color, never color alone.

STORY: A driver opens the app and sees live rows with flap counts; taps จอดเลย, pays, and gets a ticket board with big QR and flap times. At the barrier the kiosk shows the same board language and answers a scan with a full-screen result: white passes, amber needs payment or action, red fails. The owner sees the same board as a dashboard.

FIRST VIEWPORT: Driver home on a 390px phone: steel header with the ParkQ mark; active ticket as a lit board card with QR and flap start/end times when one exists; below, lot rows (name, address, rate) with a three-cell flap free count right-aligned and a status word; bottom tab bar with three tabs and the active one amber. Primary action sits on the lot row (จอดเลย) in amber.

FORM: split-flap concourse board (position 4 of the grounded list in the roll; challenger chosen by the user), seed: 4d6fd51e11672cdb. Signature move: per-character flap cells with a cascade flip on change, reduced-motion safe, semantic text in aria-label.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
