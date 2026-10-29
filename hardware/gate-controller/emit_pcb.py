"""Emit the ParkQ Gate Controller board as a KiCad 5.0-era .kicad_pcb
(zipped for EasyEDA Std import) plus a PNG preview.

Placed footprints with nets, Edge.Cuts outline, GND pours on both layers and
net classes.  Nothing is routed: do that in EasyEDA.  ASCII only.  Syntax
follows the proven spike (spike/make_spike.py).  Python stdlib (+ PIL for the
PNG preview only).
"""
import math
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import design  # noqa: E402
import footprints  # noqa: E402
from footprints import Pad  # noqa: E402

LIB = "ParkQ"
BOARD_W, BOARD_H = design.BOARD_W_MM, design.BOARD_H_MM
POUR_INSET = 0.5
POWER_NETS = ["+5V", "GND", "VIN_RAW", "VIN_FUSED"]
TITLE = "ParkQ Gate Controller v1"

# Reference-designator text position overrides (absolute board mm).
REF_AT = {"U1": (BOARD_W / 2, 14.8), "J_PWR": (22.0, 4.5), "D1": (17.0, 38.0)}
# Mounting holes and pin headers carry their own silkscreen names instead.
HIDE_REF = tuple(p.ref for p in design.PARTS
                 if p.footprint.startswith(("PinHeader", "MountingHole")))


# ------------------------------------------------------------------ geometry
def _rot(x, y, rot):
    """Local (x, y) -> board offset, rot degrees CCW on screen (y down)."""
    c = round(math.cos(math.radians(rot)))
    s = round(math.sin(math.radians(rot)))
    return x * c + y * s, -x * s + y * c


def _unrot(bx, by, rot):
    """Board offset -> local frame (inverse of _rot)."""
    return _rot(bx, by, -rot)


def abs_pad(part, pad):
    dx, dy = _rot(pad.x, pad.y, part.rot)
    w, h = (pad.h, pad.w) if part.rot % 180 == 90 else (pad.w, pad.h)
    return Pad(pad.num, round(part.x_mm + dx, 4), round(part.y_mm + dy, 4),
               w, h, pad.drill, pad.shape)


def placed_pads():
    """[(ref, Pad with absolute board coordinates, net name or '')]."""
    out = []
    for part in design.PARTS:
        for pad in footprints.pads(part.footprint):
            out.append((part.ref, abs_pad(part, pad), part.pins.get(pad.num, "")))
    return out


def board_bbox(part):
    x0, y0, x1, y1 = footprints.bbox(part.footprint)
    pts = [_rot(x, y, part.rot) for x in (x0, x1) for y in (y0, y1)]
    return (part.x_mm + min(p[0] for p in pts), part.y_mm + min(p[1] for p in pts),
            part.x_mm + max(p[0] for p in pts), part.y_mm + max(p[1] for p in pts))


def net_ids():
    names = sorted(design.NETS())
    return {n: i + 1 for i, n in enumerate(names)}


# -------------------------------------------------------------------- labels
def _pin_label(net):
    if net == "+5V":
        return "5V"
    if net == "GND":
        return "G"
    if net == "+3V3":
        return "3V3"
    if net.endswith("_TX_R"):
        return "TX"
    if net.endswith("_RX_R"):
        return "RX"
    return "S"


def labels():
    """Board silkscreen text: [(text, x, y, size, angle)]."""
    out = [(TITLE, BOARD_W / 2, 3.6, 1.2, 0),
           ("Group ParkQ", 66.0, 68.2, 1.0, 0),
           ("5V 2A", 14.0, 19.2, 1.2, 0),
           ("ESP32 DevKit", BOARD_W / 2, 12.4, 1.0, 0),
           ("USB", BOARD_W / 2, 57.6, 1.2, 0),
           ("GRN", 60.0, 16.0, 0.9, 0), ("RED", 60.0, 28.0, 0.9, 0),
           ("PWR", 60.0, 40.0, 0.9, 0)]
    for part in design.PARTS:
        if not part.footprint.startswith("PinHeader"):
            continue
        pads = [abs_pad(part, p) for p in footprints.pads(part.footprint)]
        cx = sum(p.x for p in pads) / len(pads)
        cy = sum(p.y for p in pads) / len(pads)
        if part.rot == 90:                       # row of pins along +x
            out.append((part.value, cx, pads[0].y - 2.6, 1.0, 0))
            for p in pads:
                out.append((_pin_label(part.pins.get(p.num, "")),
                            p.x, p.y + 2.5, 0.8, 0))
        else:                                    # column of pins along +y
            out.append((part.value, cx, pads[0].y - 2.6, 1.0, 0))
            for p in pads:
                out.append((_pin_label(part.pins.get(p.num, "")),
                            p.x - 2.7, p.y, 0.8, 0))
    return out


