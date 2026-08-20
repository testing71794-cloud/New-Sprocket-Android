"""Local helper for Quick Print Maestro flows.

Maestro JS (sandboxed) calls these HTTP endpoints:
  GET /health
  GET /toast?expect=present|absent&serial=
  GET /toast/arm?expect=present&serial=   (start burst capture in background)
  GET /toast/result
  GET /ocr?needle=comma,needles&serial=&seconds=
  GET /ocr/arm?needle=&seconds=&serial=   (burst capture in background)
  GET /ocr/result
  GET /select-until?want=10&kind=photos&serial=
  GET /select-one?serial=
  GET /peek-unselected?serial=
  GET /tap-xy?x=&y=&serial=
  GET /tap-unselected?serial=
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


def swipe_grid(serial: str) -> None:
    w, h = screen_size(serial)
    x = w // 2
    y1 = int(h * 0.70)
    y2 = int(h * 0.38)
    adb(
        serial,
        "shell",
        "input",
        "swipe",
        str(x),
        str(y1),
        str(x),
        str(y2),
        "320",
        timeout=10,
    )
    log(f"swipe grid {x},{y1} -> {x},{y2}")


def _node_blob(node: ET.Element) -> str:
    return f"{node.attrib.get('content-desc') or ''} {node.attrib.get('text') or ''}".strip()


def parse_selection_counts(root: ET.Element) -> tuple[int, int, str]:
    """Return (photos, videos, count_label) from Select Mode footer."""
    best = ""
    for node in root.iter():
        blob = _node_blob(node)
        if re.search(r"\bSelected\b", blob, re.I) and re.search(
            r"\d+\s*(Photo|Video)", blob, re.I
        ):
            if len(blob) > len(best):
                best = blob
    photos = 0
    videos = 0
    if best:
        m = re.search(r"(\d+)\s*Photos?", best, re.I)
        if m:
            photos = int(m.group(1))
        m = re.search(r"(\d+)\s*Videos?", best, re.I)
        if m:
            videos = int(m.group(1))
    return photos, videos, best


def _is_play_overlay(parent: tuple[int, int, int, int], child: tuple[int, int, int, int]) -> bool:
    px1, py1, px2, py2 = parent
    cx1, cy1, cx2, cy2 = child
    cw, ch = cx2 - cx1, cy2 - cy1
    pw, ph = px2 - px1, py2 - py1
    if pw < 200 or ph < 200:
        return False
    if cw > 130 or ch > 130:
        return False
    return cx1 > px1 + pw * 0.45 and cy1 > py1 + ph * 0.45


def grid_media_cells(root: ET.Element, w: int, h: int) -> list[dict]:
    """Clickable gallery thumbnails in the Select Mode grid (skip chrome / scrollbar)."""
    cells: list[dict] = []
    y_min = int(h * 0.13)
    y_max = int(h * 0.86)
    for node in root.iter():
        if node.attrib.get("clickable") != "true":
            continue
        b = _bounds(node)
        if not b:
            continue
        x1, y1, x2, y2 = b
        bw, bh = x2 - x1, y2 - y1
        if bw < 220 or bh < 220:
            continue
        if y1 < y_min or y2 > y_max:
            continue
        if x1 > int(w * 0.88):
            continue
        blob = _node_blob(node)
        if re.search(
            r"(cancel|recent|print preview|select gallery|facebook|more options)",
            blob,
            re.I,
        ):
            continue
        video = bool(re.search(r"\d{1,2}:\d{2}", blob))
        for child in node.iter():
            if child is node:
                continue
            cb = _bounds(child)
            if cb and _is_play_overlay(b, cb):
                video = True
                break
        selected = bool(re.fullmatch(r"\d{1,2}", blob.strip()))
        cells.append(
            {
                "cx": (x1 + x2) // 2,
                "cy": (y1 + y2) // 2,
                "y": y1,
                "x": x1,
                "video": video,
                "selected": selected,
            }
        )
    cells.sort(key=lambda c: (c["y"], c["x"]))
    # Deduplicate overlapping dump nodes (parent View vs inner ImageView).
    uniq: list[dict] = []
    for c in cells:
        if any(abs(c["cx"] - u["cx"]) < 40 and abs(c["cy"] - u["cy"]) < 40 for u in uniq):
            # Prefer the video/selected flags if either copy has them.
            for u in uniq:
                if abs(c["cx"] - u["cx"]) < 40 and abs(c["cy"] - u["cy"]) < 40:
                    u["video"] = u["video"] or c["video"]
                    u["selected"] = u["selected"] or c["selected"]
                    break
            continue
        uniq.append(c)
    return uniq


def select_until(serial: str, want: int = 10, kind: str = "photos") -> dict:
    """Select `want` photos (deselect videos that count toward the 10-item cap)."""
    last_text = ""
    photos = videos = 0
    for step in range(32):
        root = dump_ui(serial)
        if root is None:
            return {"ok": False, "error": "ui dump failed", "step": step}
        photos, videos, last_text = parse_selection_counts(root)
        log(f"select-until step={step} photos={photos} videos={videos} text={last_text!r}")
        w, h = screen_size(serial)
        cells = grid_media_cells(root, w, h)
        if kind == "photos" and photos >= want and videos == 0:
            nxt = next((c for c in cells if not c["selected"]), None)
            if nxt is None:
                swipe_grid(serial)
                time.sleep(0.45)
                root2 = dump_ui(serial)
                if root2 is not None:
                    cells2 = grid_media_cells(root2, *screen_size(serial))
                    nxt = next((c for c in cells2 if not c["selected"]), None)
            return {
                "ok": True,
                "photos": photos,
                "videos": videos,
                "text": last_text,
                "step": step,
                "next_ok": bool(nxt),
                "next_x": nxt["cx"] if nxt else 0,
                "next_y": nxt["cy"] if nxt else 0,
            }
        if kind == "photos" and videos > 0:
            hit = next((c for c in cells if c["video"] and c["selected"]), None)
            if hit is None:
                hit = next((c for c in cells if c["video"]), None)
            if hit:
                tap_xy(serial, hit["cx"], hit["cy"])
                time.sleep(0.35)
                continue
        if kind == "photos" and photos < want:
            hit = next((c for c in cells if (not c["video"]) and (not c["selected"])), None)
            if hit:
                tap_xy(serial, hit["cx"], hit["cy"])
                time.sleep(0.35)
                continue
            swipe_grid(serial)
            time.sleep(0.55)
            continue
        swipe_grid(serial)
        time.sleep(0.55)
    return {
        "ok": False,
        "photos": photos,
        "videos": videos,
        "text": last_text,
        "error": f"did not reach {want} photos-only",
    }


def _unselected_cell(serial: str) -> dict:
    """Find one unselected grid cell without tapping (so OCR can arm first)."""
    w, h = screen_size(serial)
    for attempt in range(2):
        root = dump_ui(serial)
        if root is not None:
            cells = grid_media_cells(root, w, h)
            hit = next((c for c in cells if not c["selected"]), None)
            if hit:
                return {
                    "ok": True,
                    "video": hit["video"],
                    "x": hit["cx"],
                    "y": hit["cy"],
                    "w": w,
                    "h": h,
                }
        if attempt == 0:
            swipe_grid(serial)
            time.sleep(0.4)
    return {
        "ok": True,
        "fallback": True,
        "x": int(w * 0.82),
        "y": int(h * 0.68),
        "w": w,
        "h": h,
    }


def tap_unselected(serial: str) -> dict:
    """Tap one more unselected grid cell (11th item / max-limit toast)."""
    hit = _unselected_cell(serial)
    tap_xy(serial, int(hit["x"]), int(hit["y"]))
    hit["tapped"] = True
    return hit


def select_one(serial: str) -> dict:
    """Select one more photo, or undo a selected video. Swipe if the row is full."""
    root = dump_ui(serial)
    if root is None:
        return {"ok": False, "error": "ui dump failed"}
    photos, videos, last_text = parse_selection_counts(root)
    w, h = screen_size(serial)
    cells = grid_media_cells(root, w, h)
    if photos >= 10 and videos == 0:
        return {
            "ok": True,
            "done": True,
            "photos": photos,
            "videos": videos,
            "text": last_text,
        }
    if videos > 0:
        hit = next((c for c in cells if c["video"] and c["selected"]), None)
        if hit is None:
            hit = next((c for c in cells if c["video"]), None)
        if hit:
            tap_xy(serial, hit["cx"], hit["cy"])
            return {
                "ok": True,
                "action": "deselect-video",
                "photos": photos,
                "videos": videos,
                "text": last_text,
            }
    hit = next((c for c in cells if (not c["video"]) and (not c["selected"])), None)
    if hit:
        tap_xy(serial, hit["cx"], hit["cy"])
        return {
            "ok": True,
            "action": "select-photo",
            "photos": photos,
            "videos": videos,
            "text": last_text,
        }
    swipe_grid(serial)
    return {
        "ok": True,
        "action": "swipe",
        "photos": photos,
        "videos": videos,
        "text": last_text,
    }


def _run_armed_ocr(serial: str, needles: list[str], seconds: float) -> None:
    ok, found, text = burst_ocr(
        serial, needles, seconds=max(1.0, seconds), prefix="qp_ocr"
    )
    with _TOAST_LOCK:
        _TOAST_JOB["payload"] = {
            "ok": ok,
            "found": found,
            "text": (text or "")[:400],
        }


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
            if u.path == "/ocr/arm":
                raw = (q.get("needle") or ["maximum of 10"])[0]
                needles = [n.strip() for n in raw.split(",") if n.strip()]
                seconds = float((q.get("seconds") or ["5"])[0])
                with _TOAST_LOCK:
                    prev = _TOAST_JOB.get("thread")
                    _TOAST_JOB["payload"] = None
                if prev is not None and prev.is_alive():
                    prev.join(timeout=1)
                t = threading.Thread(
                    target=_run_armed_ocr,
                    args=(serial, needles, seconds),
                    daemon=True,
                )
                with _TOAST_LOCK:
                    _TOAST_JOB["thread"] = t
                t.start()
                self._json(200, {"ok": True, "armed": True, "needles": needles})
                return
            if u.path == "/ocr/result":
                with _TOAST_LOCK:
                    t = _TOAST_JOB.get("thread")
                if t is not None:
                    t.join(timeout=40)
                with _TOAST_LOCK:
                    payload = _TOAST_JOB.get("payload")
                if not payload:
                    self._json(
                        200,
                        {"ok": False, "found": False, "error": "no ocr job"},
                    )
                    return
                self._json(200, payload)
                return
            if u.path == "/ocr":
                raw = (q.get("needle") or ["select mode"])[0]
                needles = [n.strip() for n in raw.split(",") if n.strip()]
                seconds = float((q.get("seconds") or ["4"])[0])
                expect = (q.get("expect") or ["present"])[0]
                if expect == "present":
                    ok, found, text = burst_ocr(
                        serial, needles, seconds=seconds, prefix="qp_ocr"
                    )
                else:
                    ok, found, text = poll_ocr(
                        serial,
                        needles,
                        expect_present=False,
                        seconds=seconds,
                        prefix="qp_ocr",
                    )
                self._json(200, {"ok": ok, "found": found, "text": text[:400]})
                return
            if u.path == "/select-until":
                want = int((q.get("want") or ["10"])[0])
                kind = (q.get("kind") or ["photos"])[0]
                self._json(200, select_until(serial, want=want, kind=kind))
                return
            if u.path == "/select-one":
                self._json(200, select_one(serial))
                return
            if u.path == "/peek-unselected":
                self._json(200, _unselected_cell(serial))
                return
            if u.path == "/tap-xy":
                x = int((q.get("x") or ["0"])[0] or "0")
                y = int((q.get("y") or ["0"])[0] or "0")
                if x <= 0 or y <= 0:
                    w, h = screen_size(serial)
                    x, y = int(w * 0.82), int(h * 0.68)
                tap_xy(serial, x, y)
                self._json(200, {"ok": True, "x": x, "y": y})
                return
            if u.path == "/tap-unselected":
                self._json(200, tap_unselected(serial))
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
