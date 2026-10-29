"""Tests for the ParkQ Gate Controller PCB emitter."""
import math
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import design  # noqa: E402
import emit_pcb  # noqa: E402
import footprints  # noqa: E402

TEXT = emit_pcb.pcb_text()


def sexpr(text):
    """Tiny s-expression parser -> nested lists of str."""
    toks = re.findall(r'\(|\)|"[^"]*"|[^\s()"]+', text)
    stack = [[]]
    for t in toks:
        if t == "(":
            stack.append([])
        elif t == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(t.strip('"'))
    return stack[0][0]


TREE = sexpr(TEXT)


def children(tree, key):
    return [c for c in tree if isinstance(c, list) and c and c[0] == key]


def outline():
    xs, ys = [], []
    for ln in children(TREE, "gr_line"):
        layer = children(ln, "layer")[0][1]
        if layer != "Edge.Cuts":
            continue
        for k in ("start", "end"):
            c = children(ln, k)[0]
            xs.append(float(c[1]))
            ys.append(float(c[2]))
    return min(xs), min(ys), max(xs), max(ys)


def rect(pad):
    return (pad.x - pad.w / 2, pad.y - pad.h / 2,
            pad.x + pad.w / 2, pad.y + pad.h / 2)


def gap(a, b):
    dx = max(a[0] - b[2], b[0] - a[2], 0)
    dy = max(a[1] - b[3], b[1] - a[3], 0)
    return math.hypot(dx, dy)


def part(ref):
    return next(p for p in design.PARTS if p.ref == ref)