def ref_pos(part):
    """Board position for the reference text (just above the part)."""
    if part.ref in REF_AT:
        return REF_AT[part.ref]
    x0, y0, x1, _y1 = board_bbox(part)
    return (x0 + x1) / 2, y0 - 1.0


# ------------------------------------------------------------------ emitting
def _fmt(v):
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _effects(size, thick=0.15):
    return ("(effects (font (size %s %s) (thickness %s)))"
            % (_fmt(size), _fmt(size), _fmt(thick)))


def _module(idx, part, ids):
    s = ["  (module %s:%s (layer F.Cu) (tedit 5C000000) (tstamp 5C%06X)\n"
         "    (at %s %s%s)\n" % (LIB, part.footprint, idx + 1, _fmt(part.x_mm),
                                 _fmt(part.y_mm),
                                 (" %d" % part.rot) if part.rot else "")]
    rx, ry = ref_pos(part)
    lx, ly = _unrot(rx - part.x_mm, ry - part.y_mm, part.rot)
    s.append("    (fp_text reference %s (at %s %s%s) (layer F.SilkS)%s\n"
             "      %s\n    )\n"
             % (part.ref, _fmt(lx), _fmt(ly),
                (" %d" % part.rot) if part.rot else "",
                " hide" if part.ref in HIDE_REF else "", _effects(0.8, 0.12)))
    s.append("    (fp_text value \"%s\" (at 0 0%s) (layer F.Fab)\n"
             "      %s\n    )\n"
             % (part.value, (" %d" % part.rot) if part.rot else "", _effects(0.7, 0.1)))
    for g in footprints.graphics(part.footprint):
        if g[0] == "line":
            s.append("    (fp_line (start %s %s) (end %s %s) (layer F.SilkS) "
                     "(width 0.15))\n" % tuple(_fmt(v) for v in g[1:]))
        else:
            s.append("    (fp_circle (center %s %s) (end %s %s) (layer F.SilkS) "
                     "(width 0.15))\n" % (_fmt(g[1]), _fmt(g[2]),
                                          _fmt(g[1] + g[3]), _fmt(g[2])))
    x0, y0, x1, y1 = footprints.bbox(part.footprint)
    x0, y0, x1, y1 = x0 - 0.25, y0 - 0.25, x1 + 0.25, y1 + 0.25
    for a, b, c, d in ((x0, y0, x1, y0), (x1, y0, x1, y1),
                       (x1, y1, x0, y1), (x0, y1, x0, y0)):
        s.append("    (fp_line (start %s %s) (end %s %s) (layer F.CrtYd) "
                 "(width 0.05))\n" % (_fmt(a), _fmt(b), _fmt(c), _fmt(d)))
    for pad in footprints.pads(part.footprint):
        ang = (" %d" % part.rot) if part.rot else ""
        net = part.pins.get(pad.num, "")
        if pad.num == "":
            s.append('    (pad "" np_thru_hole circle (at %s %s%s) (size %s %s) '
                     '(drill %s) (layers *.Cu *.Mask))\n'
                     % (_fmt(pad.x), _fmt(pad.y), ang, _fmt(pad.w), _fmt(pad.h),
                        _fmt(pad.drill)))
            continue
        netstr = (' (net %d "%s")' % (ids[net], net)) if net else ""
        s.append('    (pad "%s" thru_hole %s (at %s %s%s) (size %s %s) (drill %s) '
                 '(layers *.Cu *.Mask)%s)\n'
                 % (pad.num, pad.shape, _fmt(pad.x), _fmt(pad.y), ang,
                    _fmt(pad.w), _fmt(pad.h), _fmt(pad.drill), netstr))
    s.append("  )\n")
    return "".join(s)


