"""Local helper for Quick Print Maestro flows.

Maestro JS (sandboxed) calls these HTTP endpoints:
  GET /health
  GET /toast?expect=present|absent&serial=
  GET /toast/arm?expect=present&serial=   (start burst capture in background)
  GET /toast/result
  GET /ocr?needle=comma,needles&serial=&seconds=
  GET /ocr/arm?needle=&seconds=&serial=   (burst capture in background)
  GET /ocr/result
  GET /select-until?want=10&kind=photos|mixed|any&serial=
  GET /select-one?serial=
  GET /peek-unselected?serial=
  GET /tap-xy?x=&y=&serial=
  GET /tap-max-limit?serial=&seconds=
  GET /tap-unselected?serial=
  GET /network?state=off|on&serial=
  GET /tap?kind=overflow|tag&serial=
  GET /revoke-photos?serial=
  GET /ensure-empty-album?serial=

See: https://docs.maestro.dev/maestro-flows/javascript/make-http-requests
"""
from __future__ import annotations

import json
import os
import re
import struct
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np

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
SPROCKET_PKG = "com.hp.impulse.sprocket"
_TOAST_JOB: dict = {"thread": None, "payload": None}
_TOAST_LOCK = threading.Lock()
_QP_LATTICE_I: dict[str, int] = {}
_QP_LAST_XY: dict[str, tuple[int, int]] = {}
_QP_SKIP_DUMP: set[str] = set()
_SCREEN_SIZE: dict[str, tuple[int, int]] = {}
_OCR_PROC: subprocess.Popen[str] | None = None
_OCR_LOCK = threading.Lock()


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


def _start_ocr_worker() -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PS1),
            "-Loop",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )


def ocr_via_worker(image: Path, bottom_percent: int = 0) -> str:
    global _OCR_PROC
    line = f"{image.resolve()}|{int(bottom_percent)}\n"
    with _OCR_LOCK:
        proc = _OCR_PROC
        if proc is None or proc.poll() is not None:
            proc = _start_ocr_worker()
            _OCR_PROC = proc
        assert proc.stdin is not None and proc.stdout is not None
        try:
            proc.stdin.write(line)
            proc.stdin.flush()
            out = proc.stdout.readline().strip()
        except OSError:
            proc = _start_ocr_worker()
            _OCR_PROC = proc
            assert proc.stdin is not None and proc.stdout is not None
            proc.stdin.write(line)
            proc.stdin.flush()
            out = proc.stdout.readline().strip()
        return out


def ocr_png(image: Path, bottom_percent: int = 0) -> str:
    return ocr_via_worker(image, bottom_percent)


def write_bmp_rgb(path: Path, rgb: np.ndarray) -> None:
    rgb = np.ascontiguousarray(rgb[:, :, :3], dtype=np.uint8)
    h, w = rgb.shape[:2]
    bgr = np.ascontiguousarray(rgb[:, :, ::-1])
    row_bytes = (w * 3 + 3) & ~3
    padded = np.zeros((h, row_bytes), dtype=np.uint8)
    padded[:, : w * 3] = bgr.reshape(h, w * 3)
    pixel = np.flipud(padded).tobytes()
    header = struct.pack("<2sIHHI", b"BM", 54 + len(pixel), 0, 0, 54)
    dib = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(pixel), 0, 0, 0, 0)
    path.write_bytes(header + dib + pixel)


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
    """Grab+OCR until a needle hits. Toast is short-lived; do not batch-then-OCR."""
    deadline = time.time() + max(0.4, seconds)
    last_text = ""
    n = 0
    while time.time() < deadline:
        n += 1
        text = ocr_band(serial, y0_frac=0.52, y1_frac=0.92, name=f"{prefix}_b{n}_{serial}.bmp")
        last_text = text
        if "OCR_ENGINE_UNAVAILABLE" in text:
            return False, False, "Windows OCR unavailable"
        found = has_needles(text, needles)
        log(f"burst n={n} found={found} text={text[:140]!r}")
        if found:
            return True, True, text
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