class PcbTests(unittest.TestCase):
    def test_header_version(self):
        self.assertTrue(TEXT.startswith("(kicad_pcb (version 20171130)"))

    def test_ascii_only_and_lf(self):
        TEXT.encode("ascii")
        self.assertNotIn("\r", TEXT)

    def test_board_size(self):
        x0, y0, x1, y1 = outline()
        self.assertLessEqual(x1 - x0, 100)
        self.assertLessEqual(y1 - y0, 100)
        self.assertEqual(len([ln for ln in children(TREE, "gr_line")
                              if children(ln, "layer")[0][1] == "Edge.Cuts"]), 4)

    def test_all_pads_inside_outline(self):
        x0, y0, x1, y1 = outline()
        for ref, pad, _net in emit_pcb.placed_pads():
            r = rect(pad)
            self.assertGreaterEqual(r[0] - x0, 1.0, (ref, pad.num))
            self.assertGreaterEqual(r[1] - y0, 1.0, (ref, pad.num))
            self.assertGreaterEqual(x1 - r[2], 1.0, (ref, pad.num))
            self.assertGreaterEqual(y1 - r[3], 1.0, (ref, pad.num))

    def test_no_pad_overlap_between_parts(self):
        pads = [(ref, pad) for ref, pad, _ in emit_pcb.placed_pads()
                if pad.num != ""]              # NPTH holes carry no copper
        for i, (ra, pa) in enumerate(pads):
            for rb, pb in pads[i + 1:]:
                if ra == rb:
                    continue
                self.assertGreaterEqual(
                    gap(rect(pa), rect(pb)), 0.5,
                    "%s.%s vs %s.%s" % (ra, pa.num, rb, pb.num))

    def test_every_net_on_pcb(self):
        counts = {}
        for _ref, _pad, net in emit_pcb.placed_pads():
            if net:
                counts[net] = counts.get(net, 0) + 1
        for net, pins in design.NETS().items():
            self.assertGreaterEqual(counts.get(net, 0), 2, net)
            self.assertEqual(counts[net], len(pins), net)
        # and in the emitted text itself
        in_text = re.findall(r'\(pad "[^"]*" .*?\(net \d+ "([^"]+)"\)\)', TEXT)
        self.assertEqual(len(in_text), sum(len(v) for v in design.NETS().values()))

    def test_every_pin_has_a_pad(self):
        for p in design.PARTS:
            nums = {pd.num for pd in footprints.pads(p.footprint)}
            for pin in p.pins:
                self.assertIn(pin, nums, "%s pin %s" % (p.ref, pin))

    def test_bulk_cap_near_servos(self):
        c1 = part("C1")
        for hdr in ("J_SERVO_IN", "J_SERVO_OUT"):
            pads = [pd for r, pd, _ in emit_pcb.placed_pads() if r == hdr]
            cx = sum(p.x for p in pads) / len(pads)
            cy = sum(p.y for p in pads) / len(pads)
            self.assertLessEqual(math.hypot(c1.x_mm - cx, c1.y_mm - cy), 15, hdr)

    def test_devkit_pitch(self):
        pads = {pd.num: pd for pd in footprints.pads("ESP32_DevKit_30pin")}
        self.assertEqual(len(pads), 30)
        self.assertAlmostEqual(pads["16"].x - pads["1"].x, design.DEVKIT_ROW_PITCH_MM)
        self.assertAlmostEqual(pads["30"].x - pads["15"].x, design.DEVKIT_ROW_PITCH_MM)
        self.assertAlmostEqual(pads["2"].y - pads["1"].y, 2.54)
        placed = {pd.num: pd for r, pd, _ in emit_pcb.placed_pads() if r == "U1"}
        self.assertAlmostEqual(placed["16"].x - placed["1"].x, design.DEVKIT_ROW_PITCH_MM)

    def test_net_classes(self):
        classes = {c[1]: c for c in children(TREE, "net_class")}
        self.assertIn("Default", classes)
        self.assertIn("Power", classes)
        self.assertAlmostEqual(float(children(classes["Default"], "trace_width")[0][1]), 0.3)
        self.assertAlmostEqual(float(children(classes["Default"], "clearance")[0][1]), 0.25)
        self.assertAlmostEqual(float(children(classes["Default"], "via_dia")[0][1]), 0.6)
        self.assertGreaterEqual(float(children(classes["Power"], "trace_width")[0][1]), 1.0)
        pw = {c[1] for c in children(classes["Power"], "add_net")}
        self.assertEqual(pw, {"+5V", "GND", "VIN_RAW", "VIN_FUSED"})

    def test_gnd_zones_both_layers(self):
        zones = children(TREE, "zone")
        layers = {children(z, "layer")[0][1] for z in zones}
        self.assertEqual(layers, {"F.Cu", "B.Cu"})
        for z in zones:
            self.assertEqual(children(z, "net_name")[0][1], "GND")
            pts = children(children(z, "polygon")[0], "pts")[0]
            xs = [float(c[1]) for c in pts[1:]]
            ys = [float(c[2]) for c in pts[1:]]
            x0, y0, x1, y1 = outline()
            self.assertAlmostEqual(min(xs), x0 + 0.5)
            self.assertAlmostEqual(max(ys), y1 - 0.5)

    def test_polarity_conventions(self):
        pads = {(r, pd.num): net for r, pd, net in emit_pcb.placed_pads()}
        self.assertEqual(pads[("LED1", "1")], "GND")        # cathode
        self.assertEqual(pads[("Q1", "1")], "GND")          # emitter
        self.assertEqual(pads[("BZ1", "1")], "+5V")         # buzzer +
        self.assertEqual(pads[("D1", "2")], "+5V")          # cathode on rail
        self.assertEqual(pads[("D2", "2")], "+5V")

    def test_silkscreen_labels(self):
        for label in ("SERVO-IN", "SERVO-OUT", "QR-IN", "QR-OUT", "SLOT1", "SLOT2",
                      "SLOT3", "SLOT4", "5V 2A", "ParkQ Gate Controller v1"):
            self.assertIn('(gr_text "%s"' % label, TEXT)

    def test_mounting_holes_npth(self):
        self.assertEqual(len(re.findall(r"np_thru_hole circle .*?\(size 3\.2 3\.2\) "
                                        r"\(drill 3\.2\)", TEXT)), 4)

    def test_usb_keepout_free_of_pads(self):
        u1 = part("U1")
        bottom = u1.y_mm + 25.75                      # USB end faces +y
        zone = (u1.x_mm - 6.5, bottom - 1.0, u1.x_mm + 6.5, design.BOARD_H_MM)
        for ref, pad, _net in emit_pcb.placed_pads():
            if ref == "U1":
                continue
            self.assertGreater(gap(rect(pad), zone), 0, "%s.%s in USB zone" % (ref, pad.num))

    def test_jack_pads_have_slot_drills(self):
        jack = [pd for r, pd, _ in emit_pcb.placed_pads() if r == "J_PWR"]
        self.assertTrue(all(p.slot and max(p.slot) >= 3.0 for p in jack))
        self.assertEqual(len(re.findall(r"\(drill oval 1 3\)", TEXT)), 2)
        self.assertEqual(len(re.findall(r"\(drill oval 3 1\)", TEXT)), 1)

    def test_balanced_parens(self):
        self.assertEqual(TEXT.count("("), TEXT.count(")"))

    def test_build_all_writes_outputs(self):
        import build_all
        with tempfile.TemporaryDirectory() as d:
            build_all.main(Path(d))
            for name in ("ParkQ_Gate_SCH.zip", "ParkQ_Gate_PCB.zip",
                         "ParkQ_Gate_layout.png"):
                self.assertTrue((Path(d) / name).stat().st_size > 1000, name)
            with zipfile.ZipFile(Path(d) / "ParkQ_Gate_PCB.zip") as z:
                self.assertEqual(z.namelist(), ["ParkQ_Gate.kicad_pcb"])
                self.assertTrue(z.read("ParkQ_Gate.kicad_pcb").decode("ascii")
                                .startswith("(kicad_pcb (version 20171130)"))
            self.assertEqual((Path(d) / "ParkQ_Gate_layout.png").read_bytes()[:4],
                             b"\x89PNG")


if __name__ == "__main__":
    unittest.main()