def _zone(layer, ids, tag):
    x0, y0 = POUR_INSET, POUR_INSET
    x1, y1 = BOARD_W - POUR_INSET, BOARD_H - POUR_INSET
    pts = " ".join("(xy %s %s)" % (_fmt(x), _fmt(y))
                   for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)))
    return ('  (zone (net %d) (net_name GND) (layer %s) (tstamp 5CA0000%d) '
            '(hatch edge 0.508)\n'
            '    (connect_pads (clearance 0.3))\n    (min_thickness 0.25)\n'
            '    (fill yes (arc_segments 16) (thermal_gap 0.5) '
            '(thermal_bridge_width 0.5))\n'
            '    (polygon (pts %s))\n  )\n' % (ids["GND"], layer, tag, pts))


def pcb_text():
    ids = net_ids()
    texts = labels()
    out = []
    w = out.append
    w("(kicad_pcb (version 20171130) (host pcbnew 5.0.2)\n")
    w("  (general\n    (thickness 1.6)\n    (drawings %d)\n    (tracks 0)\n"
      "    (zones 2)\n    (modules %d)\n    (nets %d)\n  )\n"
      % (4 + len(texts), len(design.PARTS), len(ids) + 1))
    w("  (page A4)\n  (layers\n"
      "    (0 F.Cu signal)\n    (31 B.Cu signal)\n"
      "    (32 B.Adhes user)\n    (33 F.Adhes user)\n"
      "    (34 B.Paste user)\n    (35 F.Paste user)\n"
      "    (36 B.SilkS user)\n    (37 F.SilkS user)\n"
      "    (38 B.Mask user)\n    (39 F.Mask user)\n"
      "    (40 Dwgs.User user)\n    (41 Cmts.User user)\n"
      "    (42 Eco1.User user)\n    (43 Eco2.User user)\n"
      "    (44 Edge.Cuts user)\n    (45 Margin user)\n"
      "    (46 B.CrtYd user)\n    (47 F.CrtYd user)\n"
      "    (48 B.Fab user)\n    (49 F.Fab user)\n  )\n")
    w("  (setup\n    (last_trace_width 0.3)\n    (trace_clearance 0.25)\n"
      "    (zone_clearance 0.3)\n    (zone_45_only no)\n"
      "    (trace_min 0.2)\n    (via_size 0.6)\n    (via_drill 0.3)\n"
      "    (via_min_size 0.4)\n    (via_min_drill 0.3)\n"
      "    (uvia_size 0.3)\n    (uvia_drill 0.1)\n"
      "    (uvias_allowed no)\n    (uvia_min_size 0.2)\n"
      "    (uvia_min_drill 0.1)\n    (edge_width 0.15)\n"
      "    (segment_width 0.2)\n    (pcb_text_width 0.3)\n"
      "    (pcb_text_size 1.5 1.5)\n    (mod_edge_width 0.15)\n"
      "    (mod_text_size 1 1)\n    (mod_text_width 0.15)\n"
      "    (pad_size 1.7 1.7)\n    (pad_drill 1)\n"
      "    (pad_to_mask_clearance 0.051)\n    (aux_axis_origin 0 0)\n"
      "    (visible_elements FFFFFF7F)\n"
      "    (pcbplotparams\n      (layerselection 0x010fc_ffffffff)\n"
      "      (usegerberextensions false)\n      (excludeedgelayer true)\n"
      "      (linewidth 0.100000)\n      (plotframeref false)\n"
      "      (viasonmask false)\n      (mode 1)\n      (useauxorigin false)\n"
      "      (hpglpennumber 1)\n      (hpglpenspeed 20)\n"
      "      (hpglpendiameter 15.000000)\n      (psnegative false)\n"
      "      (psa4output false)\n      (plotreference true)\n"
      "      (plotvalue true)\n      (plotinvisibletext false)\n"
      "      (padsonsilk false)\n      (subtractmaskfromsilk false)\n"
      "      (outputformat 1)\n      (mirror false)\n      (drillshape 1)\n"
      "      (scaleselection 1)\n      (outputdirectory \"\")\n    )\n  )\n")
    w('  (net 0 "")\n')
    for n, i in ids.items():
        w('  (net %d "%s")\n' % (i, n))
    w('  (net_class Default "This is the default net class."\n'
      "    (clearance 0.25)\n    (trace_width 0.3)\n    (via_dia 0.6)\n"
      "    (via_drill 0.3)\n    (uvia_dia 0.3)\n    (uvia_drill 0.1)\n")
    for n in ids:
        if n not in POWER_NETS:
            w('    (add_net "%s")\n' % n)
    w("  )\n")
    w('  (net_class Power "Power rails, 1 mm tracks"\n'
      "    (clearance 0.25)\n    (trace_width 1)\n    (via_dia 0.8)\n"
      "    (via_drill 0.4)\n    (uvia_dia 0.3)\n    (uvia_drill 0.1)\n")
    for n in POWER_NETS:
        w('    (add_net "%s")\n' % n)
    w("  )\n")
    for i, part in enumerate(design.PARTS):
        w(_module(i, part, ids))
    for x0, y0, x1, y1 in ((0, 0, BOARD_W, 0), (BOARD_W, 0, BOARD_W, BOARD_H),
                           (BOARD_W, BOARD_H, 0, BOARD_H), (0, BOARD_H, 0, 0)):
        w("  (gr_line (start %s %s) (end %s %s) (layer Edge.Cuts) (width 0.15))\n"
          % (_fmt(x0), _fmt(y0), _fmt(x1), _fmt(y1)))
    for text, x, y, size, ang in texts:
        w('  (gr_text "%s" (at %s %s%s) (layer F.SilkS)\n    %s\n  )\n'
          % (text, _fmt(x), _fmt(y), (" %d" % ang) if ang else "",
             _effects(size, 0.15 if size >= 1 else 0.12)))
    w(_zone("F.Cu", ids, 1))
    w(_zone("B.Cu", ids, 2))
    w(")\n")
    return "".join(out)


