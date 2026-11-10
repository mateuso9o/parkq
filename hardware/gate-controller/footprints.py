"""Through-hole footprint library for the ParkQ Gate Controller (mm, y down).

Each footprint is a list of pads plus silkscreen graphics, all in the part's
local frame at rot 0 (see design.py for where each origin sits).  Pad number
conventions match design.py's schematic symbols:

  LED             1 = cathode (K), 2 = anode (A)
  D_DO-201AD / D_DO-35   1 = anode, 2 = cathode (band on pad 2 side)
  TO-92_Inline    1 = E, 2 = B, 3 = C   (S8050, flat face towards you)
  Buzzer          1 = +
  DC jack         1 = tip (+), 2 = sleeve (-), 3 = sleeve switch (no net)

Python stdlib only.
"""
from collections import namedtuple

Pad = namedtuple("Pad", "num x y w h drill shape slot", defaults=(None,))
# shape: circle|rect|oval; slot: optional (w, h) oval drill in the pad frame

HDR_PAD, HDR_DRILL = 1.7, 1.0
PITCH = 2.54


def _hdr(n):
    return [Pad(str(i + 1), 0.0, round(i * PITCH, 3), HDR_PAD, HDR_PAD, HDR_DRILL,
                "rect" if i == 0 else "circle") for i in range(n)]


def _axial(half, size, drill):
    return [Pad("1", -half, 0.0, size, size, drill, "circle"),
            Pad("2", half, 0.0, size, size, drill, "circle")]


def _devkit():
    pads = []
    # ESP32-DevKitC: 2 x 19 pins; pin 1 faces pin 20 at the antenna end
    for i in range(19):
        y = round(-22.86 + i * PITCH, 3)
        pads.append(Pad(str(i + 1), -12.7, y, 1.7, 1.7, 1.0,
                        "rect" if i == 0 else "circle"))
    for i in range(19):
        y = round(-22.86 + i * PITCH, 3)
        pads.append(Pad(str(i + 20), 12.7, y, 1.7, 1.7, 1.0, "circle"))
    return pads


def _rect(x0, y0, x1, y1):
    return [("line", x0, y0, x1, y0), ("line", x1, y0, x1, y1),
            ("line", x1, y1, x0, y1), ("line", x0, y1, x0, y0)]


def _hdr_gfx(n):
    return _rect(-1.27, -1.27, 1.27, round((n - 1) * PITCH + 1.27, 3))


def _to92_gfx():
    """D-shaped TO-92 outline: round side at -y, FLAT side at +y (pins E-B-C
    left to right when the flat faces the viewer/bottom of the silk)."""
    import math
    r, yf = 2.6, 1.8
    pts = [(-r, yf), (-r, 0.0)]
    pts += [(round(-r * math.cos(math.radians(a)), 3),
             round(-r * math.sin(math.radians(a)), 3)) for a in range(15, 180, 15)]
    pts += [(r, 0.0), (r, yf), (-r, yf)]
    return [("line",) + pts[i] + pts[i + 1] for i in range(len(pts) - 1)]


