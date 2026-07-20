"""Add '# ATP Test Case ID: XX_NN' as first line on Sprocket ATP top-level flows."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "ATP TestCase Flows"

PREFIXES = {
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
    updated = 0
    for folder, prefix in PREFIXES.items():
        d = ROOT / folder
        if not d.is_dir():
            continue
        pat = re.compile(rf"^{prefix}_(\d+)", re.I)
        for p in sorted(d.glob("*.yaml")):
            m = pat.match(p.name) or pat.match(p.stem)
            if not m:
                continue
            tid = f"{prefix}_{m.group(1)}"
            text = p.read_text(encoding="utf-8")
            marker = f"# ATP Test Case ID: {tid}"
            if marker in text.splitlines()[:3]:
                continue
            lines = text.splitlines(True)
            if lines and lines[0].startswith("# ATP Test Case ID:"):
                lines[0] = marker + "\n"
            else:
                lines.insert(0, marker + "\n")
            p.write_text("".join(lines), encoding="utf-8")
            updated += 1
            print(f"updated {p.relative_to(ROOT)}")
    print(f"done updated={updated}")


if __name__ == "__main__":
    main()