def write(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("ParkQ_Gate.kicad_pcb", pcb_text().encode("utf-8"))


# ----------------------------------------------------------------------- PNG
def write_png(path, scale=14):
    from PIL import Image, ImageDraw, ImageFont
    margin = 3 * scale
    W = int(BOARD_W * scale + 2 * margin)
    H = int(BOARD_H * scale + 2 * margin)
    img = Image.new("RGB", (W, H), (28, 30, 34))
    d = ImageDraw.Draw(img)

    def px(x, y):
        return margin + x * scale, margin + y * scale

    def font(size_mm):
        size = max(8, int(size_mm * scale * 1.15))
        for name in ("arial.ttf", "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                pass
        return ImageFont.load_default(size=size)

    d.rectangle([px(0, 0), px(BOARD_W, BOARD_H)], fill=(18, 92, 52),
                outline=(240, 220, 90), width=3)
    silk = (235, 235, 235)
    for part in design.PARTS:
        for g in footprints.graphics(part.footprint):
            if g[0] == "line":
                a = _rot(g[1], g[2], part.rot)
                b = _rot(g[3], g[4], part.rot)
                d.line([px(part.x_mm + a[0], part.y_mm + a[1]),
                        px(part.x_mm + b[0], part.y_mm + b[1])], fill=silk, width=2)
            else:
                c = _rot(g[1], g[2], part.rot)
                cx, cy = part.x_mm + c[0], part.y_mm + c[1]
                d.ellipse([px(cx - g[3], cy - g[3]), px(cx + g[3], cy + g[3])],
                          outline=silk, width=2)
    gold = (212, 175, 55)
    for ref, p, net in placed_pads():
        x0, y0 = px(p.x - p.w / 2, p.y - p.h / 2)
        x1, y1 = px(p.x + p.w / 2, p.y + p.h / 2)
        if p.num == "":
            pass
        elif p.shape == "rect":
            d.rectangle([x0, y0, x1, y1], fill=gold)
        elif p.shape == "oval":
            d.rounded_rectangle([x0, y0, x1, y1], radius=min(x1 - x0, y1 - y0) / 2,
                                fill=gold)
        else:
            d.ellipse([x0, y0, x1, y1], fill=gold)
        r = p.drill / 2
        d.ellipse([px(p.x - r, p.y - r), px(p.x + r, p.y + r)], fill=(10, 10, 10))
    for part in design.PARTS:
        if part.ref in HIDE_REF:
            continue
        x, y = ref_pos(part)
        d.text(px(x, y), part.ref, fill=(255, 245, 160), font=font(0.9), anchor="mm")
    for text, x, y, size, _ang in labels():
        d.text(px(x, y), text, fill=silk, font=font(size), anchor="mm")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


if __name__ == "__main__":
    target = HERE / "build" / "ParkQ_Gate_PCB.zip"
    write(target)
    print("wrote", target)
