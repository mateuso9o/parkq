"""Tests for the ParkQ Gate Controller design data and schematic emitter."""
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
import emit_sch  # noqa: E402

EXPECTED_GPIO = {"QR_IN_RX": 16, "QR_IN_TX": 17, "QR_OUT_RX": 32, "QR_OUT_TX": 33,
                 "SERVO_IN": 18, "SERVO_OUT": 19, "SLOT1": 34, "SLOT2": 35,
                 "SLOT3": 36, "SLOT4": 39, "LED_G": 23, "LED_R": 22, "BUZZER": 4}

ALLOWED_FOOTPRINTS = {
    "DC_Jack_5.5x2.1", "Fuse_PTC_TH", "D_DO-201AD", "CP_Radial_D8_P3.5",
    "C_Disc_P5.0", "ESP32_DevKitC_38pin", "PinHeader_1x03_P2.54",
    "PinHeader_1x04_P2.54", "R_Axial_P7.62", "LED_D5.0", "TO-92_Inline",
    "D_DO-35_P7.62", "Buzzer_12x9.5", "MountingHole_3.2mm"}


def part(ref):
    return next(p for p in design.PARTS if p.ref == ref)


def net_of(ref, pin):
    return part(ref).pins.get(pin, "")


class DesignTests(unittest.TestCase):
    def test_gpio_map_matches_spec(self):
        self.assertEqual(design.GPIO_MAP, EXPECTED_GPIO)
        u1 = part("U1")
        for sig, gpio in EXPECTED_GPIO.items():
            pin = design.devkit_pin(gpio)
            self.assertIsNotNone(pin, "no DevKit pin for GPIO%d" % gpio)
            self.assertEqual(u1.pins.get(pin), sig, "GPIO%d" % gpio)

    def test_devkit_is_one_38_pin_lcsc_part(self):
        # ESP32-DevKitC-32E (WROOM-32E, LCSC C19183942).  Not the -VE: its
        # WROVER module uses GPIO16/17 for PSRAM, and QR-IN needs them.
        u1 = part("U1")
        self.assertEqual(u1.value, "ESP32-DevKitC-32E")
        self.assertEqual(u1.footprint, "ESP32_DevKitC_38pin")
        self.assertEqual(u1.lcsc, "C19183942")
        self.assertEqual(len(design.DEVKIT_PINS), 38)
        self.assertEqual([n for n, _ in design.DEVKIT_PINS],
                         [str(i) for i in range(1, 39)])
        self.assertEqual(design.DEVKIT_PINS[0][1], "3V3")
        self.assertEqual(design.DEVKIT_PINS[18][1], "5V")
        self.assertEqual(design.DEVKIT_PINS[19][1], "GND")
        self.assertEqual(design.DEVKIT_PINS[20][1], "GPIO23")
        self.assertEqual(design.DEVKIT_ROW_PITCH_MM, 25.4)

    def test_devkit_power_pins(self):
        self.assertEqual(net_of("U1", "19"), "+5V")
        for pin in ("14", "20", "26"):
            self.assertEqual(net_of("U1", pin), "GND", pin)

    def test_no_strapping_pins(self):
        u1 = part("U1")
        for gpio in (0, 2, 5, 12, 15):
            pin = design.devkit_pin(gpio)
            if pin is not None:
                self.assertFalse(u1.pins.get(pin), "GPIO%d must be unused" % gpio)

    def test_unused_devkit_pins_not_in_nets(self):
        u1 = part("U1")
        for num, _ in design.DEVKIT_PINS:
            if not u1.pins.get(num):
                for members in design.NETS().values():
                    self.assertNotIn(("U1", num), members)
        self.assertNotIn("", design.NETS())

    def test_qr_rx_through_series_resistor(self):
        for hdr, esp_rx, esp_tx in (("J_QR_IN", "QR_IN_RX", "QR_IN_TX"),
                                    ("J_QR_OUT", "QR_OUT_RX", "QR_OUT_TX")):
            reader_tx = net_of(hdr, "3")   # reader TX -> ESP RX
            reader_rx = net_of(hdr, "4")   # reader RX <- ESP TX
            self.assertNotEqual(reader_tx, esp_rx)
            self.assertNotEqual(reader_rx, esp_tx)
            for a, b in ((reader_tx, esp_rx), (reader_rx, esp_tx)):
                joined = [r for r in design.PARTS if r.ref.startswith("R")
                          and set(r.pins.values()) == {a, b}]
                self.assertEqual(len(joined), 1, hdr)
                self.assertEqual(joined[0].value, "1k")

    def test_optional_divider_dnp(self):
        for ref, esp_rx in (("R5", "QR_IN_RX"), ("R6", "QR_OUT_RX")):
            r = part(ref)
            self.assertEqual(r.value, "2k DNP")
            self.assertEqual(set(r.pins.values()), {esp_rx, "GND"})

    def test_refs_unique_and_sequential_resistors(self):
        refs = [p.ref for p in design.PARTS]
        self.assertEqual(len(refs), len(set(refs)))
        nums = sorted(int(r[1:]) for r in refs if re.fullmatch(r"R\d+", r))
        self.assertEqual(nums, list(range(1, len(nums) + 1)))
        self.assertEqual(len(nums), 10)

    def test_every_net_has_two_pins(self):
        for net, members in design.NETS().items():
            self.assertGreaterEqual(len(members), 2, net)

    def test_ir_sensors_on_3v3(self):
        for i in range(1, 5):
            hdr = "J_SLOT%d" % i
            self.assertEqual(net_of(hdr, "1"), "+3V3")
            self.assertEqual(net_of(hdr, "2"), "GND")
            self.assertEqual(net_of(hdr, "3"), "SLOT%d" % i)
        self.assertEqual(net_of("U1", "1"), "+3V3")

    def test_servos_on_5v(self):
        for hdr, sig in (("J_SERVO_IN", "SERVO_IN"), ("J_SERVO_OUT", "SERVO_OUT")):
            self.assertEqual(net_of(hdr, "1"), "GND")
            self.assertEqual(net_of(hdr, "2"), "+5V")
            self.assertEqual(net_of(hdr, "3"), sig)

    def test_power_chain(self):
        self.assertEqual(part("D1").value, "1N5822")
        self.assertEqual(part("D1").footprint, "D_DO-201AD")
        self.assertEqual(net_of("J_PWR", "1"), "VIN_RAW")
        self.assertEqual(net_of("F1", "1"), "VIN_RAW")
        self.assertEqual(net_of("F1", "2"), "VIN_FUSED")
        self.assertEqual(net_of("D1", "1"), "VIN_FUSED")
        self.assertEqual(net_of("D1", "2"), "+5V")
        self.assertEqual(net_of("U1", "19"), "+5V")
        self.assertEqual(net_of("U1", "14"), "GND")
        self.assertEqual(net_of("U1", "20"), "GND")
        self.assertEqual(net_of("C1", "1"), "+5V")
        self.assertEqual(net_of("C1", "2"), "GND")

    def test_footprints_and_placement(self):
        for p in design.PARTS:
            self.assertIn(p.footprint, ALLOWED_FOOTPRINTS, p.ref)
            self.assertIn(p.rot, (0, 90, 180, 270), p.ref)
            self.assertTrue(3 <= p.x_mm <= design.BOARD_W_MM - 3, p.ref)
            self.assertTrue(3 <= p.y_mm <= design.BOARD_H_MM - 3, p.ref)
        u1 = part("U1")
        self.assertAlmostEqual(u1.x_mm, design.BOARD_W_MM / 2)
        self.assertAlmostEqual(u1.y_mm, design.BOARD_H_MM / 2)
        c1 = part("C1")
        for hdr in ("J_SERVO_IN", "J_SERVO_OUT"):
            h = part(hdr)
            self.assertLessEqual(math.hypot(c1.x_mm - h.x_mm, c1.y_mm - h.y_mm), 15)
        self.assertEqual(len([p for p in design.PARTS if p.ref.startswith("H")]), 4)

    def test_every_part_symbol_defined(self):
        for p in design.PARTS:
            self.assertIn(p.symbol, design.SYMBOLS, p.ref)
            valid = {n for n, _ in design.SYMBOLS[p.symbol].pins}
            self.assertTrue(set(p.pins) <= valid, p.ref)


class SchematicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = Path(cls.tmp.name) / "ParkQ_Gate_SCH.zip"
        emit_sch.write(path)
        with zipfile.ZipFile(path) as z:
            cls.names = sorted(z.namelist())
            cls.sch = z.read("ParkQ_Gate.sch").decode("utf-8")
            cls.lib = z.read("ParkQ_Gate.lib").decode("utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_schematic_header_and_parts(self):
        self.assertEqual(self.names, ["ParkQ_Gate.lib", "ParkQ_Gate.sch"])
        self.assertTrue(self.sch.startswith("EESchema Schematic File Version 4"))
        self.assertEqual(self.sch.split("\n")[1], "LIBS:ParkQ_Gate")
        self.assertTrue(self.sch.rstrip().endswith("$EndSCHEMATC"))
        self.assertTrue(self.lib.startswith("EESchema-LIBRARY Version 2.4"))
        self.assertNotIn("\r", self.sch + self.lib)
        self.assertEqual(self.sch.count("$Comp\n"), len(design.PARTS))
        self.assertEqual(self.sch.count("$EndComp"), len(design.PARTS))
        connected = sum(len([n for n in p.pins.values() if n]) for p in design.PARTS)
        self.assertEqual(len(re.findall(r"^Text Label ", self.sch, re.M)), connected)
        # EasyEDA Std resolves symbols by bare name only (KiCad 4 style);
        # a "nickname:symbol" reference imports with the symbol body missing.
        for p in design.PARTS:
            self.assertIn("L %s %s\n" % (p.symbol, p.ref), self.sch)
        self.assertNotIn("L ParkQ_Gate:", self.sch)
        symbols = {p.symbol for p in design.PARTS}
        for sym in symbols:
            self.assertIn("DEF %s " % sym, self.lib)
        self.assertEqual(self.lib.count("\nDEF "), len(symbols))

    def test_noconn_on_unused_pins(self):
        unused = 0
        for p in design.PARTS:
            unused += len([n for n, _ in design.SYMBOLS[p.symbol].pins
                           if not p.pins.get(n)])
        self.assertGreater(unused, 0)
        self.assertEqual(len(re.findall(r"^NoConn ~ ", self.sch, re.M)), unused)

    def test_labels_carry_net_names_on_grid(self):
        labels = re.findall(r"^Text Label (-?\d+) (-?\d+) \d+\s+\d+\s+~ 0\n(.+)$",
                            self.sch, re.M)
        names = {n for _, _, n in labels}
        self.assertEqual(names, set(design.NETS()))
        spots = set()
        for x, y, _ in labels:
            self.assertEqual(int(x) % 50, 0)
            self.assertEqual(int(y) % 50, 0)
            self.assertNotIn((x, y), spots)
            spots.add((x, y))
        wires = re.findall(r"^Wire Wire Line\n\t(-?\d+) (-?\d+) (-?\d+) (-?\d+)$",
                           self.sch, re.M)
        ends = {(a, b) for a, b, _, _ in wires} | {(c, d) for _, _, c, d in wires}
        for x, y, _ in labels:   # every label sits on a wire end
            self.assertIn((x, y), ends)

    def test_labels_are_left_justified(self):
        # EasyEDA Std shifts a right-justified (orientation 2) label left by its
        # text width on import, so it no longer touches its wire and the net
        # loses every pin. Only orientation 0 survives the import.
        orients = re.findall(r"^Text Label -?\d+ -?\d+ (\d+) ", self.sch, re.M)
        self.assertTrue(orients)
        self.assertEqual(set(orients), {"0"})

    def test_left_side_wire_runs_under_its_label(self):
        # A left-justified label on a left-side pin sits at the far end of the
        # wire with its text running back toward the pin, so the wire must be
        # at least as long as the text (about 50 mils per character).
        labels = re.findall(r"^Text Label (-?\d+) (-?\d+) \d+ .*\n(.+)$", self.sch, re.M)
        wires = re.findall(r"^Wire Wire Line\n\t(-?\d+) (-?\d+) (-?\d+) (-?\d+)$",
                           self.sch, re.M)
        by_end = {(c, d): int(a) - int(c) for a, b, c, d in wires}
        for x, y, name in labels:
            run = by_end.get((x, y))
            if run is not None and run > 0:     # wire goes left from the pin
                self.assertGreaterEqual(run, 50 * len(name), name)

    def test_no_overlapping_components(self):
        pos = re.findall(r"^P (-?\d+) (-?\d+)$", self.sch, re.M)
        self.assertEqual(len(pos), len(set(pos)))


if __name__ == "__main__":
    unittest.main()