def ensure_empty_album(serial: str) -> dict:
    """Empty Pictures/MaestroEmpty folder for QP_015 No Photos Found."""
    name = "MaestroEmpty"
    path = f"/sdcard/Pictures/{name}"
    adb(serial, "shell", "mkdir", "-p", path, timeout=15)
    adb(
        serial,
        "shell",
        "am",
        "broadcast",
        "-a",
        "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
        "-d",
        f"file://{path}",
        timeout=20,
    )
    log(f"ensured empty album {path} on {serial}")
    return {"ok": True, "name": name}


def _bounds(node: ET.Element) -> tuple[int, int, int, int] | None:
    raw = node.attrib.get("bounds") or ""
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", raw)
    if not m:
        return None
    x1, y1, x2, y2 = map(int, m.groups())
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def dump_package(root: ET.Element | None) -> str:
    if root is None:
        return ""
    for node in root.iter():
        pkg = (node.attrib.get("package") or "").strip()
        if pkg:
            return pkg
    return ""


def dump_ui(serial: str) -> ET.Element | None:
    """Fresh uiautomator dump. Ignore stale files and non-Sprocket windows.

    Maestro holds the UI, so dump often fails with 'could not get idle state'.
    A unique remote path avoids pulling an old launcher hierarchy.
    """
    stamp = int(time.time() * 1000)
    remote = f"/sdcard/qp_uidump_{stamp}.xml"
    p = adb(serial, "shell", "uiautomator", "dump", remote, timeout=20)
    out = ((p.stdout or b"") + (p.stderr or b"")).decode("utf-8", "replace")
    m = re.search(r"dumped to:\s*(\S+)", out)
    if m:
        remote = m.group(1).rstrip(".")
    pulled = REPO / "logs" / f"qp_uidump_{serial}.xml"
    pulled.parent.mkdir(parents=True, exist_ok=True)
    adb(serial, "pull", remote, str(pulled), timeout=15)
    adb(serial, "shell", "rm", "-f", remote, timeout=5)
    if p.returncode != 0:
        log(f"uidump failed rc={p.returncode} {out[:160]!r}")
        return None
    if not pulled.exists():
        return None
    try:
        root = ET.parse(pulled).getroot()
    except ET.ParseError:
        return None
    pkg = dump_package(root)
    if pkg and pkg != SPROCKET_PKG:
        log(f"uidump ignored package={pkg}")
        return None
    return root


def screen_size(serial: str) -> tuple[int, int]:
    cached = _SCREEN_SIZE.get(serial)
    if cached:
        return cached
    p = adb(serial, "shell", "wm", "size", timeout=10)
    text = (p.stdout or b"").decode("utf-8", "replace")
    m = re.search(r"(\d+)x(\d+)", text)
    size = (int(m.group(1)), int(m.group(2))) if m else (1080, 2400)
    _SCREEN_SIZE[serial] = size
    return size


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


def parse_selection_from_text(text: str) -> tuple[int, int, str]:
    """Footer counts only ('N Photo(s) Selected', mixed '1 Photo, 1 Video Selected')."""
    if not text or not re.search(r"Selected", text, re.I):
        return 0, 0, ""
    body = re.sub(r"(?i)maximum of \d+ photos? allowed[^\n]*", " ", text)
    photos = 0
    videos = 0
    m = re.search(r"(\d+)\s*Photos?", body, re.I)
    v = re.search(r"(\d+)\s*Videos?", body, re.I)
    if m:
        photos = int(m.group(1))
    if v:
        videos = int(v.group(1))
    best = ""
    if m or v:
        best = body.strip()[:120]
    return photos, videos, best


def ocr_band(serial: str, y0_frac: float, y1_frac: float, name: str) -> str:
    stamp = int(time.time() * 1000)
    base = name.rsplit(".", 1)[0]
    bmp_name = f"{base}_{stamp}.bmp"
    rgba = grab_rgba(serial)
    if rgba is None:
        ok_grab, png_or_err = grab_png(serial, f"{base}_{stamp}.png")
        if not ok_grab:
            return str(png_or_err)
        return ocr_png(Path(png_or_err), bottom_percent=max(8, int((1 - y0_frac) * 100)))
    h = rgba.shape[0]
    y0, y1 = int(h * y0_frac), int(h * y1_frac)
    band = np.ascontiguousarray(rgba[max(0, y0) : max(y0 + 8, y1), :, :3])
    if band.size == 0 or band.shape[0] < 8 or band.shape[1] < 8:
        ok_grab, png_or_err = grab_png(serial, f"{base}_{stamp}.png")
        if not ok_grab:
            return str(png_or_err)
        return ocr_png(Path(png_or_err), bottom_percent=22)
    path = REPO / "logs" / bmp_name
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        write_bmp_rgb(path, band)
        return ocr_via_worker(path, 0)
    except OSError as exc:
        log(f"bmp ocr fallback {exc}")
        ok_grab, png_or_err = grab_png(serial, f"{base}_{stamp}.png")
        if not ok_grab:
            return str(png_or_err)
        return ocr_png(Path(png_or_err), bottom_percent=max(8, int((1 - y0_frac) * 100)))


