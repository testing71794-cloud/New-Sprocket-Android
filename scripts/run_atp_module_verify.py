"""
Run all Maestro flows in one ATP TestCase Flows module; continue after FAIL/CRASH.

Writes reports/module_runs/<module>_summary.json, <module>_execution_report.xlsx,
and appends to module_runs/index.json.

Recovery is adb-side (force-stop app + Maestro + Settings, then HOME). The next
test reuses its existing launch/onboarding/navigation subflow — do not add
recovery YAML. App navigation lives in ATP TestCase Flows/common/subflows and
module subflows (excel_launch_to_home, excel_launch_to_collage, …).

Maestro CLI: global --device before test; --debug-output is a test option.
https://docs.maestro.dev/maestro-cli/maestro-cli-commands-and-options

Do not pass repo-root config.yaml here: that workspace only lists
"Non printing flows/**" and "Printing Flow/**" (see config.yaml). ATP paths
resolve relative to each flow file.

Multi-device: comma-separated --device (or repeat the flag). One worker per phone.

Login on one device runs every LO_* flow in a single Maestro process
(login/config.yaml continueOnFailure). The app is not force-stopped between
those flows, so a case skips launch when Log In is already open.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import queue
import subprocess
import sys
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

ATP = REPO / "ATP TestCase Flows"
OUT = REPO / "reports" / "module_runs"
APP_ID = "com.hp.impulse.sprocket"
# Maestro copies the app APK into %TEMP% on every launchApp (~200MB each). Keep that
# on D: so C: cannot fill during a suite. See https://docs.maestro.dev/maestro-cli/maestro-cli-commands-and-options
MAESTRO_TMP = REPO / "temp" / "maestro-java"
DEBUG_OUT = OUT / "_maestro_debug"


def _ensure_maestro_tmp() -> Path:
    MAESTRO_TMP.mkdir(parents=True, exist_ok=True)
    return MAESTRO_TMP


def _scrub_maestro_temp_copies(*dirs: Path) -> None:
    """Remove Maestro leftover APKs/videos that otherwise pile up in TEMP."""
    pats = (
        "tmp*.apk",
        "maestro-app*.apk",
        "maestro-server*.apk",
        "maestro_flow_*.mp4",
        "maestro_screenshot*.png",
    )
    for d in dirs:
        if not d or not d.is_dir():
            continue
        for pat in pats:
            for p in d.glob(pat):
                try:
                    p.unlink()
                except OSError:
                    pass


def flow_case_id(flow: Path) -> str:
    """COL_10f - Verify ....yaml → COL_10f."""
    return flow.stem.split(" - ", 1)[0].strip()


def discover_flows(module: str, only_ids: set[str] | None = None) -> list[Path]:
    root = ATP / module
    if not root.is_dir():
        return []
    slug = module.replace("-", "_")
    mapping_candidates = (
        root / f"atp_{slug}_mapping.csv",
        root / f"atp_{slug}_excel_mapping.csv",
    )
    paths: list[Path] = []
    for mapping in mapping_candidates:
        if not mapping.is_file():
            continue
        with mapping.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                rel = (row.get("FlowFile") or "").strip().replace("/", os.sep)
                if not rel:
                    continue
                p = ATP / rel
                if p.is_file() and p not in paths:
                    paths.append(p)
        if paths:
            break
    if not paths:
        paths = sorted(p for p in root.glob("*.yaml") if p.name.lower() != "config.yaml")
    if only_ids:
        wanted = {i.strip() for i in only_ids if i.strip()}
        paths = [p for p in paths if flow_case_id(p) in wanted]
    return paths


def adb_bin() -> str:
    home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if home:
        cand = Path(home) / "platform-tools" / "adb.exe"
        if cand.exists():
            return str(cand)
    win = Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe"
    return str(win) if win.exists() else "adb"


def list_authorized_devices() -> list[str]:
    adb = adb_bin()
    try:
        p = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    out: list[str] = []
    for line in (p.stdout or "").splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == "device":
            out.append(parts[0])
    return out


def prepare(serial: str, *, parallel: bool = False) -> None:
    """Shared recovery for every ATP module. Reuses execution.maestro_stabilization."""
    try:
        from execution.maestro_stabilization import recover_device_after_flow

        recover_device_after_flow(serial, APP_ID)
    except Exception:
        pass
    adb = adb_bin()
    cmds: list[list[str]] = []
    if not parallel:
        cmds.append(["forward", "--remove-all"])
    cmds.extend(
        [
            ["shell", "cmd", "connectivity", "airplane-mode", "disable"],
            ["shell", "svc", "wifi", "enable"],
            ["shell", "svc", "data", "enable"],
        ]
    )
    for args in cmds:
        subprocess.run([adb, "-s", serial, *args], capture_output=True, timeout=30, check=False)


def classify_status(rec: dict) -> str:
    """PASS / FAIL / CRASH from Maestro exit and log snippet."""
    if rec.get("status") == "PASS":
        return "PASS"
    reason = (rec.get("failure_reason") or "").lower()
    crash_needles = (
        "crash",
        "anr",
        "fatal exception",
        "instrumentation_failed",
        "instrumentation process",
        "process crashed",
        "app has stopped",
        "has stopped",
        "not responding",
        "session crashed",
        "uiautomator",
        "broken pipe",
        "connection reset",
    )
    if any(n in reason for n in crash_needles):
        return "CRASH"
    if rec.get("exit_code") == -1 and "timeout" in reason:
        return "FAIL"
    return "FAIL"


def run_flow(
    maestro: str,
    serial: str,
    flow: Path,
    timeout: int = 300,
    *,
    reinstall: bool = True,
) -> dict:
    t0 = time.time()
    # Global --device before test (docs.maestro.dev CLI); one serial per worker.
    # --no-ansi + file redirects avoid Windows Jansi UnsatisfiedLinkError (isatty on pipes).
    cmd = [maestro, "--no-ansi", "--device", serial, "test"]
    if reinstall:
        cmd.append("--reinstall-driver")
    # Official test option (space-separated): https://docs.maestro.dev/maestro-cli/maestro-cli-commands-and-options
    DEBUG_OUT.mkdir(parents=True, exist_ok=True)
    cmd.extend(["--debug-output", str(DEBUG_OUT)])
    cmd.append(str(flow))
    env = os.environ.copy()
    env["ANDROID_SERIAL"] = serial
    tmp = _ensure_maestro_tmp()
    env["TEMP"] = str(tmp)
    env["TMP"] = str(tmp)
    env["TMPDIR"] = str(tmp)
    env["MAESTRO_CLI_NO_ANSI"] = "1"
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"
    # Disable Jansi native isatty (common Windows crash when stdout is not a console).
    # preferIPv4Stack avoids Maestro connecting to [::1]:7001 while the driver binds IPv4.
    jansi_opts = (
        "-Djava.net.preferIPv4Stack=true "
        "-Dorg.fusesource.jansi.Ansi.disable=true "
        "-Djansi.passthrough=true"
    )
    prev = env.get("JAVA_TOOL_OPTIONS", "").strip()
    env["JAVA_TOOL_OPTIONS"] = f"{prev} {jansi_opts}".strip() if prev else jansi_opts
    out_dir = REPO / "reports" / "module_runs" / "_maestro_out"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{serial}_{os.getpid()}_{int(t0)}.log"
    try:
        with out_path.open("w", encoding="utf-8", errors="replace") as out_f:
            p = subprocess.run(
                cmd,
                cwd=str(REPO),
                stdout=out_f,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
                env=env,
            )
        out = out_path.read_text(encoding="utf-8", errors="replace") if out_path.exists() else ""
        try:
            out_path.unlink(missing_ok=True)
        except OSError:
            pass
        ok = p.returncode == 0
        reason = "" if ok else _fail_reason(out)
        _scrub_maestro_temp_copies(MAESTRO_TMP, Path(os.environ.get("TEMP", "")))
        rec = {
            "id": flow_case_id(flow),
            "flow": flow.name,
            "path": str(flow.relative_to(REPO)),
            "status": "PASS" if ok else "FAIL",
            "exit_code": p.returncode,
            "failure_reason": reason,
            "execution_time_sec": round(time.time() - t0, 2),
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "device": serial,
        }
        rec["status"] = classify_status(rec)
        return rec
    except subprocess.TimeoutExpired:
        try:
            out_path.unlink(missing_ok=True)
        except OSError:
            pass
        _scrub_maestro_temp_copies(MAESTRO_TMP, Path(os.environ.get("TEMP", "")))
        rec = {
            "id": flow_case_id(flow),
            "flow": flow.name,
            "path": str(flow.relative_to(REPO)),
            "status": "FAIL",
            "exit_code": -1,
            "failure_reason": f"timeout after {timeout}s",
            "execution_time_sec": round(time.time() - t0, 2),
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "device": serial,
        }
        rec["status"] = classify_status(rec)
        return rec
    except Exception as exc:  # noqa: BLE001
        try:
            out_path.unlink(missing_ok=True)
        except OSError:
            pass
        _scrub_maestro_temp_copies(MAESTRO_TMP, Path(os.environ.get("TEMP", "")))
        rec = {
            "id": flow_case_id(flow),
            "flow": flow.name,
            "path": str(flow.relative_to(REPO)),
            "status": "FAIL",
            "exit_code": -2,
            "failure_reason": str(exc),
            "execution_time_sec": round(time.time() - t0, 2),
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "device": serial,
        }
        rec["status"] = classify_status(rec)
        return rec


def _fail_reason(out: str) -> str:
    def _is_box(ln: str) -> bool:
        # Maestro pretty-errors use box drawing; Windows often renders them as "?".
        if ln.count("?") >= 20:
            return True
        letters = sum(c.isalpha() for c in ln)
        return letters < 8 and sum(c in "─│┌┐└┘├┤┬┴┼╔╗╚╝║═╭╮╰╯" for c in ln) > 8

    lines = [ln.strip() for ln in (out or "").splitlines() if ln.strip() and not _is_box(ln)]
    needles = (
        "assertion",
        "not found",
        "does not exist",
        "invalid file",
        "failed",
        "error",
        "timeout",
        "crash",
        "anr",
        "fatal exception",
        "instrumentation",
    )
    for ln in reversed(lines[-80:]):
        low = ln.lower()
        if any(x in low for x in needles):
            return ln[:300]
    return (lines[-1] if lines else "maestro non-zero exit")[:300]


def write_excel(module: str, summary: dict) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    xlsx = OUT / f"{module}_execution_report.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Execution"
    ws["A1"] = f"HP Sprocket Android - Module {module}"
    ws["A1"].font = Font(bold=True, size=14)
    ws.append(["Id", "Flow", "Device", "Status", "Failure Reason", "Execution Time", "Timestamp"])
    fills = {
        "PASS": PatternFill("solid", fgColor="C6EFCE"),
        "FAIL": PatternFill("solid", fgColor="FFC7CE"),
        "CRASH": PatternFill("solid", fgColor="FFEB9C"),
    }
    for r in summary["rows"]:
        ws.append(
            [
                r.get("id") or r["flow"],
                r["flow"],
                r.get("device", ""),
                r["status"],
                r.get("failure_reason", ""),
                r["execution_time_sec"],
                r["timestamp"],
            ]
        )
        cell = ws.cell(ws.max_row, 4)
        cell.fill = fills.get(r["status"], fills["FAIL"])
    sm = wb.create_sheet("Summary")
    for k in (
        "module",
        "total",
        "passed",
        "failed",
        "crashed",
        "pass_percent",
        "execution_time_sec",
        "devices",
    ):
        val = summary.get(k)
        if isinstance(val, list):
            val = ", ".join(str(x) for x in val)
        sm.append([k, val])
    wb.save(xlsx)
    return xlsx


def _parse_devices(raw: list[str]) -> list[str]:
    devices: list[str] = []
    for item in raw:
        for part in item.replace(";", ",").split(","):
            s = part.strip()
            if s and s not in devices:
                devices.append(s)
    return devices


def _run_one_with_retry(
    maestro: str,
    serial: str,
    flow: Path,
    timeout: int,
    *,
    reinstall_first: bool,
    parallel: bool,
) -> dict:
    prepare(serial, parallel=parallel)
    rec = run_flow(maestro, serial, flow, timeout=timeout, reinstall=reinstall_first)
    if rec["status"] == "PASS":
        prepare(serial, parallel=parallel)
        return rec
    prepare(serial, parallel=parallel)
    reason = rec.get("failure_reason") or ""
    low = reason.lower()
    letters = [c for c in reason if c.isalpha()]
    need_reinstall = rec.get("status") == "CRASH" or any(
        x in low
        for x in (
            "install failed",
            "driver",
            "7001",
            "connection refused",
            "not connected",
            "unsatisfiedlinkerror",
            "jansi",
            "deadline_exceeded",
            "waiting_for_connection",
            "crash",
        )
    ) or (
        float(rec.get("execution_time_sec") or 999) < 20
        and (not letters or set(reason.strip()) <= set("? \t"))
    )
    rec2 = run_flow(maestro, serial, flow, timeout=timeout, reinstall=need_reinstall)
    if rec2["status"] == "PASS":
        rec2["failure_reason"] = f"passed on retry (first: {rec.get('failure_reason', '')[:120]})"
    prepare(serial, parallel=parallel)
    return rec2


def run_parallel(
    maestro: str,
    devices: list[str],
    flows: list[Path],
    timeout: int,
) -> list[dict]:
    """Dynamic queue: each device worker pulls the next flow until empty."""
    work: queue.Queue[tuple[int, Path] | None] = queue.Queue()
    for i, flow in enumerate(flows):
        work.put((i, flow))
    for _ in devices:
        work.put(None)  # sentinel per worker

    results: dict[int, dict] = {}
    lock = threading.Lock()
    print_lock = threading.Lock()
    first_done = {s: False for s in devices}

    def worker(serial: str) -> None:
        while True:
            item = work.get()
            if item is None:
                work.task_done()
                break
            idx, flow = item
            with print_lock:
                print(f"[{idx + 1}/{len(flows)}] {flow.name} @ {serial} ...", flush=True)
            reinstall = False
            first_done[serial] = True
            rec = _run_one_with_retry(
                maestro,
                serial,
                flow,
                timeout,
                reinstall_first=reinstall,
                parallel=True,
            )
            with lock:
                results[idx] = rec
            with print_lock:
                print(
                    f"  [{serial}] {rec['status']} ({rec['execution_time_sec']}s) "
                    f"{rec.get('failure_reason', '')[:100]}",
                    flush=True,
                )
            work.task_done()

    with ThreadPoolExecutor(max_workers=len(devices)) as pool:
        futs = [pool.submit(worker, serial) for serial in devices]
        for f in as_completed(futs):
            f.result()

    return [results[i] for i in range(len(flows)) if i in results]


def _maestro_env(serial: str) -> dict[str, str]:
    env = os.environ.copy()
    env["ANDROID_SERIAL"] = serial
    tmp = _ensure_maestro_tmp()
    env["TEMP"] = str(tmp)
    env["TMP"] = str(tmp)
    env["TMPDIR"] = str(tmp)
    env["MAESTRO_CLI_NO_ANSI"] = "1"
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"
    jansi_opts = (
        "-Djava.net.preferIPv4Stack=true "
        "-Dorg.fusesource.jansi.Ansi.disable=true "
        "-Djansi.passthrough=true"
    )
    prev = env.get("JAVA_TOOL_OPTIONS", "").strip()
    env["JAVA_TOOL_OPTIONS"] = f"{prev} {jansi_opts}".strip() if prev else jansi_opts
    return env


def _rows_from_junit(flows: list[Path], junit_path: Path, serial: str) -> list[dict] | None:
    if not junit_path.is_file():
        return None
    try:
        root = ET.parse(junit_path).getroot()
    except ET.ParseError:
        return None
    found: dict[str, dict] = {}
    for tc in root.iter("testcase"):
        label = tc.get("name") or tc.get("id") or ""
        case_id = flow_case_id(Path(label if label.endswith(".yaml") else f"{label}.yaml"))
        failure = tc.find("failure")
        error = tc.find("error")
        status_attr = (tc.get("status") or "").upper()
        failed = failure is not None or error is not None or status_attr in {"ERROR", "FAILED", "FAIL"}
        reason = ""
        if failure is not None:
            reason = (failure.text or failure.get("message") or "").strip()
        elif error is not None:
            reason = (error.text or error.get("message") or "").strip()
        try:
            seconds = round(float(tc.get("time") or 0), 2)
        except ValueError:
            seconds = 0.0
        found[case_id] = {
            "status": "FAIL" if failed else "PASS",
            "failure_reason": reason[:300],
            "execution_time_sec": seconds,
        }
    if not found:
        return None
    rows: list[dict] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for flow in flows:
        case_id = flow_case_id(flow)
        hit = found.get(case_id)
        if hit is None:
            rec = {
                "id": case_id,
                "flow": flow.name,
                "path": str(flow.relative_to(REPO)),
                "status": "FAIL",
                "exit_code": 1,
                "failure_reason": "missing from junit report",
                "execution_time_sec": 0.0,
                "timestamp": now,
                "device": serial,
            }
        else:
            rec = {
                "id": case_id,
                "flow": flow.name,
                "path": str(flow.relative_to(REPO)),
                "status": hit["status"],
                "exit_code": 0 if hit["status"] == "PASS" else 1,
                "failure_reason": "" if hit["status"] == "PASS" else hit["failure_reason"],
                "execution_time_sec": hit["execution_time_sec"],
                "timestamp": now,
                "device": serial,
            }
        rec["status"] = classify_status(rec)
        rows.append(rec)
    return rows


def run_login_session(maestro: str, serial: str, flows: list[Path], timeout: int) -> list[dict]:
    """One Maestro process for the login folder.

    The app stays open between LO_* flows, so a later case can skip launch when
    Log In is already on screen. continueOnFailure is set in login/config.yaml.
    Other modules keep one process per flow.
    """
    prepare(serial, parallel=False)
    DEBUG_OUT.mkdir(parents=True, exist_ok=True)
    junit = OUT / f"login_{serial}_junit.xml"
    config = ATP / "login" / "config.yaml"
    cmd = [
        maestro,
        "--no-ansi",
        "--device",
        serial,
        "test",
        "--reinstall-driver",
        "--format",
        "junit",
        "--output",
        str(junit),
        "--debug-output",
        str(DEBUG_OUT),
        "--config",
        str(config),
    ]
    cmd.extend(str(flow) for flow in flows)
    print(
        f"[login] one session, {len(flows)} flows, continue on failure",
        flush=True,
    )
    env = _maestro_env(serial)
    out_dir = OUT / "_maestro_out"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{serial}_login_session.log"
    session_timeout = max(timeout, timeout * len(flows))
    try:
        with out_path.open("w", encoding="utf-8", errors="replace") as out_f:
            proc = subprocess.run(
                cmd,
                cwd=str(REPO),
                stdout=out_f,
                stderr=subprocess.STDOUT,
                timeout=session_timeout,
                check=False,
                env=env,
            )
    except subprocess.TimeoutExpired:
        rows = []
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for flow in flows:
            rows.append(
                {
                    "id": flow_case_id(flow),
                    "flow": flow.name,
                    "path": str(flow.relative_to(REPO)),
                    "status": "FAIL",
                    "exit_code": -1,
                    "failure_reason": f"login session timeout after {session_timeout}s",
                    "execution_time_sec": 0.0,
                    "timestamp": now,
                    "device": serial,
                }
            )
        return rows
    rows = _rows_from_junit(flows, junit, serial)
    if rows is None:
        log = out_path.read_text(encoding="utf-8", errors="replace") if out_path.exists() else ""
        reason = _fail_reason(log) if proc.returncode != 0 else "junit report missing"
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = []
        for flow in flows:
            rows.append(
                {
                    "id": flow_case_id(flow),
                    "flow": flow.name,
                    "path": str(flow.relative_to(REPO)),
                    "status": "FAIL" if proc.returncode != 0 else "PASS",
                    "exit_code": proc.returncode,
                    "failure_reason": "" if proc.returncode == 0 else reason,
                    "execution_time_sec": 0.0,
                    "timestamp": now,
                    "device": serial,
                }
            )
    for rec in rows:
        print(
            f"  {rec['id']} {rec['status']} ({rec['execution_time_sec']}s) {rec.get('failure_reason', '')[:120]}",
            flush=True,
        )
    failed = [flow for flow, rec in zip(flows, rows) if rec["status"] != "PASS"]
    if not failed:
        return rows
    print(f"[login] retrying {len(failed)} failed flow(s) one at a time", flush=True)
    by_name = {rec["flow"]: rec for rec in rows}
    for flow in failed:
        prepare(serial, parallel=False)
        rec2 = run_flow(maestro, serial, flow, timeout=timeout, reinstall=False)
        if rec2["status"] == "PASS":
            rec2["failure_reason"] = ""
        by_name[flow.name] = rec2
        print(
            f"  retry {rec2['id']} {rec2['status']} ({rec2['execution_time_sec']}s)",
            flush=True,
        )
    return [by_name[flow.name] for flow in flows]


def run_sequential(maestro: str, serial: str, flows: list[Path], timeout: int) -> list[dict]:
    rows: list[dict] = []
    prepare(serial, parallel=False)
    for i, flow in enumerate(flows, 1):
        print(f"[{i}/{len(flows)}] {flow.name} ...", flush=True)
        rec = _run_one_with_retry(
            maestro,
            serial,
            flow,
            timeout,
            reinstall_first=(i == 1),
            parallel=False,
        )
        rows.append(rec)
        print(f"  {rec['status']} ({rec['execution_time_sec']}s) {rec.get('failure_reason', '')[:120]}")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", required=True, help="ATP folder name e.g. home, photo-id")
    ap.add_argument(
        "--device",
        action="append",
        required=True,
        help="Device serial (repeat flag or comma-separate for parallel)",
    )
    ap.add_argument("--maestro", default=r"C:\Users\HP\maestro\maestro\bin\maestro.bat")
    ap.add_argument("--limit", type=int, default=0, help="Max flows (0=all)")
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument(
        "--ids",
        default="",
        help="Comma-separated TestCaseIDs from the module mapping CSV (e.g. COL_10f,COL_14b)",
    )
    ap.add_argument(
        "--only-failed",
        action="store_true",
        help="Re-run FAIL/CRASH rows from reports/module_runs/<module>_summary.json and merge results",
    )
    ap.add_argument(
        "--from-flow",
        default="",
        help="Skip flows until this flow name (substring match) is reached",
    )
    ap.add_argument(
        "--parallel",
        action="store_true",
        help="Force parallel even with 1 device listed (no-op). Multi-device always parallel.",
    )
    args = ap.parse_args()

    devices = _parse_devices(args.device)
    if not devices:
        print("ERROR: no device serials")
        return 2
    online = set(list_authorized_devices())
    missing = [d for d in devices if d not in online]
    if missing:
        print(f"ERROR: device(s) not in adb 'device' state: {', '.join(missing)}")
        print(f"Online now: {', '.join(sorted(online)) or '(none)'}")
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    only_ids = {p.strip() for p in args.ids.replace(";", ",").split(",") if p.strip()} if args.ids else None
    flows = discover_flows(args.module, only_ids=only_ids)
    if only_ids:
        print(f"[ids] {len(flows)} flow(s): {', '.join(flow_case_id(f) for f in flows)}", flush=True)
    prior_rows: list[dict] = []
    if args.only_failed:
        js_path = OUT / f"{args.module}_summary.json"
        if not js_path.is_file():
            print(f"ERROR: no summary to retry: {js_path}")
            return 2
        prior = json.loads(js_path.read_text(encoding="utf-8"))
        prior_rows = list(prior.get("rows") or [])
        fail_names = {r["flow"] for r in prior_rows if r.get("status") != "PASS"}
        flows = [f for f in flows if f.name in fail_names]
        print(f"[only-failed] retrying {len(flows)} failed flow(s) from {js_path.name}")
    if args.from_flow:
        needle = args.from_flow.strip().lower()
        idx = next((i for i, f in enumerate(flows) if needle in f.name.lower()), None)
        if idx is None:
            print(f"ERROR: --from-flow {args.from_flow!r} not found in module {args.module}")
            return 2
        flows = flows[idx:]
        print(f"[from-flow] starting at {flows[0].name} ({len(flows)} remaining)")
    if args.limit and args.limit > 0:
        flows = flows[: args.limit]
    if not flows:
        print(f"No flows in module: {args.module}")
        return 2

    mode = "parallel" if len(devices) > 1 else "sequential"
    print(
        f"===== MODULE {args.module} ({len(flows)} flows) devices={len(devices)} mode={mode} =====",
        flush=True,
    )
    print(f"Devices: {', '.join(devices)}", flush=True)

    ocr_proc = None
    if args.module == "quick-print":
        env = os.environ.copy()
        env["ANDROID_SERIAL"] = devices[0]
        ocr_proc = subprocess.Popen(
            [sys.executable, str(REPO / "scripts" / "qp005_toast_ocr_server.py")],
            cwd=str(REPO),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(20):
            try:
                urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=1)
                print("[qp005] toast OCR helper ready on :8765", flush=True)
                break
            except Exception:
                time.sleep(0.25)
        else:
            print("[qp005] WARN: toast OCR helper did not start", flush=True)

    t0 = time.time()
    try:
        if len(devices) > 1:
            rows = run_parallel(args.maestro, devices, flows, args.timeout)
        elif args.module == "login":
            rows = run_login_session(args.maestro, devices[0], flows, args.timeout)
        else:
            rows = run_sequential(args.maestro, devices[0], flows, args.timeout)
    finally:
        if ocr_proc is not None:
            ocr_proc.terminate()
            try:
                ocr_proc.wait(timeout=5)
            except Exception:
                ocr_proc.kill()

    if args.only_failed and prior_rows:
        by_name = {r["flow"]: r for r in prior_rows}
        for r in rows:
            by_name[r["flow"]] = r
        rows = [by_name[f.name] for f in discover_flows(args.module) if f.name in by_name]
        seen = {r["flow"] for r in rows}
        for r in prior_rows:
            if r["flow"] not in seen:
                rows.append(r)

    passed = sum(1 for r in rows if r["status"] == "PASS")
    crashed = sum(1 for r in rows if r["status"] == "CRASH")
    failed = sum(1 for r in rows if r["status"] == "FAIL")
    summary = {
        "module": args.module,
        "total": len(rows),
        "passed": passed,
        "failed": failed,
        "crashed": crashed,
        "pass_percent": round((passed / len(rows)) * 100, 2) if rows else 0.0,
        "execution_time_sec": round(time.time() - t0, 2),
        "device": ",".join(devices),
        "devices": devices,
        "app": APP_ID,
        "rows": rows,
    }
    js = OUT / f"{args.module}_summary.json"
    js.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    xlsx = write_excel(args.module, summary)

    index_path = OUT / "index.json"
    index = []
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            index = []
    index = [x for x in index if x.get("module") != args.module]
    index.append({k: summary[k] for k in summary if k != "rows"})
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    print("\n===== MODULE SUMMARY =====")
    print(json.dumps({k: summary[k] for k in summary if k != "rows"}, indent=2))
    print(f"report: {xlsx}")
    print(f"summary: {js}")
    _scrub_maestro_temp_copies(MAESTRO_TMP, Path(os.environ.get("TEMP", "")))
    return 0 if (failed + crashed) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
