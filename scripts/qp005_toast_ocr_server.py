"""Local helper for Quick Print Maestro flows.

Maestro JS (sandboxed) calls these HTTP endpoints:
  GET /health
  GET /toast?expect=present|absent&serial=
  GET /toast/arm?expect=present&serial=   (start burst capture in background)
  GET /toast/result
  GET /ocr?needle=comma,needles&serial=&seconds=
  GET /network?state=off|on&serial=
  GET /tap?kind=overflow|tag&serial=
  GET /revoke-photos?serial=

See: https://docs.maestro.dev/maestro-flows/javascript/make-http-requests
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parents[1]
PS1 = Path(__file__).resolve().with_name("ocr_select_mode_toast.ps1")
TOAST_NEEDLES = (
    "tap and hold",
    "select mode",
    "hold an image",
    "enter select",
    "long press",
    "long-press",
)
PORT = int(os.environ.get("QP005_OCR_PORT", "8765"))
LOG = REPO / "logs" / "qp_helper.log"
_TOAST_JOB: dict = {"thread": None, "payload": None}
_TOAST_LOCK = threading.Lock()


def adb_bin() -> str:
    home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if home:
        cand = Path(home) / "platform-tools" / "adb.exe"
        if cand.exists():
            return str(cand)
    win = Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe"
    return str(win) if win.exists() else "adb"


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{time.strftime('%H:%M:%S')} {msg}\n"
    try:
        with LOG.open("a", encoding="utf-8", errors="replace") as fh:
            fh.write(line)
    except OSError:
        pass
    sys.stderr.write("qp-helper: " + msg + "\n")


def adb(serial: str, *args: str, timeout: int = 30) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [adb_bin(), "-s", serial, *args],
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def ocr_png(image: Path, bottom_percent: int = 0) -> str:
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(PS1),
        "-ImagePath",
        str(image.resolve()),
    ]
    if bottom_percent > 0:
        cmd.extend(["-BottomPercent", str(bottom_percent)])
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    return ((p.stdout or "") + (p.stderr or "")).strip()


def has_needles(text: str, needles: tuple[str, ...] | list[str]) -> bool:
    low = " ".join(text.lower().split())
    return any(n.lower() in low for n in needles)


def grab_png(serial: str, name: str) -> tuple[bool, Path | str]:
    raw = adb(serial, "exec-out", "screencap", "-p", timeout=30)
    if raw.returncode != 0 or not raw.stdout:
        err = (raw.stderr or b"").decode("utf-8", "replace")
        return False, f"screencap failed: {err[:200]}"
    logs = REPO / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    png = logs / name
    png.write_bytes(raw.stdout)
    return True, png


def poll_ocr(
    serial: str,
    needles: tuple[str, ...] | list[str],
    *,
    expect_present: bool,
    seconds: float,
    prefix: str,
) -> tuple[bool, bool, str]:
    """Return (ok, found, text). For present, poll until found or timeout."""
    deadline = time.time() + max(0.2, seconds)
    last_text = ""
    found = False
    attempt = 0
    while True:
        attempt += 1
        ok_grab, png_or_err = grab_png(serial, f"{prefix}_{serial}.png")
        if not ok_grab:
            last_text = str(png_or_err)
            if time.time() >= deadline:
                break
            time.sleep(0.2)
            continue
        png = Path(png_or_err)
        text = ocr_png(png, bottom_percent=34)
        if "OCR_ENGINE_UNAVAILABLE" in text:
            return False, False, "Windows OCR unavailable"
        last_text = text
        (REPO / "logs" / f"{prefix}_ocr_{serial}.txt").write_text(
            text, encoding="utf-8", errors="replace"
        )
        found = has_needles(text, needles)
        log(f"ocr attempt={attempt} found={found} text={text[:160]!r}")
        if expect_present and found:
            break
        if not expect_present:
            break
        if time.time() >= deadline:
            break
        time.sleep(0.15)
    if expect_present and not found:
        ok_grab, png_or_err = grab_png(serial, f"{prefix}_{serial}.png")
        if ok_grab:
            text_full = ocr_png(Path(png_or_err), bottom_percent=0)
            last_text = text_full or last_text
            found = has_needles(text_full, needles)
            log(f"ocr full found={found} text={text_full[:160]!r}")
    ok = found if expect_present else (not found)
    return ok, found, last_text


def burst_ocr(
    serial: str,
    needles: tuple[str, ...] | list[str],
    *,
    seconds: float,
    prefix: str,
) -> tuple[bool, bool, str]:
    """Grab screenshots for `seconds`, then OCR until a needle hits (toast is ~5s)."""
    frames: list[Path] = []
    deadline = time.time() + max(0.5, seconds)
    n = 0
    while time.time() < deadline:
        n += 1
        ok_grab, png_or_err = grab_png(serial, f"{prefix}_b{n}_{serial}.png")
        if ok_grab:
            frames.append(Path(png_or_err))
        time.sleep(0.18)
    last_text = ""
    for png in frames:
        text = ocr_png(png, bottom_percent=45)
        last_text = text
        if "OCR_ENGINE_UNAVAILABLE" in text:
            return False, False, "Windows OCR unavailable"
        found = has_needles(text, needles)
        log(f"burst {png.name} found={found} text={text[:140]!r}")
        if found:
            return True, True, text
    if frames:
        text_full = ocr_png(frames[len(frames) // 2], bottom_percent=0)
        last_text = text_full or last_text
        found = has_needles(text_full, needles)
        log(f"burst full found={found} text={text_full[:160]!r}")
        if found:
            return True, True, text_full
    return False, False, last_text


def _run_armed_toast(serial: str, expect: str) -> None:
    if expect == "present":
        ok, found, text = burst_ocr(
            serial, TOAST_NEEDLES, seconds=6.0, prefix="qp005_toast"
        )
    else:
        ok, found, text = poll_ocr(
            serial,
            TOAST_NEEDLES,
            expect_present=False,
            seconds=0.4,
            prefix="qp005_toast",
        )
    with _TOAST_LOCK:
        _TOAST_JOB["payload"] = {
            "ok": ok,
            "found": found,
            "expect": expect,
            "text": (text or "")[:400],
        }


def set_network(serial: str, state: str) -> dict:
    if state == "off":
        cmds = [
            ["shell", "cmd", "connectivity", "airplane-mode", "enable"],
            ["shell", "settings", "put", "global", "airplane_mode_on", "1"],
            ["shell", "svc", "wifi", "disable"],
            ["shell", "svc", "data", "disable"],
        ]
    else:
        cmds = [
            ["shell", "cmd", "connectivity", "airplane-mode", "disable"],
            ["shell", "settings", "put", "global", "airplane_mode_on", "0"],
            ["shell", "svc", "wifi", "enable"],
            ["shell", "svc", "data", "enable"],
        ]
    details = []
    for c in cmds:
        p = adb(serial, *c, timeout=20)
        details.append(f"{' '.join(c)} rc={p.returncode}")
    log(f"network {state}: {details}")
    return {"ok": True, "state": state, "details": details}


def revoke_photos(serial: str) -> dict:
    perms = [
        "android.permission.READ_MEDIA_IMAGES",
        "android.permission.READ_MEDIA_VIDEO",
        "android.permission.READ_MEDIA_VISUAL_USER_SELECTED",
        "android.permission.READ_EXTERNAL_STORAGE",
        "android.permission.WRITE_EXTERNAL_STORAGE",
    ]
    for perm in perms:
        adb(serial, "shell", "pm", "revoke", "com.hp.impulse.sprocket", perm, timeout=15)
    log(f"revoked photos on {serial}")
    return {"ok": True}


def _bounds(node: ET.Element) -> tuple[int, int, int, int] | None:
    raw = node.attrib.get("bounds") or ""
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", raw)
    if not m:
        return None
    x1, y1, x2, y2 = map(int, m.groups())
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def dump_ui(serial: str) -> ET.Element | None:
    remote = "/data/local/tmp/qp_uidump.xml"
    p = adb(serial, "shell", "uiautomator", "dump", remote, timeout=25)
    if p.returncode != 0:
        p = adb(serial, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml", timeout=25)
        remote = "/sdcard/window_dump.xml"
    pulled = REPO / "logs" / f"qp_uidump_{serial}.xml"
    pulled.parent.mkdir(parents=True, exist_ok=True)
    adb(serial, "pull", remote, str(pulled), timeout=20)
    if not pulled.exists():
        return None
    try:
        return ET.parse(pulled).getroot()
    except ET.ParseError:
        return None


def screen_size(serial: str) -> tuple[int, int]:
    p = adb(serial, "shell", "wm", "size", timeout=10)
    text = (p.stdout or b"").decode("utf-8", "replace")
    m = re.search(r"(\d+)x(\d+)", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 1080, 2400


def tap_xy(serial: str, x: int, y: int) -> None:
    adb(serial, "shell", "input", "tap", str(x), str(y), timeout=10)
    log(f"tap {x},{y}")


def tap_kind(serial: str, kind: str) -> dict:
    root = dump_ui(serial)
    w, h = screen_size(serial)
    if root is None:
        if kind == "overflow":
            tap_xy(serial, int(w * 0.94), int(h * 0.07))
        else:
            tap_xy(serial, int(w * 0.88), int(h * 0.88))
        return {"ok": True, "fallback": True, "kind": kind}

    overflow_re = re.compile(r"(more options|more option|overflow|unlink|overflow menu)", re.I)
    tag_re = re.compile(r"(tag|hashtag|#)", re.I)
    hits: list[tuple[int, int, int, str]] = []
    right_bar: list[tuple[int, int, int]] = []

    for node in root.iter():
        desc = node.attrib.get("content-desc") or ""
        text = node.attrib.get("text") or ""
        blob = f"{desc} {text}".strip()
        b = _bounds(node)
        if not b:
            continue
        x1, y1, x2, y2 = b
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        clickable = node.attrib.get("clickable") == "true"
        if kind == "overflow" and blob and overflow_re.search(blob):
            hits.append((cx, cy, x1, blob))
        if kind == "tag" and blob and tag_re.search(blob) and cy > int(h * 0.7):
            hits.append((cx, cy, x1, blob))
        if kind == "overflow" and clickable and cy < int(h * 0.14) and cx > int(w * 0.72):
            right_bar.append((cx, cy, x1))

    if hits:
        hits.sort(key=lambda t: t[2], reverse=True)
        tap_xy(serial, hits[0][0], hits[0][1])
        return {"ok": True, "via": "desc", "label": hits[0][3], "kind": kind}
    if kind == "overflow" and right_bar:
        right_bar.sort(key=lambda t: t[0], reverse=True)
        tap_xy(serial, right_bar[0][0], right_bar[0][1])
        return {"ok": True, "via": "top-right", "kind": kind}
    if kind == "overflow":
        tap_xy(serial, int(w * 0.94), int(h * 0.07))
    else:
        tap_xy(serial, int(w * 0.88), int(h * 0.88))
    return {"ok": True, "fallback": True, "kind": kind}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        sys.stderr.write("qp-helper: " + (fmt % args) + "\n")

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        q = parse_qs(u.query)
        serial = (q.get("serial") or [os.environ.get("ANDROID_SERIAL", "")])[0]
        if u.path in ("/health", "/"):
            self._json(200, {"ok": True})
            return
        if not serial and u.path != "/health":
            self._json(400, {"ok": False, "error": "serial required"})
            return
        try:
            if u.path == "/toast/arm":
                expect = (q.get("expect") or ["present"])[0]
                with _TOAST_LOCK:
                    prev = _TOAST_JOB.get("thread")
                    _TOAST_JOB["payload"] = None
                if prev is not None and prev.is_alive():
                    prev.join(timeout=1)
                t = threading.Thread(
                    target=_run_armed_toast,
                    args=(serial, expect),
                    daemon=True,
                )
                with _TOAST_LOCK:
                    _TOAST_JOB["thread"] = t
                t.start()
                self._json(200, {"ok": True, "armed": True, "expect": expect})
                return
            if u.path == "/toast/result":
                with _TOAST_LOCK:
                    t = _TOAST_JOB.get("thread")
                if t is not None:
                    t.join(timeout=40)
                with _TOAST_LOCK:
                    payload = _TOAST_JOB.get("payload")
                if not payload:
                    self._json(
                        200,
                        {"ok": False, "found": False, "error": "no toast job"},
                    )
                    return
                self._json(200, payload)
                return
            if u.path == "/toast":
                expect = (q.get("expect") or ["present"])[0]
                seconds = 10.0 if expect == "present" else 0.4
                ok, found, text = poll_ocr(
                    serial,
                    TOAST_NEEDLES,
                    expect_present=(expect == "present"),
                    seconds=seconds,
                    prefix="qp005_toast",
                )
                self._json(200, {"ok": ok, "found": found, "expect": expect, "text": text[:400]})
                return
            if u.path == "/ocr":
                raw = (q.get("needle") or ["select mode"])[0]
                needles = [n.strip() for n in raw.split(",") if n.strip()]
                seconds = float((q.get("seconds") or ["4"])[0])
                expect = (q.get("expect") or ["present"])[0]
                ok, found, text = poll_ocr(
                    serial,
                    needles,
                    expect_present=(expect == "present"),
                    seconds=seconds,
                    prefix="qp_ocr",
                )
                self._json(200, {"ok": ok, "found": found, "text": text[:400]})
                return
            if u.path == "/network":
                state = (q.get("state") or ["on"])[0]
                self._json(200, set_network(serial, state))
                return
            if u.path == "/tap":
                kind = (q.get("kind") or ["overflow"])[0]
                self._json(200, tap_kind(serial, kind))
                return
            if u.path == "/revoke-photos":
                self._json(200, revoke_photos(serial))
                return
            self._json(404, {"ok": False, "error": "not found"})
        except Exception as exc:  # noqa: BLE001
            log(f"error {u.path}: {exc}")
            self._json(500, {"ok": False, "error": str(exc)})


def main() -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"qp helper listening on http://127.0.0.1:{PORT}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
