"""Run all ATP Excel cases that have a Maestro flow mapping.

Uses reports/module_runs/full_sheet/excel_flow_map.json
Sense setup once, then SKIP_SENSE=1 for speed.
Updates Excel Pass/Fail (Android) after each case.
CLI: https://docs.maestro.dev/maestro-cli/maestro-cli-commands-and-options
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill

REPO = Path(__file__).resolve().parents[1]
XLSX = Path(r"c:\Users\CA Global\Downloads\Hp new sprocket ATP Sheet.xlsx")
OUT_DIR = REPO / "reports" / "module_runs" / "full_sheet"
MAP = OUT_DIR / "excel_flow_map.json"
SUMMARY = OUT_DIR / "full_sheet_summary.json"
MAESTRO = Path(r"C:\Tools\maestro-parallel\bin\maestro.bat")


def _detect_device() -> str:
    try:
        out = subprocess.check_output(["adb", "devices"], text=True, encoding="utf-8", errors="replace")
    except Exception:
        out = ""
    serials = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serials.append(parts[0])
    env = (os.environ.get("ANDROID_SERIAL") or "").strip()
    if env and env in serials:
        return env
    for preferred in ("YLQGQOYS8TONEYNZ", "PVFM5L7LTGHUNZA6"):
        if preferred in serials:
            return preferred
    return serials[0] if serials else (env or "UNKNOWN")


DEVICE = _detect_device()


def _extract_reason(blob: str, exit_code: int) -> str:
    lines = [
        ln
        for ln in (blob or "").splitlines()
        if ln.strip() and "JAVA_TOOL_OPTIONS" not in ln and "Picked up" not in ln
    ]
    cleaned = "\n".join(lines)
    m = re.search(
        r"(Unable to launch app[^\n]*|Assertion is false[^\n]*|Element not found[^\n]*|Timeout[^\n]*|Parsing Failed[^\n]*|UNAVAILABLE[^\n]*|Device [^\n]*not connected[^\n]*)",
        cleaned,
        re.I,
    )
    if m:
        return m.group(1)[:300]
    for ln in reversed(lines):
        if "Failed" in ln or "FAILED" in ln:
            return ln[:300]
    return f"exit {exit_code}"


def _run_one(excel_id: str, rel: str, *, skip_sense: bool, max_attempts: int = 1) -> dict:
    flow = REPO / rel
    safe = re.sub(r"[^\w\-]+", "_", excel_id)[:80]
    junit = OUT_DIR / "junit" / f"{safe}.xml"
    debug = OUT_DIR / "debug" / safe
    junit.parent.mkdir(parents=True, exist_ok=True)
    debug.mkdir(parents=True, exist_ok=True)
    # Global --device before test; space-separated values
    cmd = [
        str(MAESTRO),
        "--no-ansi",
        "--device",
        DEVICE,
        "test",
        "--format",
        "junit",
        "--output",
        str(junit),
        "--debug-output",
        str(debug),
        "-e",
        f"SKIP_SENSE={'1' if skip_sense else '0'}",
        str(flow),
    ]
    print(f"\n=== RUN {excel_id} ===", flush=True)
    t0 = time.time()
    env = {
        **os.environ,
        "ANDROID_SERIAL": DEVICE,
        "MAESTRO_CLI_NO_ANSI": "1",
        "NO_COLOR": "1",
        "TERM": "dumb",
    }
    prev = env.get("JAVA_TOOL_OPTIONS", "").strip()
    jansi = (
        "-Djava.net.preferIPv4Stack=true "
        "-Dorg.fusesource.jansi.Ansi.disable=true "
        "-Djansi.passthrough=true"
    )
    env["JAVA_TOOL_OPTIONS"] = f"{prev} {jansi}".strip() if prev else jansi

    last: dict | None = None
    for attempt in range(1, max_attempts + 1):
        log = OUT_DIR / "logs" / f"{safe}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        try:
            with log.open("w", encoding="utf-8", errors="replace") as lf:
                proc = subprocess.run(
                    cmd,
                    cwd=str(REPO),
                    stdout=lf,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=600,
                    env=env,
                )
        except subprocess.TimeoutExpired:
            elapsed = round(time.time() - t0, 1)
            last = {
                "excel_id": excel_id,
                "flow": rel,
                "status": "FAIL",
                "elapsed_s": elapsed,
                "failure_reason": "Timeout after 600s",
                "attempts": attempt,
            }
            break
        elapsed = round(time.time() - t0, 1)
        blob = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
        status = "PASS" if proc.returncode == 0 else "FAIL"
        reason = _extract_reason(blob, proc.returncode) if status == "FAIL" else ""
        last = {
            "excel_id": excel_id,
            "flow": rel,
            "status": status,
            "elapsed_s": elapsed,
            "failure_reason": reason,
            "attempts": attempt,
            "log": str(log),
        }
        print(f"=== {excel_id} {status} ({elapsed}s) ===", flush=True)
        if status == "PASS":
            return last
        if attempt < max_attempts and re.search(
            r"Unable to launch|not connected|UNAVAILABLE|CommandFailed|Maestro driver",
            reason + blob,
            re.I,
        ):
            subprocess.run(
                ["adb", "-s", DEVICE, "shell", "input", "keyevent", "224"],
                capture_output=True,
            )
            time.sleep(2)
            continue
        break
    assert last is not None
    return last


def _match_row(aid: str, mod: str, excel_id: str) -> bool:
    if aid.strip().casefold() == excel_id.casefold():
        if excel_id.casefold() == "print preview_06" and "select" in mod.lower():
            return False
        return True
    if excel_id.casefold() == "print preview_06 (select)":
        return aid.casefold() == "print preview_06" and "select" in mod.lower()
    return re.sub(r"\s+", "", aid).casefold() == re.sub(r"\s+", "", excel_id).casefold()


def _update_excel_one(rec: dict) -> None:
    wb = load_workbook(XLSX)
    ws = wb["New Sprocket Final ATP"]
    pf = PatternFill("solid", fgColor="C6EFCE")
    ff = PatternFill("solid", fgColor="FFC7CE")
    excel_id = rec["excel_id"]
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        aid = str(row[0].value or "").strip()
        mod = str(row[1].value or "")
        if not _match_row(aid, mod, excel_id):
            continue
        st = rec["status"]
        reason = (rec.get("failure_reason") or "").strip()
        elapsed = rec.get("elapsed_s", "")
        row[6].value = (
            f"Maestro {st} on {DEVICE} (full sheet, {elapsed}s)"
            + (f": {reason[:160]}" if st != "PASS" and reason else "")
        )
        row[7].value = "Pass" if st == "PASS" else "Fail"
        row[7].fill = pf if st == "PASS" else ff
        row[7].font = Font(bold=True)
        break
    wb.save(XLSX)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not MAP.exists():
        print(f"Missing map: {MAP}. Generate excel_flow_map.json first.", flush=True)
        return 2
    mapping = json.loads(MAP.read_text(encoding="utf-8"))
    flows = mapping.get("matched") or []
    # Optional filter: --only-folder quick-print
    only_folder = None
    import sys

    if "--only-folder" in sys.argv:
        i = sys.argv.index("--only-folder")
        only_folder = sys.argv[i + 1]
        flows = [f for f in flows if f"/{only_folder}/" in f["flow"].replace("\\", "/")]
    # Resume: skip already PASS in summary
    prior: dict[str, dict] = {}
    if SUMMARY.exists() and "--resume" in sys.argv:
        try:
            prior = {
                r["excel_id"]: r
                for r in (json.loads(SUMMARY.read_text(encoding="utf-8")).get("rows") or [])
            }
        except Exception:
            prior = {}

    print(f"Device: {DEVICE}", flush=True)
    print(f"Cases to run: {len(flows)} (unmatched Excel IDs skipped: {mapping.get('unmatched_count')})", flush=True)

    subprocess.run(["adb", "-s", DEVICE, "shell", "input", "keyevent", "224"], capture_output=True)
    subprocess.run(
        [
            "adb",
            "-s",
            DEVICE,
            "shell",
            "monkey",
            "-p",
            "com.caglobal.hp.sprocket",
            "-c",
            "android.intent.category.LAUNCHER",
            "1",
        ],
        capture_output=True,
    )
    time.sleep(3)

    # Sense once
    print("\n=== SETUP Sense 5D:6C ===", flush=True)
    setup = _run_one(
        "SETUP_SENSE",
        "ATP TestCase Flows/common/subflows/setup_sense_once.yaml",
        skip_sense=False,
        max_attempts=1,
    )
    print(f"SETUP {setup['status']}", flush=True)

    results: list[dict] = []
    # keep prior non-PASS for resume rewrite
    if prior:
        results = [prior[k] for k in prior if k != "SETUP_SENSE"]

    for i, item in enumerate(flows, 1):
        eid, rel = item["excel_id"], item["flow"]
        if "--resume" in sys.argv and eid in prior and prior[eid].get("status") == "PASS":
            print(f"--- skip PASS {eid} ---", flush=True)
            continue
        print(f"\n[{i}/{len(flows)}]", flush=True)
        rec = _run_one(eid, rel, skip_sense=True, max_attempts=2)
        # replace if exists
        results = [r for r in results if r["excel_id"] != eid]
        results.append(rec)
        try:
            _update_excel_one(rec)
        except Exception as exc:
            print(f"Excel update warn: {exc}", flush=True)
        SUMMARY.write_text(
            json.dumps(
                {
                    "device": DEVICE,
                    "updated": datetime.now(timezone.utc).isoformat(),
                    "total_mapped": len(flows),
                    "completed": len(results),
                    "passed": sum(1 for r in results if r["status"] == "PASS"),
                    "failed": sum(1 for r in results if r["status"] == "FAIL"),
                    "rows": results,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    passed = sum(1 for r in results if r["status"] == "PASS")
    print(f"\nDone: {passed}/{len(results)} PASS", flush=True)
    print(f"Summary: {SUMMARY}", flush=True)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
