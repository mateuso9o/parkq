"""Emit the ParkQ Gate Controller schematic as KiCad 5.0-era legacy files
(ParkQ_Gate.sch + ParkQ_Gate.lib) zipped for EasyEDA Std import.

Style: every symbol is a rectangle; each connected pin gets a short wire
stub ending in a local net label (so nets join by name), each unused pin
gets a NoConn flag.  Syntax follows the proven spike (spike/make_spike.py).
Units are mils; the schematic y axis points down, the library y axis up.
Python stdlib only.
"""
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import design  # noqa: E402

LIBNAME = "ParkQ_Gate"
PIN_LEN = 150          # library pin length (mils)
PITCH = 100            # vertical pin pitch (mils)
STUB = 100             # wire stub from pin end to its label
CHAR_W = 55            # rough text width per character at size 50


# ------------------------------------------------------------------ geometry
def _layout(sym):
    """Pin positions in library coordinates.
    Returns (half_width, top, bottom, {pin_num: (x, y, orient_char, name)}),
    where top/bottom bound the body rectangle (y up)."""
    left = [p for p in sym.pins if p[0] not in sym.right]
    right = [p for p in sym.pins if p[0] in sym.right]
    longest = max([len(n) for _, n in sym.pins] or [3])
    # body wide enough for names on both sides, multiple of 100
    width = max(300, -(-(longest * CHAR_W * (2 if right else 1) + 100) // 100) * 100)
    half = width // 2
    rows = max(len(left), len(right), 1)
    top = 50
    bottom = -PITCH * (rows - 1) - 50
    pos = {}
    for i, (num, name) in enumerate(left):
        pos[num] = (-(half + PIN_LEN), -PITCH * i, "R", name)
    for i, (num, name) in enumerate(right):
        pos[num] = (half + PIN_LEN, -PITCH * i, "L", name)
    return half, top, bottom, pos


def lib_text():
    out = ["EESchema-LIBRARY Version 2.4\n#encoding utf-8\n"]
    for name, sym in design.SYMBOLS.items():
        half, top, bottom, pos = _layout(sym)
        out.append("#\n# %s\n#\n" % name)
        out.append("DEF %s %s 0 40 Y Y 1 F N\n" % (name, sym.prefix))
        out.append('F0 "%s" 0 %d 50 H V C CNN\n' % (sym.prefix, top + 50))
        out.append('F1 "%s" 0 %d 50 H V C CNN\n' % (name, bottom - 50))
        out.append('F2 "" 0 0 50 H I C CNN\n')
        out.append('F3 "" 0 0 50 H I C CNN\n')
        out.append("DRAW\n")
        out.append("S %d %d %d %d 0 1 10 N\n" % (-half, top, half, bottom))
        for num, (x, y, orient, pname) in sorted(
                pos.items(), key=lambda kv: int(kv[0])):
            out.append("X %s %s %d %d %d %s 50 50 1 1 P\n"
                       % (pname, num, x, y, PIN_LEN, orient))
        out.append("ENDDRAW\nENDDEF\n")
    out.append("#\n#End Library\n")
    return "".join(out)


# -------------------------------------------------------------- placement
BLOCKS = [   # one column per functional block, parts stacked top to bottom
    ["J_PWR", "F1", "D1", "C1", "C2"],
    ["U1"],
    ["J_SERVO_IN", "J_SERVO_OUT", "J_QR_IN", "J_QR_OUT",
     "J_SLOT1", "J_SLOT2", "J_SLOT3", "J_SLOT4"],
    ["R1", "R2", "R3", "R4", "R5", "R6"],
    ["R7", "LED1", "R8", "LED2", "R9", "LED3",
     "R10", "Q1", "D2", "BZ1", "H1", "H2", "H3", "H4"],
]
TOP_Y = 1500
GAP = 450
LABEL_MARGIN = 900     # room for net labels each side of a column


def _col_width(refs, parts):
    best = 0
    for r in refs:
        half = _layout(design.SYMBOLS[parts[r].symbol])[0]
        best = max(best, half)
    return 2 * (best + PIN_LEN + STUB + LABEL_MARGIN)


def place():
    """ref -> (x, y) schematic position in mils (50-mil grid)."""
    parts = {p.ref: p for p in design.PARTS}
    placed, x = {}, 800
    for refs in BLOCKS:
        w = _col_width(refs, parts)
        cx = x + w // 2
        cx = -(-cx // 100) * 100
        y = TOP_Y
        for r in refs:
            _, top, bottom, _ = _layout(design.SYMBOLS[parts[r].symbol])
            placed[r] = (cx, y)
            y += (top - bottom) + GAP
            y = -(-y // 100) * 100
        x += w
    missing = set(parts) - set(placed)
    assert not missing, missing
    return placed


# ----------------------------------------------------------------- schematic
def sch_text():
    placed = place()
    out = ["EESchema Schematic File Version 4\nLIBS:%s\nEELAYER 26 0\nEELAYER END\n"
           % LIBNAME,
           "$Descr A3 16535 11693\nencoding utf-8\nSheet 1 1\n"
           'Title "ParkQ Gate Controller v1"\nDate "2026-10-30"\nRev "1"\n'
           'Comp "ParkQ"\nComment1 ""\nComment2 ""\nComment3 ""\nComment4 ""\n'
           "$EndDescr\n"]
    body = []
    for n, p in enumerate(design.PARTS, 1):
        sym = design.SYMBOLS[p.symbol]
        half, top, bottom, pos = _layout(sym)
        cx, cy = placed[p.ref]
        out.append("$Comp\nL %s:%s %s\nU 1 1 %08X\nP %d %d\n"
                   % (LIBNAME, p.symbol, p.ref, 0x5C000000 + n, cx, cy))
        out.append('F 0 "%s" H %d %d 50  0000 C CNN\n'
                   % (p.ref, cx, cy - top - 100))
        out.append('F 1 "%s" H %d %d 50  0000 C CNN\n'
                   % (p.value, cx, cy - bottom + 100))
        out.append('F 2 "%s:%s" H %d %d 50  0001 C CNN\n'
                   % (LIBNAME, p.footprint, cx, cy))
        out.append('F 3 "" H %d %d 50  0001 C CNN\n' % (cx, cy))
        out.append("\t1    %d %d\n\t1    0    0    -1\n$EndComp\n" % (cx, cy))
        for num, (px, py, orient, _) in sorted(
                pos.items(), key=lambda kv: int(kv[0])):
            sx, sy = cx + px, cy - py            # y flips into sheet coords
            net = p.pins.get(num, "")
            if not net:
                body.append("NoConn ~ %d %d\n" % (sx, sy))
                continue
            dx = -STUB if orient == "R" else STUB    # stub points away from body
            ex = sx + dx
            body.append("Wire Wire Line\n\t%d %d %d %d\n" % (sx, sy, ex, sy))
            body.append("Text Label %d %d %d    50   ~ 0\n%s\n"
                        % (ex, sy, 2 if dx < 0 else 0, net))
    out.extend(body)
    out.append("$EndSCHEMATC\n")
    return "".join(out)


def write(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("ParkQ_Gate.sch", sch_text().encode("utf-8"))
        z.writestr("ParkQ_Gate.lib", lib_text().encode("utf-8"))


if __name__ == "__main__":
    target = HERE / "build" / "ParkQ_Gate_SCH.zip"
    write(target)
    print("wrote", target)
