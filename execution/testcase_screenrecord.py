"""Per-testcase Android screenrecord. Device-safe paths; does not change Maestro scheduling.

Stock Android screenrecord stops at 180s. Longer flows keep the first three minutes.
Disable with ATP_SCREENRECORD=0.
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


def _truthy(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() not in ("0", "false", "no", "off")


def _slug(value: str, *, max_len: int = 48) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "unknown").strip("._") or "unknown"
    return s[:max_len]


def _adb() -> str:
    home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or ""
    if home:
        cand = Path(home) / "platform-tools" / "adb.exe"
        if cand.is_file():
            return str(cand)
        cand2 = Path(home) / "platform-tools" / "adb"
        if cand2.is_file():
            return str(cand2)
    return "adb"


@dataclass
class ScreenRecordSession:
    device_id: str
    remote: str
    local: Path
    proc: subprocess.Popen[bytes] | None


def start_screenrecord(
    *,
    repo: Path,
    device_id: str,
    suite_id: str,
    case_id: str,
) -> ScreenRecordSession | None:
    if not _truthy("ATP_SCREENRECORD", "1"):
        return None
    adb = _adb()
    ts = time.strftime("%Y%m%d_%H%M%S")
    dev = _slug(device_id, max_len=32)
    mod = _slug(suite_id, max_len=40)
    cid = _slug(case_id, max_len=40)
    dest_dir = repo / "reports" / "videos" / dev / mod
    dest_dir.mkdir(parents=True, exist_ok=True)
    local = dest_dir / f"{dev}_{mod}_{cid}_FAIL_{ts}.mp4"
    remote = f"/sdcard/atp_{os.getpid()}_{dev}_{cid}.mp4"
    try:
        subprocess.run(
            [adb, "-s", device_id, "shell", "rm", "-f", remote],
            capture_output=True,
            timeout=15,
            check=False,
        )
        proc = subprocess.Popen(
            [
                adb,
                "-s",
                device_id,
                "shell",
                "screenrecord",
                "--time-limit",
                "180",
                "--bit-rate",
                "2000000",
                remote,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.4)
        if proc.poll() is not None:
            print(
                f"[ATP] screenrecord_start_failed device={device_id} case={case_id} "
                f"(adb screenrecord exited immediately)",
                flush=True,
            )
            return None
        print(f"[ATP] screenrecord_start device={device_id} case={case_id} remote={remote}", flush=True)
        return ScreenRecordSession(device_id=device_id, remote=remote, local=local, proc=proc)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"[ATP] screenrecord_start_error device={device_id} error={exc}", flush=True)
        return None


def stop_screenrecord(session: ScreenRecordSession | None, *, keep: bool) -> str:
    """Stop recording. Return repo-relative path if kept, else empty string."""
    if session is None:
        return ""
    adb = _adb()
    try:
        subprocess.run(
            [adb, "-s", session.device_id, "shell", "pkill", "-2", "screenrecord"],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass
    if session.proc is not None and session.proc.poll() is None:
        try:
            session.proc.terminate()
            session.proc.wait(timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            try:
                session.proc.kill()
            except OSError:
                pass
    time.sleep(0.6)
    if not keep:
        try:
            subprocess.run(
                [adb, "-s", session.device_id, "shell", "rm", "-f", session.remote],
                capture_output=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        print(f"[ATP] screenrecord_discarded device={session.device_id}", flush=True)
        return ""
    try:
        session.local.parent.mkdir(parents=True, exist_ok=True)
        pull = subprocess.run(
            [adb, "-s", session.device_id, "pull", session.remote, str(session.local)],
            capture_output=True,
            timeout=60,
            check=False,
        )
        subprocess.run(
            [adb, "-s", session.device_id, "shell", "rm", "-f", session.remote],
            capture_output=True,
            timeout=15,
            check=False,
        )
        if pull.returncode != 0 or not session.local.is_file() or session.local.stat().st_size < 64:
            print(
                f"[ATP] screenrecord_pull_failed device={session.device_id} rc={pull.returncode}",
                flush=True,
            )
            return ""
        rel = session.local.as_posix()
        print(f"[ATP] screenrecord_kept path={rel}", flush=True)
        return rel
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"[ATP] screenrecord_stop_error device={session.device_id} error={exc}", flush=True)
        return ""


def append_video_to_status(status_file: Path, video_path: str, repo: Path) -> None:
    if not status_file.is_file():
        return
    try:
        p = Path(video_path)
        rel = p.resolve().relative_to(repo.resolve()).as_posix() if p.is_absolute() else video_path.replace("\\", "/")
    except ValueError:
        rel = video_path.replace("\\", "/")
    try:
        with status_file.open("a", encoding="utf-8") as fh:
            fh.write(f"video_path={rel}\n")
            fh.write(f"failure_video={rel}\n")
    except OSError:
        pass
