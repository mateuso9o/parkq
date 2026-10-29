"""ParkQ Gate Controller PCB - single source of truth for the design.

Everything the schematic (emit_sch.py) and, later, the board generator
need lives in the PARTS table below.  Read it top to bottom to follow the
circuit:

  power jack -> fuse -> reverse-polarity diode -> +5V rail -> ESP32 VIN
  ESP32 3V3 pin -> +3V3 rail -> IR slot sensors
  ESP32 GPIO -> servos, QR readers (via 1k series resistors), LEDs, buzzer

Conventions
  * Part.pins maps pin number (string) -> net name.  A pin that is absent
    or "" is deliberately unconnected ("no net"); NETS() never lists it.
  * PCB placement: x_mm, y_mm = footprint origin, in mm on an 80 x 70 mm
    board, origin top-left, y down.  Origin of each footprint:
      ESP32_DevKit_30pin  centre of the two pin rows (rows run along Y,
                          pin 1 top-left, pins 1-15 left row, 16-30 right)
      PinHeader_*         pin 1 (further pins go +2.54 mm along the part's
                          local +Y: downward at rot 0, rightward (+X)
                          at rot 90)
      R_Axial / D_DO-35   body centre, leads along local X at rot 0
      others              body centre
    rot is degrees counter-clockwise on screen: 0, 90, 180 or 270.
  * Python stdlib only.
"""
import re
from collections import namedtuple
from dataclasses import dataclass, field

BOARD_W_MM = 80.0
BOARD_H_MM = 70.0
DEVKIT_ROW_PITCH_MM = 25.4   # measure the real DevKit (25.4 or 22.86) first

# Signal name -> ESP32 GPIO number (spec section 6.2).  "RX"/"TX" are from
# the ESP32's point of view: QR_IN_RX (GPIO16) listens to the reader's TX.
GPIO_MAP = {
    "QR_IN_RX": 16, "QR_IN_TX": 17,
    "QR_OUT_RX": 32, "QR_OUT_TX": 33,
    "SERVO_IN": 18, "SERVO_OUT": 19,
    "SLOT1": 34, "SLOT2": 35, "SLOT3": 36, "SLOT4": 39,
    "LED_G": 23, "LED_R": 22,
    "BUZZER": 4,
}

# --------------------------------------------------------------------------
# Schematic symbols: name -> pins [(number, name)].  `right` lists the pin
# numbers drawn on the right-hand side of the box (the rest are on the left).
# --------------------------------------------------------------------------
Symbol = namedtuple("Symbol", "prefix pins right")

# ESP32 DevKit V1 (DOIT) 30-pin, pin numbers in DOIT order.
DEVKIT_PINS = [
    # left row, top -> bottom
    ("1", "EN"), ("2", "GPIO36(VP)"), ("3", "GPIO39(VN)"), ("4", "GPIO34"),
    ("5", "GPIO35"), ("6", "GPIO32"), ("7", "GPIO33"), ("8", "GPIO25"),
    ("9", "GPIO26"), ("10", "GPIO27"), ("11", "GPIO14"), ("12", "GPIO12"),
    ("13", "GPIO13"), ("14", "GND"), ("15", "VIN"),
    # right row, top -> bottom
    ("16", "GPIO23"), ("17", "GPIO22"), ("18", "GPIO1(TX0)"),
    ("19", "GPIO3(RX0)"), ("20", "GPIO21"), ("21", "GPIO19"),
    ("22", "GPIO18"), ("23", "GPIO5"), ("24", "GPIO17(TX2)"),
    ("25", "GPIO16(RX2)"), ("26", "GPIO4"), ("27", "GPIO2"),
    ("28", "GPIO15"), ("29", "GND"), ("30", "3V3"),
]


def devkit_pin(gpio):
    """DevKit pin number (str) carrying GPIO<gpio>, or None if not broken out."""
    for num, name in DEVKIT_PINS:
        if re.match(r"GPIO%d(?!\d)" % gpio, name):
            return num
    return None


def _pins(*names):
    return [(str(i + 1), n) for i, n in enumerate(names)]


SYMBOLS = {
    "DC_Jack": Symbol("J", _pins("TIP(+)", "SLEEVE(-)"), {"2"}),
    "PTC_Fuse": Symbol("F", _pins("1", "2"), {"2"}),
    "Diode": Symbol("D", _pins("A", "K"), {"2"}),
    "CP": Symbol("C", _pins("+", "-"), {"2"}),
    "C": Symbol("C", _pins("1", "2"), {"2"}),
    "ESP32_DevKit_30pin": Symbol("U", DEVKIT_PINS,
                                 {str(i) for i in range(16, 31)}),
    "Conn_01x03": Symbol("J", _pins("1", "2", "3"), set()),
    "Conn_01x04": Symbol("J", _pins("1", "2", "3", "4"), set()),
    "R": Symbol("R", _pins("1", "2"), {"2"}),
    "LED": Symbol("D", _pins("K", "A"), {"2"}),
    "Q_NPN_EBC": Symbol("Q", _pins("E", "B", "C"), set()),
    "Buzzer": Symbol("BZ", _pins("+", "-"), {"2"}),
    "MountingHole": Symbol("H", [], set()),
}


