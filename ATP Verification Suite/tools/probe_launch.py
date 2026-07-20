"""Probe current UI after launching Sprocket."""
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.hierarchy import Hierarchy

ADB = Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe"
SERIAL = sys.argv[1] if len(sys.argv) > 1 else "ZA222RFQ75"
APP = "com.hp.impulse.sprocket"


def adb(*args):
    return subprocess.run([str(ADB), "-s", SERIAL, *args], capture_output=True, text=True)


print("path:", adb("shell", "pm", "path", APP).stdout.strip())
print("clear:", adb("shell", "pm", "clear", APP).stdout.strip())
time.sleep(1)
print("launch:", adb("shell", "monkey", "-p", APP, "-c", "android.intent.category.LAUNCHER", "1").stdout.strip())
time.sleep(10)
h = Hierarchy(SERIAL, adb=str(ADB), repo_root=ROOT)
print("refresh", h.refresh(), "nodes", len(h.nodes))
for n in h.nodes:
    t = n.text or n.content_desc
    if t:
        print(" -", t[:120])
focus = adb("shell", "dumpsys", "window", "windows")
for line in focus.stdout.splitlines():
    if "mCurrentFocus" in line or "mFocusedApp" in line:
        print(line.strip())
