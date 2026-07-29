"""Dump gallery UI hierarchy and list nodes that distinguish videos from photos."""
from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "ATP Verification Suite" / "lib"))
from hierarchy import Hierarchy  # noqa: E402

SERIAL = sys.argv[1] if len(sys.argv) > 1 else "ZA222RFQ75"
APP = "com.hp.impulse.sprocket"
ADB = (
    Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe"
).as_posix()
if not Path(ADB).exists():
    ADB = "adb"


def adb(*args: str) -> None:
    subprocess.run(
        [ADB, "-s", SERIAL, *args],
        check=False,
        capture_output=True,
    )


def main() -> int:
    adb("shell", "am", "force-stop", APP)
    time.sleep(1)
    adb(
        "shell",
        "monkey",
        "-p",
        APP,
        "-c",
        "android.intent.category.LAUNCHER",
        "1",
    )
    time.sleep(8)
    h = Hierarchy(SERIAL, repo_root=REPO)
    if not h.refresh(retries=3):
        print("ERROR: hierarchy dump failed")
        return 1

    duration_rx = re.compile(r"\d+:\d{2}")
    video_rx = re.compile(r"video|play|duration", re.I)

    print(f"nodes={len(h.nodes)} package={APP}")
    print("\n=== Duration-like nodes (mm:ss) ===")
    for n in h.nodes:
        blob = f"{n.text} {n.content_desc}".strip()
        if duration_rx.search(blob):
            print(
                f"text={n.text!r} desc={n.content_desc!r} "
                f"click={n.clickable} bounds={n.bounds}"
            )

    print("\n=== Video/play keyword nodes ===")
    for n in h.nodes:
        blob = f"{n.text} {n.content_desc}".strip()
        if video_rx.search(blob) and blob:
            print(
                f"text={n.text!r} desc={n.content_desc!r} "
                f"click={n.clickable} bounds={n.bounds}"
            )

    out = REPO / "reports" / "gallery_hierarchy_latest.xml"
    out.write_text(h.raw, encoding="utf-8", errors="ignore")
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