@dataclass
class Part:
    ref: str
    value: str
    symbol: str
    footprint: str
    pins: dict = field(default_factory=dict)   # pin number -> net name
    lcsc: str = ""                              # filled in by the BOM task
    x_mm: float = 0.0
    y_mm: float = 0.0
    rot: int = 0


def _devkit_pins():
    """U1 pin -> net, built from GPIO_MAP plus power; all else has no net."""
    pins = {devkit_pin(gpio): sig for sig, gpio in GPIO_MAP.items()}
    pins["15"] = "+5V"    # VIN: DevKit's own regulator makes 3.3 V from this
    pins["30"] = "+3V3"   # 3V3 output feeds the IR sensors
    pins["14"] = "GND"
    pins["29"] = "GND"
    return pins


def P(*args, **kw):
    return Part(*args, **kw)


# --------------------------------------------------------------------------
# THE PARTS TABLE.  (ref, value, symbol, footprint, pins, ..., x, y, rot)
# Layout (board 80 x 70 mm):  power block left edge, servo + QR headers
# bottom edge, SLOT1-4 headers right edge, LEDs/buzzer between DevKit and
# the slot headers, QR series resistors under the DevKit between its rows.
# --------------------------------------------------------------------------
PARTS = [
    # ---- power input ------------------------------------------------------
    P("J_PWR", "DC-Jack 5.5x2.1", "DC_Jack", "DC_Jack_5.5x2.1",
      {"1": "VIN_RAW", "2": "GND"}, x_mm=14, y_mm=8),
    P("F1", "PTC 2A", "PTC_Fuse", "Fuse_PTC_TH",
      {"1": "VIN_RAW", "2": "VIN_FUSED"}, x_mm=10, y_mm=26, rot=90),
    P("D1", "1N5822", "Diode", "D_DO-201AD",       # anode VIN_FUSED, cathode +5V
      {"1": "VIN_FUSED", "2": "+5V"}, x_mm=10, y_mm=38, rot=90),
    P("C1", "470uF 16V", "CP", "CP_Radial_D8_P3.5",
      {"1": "+5V", "2": "GND"}, x_mm=19, y_mm=56),
    P("C2", "100nF", "C", "C_Disc_P5.0",
      {"1": "+5V", "2": "GND"}, x_mm=11, y_mm=56),

    # ---- brain --------------------------------------------------------------
    P("U1", "ESP32-DevKit-V1-30pin", "ESP32_DevKit_30pin", "ESP32_DevKit_30pin",
      _devkit_pins(), x_mm=BOARD_W_MM / 2, y_mm=BOARD_H_MM / 2),

    # ---- servo headers: 1 GND, 2 +5V, 3 signal ------------------------------
    P("J_SERVO_IN", "SERVO-IN", "Conn_01x03", "PinHeader_1x03_P2.54",
      {"1": "GND", "2": "+5V", "3": "SERVO_IN"}, x_mm=13, y_mm=65, rot=90),
    P("J_SERVO_OUT", "SERVO-OUT", "Conn_01x03", "PinHeader_1x03_P2.54",
      {"1": "GND", "2": "+5V", "3": "SERVO_OUT"}, x_mm=25, y_mm=65, rot=90),

    # ---- QR readers: 1 +5V, 2 GND, 3 reader TX, 4 reader RX -----------------
    P("J_QR_IN", "QR-IN", "Conn_01x04", "PinHeader_1x04_P2.54",
      {"1": "+5V", "2": "GND", "3": "QR_IN_TX_R", "4": "QR_IN_RX_R"},
      x_mm=37, y_mm=65, rot=90),
    P("J_QR_OUT", "QR-OUT", "Conn_01x04", "PinHeader_1x04_P2.54",
      {"1": "+5V", "2": "GND", "3": "QR_OUT_TX_R", "4": "QR_OUT_RX_R"},
      x_mm=49, y_mm=65, rot=90),

    # ---- QR series resistors (1k) + optional DNP dividers (2k) ---------------
    # reader TX -> R1 -> ESP RX (GPIO16);  ESP TX (GPIO17) -> R2 -> reader RX
    P("R1", "1k", "R", "R_Axial_P7.62",
      {"1": "QR_IN_TX_R", "2": "QR_IN_RX"}, x_mm=34, y_mm=24),
    P("R2", "1k", "R", "R_Axial_P7.62",
      {"1": "QR_IN_TX", "2": "QR_IN_RX_R"}, x_mm=34, y_mm=30),
    P("R3", "1k", "R", "R_Axial_P7.62",
      {"1": "QR_OUT_TX_R", "2": "QR_OUT_RX"}, x_mm=46, y_mm=24),
    P("R4", "1k", "R", "R_Axial_P7.62",
      {"1": "QR_OUT_TX", "2": "QR_OUT_RX_R"}, x_mm=46, y_mm=30),
    # fit R5/R6 ONLY if the reader's TX is 5 V: ESP RX node -> 2k -> GND
    P("R5", "2k DNP", "R", "R_Axial_P7.62",
      {"1": "QR_IN_RX", "2": "GND"}, x_mm=34, y_mm=36),
    P("R6", "2k DNP", "R", "R_Axial_P7.62",
      {"1": "QR_OUT_RX", "2": "GND"}, x_mm=46, y_mm=36),

    # ---- IR slot sensors (3V3 so OUT never exceeds 3.3 V): 1 3V3, 2 GND, 3 OUT
    P("J_SLOT1", "SLOT1", "Conn_01x03", "PinHeader_1x03_P2.54",
      {"1": "+3V3", "2": "GND", "3": "SLOT1"}, x_mm=75, y_mm=11),
    P("J_SLOT2", "SLOT2", "Conn_01x03", "PinHeader_1x03_P2.54",
      {"1": "+3V3", "2": "GND", "3": "SLOT2"}, x_mm=75, y_mm=23),
    P("J_SLOT3", "SLOT3", "Conn_01x03", "PinHeader_1x03_P2.54",
      {"1": "+3V3", "2": "GND", "3": "SLOT3"}, x_mm=75, y_mm=35),
    P("J_SLOT4", "SLOT4", "Conn_01x03", "PinHeader_1x03_P2.54",
      {"1": "+3V3", "2": "GND", "3": "SLOT4"}, x_mm=75, y_mm=47),

    # ---- indicators: LED pin 1 = cathode (K), pin 2 = anode (A) --------------
    P("R7", "330", "R", "R_Axial_P7.62",
      {"1": "LED_G", "2": "LED_G_A"}, x_mm=67, y_mm=12, rot=90),
    P("LED1", "LED Green", "LED", "LED_D5.0",
      {"1": "GND", "2": "LED_G_A"}, x_mm=60, y_mm=12),
    P("R8", "330", "R", "R_Axial_P7.62",
      {"1": "LED_R", "2": "LED_R_A"}, x_mm=67, y_mm=24, rot=90),
    P("LED2", "LED Red", "LED", "LED_D5.0",
      {"1": "GND", "2": "LED_R_A"}, x_mm=60, y_mm=24),
    P("R9", "330", "R", "R_Axial_P7.62",
      {"1": "+5V", "2": "PWR_LED_A"}, x_mm=67, y_mm=36, rot=90),
    P("LED3", "LED Power", "LED", "LED_D5.0",
      {"1": "GND", "2": "PWR_LED_A"}, x_mm=60, y_mm=36),

    # ---- buzzer: GPIO4 -> 1k -> S8050 base; buzzer on +5V, flyback 1N4148 ----
    P("R10", "1k", "R", "R_Axial_P7.62",
      {"1": "BUZZER", "2": "BUZ_B"}, x_mm=71, y_mm=58, rot=90),
    P("Q1", "S8050", "Q_NPN_EBC", "TO-92_Inline",       # 1 E, 2 B, 3 C
      {"1": "GND", "2": "BUZ_B", "3": "BUZ_C"}, x_mm=64, y_mm=61),
    P("D2", "1N4148", "Diode", "D_DO-35_P7.62",         # cathode on +5V
      {"1": "BUZ_C", "2": "+5V"}, x_mm=58, y_mm=58, rot=90),
    P("BZ1", "Active buzzer 5V", "Buzzer", "Buzzer_12x9.5",
      {"1": "+5V", "2": "BUZ_C"}, x_mm=64, y_mm=48),

    # ---- mounting holes -------------------------------------------------------
    P("H1", "M3", "MountingHole", "MountingHole_3.2mm", x_mm=5, y_mm=5),
    P("H2", "M3", "MountingHole", "MountingHole_3.2mm", x_mm=75, y_mm=5),
    P("H3", "M3", "MountingHole", "MountingHole_3.2mm", x_mm=5, y_mm=65),
    P("H4", "M3", "MountingHole", "MountingHole_3.2mm", x_mm=75, y_mm=65),
]


def NETS():
    """net name -> [(ref, pin number), ...]; pins with no net are omitted."""
    nets = {}
    for p in PARTS:
        for pin, net in p.pins.items():
            if net:
                nets.setdefault(net, []).append((p.ref, pin))
    return nets
