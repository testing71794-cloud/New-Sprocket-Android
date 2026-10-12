"""Run all Excel Print Preview ATP cases (through Print Preview CTA).

Stops at Print Preview readiness (Print CTA) — does not wait for physical Print Complete.
Uses Maestro CLI space-separated flags per https://docs.maestro.dev/maestro-cli/maestro-cli-commands-and-options
After first successful Sense connect, passes -e SKIP_SENSE=1 to speed later cases.
Updates ATP Excel Pass/Fail (Android).
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
OUT_DIR = REPO / "reports" / "module_runs" / "print_preview_suite"
SUMMARY = OUT_DIR / "print_preview_suite_summary.json"
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
    env = (os.environ.get("ANDROID_SERIAL") or os.environ.get("MAESTRO_DEVICE") or "").strip()
    if env and env in serials:
        return env
    for preferred in ("YLQGQOYS8TONEYNZ", "PVFM5L7LTGHUNZA6"):
        if preferred in serials:
            return preferred
    return serials[0] if serials else (env or "YLQGQOYS8TONEYNZ")


DEVICE = _detect_device()

# Excel Print Preview_* → PR flows (through Print Preview only)
FLOWS: list[tuple[str, str]] = [
    ("Print Preview_01", "ATP TestCase Flows/printing/PR_01 - BLE printer connection and Quick Print navigation.yaml"),
    ("Print Preview_02", "ATP TestCase Flows/printing/PR_02 - HP600 Wi-Fi connection and Quick Print navigation.yaml"),
    ("Print Preview_03", "ATP TestCase Flows/printing/PR_03 - HP200 2 x 3 preview canvas.yaml"),
    ("Print Preview_04", "ATP TestCase Flows/printing/PR_04 - Original HP Sprocket 2 x 3 preview canvas.yaml"),
    ("Print Preview_05", "ATP TestCase Flows/printing/PR_05 - HP Sprocket Studio 2 x 3 preview canvas.yaml"),
    ("Print Preview_06", "ATP TestCase Flows/printing/PR_06a - HP Sprocket Studio Plus 2 x 3 preview canvas.yaml"),
    ("Print Preview_06 (Select)", "ATP TestCase Flows/printing/PR_06b - HP Sprocket Select 2.3 x 3.4 preview canvas.yaml"),
    ("Print Preview_07", "ATP TestCase Flows/printing/PR_07 - HP Sprocket Plus 2.3 x 3.4 preview canvas.yaml"),
    ("Print Preview_08", "ATP TestCase Flows/printing/PR_08 - HP Sprocket 3x4 3.5 x 4.25 preview canvas.yaml"),
    ("Print Preview_09", "ATP TestCase Flows/printing/PR_09 - Connected and disconnected printer status.yaml"),
    ("Print Preview_10", "ATP TestCase Flows/printing/PR_10 - Copies controls from 1 to 10.yaml"),
    ("Print Preview_11", "ATP TestCase Flows/printing/PR_11 - Tiles options and default 2x2 grid.yaml"),
    ("Print Preview_12", "ATP TestCase Flows/printing/PR_12 - Apply an AI tool from Print Preview.yaml"),
    ("Print Preview_13", "ATP TestCase Flows/printing/PR_13 - Apply a Frame from Edit Options.yaml"),
    ("Print Preview_14", "ATP TestCase Flows/printing/PR_14 - Edit one of four selected photos.yaml"),
    ("Print Preview_15", "ATP TestCase Flows/printing/PR_15 - Print Preview image gestures and Fit Fill.yaml"),
    ("Print Preview_16", "ATP TestCase Flows/printing/PR_16 - Fit Fill toast session behavior.yaml"),
    ("Print Preview_17", "ATP TestCase Flows/printing/PR_17 - Image rotation snap guide.yaml"),
    ("Print Preview_18", "ATP TestCase Flows/printing/PR_18 - Image center reposition snap.yaml"),
    ("Print Preview_19", "ATP TestCase Flows/printing/PR_19 - Image edge reposition snap.yaml"),
    ("Print Preview_20", "ATP TestCase Flows/printing/PR_20 - Back navigation without changes.yaml"),
    ("Print Preview_21", "ATP TestCase Flows/printing/PR_21 - Save as new photo popup after editing.yaml"),
    ("Print Preview_22", "ATP TestCase Flows/printing/PR_22 - Save or discard edited image.yaml"),
    ("Print Preview_23", "ATP TestCase Flows/printing/PR_23 - Low-resolution warning from native Gallery.yaml"),
    ("Print Preview_24", "ATP TestCase Flows/printing/PR_24 - Low-resolution warning from social media Gallery.yaml"),
]


def _extract_reason(blob: str, exit_code: int) -> str:
    lines = [
        ln
        for ln in (blob or "").splitlines()
        if ln.strip() and "JAVA_TOOL_OPTIONS" not in ln and "Picked up" not in ln
    ]
    cleaned = "\n".join(lines)
    m = re.search(
        r"(Unable to launch app[^\n]*|Assertion is false[^\n]*|Element not found[^\n]*|Timeout[^\n]*|Device [^\n]*not connected[^\n]*)",
        cleaned,
        re.I,
    )
    if m:
        return m.group(1)[:300]
    for ln in reversed(lines):
        if "Failed" in ln or "FAILED" in ln:
            return ln[:300]
    return f"exit {exit_code}"


def _run_one(excel_id: str, rel: str, *, skip_sense: bool, max_attempts: int = 2) -> dict:
    flow = REPO / rel
    safe = re.sub(r"[^\w\-]+", "_", excel_id)
    junit = OUT_DIR / f"{safe}.xml"
    debug = OUT_DIR / f"{safe}_debug"
    debug.mkdir(parents=True, exist_ok=True)
    # Global --device before test; space-separated values.
    # https://docs.maestro.dev/maestro-cli/maestro-cli-commands-and-options
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
    print(f"\n=== RUN {excel_id} (SKIP_SENSE={1 if skip_sense else 0}) ===", flush=True)
    print(" ".join(cmd), flush=True)
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
        log = OUT_DIR / f"{safe}.log"
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
            with log.open("a", encoding="utf-8", errors="replace") as lf:
                lf.write("\nTIMEOUT after 600s\n")
            last = {
                "excel_id": excel_id,
                "flow": rel,
                "status": "FAIL",
                "exit_code": -1,
                "elapsed_s": elapsed,
                "failure_reason": "Timeout after 600s",
                "junit": str(junit),
                "log": str(log),
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
            "exit_code": proc.returncode,
            "elapsed_s": elapsed,
            "failure_reason": reason,
            "junit": str(junit),
            "log": str(log),
            "attempts": attempt,
        }
        print(f"=== {excel_id} {status} ({elapsed}s) attempt {attempt} ===", flush=True)
        if status == "PASS":
            return last
        if attempt < max_attempts and re.search(
            r"Unable to launch app|not connected|device offline|Maestro driver|UiAutomator|UNAVAILABLE|CommandFailed",
            reason + "\n" + blob,
            re.I,
        ):
            print(f"--- retry {excel_id} ---", flush=True)
            subprocess.run(["adb", "-s", DEVICE, "wait-for-device"], capture_output=True, timeout=60)
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
    if excel_id.casefold() == "print preview_06 (select)":
        return aid.casefold() == "print preview_06" and "select" in mod.lower()
    if aid.strip().casefold() == excel_id.casefold():
        if excel_id.casefold() == "print preview_06" and "select" in mod.lower():
            return False
        return True
    return re.sub(r"\s+", "", aid).casefold() == re.sub(r"\s+", "", excel_id).casefold()


def _update_excel(rows: list[dict]) -> int:
    wb = load_workbook(XLSX)
    ws = wb["New Sprocket Final ATP"]
    pf = PatternFill("solid", fgColor="C6EFCE")
    ff = PatternFill("solid", fgColor="FFC7CE")
    by_id = {r["excel_id"]: r for r in rows}
    updated = 0
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        aid = str(row[0].value or "").strip()
        mod = str(row[1].value or "")
        for excel_id, rec in by_id.items():
            if not _match_row(aid, mod, excel_id):
                continue
            st = rec["status"]
            reason = (rec.get("failure_reason") or "").strip()
            elapsed = rec.get("elapsed_s", "")
            row[6].value = (
                f"Maestro {st} on {DEVICE} (Print Preview suite, {elapsed}s)"
                + (f": {reason[:160]}" if st != "PASS" and reason else "")
            )
            row[7].value = "Pass" if st == "PASS" else "Fail"
            row[7].fill = pf if st == "PASS" else ff
            row[7].font = Font(bold=True)
            updated += 1
            break
    wb.save(XLSX)
    return updated


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Device: {DEVICE}", flush=True)
    print(f"Cases: {len(FLOWS)} Print Preview flows (through Print CTA)", flush=True)

    subprocess.run(
        ["adb", "-s", DEVICE, "shell", "input", "keyevent", "224"],
        capture_output=True,
    )
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
    time.sleep(2)

    # One-time Sense connect (HP Sprocket Sense 5D:6C), then all cases SKIP_SENSE=1
    print("\n=== SETUP Sense 5D:6C once ===", flush=True)
    setup = _run_one(
        "SETUP_SENSE",
        "ATP TestCase Flows/common/subflows/setup_sense_once.yaml",
        skip_sense=False,
        max_attempts=1,
    )
    print(f"=== SETUP {setup['status']} ({setup.get('elapsed_s')}s) ===", flush=True)

    results: list[dict] = []
    for excel_id, rel in FLOWS:
        rec = _run_one(excel_id, rel, skip_sense=True)
        results.append(rec)
        SUMMARY.write_text(
            json.dumps(
                {
                    "device": DEVICE,
                    "started": datetime.now(timezone.utc).isoformat(),
                    "scope": "Print Preview sheet cases through Print CTA (no physical print wait)",
                    "rows": results,
                    "passed": sum(1 for r in results if r["status"] == "PASS"),
                    "failed": sum(1 for r in results if r["status"] == "FAIL"),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    n = _update_excel(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    print(f"\nDone: {passed}/{len(results)} PASS; Excel rows updated: {n}", flush=True)
    print(f"Summary: {SUMMARY}", flush=True)
    for r in results:
        mark = "PASS" if r["status"] == "PASS" else "FAIL"
        extra = f" | {r.get('failure_reason','')[:80]}" if r["status"] != "PASS" else ""
        print(f"  {mark} {r['excel_id']} ({r.get('elapsed_s')}s){extra}", flush=True)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
