# ParkQ Gate Controller PCB + Firmware Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a KiCad-5-format schematic + PCB of the ParkQ Gate Controller that imports into EasyEDA Std, a Thai build/explain guide, and ESP32 firmware that talks to the existing Device API.

**Architecture:** One Python data module (`design.py`) is the single source of truth: parts, footprints, pin→net map, placement. Two emitters turn it into a legacy `.sch` + `.lib` (net-label style, no wire drawing) and a `.kicad_pcb` (version 20171130) with placed parts, nets, outline and GND pours; routing is done by EasyEDA's Auto Router after import. Firmware is a PlatformIO Arduino project whose pins come from the same table.

**Tech Stack:** Python 3.12 stdlib (unittest, zipfile), KiCad 5 legacy file formats, PlatformIO 6 + Arduino-ESP32 (`espressif32`, board `esp32dev`), ESP32Servo, ArduinoJson 7.

**Spec:** `docs/superpowers/specs/2026-10-30-gate-controller-pcb-design.md`

## Global Constraints

- Import target: EasyEDA Std, KiCad ≥ 4.06 but pre-5.1.3 document format → schematic `EESchema Schematic File Version 4`, library `EESchema-LIBRARY Version 2.4`, PCB `(kicad_pcb (version 20171130) ...)`. Each delivered as its own ZIP (schematic + lib together; PCB alone).
- 2 layers, board ≤ 100×100 mm (target ≈ 80×70 mm), 4 × M3 holes.
- All parts through-hole; ESP32 DevKit V1 30-pin on two 1×15 female headers, row pitch 25.4 mm (constant `DEVKIT_ROW_PITCH_MM`, single place to change to 22.86).
- Pin map exactly as spec §6.2: QR-IN RX/TX = GPIO16/17, QR-OUT RX/TX = GPIO32/33, SERVO-IN = GPIO18, SERVO-OUT = GPIO19, SLOT1–4 = GPIO34/35/36/39, LED-G = GPIO23, LED-R = GPIO22, BUZZER = GPIO4. GPIO0/2/5/12/15 unused.
- Power: DC jack 5.5×2.1 → PTC 2 A → SS34 → net `+5V` → DevKit VIN, servos, QR readers, buzzer. IR sensors on `+3V3` (DevKit 3V3 pin). 470 µF/16 V + 100 nF near servo headers.
- 1 kΩ series resistor on each ESP32 RX line from a QR reader; optional divider footprints (2 kΩ / 3.3 kΩ) marked "DNP — 5V readers only".
- Track widths: signal 0.3 mm, `+5V`/`GND` ≥ 1.0 mm (as net classes / documented autoroute rules).
- Silkscreen: every connector labelled (`SERVO-IN`, `SERVO-OUT`, `QR-IN`, `QR-OUT`, `SLOT1`…`SLOT4`, `5V 2A`), title "ParkQ Gate Controller v1 · กลุ่ม ParkQ".
- Firmware uses only the documented Device API: `POST /api/iot/{lot}/slots {"device_key","slots":[..4 ints..]}`, `GET /api/iot/{lot}/commands?device_key=` → `[{"gate":"in|out","command":"OPEN"}]`, `POST /api/gate/{lot}/in|out/scan {"token"}`. Slots must be posted at least every 30 s (server marks stale after 2 min).

## Review Focus

1. **Servo current dip resets the ESP32** — expect the bulk capacitor on `+5V` within 15 mm of the servo headers; test in Task 3.
2. **5 V QR reader drives an ESP32 RX pin** — expect every QR→ESP32 line to pass through the 1 kΩ series resistor; test in Task 2.
3. **A strapping pin used by mistake** — expect no net on GPIO0/2/5/12/15; test in Task 2.
4. **Import silently drops a pad or net** — expect every net to touch ≥ 2 pads and every part to sit inside the outline; tests in Task 3, and a human import check in Task 6.
5. **Wi-Fi drops mid-demo** — expect firmware to reconnect and keep the barrier closed while offline; covered by Task 5's simulator test on reconnect order and code review.

---

### Task 1: Import spike (do first, user runs it)

**Files:**
- Create: `hardware/gate-controller/spike/make_spike.py`
- Output: `hardware/gate-controller/build/spike_sch.zip`, `hardware/gate-controller/build/spike_pcb.zip`

- [ ] **Step 1:** Write `make_spike.py` emitting a 2-part design (one resistor `R1`, one 2-pin header `J1`, nets `A`, `B`) in the three legacy formats, zipped as the constraints say.
- [ ] **Step 2:** Run `python hardware/gate-controller/spike/make_spike.py`; expect both ZIPs created.
- [ ] **Step 3:** Ask the user to import both ZIPs in EasyEDA Std (File → Import → KiCad) and send a screenshot. Continue Tasks 2–5 while waiting; if the import fails, stop and revisit the format before Task 3's output is final.

