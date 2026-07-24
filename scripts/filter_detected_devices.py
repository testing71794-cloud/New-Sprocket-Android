#!/usr/bin/env python3
"""Rewrite detected_devices.txt to Samsung-only serials (see utils/device_filter.py)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from utils.device_filter import describe_rejected_devices, require_samsung_devices  # noqa: E402


def main() -> int:
    path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else REPO / "detected_devices.txt"
    if not path.is_file():
        print(f"[filter_detected_devices] missing file: {path}", file=sys.stderr)
        return 0
    raw = path.read_text(encoding="utf-8", errors="replace").splitlines()
    serials = [ln.strip() for ln in raw if ln.strip() and not ln.strip().startswith("#")]
    if not serials:
        print("[filter_detected_devices] no serials in file — skip")
        return 0
    try:
        kept = require_samsung_devices(serials)
    except RuntimeError as exc:
        print(f"[filter_detected_devices] ERROR: {exc}", file=sys.stderr)
        path.write_text("", encoding="utf-8")
        return 1
    dropped = [s for s in serials if s not in kept]
    if dropped:
        print(
            f"[filter_detected_devices] dropped non-Samsung: "
            f"{describe_rejected_devices(dropped)}"
        )
    path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    print(f"[filter_detected_devices] wrote {len(kept)} Samsung device(s) to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
