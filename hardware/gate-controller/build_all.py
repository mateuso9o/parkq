"""Write every ParkQ Gate Controller output into build/ (git-ignored):
ParkQ_Gate_SCH.zip, ParkQ_Gate_PCB.zip, ParkQ_Gate_ALL.zip, ParkQ_Gate_layout.png."""
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import emit_pcb  # noqa: E402
import emit_sch  # noqa: E402


def main(out_dir=None):
    out = Path(out_dir) if out_dir else HERE / "build"
    out.mkdir(parents=True, exist_ok=True)
    emit_sch.write(out / "ParkQ_Gate_SCH.zip")
    emit_pcb.write(out / "ParkQ_Gate_PCB.zip")
    # One zip with schematic + library + PCB: EasyEDA Std imports it as a
    # single project with both documents (recommended import path).
    with zipfile.ZipFile(out / "ParkQ_Gate_ALL.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for part in ("ParkQ_Gate_SCH.zip", "ParkQ_Gate_PCB.zip"):
            with zipfile.ZipFile(out / part) as src:
                for name in src.namelist():
                    z.writestr(name, src.read(name))
    names = ["ParkQ_Gate_SCH.zip", "ParkQ_Gate_PCB.zip", "ParkQ_Gate_ALL.zip"]
    try:
        emit_pcb.write_png(out / "ParkQ_Gate_layout.png")
        names.append("ParkQ_Gate_layout.png")
    except ImportError:
        print("pip install pillow to also get the layout preview")
    for name in names:
        print("wrote", out / name)


if __name__ == "__main__":
    main()
