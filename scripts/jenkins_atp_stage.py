#!/usr/bin/env python3
"""
Jenkins CPS helper: run / validate / excel for one ATP folder in one process.
Keeps Jenkinsfile small (avoids WorkflowScript MethodTooLargeException).

Does not replace run_atp_testcase_flows.ps1 for manual runs — Jenkins ``cmd_run`` uses
``python -m execution.atp_jenkins_orchestrator`` (blocking Stack A; same reports/status as ``run_one_flow_on_device.bat``).
Suite ids match run_atp_testcase_flows.ps1 Get-AtpSuiteId(folder).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ORCHESTRATOR_MODULE = "execution.atp_jenkins_orchestrator"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from execution.atp_folder_paths import discover_atp_yaml_files, resolve_atp_subfolder  # noqa: E402
from execution.subprocess_launch import log_subprocess_launch, windows_cmd_bat_argv  # noqa: E402


def folder_to_suite_id(folder: str) -> str:
    t = re.sub(r"[^a-zA-Z0-9]+", "_", folder.strip())
    t = t.strip("_").lower()
    if not t:
        t = "unknown"
    return f"atp_{t}"


def touch_flag(name: str) -> None:
    (REPO / name).write_text("1\n", encoding="utf-8")


def _adb_serials_via_python() -> tuple[str | None, list[str], str]:
    """
    Space-safe live adb devices (no cmd.exe). Returns (adb_exe, serials, raw_output).
    Prefer ADB_HOME / ANDROID_HOME / C:\\Tools\\platform-tools over PATH WinGet adb.
    """
    from execution.subprocess_launch import resolve_adb_executable

    adb = resolve_adb_executable()
    if not adb:
        for candidate in (
            Path(r"C:\Tools\platform-tools\adb.exe"),
            Path(r"C:\Android\platform-tools\adb.exe"),
            Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe",
        ):
            if candidate.is_file():
                adb = str(candidate.resolve())
                break
    if not adb:
        return None, [], ""
    try:
        # Do not capture start-server pipes — can deadlock on Windows like WinGet adb.
        subprocess.run(
            [adb, "start-server"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=25,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass
    # Settle window — racing devices right after start-server often hangs on flaky USB agents.
    import time as _time

    _time.sleep(5)
    try:
        proc = subprocess.run(
            [adb, "devices"],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return adb, [], f"ERROR: adb devices failed: {exc}"
    raw = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    serials: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        m = re.match(r"^(\S+)\s+device\s*$", line)
        if m:
            serials.append(m.group(1))
    return adb, serials, raw


def _write_detected_devices(repo: Path, serials: list[str]) -> Path:
    out = repo / "detected_devices.txt"
    out.write_text("\n".join(serials) + ("\n" if serials else ""), encoding="utf-8")
    return out


def _refresh_devices_on_this_agent(repo: Path) -> int:
    """
    Re-run adb device discovery on the current Windows agent before Maestro.
    Hybrid: Detect Connected Devices may run on a different executor than ATP stages.

    Returns 0 when at least one authorized device is written to detected_devices.txt.
    """
    if os.environ.get("ATP_REFRESH_DEVICES_BEFORE_RUN", "1").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        print("[jenkins_atp_stage] ATP_REFRESH_DEVICES_BEFORE_RUN=0 — skip device refresh", flush=True)
        return 0
    bat = repo / "scripts" / "windows_agent" / "list_devices.bat"
    if not bat.is_file():
        bat = repo / "scripts" / "list_devices.bat"
    env = os.environ.copy()
    # Avoid cmd.exe splitting workspace paths if a prior stage set MAESTRO_OPTS with -Duser.home=...
    for _k in (
        "MAESTRO_OPTS",
        "ATP_JAVA_USER_HOME",
        "JAVA_TOOL_OPTIONS",
        "_JAVA_OPTIONS",
        "JDK_JAVA_OPTIONS",
    ):
        env.pop(_k, None)

    if bat.is_file():
        print(
            f"[jenkins_atp_stage] refreshing detected_devices.txt on this agent ({bat.name})",
            flush=True,
        )
        cmd = windows_cmd_bat_argv(bat, str(repo.resolve()))
        log_subprocess_launch(cmd, cwd=repo.resolve(), shell=False, label="list_devices")
        subprocess.run(
            cmd,
            cwd=str(repo.resolve()),
            env=env,
            check=False,
            shell=False,
        )

    # Authoritative fallback: Python argv adb (space-safe; works when bat/OutFile path is broken).
    adb, serials, raw = _adb_serials_via_python()
    print(f"[jenkins_atp_stage] python adb fallback exe={adb!r}", flush=True)
    print("[jenkins_atp_stage] python adb devices output:", flush=True)
    print(raw if raw.strip() else "(empty)", flush=True)
    if serials:
        out = _write_detected_devices(repo, serials)
        print(
            f"[jenkins_atp_stage] wrote {len(serials)} device(s) to {out}: {', '.join(serials)}",
            flush=True,
        )
        return 0

    print(
        "[jenkins_atp_stage] ERROR: no Android device in state 'device'. "
        "On the agent user session run:  adb kill-server & adb devices  "
        "(expect SERIAL\\tdevice). Prefer C:\\Tools\\platform-tools over WinGet adb.",
        flush=True,
    )
    _write_detected_devices(repo, [])
    return 1


def _log_orchestrator_fingerprint(repo: Path) -> None:
    orch_py = repo / "execution" / "atp_jenkins_orchestrator.py"
    print(f"[jenkins_atp_stage] orchestrator_module={ORCHESTRATOR_MODULE}", flush=True)
    print(f"[jenkins_atp_stage] orchestrator_path={orch_py}", flush=True)
    if orch_py.is_file():
        print(f"[jenkins_atp_stage] orchestrator_mtime={orch_py.stat().st_mtime}", flush=True)
    rev_file = repo / "execution" / "ORCHESTRATOR_REV.txt"
    if rev_file.is_file():
        rev = rev_file.read_text(encoding="utf-8", errors="replace").strip().splitlines()[0].strip()
        if rev:
            print(f"[jenkins_atp_stage] orchestrator_rev={rev}", flush=True)


def _log_folder_discovery(folder_arg: str, resolved: str) -> None:
    print(f"[jenkins_atp_stage] workspace={REPO.resolve()}", flush=True)
    print(f"[jenkins_atp_stage] folder_arg={folder_arg!r} resolved_folder={resolved!r}", flush=True)
    flows = discover_atp_yaml_files(REPO, resolved or folder_arg, exclude_subflows=True)
    if flows:
        print(f"[jenkins_atp_stage] preflight: {len(flows)} yaml test file(s) to run:", flush=True)
        for p in flows:
            try:
                rel = p.resolve().relative_to(REPO.resolve())
            except ValueError:
                rel = p
            print(f"[jenkins_atp_stage]   - {rel}", flush=True)
    else:
        print("[jenkins_atp_stage] preflight: 0 yaml test files (stage will fail)", flush=True)


def _validate_maestro_yaml_preflight() -> int:
    if os.environ.get("ATP_VALIDATE_MAESTRO_YAML", "1").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return 0
    validator = REPO / "scripts" / "validate_maestro_yaml.py"
    atp_root = REPO / "ATP TestCase Flows"
    if not validator.is_file():
        print("[jenkins_atp_stage] validate_maestro_yaml: script missing — skip", flush=True)
        return 0
    if not atp_root.is_dir():
        return 0
    cmd = [sys.executable, str(validator), str(atp_root)]
    log_subprocess_launch(cmd, cwd=REPO, shell=False, label="validate_maestro_yaml")
    proc = subprocess.run(cmd, cwd=str(REPO), check=False)
    if proc.returncode != 0:
        print("[jenkins_atp_stage] ERROR: Maestro YAML validation failed", flush=True)
    return proc.returncode


def cmd_run(folder: str, app: str, clear_state: str, maestro_cmd: str) -> int:
    resolved = resolve_atp_subfolder(REPO, folder)
    sid = folder_to_suite_id(resolved or folder)
    _log_folder_discovery(folder, resolved)
    yaml_rc = _validate_maestro_yaml_preflight()
    if yaml_rc != 0:
        touch_flag(f"{sid}_failed.flag")
        return yaml_rc
    refresh_rc = _refresh_devices_on_this_agent(REPO)
    if refresh_rc != 0:
        touch_flag(f"{sid}_failed.flag")
        return refresh_rc
    _log_orchestrator_fingerprint(REPO)
    maestro_argv = [
        sys.executable,
        "-m",
        ORCHESTRATOR_MODULE,
        str(REPO),
        app,
        clear_state,
        maestro_cmd,
        resolved or folder,
    ]
    if not discover_atp_yaml_files(REPO, resolved or folder, exclude_subflows=True):
        print("[jenkins_atp_stage] ERROR: no yaml test files — aborting stage", flush=True)
        touch_flag(f"{sid}_no_results.flag")
        return 1
    print(f"[jenkins_atp_stage] maestro_command={' '.join(maestro_argv)!r}", flush=True)
    # Stack A: blocking Python orchestrator (no detached PowerShell Start-Process chain).
    p = subprocess.run(maestro_argv, cwd=str(REPO))
    if p.returncode != 0:
        touch_flag(f"{sid}_failed.flag")
    return p.returncode


def cmd_validate(suite_id: str) -> int:
    """Match Jenkins bat: set *_no_results.flag on issues; step exit 0 (catchError / flags)."""
    root = REPO
    py = sys.executable
    v = subprocess.run(
        [py, str(REPO / "scripts" / "validate_suite_artifacts.py"), suite_id, str(root)],
        cwd=str(root),
    )
    if v.returncode != 0:
        touch_flag(f"{suite_id}_no_results.flag")

    status_dir = root / "status"
    rep = root / "reports" / suite_id
    st = list(status_dir.glob(f"{suite_id}__*.txt")) if status_dir.is_dir() else []
    csv = list((rep / "results").glob("*.csv")) if (rep / "results").is_dir() else []
    logs = list((rep / "logs").glob("*.log")) if (rep / "logs").is_dir() else []
    if not st or not csv or not logs:
        touch_flag(f"{suite_id}_no_results.flag")
    return 0


def cmd_excel(folder: str) -> int:
    """Per-folder Excel merge; flag on failure; exit 0 like Jenkins bat echo chain."""
    sid = folder_to_suite_id(folder)
    label = folder
    (REPO / "build-summary").mkdir(parents=True, exist_ok=True)
    out_dir = REPO / "reports" / f"{sid}_summary"
    py = sys.executable
    # Do NOT pass --skip-if-empty: failed runs may have no parsable status rows yet we still
    # must merge into final_execution_report.xlsx (generate_excel_report writes placeholder rows).
    p = subprocess.run(
        [
            py,
            str(REPO / "scripts" / "generate_excel_report.py"),
            str(REPO / "status"),
            str(out_dir),
            sid,
            label,
        ],
        cwd=str(REPO),
    )
    if p.returncode != 0:
        touch_flag(f"{sid}_report_failed.flag")
    return 0


def cmd_all(folder: str, app: str, clear_state: str, maestro_cmd: str) -> int:
    """One Jenkins stage per folder: run → validate → excel (shrinks CPS bytecode vs 3 stages)."""
    resolved = resolve_atp_subfolder(REPO, folder)
    sid = folder_to_suite_id(resolved or folder)
    print(f"[jenkins_atp_stage] === ATP folder={folder!r} resolved={resolved!r} suite={sid!r} ===", flush=True)
    print(
        f"[jenkins_atp_stage] agent_env MAESTRO_HOME={os.environ.get('MAESTRO_HOME', '')} "
        f"ATP_MAESTRO_PARALLEL_HOME={os.environ.get('ATP_MAESTRO_PARALLEL_HOME', '')} "
        f"JAVA_HOME={os.environ.get('JAVA_HOME', '')}",
        flush=True,
    )
    rc_run = cmd_run(folder, app, clear_state, maestro_cmd)
    cmd_validate(sid)
    cmd_excel(resolved or folder)
    if rc_run != 0:
        print(f"[jenkins_atp_stage] stage_status=FAILED suite={sid!r} exit={rc_run}", flush=True)
    else:
        print(f"[jenkins_atp_stage] stage_status=OK suite={sid!r}", flush=True)
    return rc_run


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "Usage: jenkins_atp_stage.py run <Folder> <APP_PACKAGE> <CLEAR_STATE> <MAESTRO_CMD>\n"
            "       jenkins_atp_stage.py validate <suite_id>\n"
            "       jenkins_atp_stage.py excel <Folder>\n"
            "       jenkins_atp_stage.py all <Folder> <APP_PACKAGE> <CLEAR_STATE> <MAESTRO_CMD>",
            file=sys.stderr,
        )
        return 2
    op = sys.argv[1].lower().strip()
    if op == "run":
        if len(sys.argv) < 6:
            print("run: need Folder APP CLEAR_STATE MAESTRO_CMD", file=sys.stderr)
            return 2
        return cmd_run(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    if op == "validate":
        if len(sys.argv) < 3:
            print("validate: need suite_id", file=sys.stderr)
            return 2
        return cmd_validate(sys.argv[2].strip().lower())
    if op == "excel":
        if len(sys.argv) < 3:
            print("excel: need Folder", file=sys.stderr)
            return 2
        return cmd_excel(sys.argv[2])
    if op == "all":
        if len(sys.argv) < 6:
            print("all: need Folder APP CLEAR_STATE MAESTRO_CMD", file=sys.stderr)
            return 2
        return cmd_all(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    print(f"Unknown op: {op}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