### Task 2: Design data + schematic

**Files:**
- Create: `hardware/gate-controller/design.py`, `hardware/gate-controller/emit_sch.py`, `hardware/gate-controller/test_design.py`
- Output: `hardware/gate-controller/build/ParkQ_Gate_SCH.zip` (`ParkQ_Gate.sch` + `ParkQ_Gate.lib`)

**Interfaces:**
- Produces: `design.PARTS: list[Part]` where `Part(ref: str, value: str, symbol: str, footprint: str, pins: dict[str, str], lcsc: str, x_mm: float, y_mm: float, rot: int)` — `pins` maps pin number → net name; `design.NETS() -> dict[str, list[tuple[str, str]]]` (net → [(ref, pin)]); `design.GPIO_MAP: dict[str, int]` (signal name → GPIO); `design.DEVKIT_ROW_PITCH_MM = 25.4`; `emit_sch.write(path: Path) -> None`.

- [ ] **Step 1: Write failing tests** in `test_design.py`:
  - `test_gpio_map_matches_spec` — `GPIO_MAP == {"QR_IN_RX":16,"QR_IN_TX":17,"QR_OUT_RX":32,"QR_OUT_TX":33,"SERVO_IN":18,"SERVO_OUT":19,"SLOT1":34,"SLOT2":35,"SLOT3":36,"SLOT4":39,"LED_G":23,"LED_R":22,"BUZZER":4}`, and the DevKit part's pin for each GPIO carries that net.
  - `test_no_strapping_pins` — DevKit pins for GPIO0/2/5/12/15 have no net.
  - `test_qr_rx_through_series_resistor` — net on the QR header TX pin ≠ net on ESP32 RX pin, and a 1 kΩ resistor joins them (both QR readers).
  - `test_every_net_has_two_pins` — every net in `NETS()` has ≥ 2 members.
  - `test_ir_sensors_on_3v3` and `test_servos_on_5v`.
  - `test_schematic_header_and_parts` — after `emit_sch.write`, the `.sch` starts with `EESchema Schematic File Version 4`, contains one `$Comp` per part and one label per connected pin; the `.lib` starts with `EESchema-LIBRARY Version 2.4` and defines every `symbol` used.
- [ ] **Step 2:** Run `python -m unittest hardware/gate-controller/test_design.py -v`; expect FAIL (module missing).
- [ ] **Step 3:** Implement `design.py` (parts per spec §6.1: J_PWR DC jack, F1 PTC, D1 SS34, C1 470µF, C2 100nF, U1 DevKit as two headers J_L/J_R or one 30-pin symbol, J_SERVO_IN/OUT 3-pin, J_QR_IN/OUT 4-pin, R1–R4 1 kΩ series (RX and TX), R5–R8 DNP divider, J_SLOT1–4 3-pin, LED1 G, LED2 R, LED3 power, R9–R11 330 Ω, Q1 S8050, R12 1 kΩ base, D2 1N4148, BZ1 active buzzer, H1–H4 M3) and `emit_sch.py` (rectangle symbols, one short pin stub + local label per connected pin, `NoConn` on unused pins; grid placement by function block).
- [ ] **Step 4:** Run the tests; expect all PASS.
- [ ] **Step 5:** `git add hardware/gate-controller && git commit -m "feat(pcb): gate controller design data and schematic"` (only when the user has approved commits).

### Task 3: PCB emitter

**Files:**
- Create: `hardware/gate-controller/emit_pcb.py`, `hardware/gate-controller/footprints.py`, `hardware/gate-controller/test_pcb.py`, `hardware/gate-controller/build_all.py`
- Output: `hardware/gate-controller/build/ParkQ_Gate_PCB.zip` (`ParkQ_Gate.kicad_pcb`), `hardware/gate-controller/build/ParkQ_Gate_layout.png`

**Interfaces:**
- Consumes: `design.PARTS`, `design.NETS()`, `design.DEVKIT_ROW_PITCH_MM`.
- Produces: `footprints.pads(footprint: str) -> list[Pad]` with `Pad(num: str, x: float, y: float, w: float, h: float, drill: float, shape: str)` relative to origin; `emit_pcb.write(path: Path) -> None`; `emit_pcb.placed_pads() -> list[tuple[ref, Pad_abs, net]]`; `build_all.main()` writes every ZIP + the PNG.

- [ ] **Step 1: Write failing tests** in `test_pcb.py`:
  - `test_header_version` — file starts with `(kicad_pcb (version 20171130)`.
  - `test_board_size` — Edge.Cuts outline ≤ 100×100 mm.
  - `test_all_pads_inside_outline` — every pad edge ≥ 1 mm inside the outline.
  - `test_no_pad_overlap_between_parts` — copper pads of different parts keep ≥ 0.5 mm clearance.
  - `test_every_net_on_pcb` — each net from `NETS()` appears on ≥ 2 pads in the PCB.
  - `test_bulk_cap_near_servos` — C1 centre within 15 mm of both servo headers.
  - `test_devkit_pitch` — the two DevKit header rows are `DEVKIT_ROW_PITCH_MM` apart.
  - `test_net_classes` — `+5V` and `GND` in a net class with track width ≥ 1.0; default 0.3.
