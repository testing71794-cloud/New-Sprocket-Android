"""Reach gallery via Maestro, dump hierarchy while app is open, print video markers."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SERIAL = sys.argv[1] if len(sys.argv) > 1 else "ZA222RFQ75"
MAESTRO = r"C:\Users\HP\maestro\maestro\bin\maestro.bat"
FLOW = REPO / "ATP TestCase Flows/video/subflows/_probe_gallery_hierarchy.yaml"
ADB = Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe"
OUT = REPO / "reports/gallery_at_recent.xml"


def main() -> int:
    env = os.environ.copy()
    env["JAVA_TOOL_OPTIONS"] = "-Dorg.fusesource.jansi.Ansi.disable=true -Djansi.passthrough=true"
    proc = subprocess.Popen(
        [MAESTRO, "--no-ansi", "--device", SERIAL, "test", str(FLOW), "--no-reinstall-driver"],
        cwd=str(REPO),
        env=env,
    )
    time.sleep(80)
    subprocess.run(
        [str(ADB), "-s", SERIAL, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"],
        check=False,
    )
    subprocess.run(
        [str(ADB), "-s", SERIAL, "pull", "/sdcard/window_dump.xml", str(OUT)],
        check=False,
    )
    proc.kill()
    text = OUT.read_text(encoding="utf-8", errors="ignore") if OUT.exists() else ""
    print(f"size={len(text)} sprocket={'com.hp.impulse.sprocket' in text}")
    duration_rx = re.compile(r'text="([^"]*:\d{2}[^"]*)"|content-desc="([^"]*:\d{2}[^"]*)"')
    for m in duration_rx.finditer(text):
        print("DURATION", m.group(1) or m.group(2))
    video_rx = re.compile(r'content-desc="([^"]*[Vv]ideo[^"]*)"')
    for m in video_rx.finditer(text):
        print("VIDEO_DESC", m.group(1)[:160])
    id_rx = re.compile(r'resource-id="([^"]*(?:video|Video)[^"]*)"')
    for m in id_rx.finditer(text):
        print("RESOURCE_ID", m.group(1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