def ocr_selection_counts(serial: str) -> tuple[int, int, str]:
    text = ocr_band(serial, 0.78, 0.96, f"qp_sel_{serial}.bmp")
    if "OCR_ENGINE_UNAVAILABLE" in text:
        return 0, 0, text
    return parse_selection_from_text(text)


def read_selection_counts(serial: str) -> tuple[int, int, str]:
    # uiautomator dump waits for idle and hangs while Maestro is attached / videos loop.
    return ocr_selection_counts(serial)


def grab_rgba(serial: str) -> np.ndarray | None:
    """Raw `adb screencap` RGBA (not PNG). Maestro-safe; no idle-state wait."""
    raw = adb(serial, "exec-out", "screencap", timeout=30)
    data = raw.stdout or b""
    if len(data) < 12:
        log(f"screencap short {len(data)}")
        return None
    w, h, fmt = struct.unpack_from("<III", data, 0)
    if w <= 0 or h <= 0 or w > 4096 or h > 4096:
        return None
    expected = w * h * 4
    offset = 16 if len(data) >= 16 + expected else 12
    payload = data[offset : offset + expected]
    if len(payload) < expected:
        payload = data[12 : 12 + expected]
    if len(payload) < expected:
        log(f"screencap payload {len(data)} w={w} h={h} fmt={fmt}")
        return None
    return np.frombuffer(payload, dtype=np.uint8).reshape((h, w, 4)).copy()