- [ ] **Step 2:** Run `python -m unittest hardware/gate-controller/test_pcb.py -v`; expect FAIL.
- [ ] **Step 3:** Implement footprints (DC jack, 2.54 mm headers, TH resistor 7.62 mm, radial cap 5 mm/2.5 mm, DO-41/DO-214→TH 1N5819 alternative if SS34 is SMD: use **1N5822 TH** instead and note it, TO-92, 5 mm LED, 12 mm buzzer, 3.2 mm holes), placement from `Part.x_mm/y_mm/rot`, silkscreen labels + title, GND pour on both layers, and a PNG preview drawn with PIL (pads + labels; English only to avoid Thai font issues).
- [ ] **Step 4:** Run both test files; expect all PASS. Run `python hardware/gate-controller/build_all.py`; expect 3 ZIPs + PNG; look at the PNG.
- [ ] **Step 5:** Commit (when approved).

### Task 4: Firmware project

**Files:**
- Create: `firmware/gate-controller/platformio.ini`, `firmware/gate-controller/include/pins.h`, `firmware/gate-controller/include/config.example.h`, `firmware/gate-controller/src/main.cpp`, `firmware/gate-controller/.gitignore` (`include/config.h`, `.pio/`)

**Interfaces:**
- Consumes: pin numbers identical to `design.GPIO_MAP` (Task 5's test compares them).
- Produces: `config.h` macros `WIFI_SSID`, `WIFI_PASS`, `API_BASE` (e.g. `"https://parkq.onrender.com"`), `LOT_ID`, `DEVICE_KEY`.

- [ ] **Step 1:** `platformio.ini`: env `esp32dev`, `platform = espressif32`, `framework = arduino`, `lib_deps = madhephaestus/ESP32Servo, bblanchon/ArduinoJson@^7`, `monitor_speed = 115200`.
- [ ] **Step 2:** `main.cpp` loop: Wi-Fi connect/reconnect; every 1 s GET commands → `OPEN` → servo to 90° for 3 s then 0°, green LED + short beep; QR line from Serial2/Serial1 (terminated by `\r` or `\n`) → POST scan → 200 ok: open locally + green/short beep, else red LED + long beep; read SLOT1–4 (IR module LOW = car present → 1) and POST when changed or every 30 s; HTTPS via `WiFiClientSecure.setInsecure()` (documented as demo-only).
- [ ] **Step 3:** Run `pio run -d firmware/gate-controller -e esp32dev` (first run downloads the ESP32 toolchain); expect `SUCCESS`.
- [ ] **Step 4:** Commit (when approved).

### Task 5: Firmware ↔ API contract test

**Files:**
- Create: `firmware/gate-controller/test_contract.py`

- [ ] **Step 1: Write tests** (unittest, local server on 127.0.0.1:8000 with `PARKQ_RESET=1`): `test_pins_match_pcb` (parse `pins.h` `#define` values == `design.GPIO_MAP`); `test_slots_post_shape` (POST exactly the firmware's JSON shape for LOT01 with its `device_key` from the DB → 200, lot status changes); `test_commands_poll_shape` (GET returns a JSON list; after an admin manual-open, contains `{"gate":"in","command":"OPEN"}`); `test_scan_bad_token` (POST garbage token → non-200, firmware's red path).
- [ ] **Step 2:** Run against the server; fix the firmware (not the test) on any shape mismatch; expect all PASS.
- [ ] **Step 3:** Commit (when approved).

### Task 6: Thai guide + verification

**Files:**
- Create: `hardware/gate-controller/README.md`

- [ ] **Step 1:** Write the guide: (1) import in EasyEDA Std — schematic ZIP and PCB ZIP, (2) Auto Router settings (track 0.3/1.0 mm, clearance 0.25 mm, 2 layers), then Design Rule Check, (3) order at JLCPCB from EasyEDA (Gerber, 2 layers, 1.6 mm, HASL), (4) BOM table with LCSC codes and Thai-shop names + approximate prices, (5) circuit explanation block by block for the teacher's Q&A, (6) firmware flash steps (`config.h`, `pio run -t upload`), (7) measure the DevKit row pitch before ordering.
- [ ] **Step 2:** Run every test file and `build_all.py` and `pio run`; quote the results.
- [ ] **Step 3:** User imports `ParkQ_Gate_SCH.zip` and `ParkQ_Gate_PCB.zip` in EasyEDA Std and sends screenshots; fix anything broken.
