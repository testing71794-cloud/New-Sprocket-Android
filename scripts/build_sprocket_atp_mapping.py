"""Build master HP Sprocket ATP mapping from on-disk top-level flows."""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "ATP TestCase Flows"
OUT = ROOT / "atp_sprocket_mapping.csv"

# ATP execution order (matches Jenkins stage order)
ORDER = [
    "splash",
    "onboarding",
    "signup",
    "login",
    "signup-later",
    "connection",
    "permission",
    "gallery",
    "quick-print",
    "collage",
]

PREFIX = {
    "splash": "SP",
    "onboarding": "ON",
    "signup": "SG",
    "login": "LO",
    "signup-later": "SL",
    "connection": "CO",
    "gallery": "GA",
    "permission": "PM",
    "quick-print": "QP",
    "collage": "COL",
}


def main() -> None:
    rows: list[dict[str, str]] = []
    for module in ORDER:
        d = ROOT / module
        if not d.is_dir():
            continue
        prefix = PREFIX[module]
        pat = re.compile(rf"^{prefix}_(\d+)", re.I)
        files = []
        for p in d.glob("*.yaml"):
            m = pat.match(p.name) or pat.match(p.stem)
            if m:
                files.append((int(m.group(1)), p, f"{prefix}_{m.group(1)}"))
        for _, p, tid in sorted(files, key=lambda x: x[0]):
            rows.append(
                {
                    "TestCaseID": tid,
                    "Module": module,
                    "FlowFile": f"{module}/{p.name}",
                    "App": "com.hp.impulse.sprocket",
                }
            )
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["TestCaseID", "Module", "FlowFile", "App"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT} rows={len(rows)}")


if __name__ == "__main__":
    main()
