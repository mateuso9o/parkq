"""Write every ParkQ Gate Controller output into build/ (git-ignored):
ParkQ_Gate_SCH.zip, ParkQ_Gate_PCB.zip, ParkQ_Gate_layout.png."""
import sys
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
    emit_pcb.write_png(out / "ParkQ_Gate_layout.png")
    for name in ("ParkQ_Gate_SCH.zip", "ParkQ_Gate_PCB.zip", "ParkQ_Gate_layout.png"):
        print("wrote", out / name)


if __name__ == "__main__":
    main()