def _build():
    import design
    pitch = design.DEVKIT_ROW_PITCH_MM
    devkit = _devkit()
    devkit = [p._replace(x=(-pitch / 2 if p.x < 0 else pitch / 2)) for p in devkit]
    fp = {}

    # PJ-002A style barrel jack, opening towards -y (board edge).  Jack axis = Y.
    # Tip/sleeve blades lie ACROSS the axis (slot long in x); the switch blade
    # lies ALONG it (slot long in y) - KiCad BarrelJack_Horizontal rotated 90 deg.
    fp["DC_Jack_5.5x2.1"] = (
        [Pad("1", 0.0, 6.0, 3.6, 2.4, 1.0, "oval", (3.0, 1.0)),   # tip: blade lies across the Y axis
         Pad("2", 0.0, 0.0, 3.6, 2.4, 1.0, "oval", (3.0, 1.0)),   # sleeve: same
         Pad("3", 4.7, 3.0, 2.4, 3.6, 1.0, "oval", (1.0, 3.0))],  # switch: along the axis
        _rect(-4.5, -7.0, 4.5, 7.0) + [("line", -4.5, -4.0, 4.5, -4.0)])
    fp["Fuse_PTC_TH"] = (
        _axial(2.54, 2.0, 1.1),
        _rect(-4.2, -2.4, 4.2, 2.4))
    fp["D_DO-201AD"] = (
        _axial(6.35, 3.0, 1.5),
        _rect(-4.75, -2.65, 4.75, 2.65) + _rect(3.0, -2.65, 4.0, 2.65))
    fp["CP_Radial_D8_P3.5"] = (
        [Pad("1", -1.75, 0.0, 1.8, 1.8, 0.9, "rect"),
         Pad("2", 1.75, 0.0, 1.8, 1.8, 0.9, "circle")],
        [("circle", 0.0, 0.0, 4.25), ("line", -3.6, -3.0, -2.6, -3.0),
         ("line", -3.1, -3.5, -3.1, -2.5)])
    fp["C_Disc_P5.0"] = (
        _axial(2.5, 1.6, 0.8),
        _rect(-3.5, -1.6, 3.5, 1.6))
    fp["ESP32_DevKitC_38pin"] = (
        devkit,
        _rect(-14.0, -27.2, 14.0, 27.2) + _rect(-5.0, 21.5, 5.0, 27.2)
        + _rect(-9.0, -27.2, 9.0, -24.0))
    fp["PinHeader_1x03_P2.54"] = (_hdr(3), _hdr_gfx(3))
    fp["PinHeader_1x04_P2.54"] = (_hdr(4), _hdr_gfx(4))
    fp["R_Axial_P7.62"] = (
        _axial(3.81, 1.6, 0.8),
        _rect(-3.2, -1.2, 3.2, 1.2))
    fp["LED_D5.0"] = (
        [Pad("1", -1.27, 0.0, 1.8, 1.8, 0.9, "rect"),       # cathode
         Pad("2", 1.27, 0.0, 1.8, 1.8, 0.9, "circle")],     # anode
        [("circle", 0.0, 0.0, 2.9), ("line", -2.9, -1.2, -2.9, 1.2)])
    fp["TO-92_Inline"] = (
        [Pad("1", -2.54, 0.0, 1.5, 1.5, 0.8, "rect"),       # E
         Pad("2", 0.0, 0.0, 1.5, 1.5, 0.8, "circle"),       # B
         Pad("3", 2.54, 0.0, 1.5, 1.5, 0.8, "circle")],     # C
        _to92_gfx())
    fp["D_DO-35_P7.62"] = (
        _axial(3.81, 1.6, 0.8),
        _rect(-1.8, -0.9, 1.8, 0.9) + _rect(0.9, -0.9, 1.3, 0.9))
    fp["Buzzer_12x9.5"] = (
        [Pad("1", -3.8, 0.0, 2.0, 2.0, 1.0, "rect"),
         Pad("2", 3.8, 0.0, 2.0, 2.0, 1.0, "circle")],
        [("circle", 0.0, 0.0, 6.0), ("line", -5.6, -2.2, -4.6, -2.2),
         ("line", -5.1, -2.7, -5.1, -1.7)])
    fp["MountingHole_3.2mm"] = (
        [Pad("", 0.0, 0.0, 3.2, 3.2, 3.2, "circle")],        # NPTH
        [("circle", 0.0, 0.0, 3.5)])
    return fp


_LIB = None


def _lib():
    global _LIB
    if _LIB is None:
        _LIB = _build()
    return _LIB


def names():
    return sorted(_lib())


def pads(footprint):
    """Pads of `footprint` relative to its origin, rot 0."""
    return list(_lib()[footprint][0])


def graphics(footprint):
    """Silkscreen primitives: ('line', x1, y1, x2, y2) / ('circle', cx, cy, r)."""
    return list(_lib()[footprint][1])


def bbox(footprint):
    """(xmin, ymin, xmax, ymax) over pads and graphics, rot 0."""
    xs, ys = [], []
    for p in pads(footprint):
        xs += [p.x - p.w / 2, p.x + p.w / 2]
        ys += [p.y - p.h / 2, p.y + p.h / 2]
    for g in graphics(footprint):
        if g[0] == "line":
            xs += [g[1], g[3]]
            ys += [g[2], g[4]]
        else:
            xs += [g[1] - g[3], g[1] + g[3]]
            ys += [g[2] - g[3], g[2] + g[3]]
    return min(xs), min(ys), max(xs), max(ys)
