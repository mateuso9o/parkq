"""Import spike: tiny 2-part design (R1, J1; nets A, B) in KiCad 5.0-era legacy
formats, zipped for EasyEDA Std import. Python stdlib only."""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "..", "build")

LIB = """EESchema-LIBRARY Version 2.4
#encoding utf-8
#
# R
#
DEF R R 0 0 N Y 1 F N
F0 "R" 80 0 50 V V C CNN
F1 "R" 0 0 50 V V C CNN
F2 "spike:R_Axial" -70 0 50 V I C CNN
F3 "" 0 0 50 H I C CNN
DRAW
S -40 100 40 -100 0 1 10 N
X ~ 1 0 150 50 D 50 50 1 1 P
X ~ 2 0 -150 50 U 50 50 1 1 P
ENDDRAW
ENDDEF
#
# CONN_01X02
#
DEF CONN_01X02 J 0 40 Y N 1 F N
F0 "J" 0 100 50 H V C CNN
F1 "CONN_01X02" 0 -150 50 H V C CNN
F2 "spike:Header_1x02" 0 0 50 H I C CNN
F3 "" 0 0 50 H I C CNN
DRAW
S -50 50 50 -100 0 1 10 N
X Pin_1 1 -200 0 150 R 50 50 1 1 P
X Pin_2 2 -200 -100 150 R 50 50 1 1 P
ENDDRAW
ENDDEF
#
#End Library
"""

# Pin connection points (schematic y is down):
#   R1  (at 4000,3000): pin1 (4000,2850), pin2 (4000,3150)
#   J1  (at 2500,3000): pin1 (2300,3000), pin2 (2300,3100)
SCH = """EESchema Schematic File Version 4
EELAYER 26 0
EELAYER END
$Descr A4 11693 8268
encoding utf-8
Sheet 1 1
Title "spike"
Date ""
Rev ""
Comp ""
Comment1 ""
Comment2 ""
Comment3 ""
Comment4 ""
$EndDescr
$Comp
L spike:R R1
U 1 1 5C000001
P 4000 3000
F 0 "R1" V 3920 3000 50  0000 C CNN
F 1 "1k" V 4000 3000 50  0000 C CNN
F 2 "spike:R_Axial" V 3930 3000 50  0001 C CNN
F 3 "" H 4000 3000 50  0001 C CNN
	1    4000 3000
	1    0    0    -1
$EndComp
$Comp
L spike:CONN_01X02 J1
U 1 1 5C000002
P 2500 3000
F 0 "J1" H 2500 3150 50  0000 C CNN
F 1 "CONN_01X02" H 2500 2850 50  0000 C CNN
F 2 "spike:Header_1x02" H 2500 3000 50  0001 C CNN
F 3 "" H 2500 3000 50  0001 C CNN
	1    2500 3000
	1    0    0    -1
$EndComp
Wire Wire Line
	2300 3000 2300 2850
Wire Wire Line
	2300 2850 4000 2850
Wire Wire Line
	2300 3100 2300 3150
Wire Wire Line
	2300 3150 4000 3150
Text Label 3000 2850 0    50   ~ 0
A
Text Label 3000 3150 0    50   ~ 0
B
$EndSCHEMATC
"""


