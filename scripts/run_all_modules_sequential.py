"""Re-run ATP modules after setup fix; continue after failures."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Full sheet coverage: setup-fixed modules first, then pending, skip printing.
MODULES = [
    "settings",
    "home",
    "splash",
    "onboarding",
    "onboarding-splash",
    "video",
    "photo-id",
    "photobooth",
    "tile-print",
    "custom-sdk",
    "precut",
    "collage",
    "quick-print",
    "signup",
    "login",
    "signup-later",
    "permission",
    "gallery",
    "general",
    "alerts",
    "ai",
    "firmware",
    "connection",
]


def main() -> int:
    device = sys.argv[1] if len(sys.argv) > 1 else "ZA222RFQ75"
    maestro = sys.argv[2] if len(sys.argv) > 2 else r"C:\Users\HP\maestro\maestro\bin\maestro.bat"
    start = sys.argv[3] if len(sys.argv) > 3 else MODULES[0]
    if start in MODULES:
        mods = MODULES[MODULES.index(start) :]
    else:
        mods = MODULES
    for mod in mods:
        print(f"\n########## START MODULE {mod} ##########\n", flush=True)
        rc = subprocess.call(
            [
                sys.executable,
                "-u",
                str(REPO / "scripts" / "run_atp_module_verify.py"),
                "--module",
                mod,
                "--device",
                device,
                "--maestro",
                maestro,
                "--timeout",
                "300",
            ],
            cwd=str(REPO),
        )
        print(f"\n########## END MODULE {mod} rc={rc} ##########\n", flush=True)
        index = REPO / "reports" / "module_runs" / "index.json"
        if index.exists():
            data = json.loads(index.read_text(encoding="utf-8"))
            overall = {
                "modules_completed": len(data),
                "total_flows": sum(x.get("total", 0) for x in data),
                "passed": sum(x.get("passed", 0) for x in data),
                "failed": sum(x.get("failed", 0) for x in data),
            }
            (REPO / "reports" / "module_runs" / "overall.json").write_text(
                json.dumps(overall, indent=2), encoding="utf-8"
            )
            print("OVERALL", overall, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
