# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
- **Driver** (primary): a car owner in Bangkok, on a phone (mobile web, thai). Two equally important situations: standing at the lot gate (often outdoors, in sun, one hand) needing a big, instantly scannable ticket QR; and planning ahead (home or work) to check live availability, choose a time, book and pay.
- **Gate attendant**: staff at the lot who searches tickets, opens the barrier manually and answers "call staff" alerts.
- **Lot owner / admin**: watches live occupancy, sets price and opening hours, reads the revenue report.
- **Gate kiosk** (a screen at each barrier, no keyboard): shows free spaces and scan result to a driver standing in front of it.
- Evaluators for the current milestone: the course lecturer and classmates trying every flow during a presentation.

## Product Purpose
ParkQ lets drivers see how many spaces a lot has right now, buy the right to park immediately or reserve ahead, and enter and leave by scanning a signed ticket QR at the barrier. Success: a driver gets from opening the app to a valid ticket in a few taps, the barrier opens on scan, and the owner sees the same live numbers. It is a software-engineering course project that must behave like a real service end to end (e-mail OTP sign-in, persistent data, camera QR scan, booking), with payment simulated.

## Positioning
Availability and entry are connected to hardware: a model lot (LOT02) is driven by an ESP32 gate controller with servo barriers, four slot sensors and two QR readers, so the ticket the driver buys is what actually lifts the barrier and the free-space count comes from sensors.

## Operating Context
- All user-facing text is Thai; currency THB; times are Bangkok time (UTC+7).
- Sign-in is by e-mail + 6-digit OTP (no password). Accounts are keyed by e-mail.
- Ticket flow: book (now, or advance up to 7 days) -> pay (PromptPay QR, simulated) -> signed ticket QR -> scan at entry -> scan at exit (overstay fee payable by QR) -> refund rules on cancellation.
- Roles: driver, attendant, admin. Back office at /admin, staff at /staff, gate kiosk at /gate?lot=..&dir=in|out.
- Kiosk input: USB QR reader (types the code + Enter) or the device camera.
- Four lots are seeded: a university lot, the IoT model lot (4 spaces), a market car park, a rail-station lot.

## Capabilities and Constraints
- Static front end served by FastAPI (vanilla JS single-page modules, no build step); hosting on Render, data on Neon PostgreSQL (SQLite locally).
- Must work on small phone screens first and on a laptop for admin; the kiosk is landscape.
- Camera scanning needs https or localhost.
- Payment is simulated; no real money moves.
- Undecided: final lot branding images, real map provider.

## Brand Commitments
None binding. The user explicitly allowed a full redesign, including the name's visual identity (the name ParkQ itself is the product's name).

## Evidence on Hand
Seeded lots, a 14-day synthetic revenue history for the report, and the existing screens (driver app, admin, kiosk). No real testimonials, customer logos or usage numbers exist; do not fabricate any.

## Product Principles
1. The ticket QR and the free-space number are the two things that must never be hard to read, at arm's length and in sunlight.
2. One clear next action per screen; a driver should never have to think about what to tap.
3. Show real state (live counts, stale sensor warnings, payment status) rather than reassure with decoration.
4. Failure states (full lot, expired ticket, wrong gate, offline) are designed screens, because they happen at the barrier with a car waiting.
5. Thai first: sizes, line-height and weights chosen for Thai script, not copied from Latin defaults.

## Accessibility & Inclusion
Outdoor legibility (high contrast, large targets, no reliance on color alone for status), one-handed use on phones, Thai text rendering, reduced-motion respected.