def pcb():
    out = []
    w = out.append
    w("(kicad_pcb (version 20171130) (host pcbnew 5.0.2)\n")
    w("  (general\n    (thickness 1.6)\n    (drawings 4)\n    (tracks 0)\n"
      "    (zones 0)\n    (modules 2)\n    (nets 3)\n  )\n")
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
    w("  (setup\n    (last_trace_width 0.25)\n    (trace_clearance 0.2)\n"
      "    (zone_clearance 0.508)\n    (zone_45_only no)\n"
      "    (trace_min 0.2)\n    (via_size 0.8)\n    (via_drill 0.4)\n"
      "    (via_min_size 0.4)\n    (via_min_drill 0.3)\n"
      "    (uvia_size 0.3)\n    (uvia_drill 0.1)\n"
      "    (uvias_allowed no)\n    (uvia_min_size 0.2)\n"
      "    (uvia_min_drill 0.1)\n    (edge_width 0.15)\n"
      "    (segment_width 0.2)\n    (pcb_text_width 0.3)\n"
      "    (pcb_text_size 1.5 1.5)\n    (mod_edge_width 0.15)\n"
      "    (mod_text_size 1 1)\n    (mod_text_width 0.15)\n"
      "    (pad_size 1.524 1.524)\n    (pad_drill 0.762)\n"
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
    w('  (net 0 "")\n  (net 1 A)\n  (net 2 B)\n')
    w("  (net_class Default \"This is the default net class.\"\n"
      "    (clearance 0.2)\n    (trace_width 0.25)\n    (via_dia 0.8)\n"
      "    (via_drill 0.4)\n    (uvia_dia 0.3)\n    (uvia_drill 0.1)\n"
      "    (add_net A)\n    (add_net B)\n  )\n")

    def module(fp, ref, val, x, y, pads, tag):
        s = ["  (module spike:%s (layer F.Cu) (tedit 5C000000) (tstamp %s)\n"
             "    (at %s %s)\n" % (fp, tag, x, y)]
        s.append("    (fp_text reference %s (at 0 -2.5) (layer F.SilkS)\n"
                 "      (effects (font (size 1 1) (thickness 0.15)))\n    )\n" % ref)
        s.append("    (fp_text value %s (at 0 2.5) (layer F.Fab)\n"
                 "      (effects (font (size 1 1) (thickness 0.15)))\n    )\n" % val)
        for num, px, py, (nid, nname) in pads:
            s.append('    (pad "%s" thru_hole circle (at %s %s) (size 1.7 1.7) '
                     '(drill 1) (layers *.Cu *.Mask) (net %d "%s"))\n'
                     % (num, px, py, nid, nname))
        s.append("  )\n")
        return "".join(s)

    w(module("R_Axial", "R1", "1k", 20, 15,
             [(1, -5.08, 0, (1, "A")), (2, 5.08, 0, (2, "B"))], "5C000001"))
    w(module("Header_1x02", "J1", "CONN_01X02", 10, 15,
             [(1, 0, 0, (1, "A")), (2, 0, 2.54, (2, "B"))], "5C000002"))
    for x1, y1, x2, y2 in [(0, 0, 30, 0), (30, 0, 30, 30),
                           (30, 30, 0, 30), (0, 30, 0, 0)]:
        w("  (gr_line (start %d %d) (end %d %d) (layer Edge.Cuts) "
          "(width 0.15))\n" % (x1, y1, x2, y2))
    w(")\n")
    return "".join(out)


def write_zip(name, members):
    os.makedirs(BUILD, exist_ok=True)
    path = os.path.join(BUILD, name)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for member, text in members:
            z.writestr(member, text.encode("utf-8"))
    return path


def main():
    write_zip("spike_sch.zip", [("spike.sch", SCH), ("spike.lib", LIB)])
    write_zip("spike_pcb.zip", [("spike.kicad_pcb", pcb())])

    # self-check
    expect = {
        "spike_sch.zip": (["spike.sch", "spike.lib"],
                          "EESchema Schematic File Version 4"),
        "spike_pcb.zip": (["spike.kicad_pcb"], "(kicad_pcb (version 20171130)"),
    }
    for zname, (names, header) in expect.items():
        with zipfile.ZipFile(os.path.join(BUILD, zname)) as z:
            assert sorted(z.namelist()) == sorted(names), z.namelist()
            data = z.read(names[0])
            first = data.decode("utf-8").split("\n", 1)[0]
            assert first.startswith(header), first
            assert b"\r" not in data
    print("OK")


if __name__ == "__main__":
    main()