def _tile_selected(rgb: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> bool:
    """Select-mode badge is a lime circle in the thumbnail's top-left."""
    patch = rgb[y1 : y1 + 52, x1 : x1 + 52]
    if patch.size == 0:
        return False
    r, g, b = patch[:, :, 0], patch[:, :, 1], patch[:, :, 2]
    lime = (g > 150) & (g > r + 15) & (g > b + 15) & (r > 60)
    return int(lime.sum()) >= 40


def _tile_video(rgb: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> bool:
    """Play overlay: dark disk + white triangle in the thumbnail's bottom-right."""
    tw, th = max(1, x2 - x1), max(1, y2 - y1)
    patch = rgb[y1 + int(th * 0.55) : y2, x1 + int(tw * 0.55) : x2]
    if patch.size == 0:
        return False
    lum = patch.mean(axis=2)
    return int((lum < 80).sum()) >= 40 and int((lum > 210).sum()) >= 20


def find_gallery_tiles(serial: str) -> list[dict]:
    """Thumbnails = non-white blobs on the Quick Print canvas (date-grouped, ragged)."""
    rgba = grab_rgba(serial)
    if rgba is None:
        return []
    h, w = rgba.shape[:2]
    rgb = rgba[:, :, :3]
    y0, y1 = int(h * 0.12), int(h * 0.74)
    x0, x1 = 4, int(w * 0.92)
    lum = rgb[y0:y1, x0:x1].mean(axis=2)
    step = 4
    small = lum[::step, ::step] < 248
    gh, gw = small.shape
    vis = np.zeros_like(small, dtype=bool)
    tiles: list[dict] = []
    for iy in range(gh):
        for ix in range(gw):
            if not small[iy, ix] or vis[iy, ix]:
                continue
            stack = [(iy, ix)]
            vis[iy, ix] = True
            cells: list[tuple[int, int]] = []
            while stack:
                cy, cx = stack.pop()
                cells.append((cy, cx))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < gh and 0 <= nx < gw and small[ny, nx] and not vis[ny, nx]:
                        vis[ny, nx] = True
                        stack.append((ny, nx))
            if len(cells) < 80:
                continue
            ys = [c[0] for c in cells]
            xs = [c[1] for c in cells]
            x1t = min(xs) * step + x0
            x2t = (max(xs) + 1) * step + x0
            y1t = min(ys) * step + y0
            y2t = (max(ys) + 1) * step + y0
            tw, th = x2t - x1t, y2t - y1t
            if tw < 80 or th < 80:
                continue
            cx = int(sum(xs) / len(xs) * step + x0)
            cy = int(sum(ys) / len(ys) * step + y0)
            if cy > int(h * 0.72):
                continue
            tiles.append(
                {
                    "cx": cx,
                    "cy": cy,
                    "x": x1t,
                    "y": y1t,
                    "w": tw,
                    "h": th,
                    "selected": _tile_selected(rgb, x1t, y1t, x2t, y2t),
                    "video": _tile_video(rgb, x1t, y1t, x2t, y2t),
                }
            )
    tiles.sort(key=lambda t: (t["y"], t["x"]))
    uniq: list[dict] = []
    for t in tiles:
        if any(abs(t["cx"] - u["cx"]) < 36 and abs(t["cy"] - u["cy"]) < 36 for u in uniq):
            continue
        uniq.append(t)
    log(
        "tiles "
        + ",".join(
            f"{t['cx']}x{t['cy']}{'S' if t['selected'] else ''}{'V' if t['video'] else ''}"
            for t in uniq
        )
    )
    return uniq


def lattice_points(w: int, h: int, page: int) -> list[tuple[int, int]]:
    xs = (0.17, 0.50, 0.83)
    ys = (0.26, 0.40, 0.54, 0.66)
    dy = 0.04 * (page % 2)
    return [(int(w * x), int(h * min(0.72, y + dy))) for y in ys for x in xs]


def next_lattice_tap(serial: str, *, swipe_if_wrapped: bool) -> tuple[int, int]:
    w, h = screen_size(serial)
    per_page = 12
    i = _QP_LATTICE_I.get(serial, 0)
    page, local = divmod(i, per_page)
    if swipe_if_wrapped and i > 0 and local == 0:
        swipe_grid(serial)
        time.sleep(0.4)
    x, y = lattice_points(w, h, page)[local]
    _QP_LATTICE_I[serial] = i + 1
    _QP_LAST_XY[serial] = (x, y)
    return x, y


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
        for child in node.iter():
            if child is node:
                continue
            cblob = _node_blob(child)
            if re.fullmatch(r"\d{1,2}", (cblob or "").strip()):
                selected = True
                break
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


def _atp_two_selected(photos: int, videos: int, text: str) -> bool:
    """QP_006c: 2 photos OR 2 videos OR 1 photo & 1 video."""
    if photos == 2 and videos == 0:
        return True
    if videos == 2 and photos == 0:
        return True
    if photos >= 1 and videos >= 1:
        return True
    return bool(
        re.search(
            r"2\s*Photos?\s*Selected|2\s*Videos?\s*Selected|1\s*Photo.{0,12}1\s*Video\s*Selected",
            text or "",
            re.I,
        )
    )


def select_any_two(serial: str) -> dict:
    """Select two items of any type (QP_006c). ADB taps; no Maestro swipe."""
    photos, videos, last_text = ocr_selection_counts(serial)
    log(f"select-any-two start photos={photos} videos={videos} text={last_text!r}")
    stagnant = 0
    for page in range(10):
        if _atp_two_selected(photos, videos, last_text):
            log(f"select-any-two done photos={photos} videos={videos} text={last_text!r}")
            return {
                "ok": True,
                "photos": photos,
                "videos": videos,
                "text": last_text,
                "step": page,
            }
        tiles = find_gallery_tiles(serial)
        hit = next((t for t in tiles if not t["selected"]), None)
        if hit is None:
            swipe_grid(serial)
            time.sleep(0.28)
            stagnant += 1
            if stagnant >= 6:
                break
            continue
        tap_xy(serial, hit["cx"], hit["cy"])
        _QP_LAST_XY[serial] = (hit["cx"], hit["cy"])
        time.sleep(0.18)
        np_, nv, nt = ocr_selection_counts(serial)
        if nt:
            photos, videos, last_text = np_, nv, nt
            stagnant = 0
        else:
            stagnant += 1
        log(
            f"select-any-two tap {hit['cx']},{hit['cy']} "
            f"photos={photos} videos={videos} text={last_text!r}"
        )
    ok = _atp_two_selected(photos, videos, last_text)
    log(f"select-any-two fail photos={photos} videos={videos} text={last_text!r}")
    return {
        "ok": ok,
        "photos": photos,
        "videos": videos,
        "text": last_text,
        "error": "" if ok else "did not reach 2 selected items",
    }


def select_mixed(serial: str) -> dict:
    """Select at least one photo and one video. ADB taps; no Maestro swipe."""
    photos, videos, last_text = ocr_selection_counts(serial)
    log(f"select-mixed start photos={photos} videos={videos} text={last_text!r}")
    stagnant = 0
    for page in range(14):
        if photos >= 1 and videos >= 1:
            log(f"select-mixed done photos={photos} videos={videos} text={last_text!r}")
            return {
                "ok": True,
                "photos": photos,
                "videos": videos,
                "text": last_text,
                "step": page,
            }
        tiles = find_gallery_tiles(serial)
        hit = None
        if photos < 1:
            hit = next((t for t in tiles if not t["selected"] and not t["video"]), None)
        if hit is None and videos < 1:
            hit = next((t for t in tiles if not t["selected"] and t["video"]), None)
        if hit is None:
            swipe_grid(serial)
            time.sleep(0.28)
            stagnant += 1
            if stagnant >= 6:
                break
            continue
        tap_xy(serial, hit["cx"], hit["cy"])
        _QP_LAST_XY[serial] = (hit["cx"], hit["cy"])
        time.sleep(0.18)
        np_, nv, nt = ocr_selection_counts(serial)
        if nt:
            photos, videos, last_text = np_, nv, nt
            stagnant = 0
        else:
            stagnant += 1
        log(
            f"select-mixed tap {hit['cx']},{hit['cy']} "
            f"photos={photos} videos={videos} text={last_text!r}"
        )
    ok = photos >= 1 and videos >= 1
    log(f"select-mixed fail photos={photos} videos={videos} text={last_text!r}")
    return {
        "ok": ok,
        "photos": photos,
        "videos": videos,
        "text": last_text,
        "error": "" if ok else "did not select both a photo and a video",
    }


def select_until(serial: str, want: int = 10, kind: str = "photos") -> dict:
    """Select `want` photos, mixed photo+video, or any two items."""
    kind_l = str(kind).lower()
    if kind_l in ("any", "two"):
        return select_any_two(serial)
    if kind_l == "mixed":
        return select_mixed(serial)
    photos, videos, last_text = ocr_selection_counts(serial)
    log(f"select-until start photos={photos} videos={videos} text={last_text!r}")
    if not last_text:
        photos, videos = 1, 0

    def read_counts(prev_p: int, prev_v: int, prev_t: str) -> tuple[int, int, str]:
        np_, nv, text = ocr_selection_counts(serial)
        if text:
            return np_, nv, text
        return prev_p, prev_v, prev_t

    def apply_tap(x: int, y: int, p: int, v: int, t: str) -> tuple[int, int, str]:
        tap_xy(serial, x, y)
        _QP_LAST_XY[serial] = (x, y)
        time.sleep(0.08)
        np_, nv, nt = read_counts(p, v, t)
        if nv > v:
            tap_xy(serial, x, y)
            time.sleep(0.08)
            np_, nv, nt = read_counts(p, v, t)
            log(f"select-until undo-video photos={np_} videos={nv}")
            return np_, nv, nt
        if np_ < p:
            tap_xy(serial, x, y)
            time.sleep(0.08)
            np_, nv, nt = read_counts(p, v, t)
            log(f"select-until restore photos={np_} videos={nv}")
            return np_, nv, nt
        return np_, nv, nt

    stagnant = 0
    video_tries = 0
    for page in range(12):
        if kind == "photos" and photos >= want and videos == 0:
            log(f"select-until done photos={photos} text={last_text!r}")
            return {
                "ok": True,
                "photos": photos,
                "videos": videos,
                "text": last_text,
                "step": page,
            }
        tiles = find_gallery_tiles(serial)
        if not tiles:
            swipe_grid(serial)
            time.sleep(0.25)
            stagnant += 1
            if stagnant >= 5:
                break
            continue
        if videos > 0 and video_tries < 3:
            video_tries += 1
            hit = next((t for t in tiles if t["selected"]), None)
            if hit is None:
                hit = next((t for t in tiles if t["video"]), None)
            if hit:
                photos, videos, last_text = apply_tap(
                    hit["cx"], hit["cy"], photos, videos, last_text
                )
                log(f"select-until deselect photos={photos} videos={videos}")
            continue
        if videos > 0:
            videos = 0
            log("select-until ignore stale video count")
        cands = [t for t in tiles if not t["selected"] and not t["video"]]
        if not cands:
            swipe_grid(serial)
            time.sleep(0.22)
            stagnant += 1
            if stagnant >= 5:
                break
            continue
        page_gains = 0
        pending = 0
        before_sync = photos
        batch: list[tuple[int, int]] = []
        for t in cands:
            if photos >= want and videos == 0:
                break
            tap_xy(serial, t["cx"], t["cy"])
            batch.append((t["cx"], t["cy"]))
            _QP_LAST_XY[serial] = (t["cx"], t["cy"])
            pending += 1
            time.sleep(0.06)
            should_read = pending >= 3 or photos + pending >= want or t is cands[-1]
            if not should_read:
                continue
            np_, nv, nt = read_counts(photos, videos, last_text)
            if nv > videos:
                for bx, by in reversed(batch):
                    tap_xy(serial, bx, by)
                    time.sleep(0.05)
                np_, nv, nt = read_counts(photos, videos, last_text)
                log(f"select-until undo-video-batch photos={np_} videos={nv}")
                photos, videos, last_text = np_, nv, nt
                batch.clear()
                pending = 0
                break
            log(
                f"select-until page={page} photos={np_} videos={nv} "
                f"pending={pending} text={nt!r}"
            )
            pending = 0
            batch.clear()
            if np_ > photos:
                page_gains += np_ - photos
                stagnant = 0
            elif np_ <= before_sync:
                photos, videos, last_text = np_, nv, nt
                break
            photos, videos, last_text = np_, nv, nt
            before_sync = photos
            if photos >= want and videos == 0:
                log(f"select-until done photos={photos} text={last_text!r}")
                return {
                    "ok": True,
                    "photos": photos,
                    "videos": videos,
                    "text": last_text,
                    "step": page,
                }
            if videos > 0:
                break
        if pending:
            photos, videos, last_text = read_counts(photos, videos, last_text)
        if photos >= want and videos == 0:
            log(f"select-until done photos={photos} text={last_text!r}")
            return {
                "ok": True,
                "photos": photos,
                "videos": videos,
                "text": last_text,
                "step": page,
            }
        swipe_grid(serial)
        time.sleep(0.22)
        if page_gains == 0:
            stagnant += 1
        if stagnant >= 5:
            break
    log(f"select-until fail photos={photos} videos={videos} text={last_text!r}")
    return {
        "ok": photos >= want and videos == 0,
        "photos": photos,
        "videos": videos,
        "text": last_text,
        "error": "" if photos >= want and videos == 0 else f"did not reach {want} photos-only",
    }


def first_adb_serial() -> str:
    p = subprocess.run(
        [adb_bin(), "devices"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    for line in (p.stdout or "").splitlines():
        line = line.strip()
        if re.match(r"^\S+\s+device$", line):
            return line.split()[0]
    return ""


def resolve_serial(q: dict) -> str:
    raw = ((q.get("serial") or [""])[0] or "").strip()
    if raw:
        return raw
    env = (os.environ.get("ANDROID_SERIAL") or "").strip()
    if env:
        return env
    return first_adb_serial()


def _unselected_cell(serial: str) -> dict:
    """11th thumbnail: screenshot tiles, then adb swipe (not Maestro)."""
    w, h = screen_size(serial)
    tiles = find_gallery_tiles(serial)
    hit = next((t for t in tiles if not t["selected"] and not t["video"]), None)
    if hit is None:
        swipe_grid(serial)
        time.sleep(0.35)
        tiles = find_gallery_tiles(serial)
        hit = next((t for t in tiles if not t["selected"] and not t["video"]), None)
    if hit:
        return {
            "ok": True,
            "x": hit["cx"],
            "y": hit["cy"],
            "w": w,
            "h": h,
            "via": "tiles",
        }
    x, y = int(w * 0.83), int(h * 0.62)
    last = _QP_LAST_XY.get(serial)
    if last and abs(last[0] - x) < 48 and abs(last[1] - y) < 48:
        x, y = int(w * 0.17), int(h * 0.62)
    return {
        "ok": True,
        "fallback": True,
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "via": "swipe-percent",
    }


def tap_max_limit(serial: str, needles: list[str], seconds: float) -> dict:
    """Find 11th cell, start OCR burst, tap, wait for toast text."""
    hit = _unselected_cell(serial)
    with _TOAST_LOCK:
        prev = _TOAST_JOB.get("thread")
        _TOAST_JOB["payload"] = None
    if prev is not None and prev.is_alive():
        prev.join(timeout=1)
    t = threading.Thread(
        target=_run_armed_ocr,
        args=(serial, needles, max(1.0, seconds)),
        daemon=True,
    )
    with _TOAST_LOCK:
        _TOAST_JOB["thread"] = t
    t.start()
    time.sleep(0.12)
    tap_xy(serial, int(hit["x"]), int(hit["y"]))
    t.join(timeout=40)
    with _TOAST_LOCK:
        payload = _TOAST_JOB.get("payload") or {}
    return {
        "ok": bool(payload.get("ok")),
        "found": bool(payload.get("found")),
        "text": (payload.get("text") or "")[:400],
        "x": hit["x"],
        "y": hit["y"],
        "via": hit.get("via"),
        "tapped": True,
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
        # Tag chip sits above the More/Create/Printer bar, bottom-right.
        if kind == "tag" and clickable and int(h * 0.70) < cy < int(h * 0.90) and cx > int(w * 0.72):
            right_bar.append((cx, cy, x1))
        if kind == "overflow" and clickable and cy < int(h * 0.14) and cx > int(w * 0.72):
            right_bar.append((cx, cy, x1))
        # Facebook ⋮ sits on the account sub-header under Select Gallery.
        if kind == "overflow" and clickable and int(h * 0.12) < cy < int(h * 0.32) and cx > int(w * 0.78):
            right_bar.append((cx, cy, x1))

    if hits:
        hits.sort(key=lambda t: t[2], reverse=True)
        tap_xy(serial, hits[0][0], hits[0][1])
        return {"ok": True, "via": "desc", "label": hits[0][3], "kind": kind}
    if kind == "overflow" and right_bar:
        right_bar.sort(key=lambda t: t[0], reverse=True)
        tap_xy(serial, right_bar[0][0], right_bar[0][1])
        return {"ok": True, "via": "top-right", "kind": kind}
    if kind == "tag" and right_bar:
        right_bar.sort(key=lambda t: t[0], reverse=True)
        tap_xy(serial, right_bar[0][0], right_bar[0][1])
        return {"ok": True, "via": "bottom-right", "kind": kind}
    if kind == "overflow":
        tap_xy(serial, int(w * 0.94), int(h * 0.07))
    else:
        tap_xy(serial, int(w * 0.90), int(h * 0.82))
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
        serial = resolve_serial(q)
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
                    x, y = int(w * 0.82), int(h * 0.40)
                tap_xy(serial, x, y)
                self._json(200, {"ok": True, "x": x, "y": y})
                return
            if u.path == "/tap-max-limit":
                raw = (q.get("needle") or ["maximum of 10 photos allowed,maximum of 10,10 photos allowed"])[0]
                needles = [n.strip() for n in raw.split(",") if n.strip()]
                seconds = float((q.get("seconds") or ["6"])[0])
                self._json(200, tap_max_limit(serial, needles, seconds))
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
            if u.path == "/ensure-empty-album":
                self._json(200, ensure_empty_album(serial))
                return
            self._json(404, {"ok": False, "error": "not found"})
        except Exception as exc:  # noqa: BLE001
            log(f"error {u.path}: {exc}")
            self._json(500, {"ok": False, "error": str(exc)})


def main() -> None:
    global _OCR_PROC
    _OCR_PROC = _start_ocr_worker()
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"qp helper listening on http://127.0.0.1:{PORT}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
