#!/usr/bin/env python3
"""
Serialize Maestro AndroidDriver session initialization across devices on one host.

Holds a global lock only until the per-flow log shows a stable session (e.g. 'Running on <serial>').
Full YAML execution continues in parallel after the lock is released.
"""
from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

_startup_lock = threading.Lock()


def startup_gate_enabled() -> bool:
    return os.environ.get("ATP_MAESTRO_STARTUP_GATE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def parallel_startup_delay_sec() -> float:
    raw = (os.environ.get("MAESTRO_PARALLEL_STARTUP_DELAY_SEC") or "5").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 5.0


def startup_ready_timeout_sec() -> float:
    raw = (os.environ.get("ATP_MAESTRO_STARTUP_READY_TIMEOUT_SEC") or "180").strip()
    try:
        return max(30.0, float(raw))
    except ValueError:
        return 180.0


def startup_max_retries() -> int:
    raw = (os.environ.get("ATP_MAESTRO_STARTUP_RETRIES") or "2").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 2


def planned_driver_port(launch_index: int) -> int:
    """Deterministic host port plan (7001 + index). CLI flag used only if ATP_MAESTRO_DRIVER_PORTS=1."""
    try:
        base = int((os.environ.get("ATP_MAESTRO_DRIVER_PORT_BASE") or "7001").strip())
    except ValueError:
        base = 7001
    return base + max(0, launch_index)


def _adb_exe() -> str | None:
    import shutil

    for root_env in ("ADB_HOME", "ANDROID_HOME", "ANDROID_SDK_ROOT"):
        root = os.environ.get(root_env, "").strip().strip('"')
        if not root:
            continue
        if root_env == "ADB_HOME":
            exe = Path(root) / ("adb.exe" if os.name == "nt" else "adb")
        else:
            exe = Path(root) / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
        if exe.is_file():
            return str(exe)
    found = shutil.which("adb")
    return found


def validate_device_health(device_id: str, *, suite_id: str, repo: Path) -> bool:
    """adb responsive + boot completed before Maestro startup."""
    if os.environ.get("ATP_DEVICE_HEALTH_CHECK", "1").strip().lower() in ("0", "false", "no", "off"):
        return True
    exe = _adb_exe()
    if not exe:
        print(f"[ATP] device_health_skip device={device_id} reason=adb_not_found", flush=True)
        return True
    t0 = time.time()
    try:
        w = subprocess.run(
            [exe, "-s", device_id, "wait-for-device"],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        if w.returncode != 0:
            print(
                f"[ATP] device_health_fail device={device_id} step=wait-for-device rc={w.returncode}",
                flush=True,
            )
            return False
        for _ in range(15):
            proc = subprocess.run(
                [exe, "-s", device_id, "shell", "getprop", "sys.boot_completed"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            val = (proc.stdout or "").strip()
            if val == "1":
                print(
                    f"[ATP] device_health_ok device={device_id} boot_completed=1 "
                    f"elapsed_sec={time.time() - t0:.1f}",
                    flush=True,
                )
                return True
            time.sleep(1.0)
        print(f"[ATP] device_health_fail device={device_id} step=boot_completed", flush=True)
        return False
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"[ATP] device_health_fail device={device_id} error={e}", flush=True)
        return False


def _read_log_tail(log_path: Path, max_lines: int = 80) -> str:
    if not log_path.is_file():
        return ""
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-max_lines:])
    except OSError:
        return ""


def _startup_failed_in_log(tail: str) -> str | None:
    if not tail:
        return None
    if "TcpForwarder.waitFor" in tail or "allocateForwarder" in tail:
        return "tcp_forwarder"
    if "TimeoutException" in tail and "tcpForward" in tail:
        return "tcp_forward_timeout"
    if "Unknown options:" in tail and "driver-host-port" in tail:
        return "unsupported_driver_port_flag"
    if "SHGetKnownFolderPath" in tail or "AppDirsException" in tail:
        return "app_dirs"
    return None


def wait_for_maestro_session_ready(
    *,
    log_path: Path,
    device_id: str,
    timeout_sec: float | None = None,
) -> tuple[bool, str]:
    """
    Poll per-flow Maestro log until session is ready or startup fails.
    Returns (ready, reason).
    """
    timeout = timeout_sec if timeout_sec is not None else startup_ready_timeout_sec()
    deadline = time.monotonic() + timeout
    device_re = re.compile(rf"Running on\s+{re.escape(device_id)}\b", re.I)
    while time.monotonic() < deadline:
        tail = _read_log_tail(log_path, 100)
        fail = _startup_failed_in_log(tail)
        if fail:
            return False, fail
        if device_re.search(tail) or (
            "> Flow " in tail and device_id in tail
        ):
            return True, "running_on"
        if "Running on" in tail and device_id in tail:
            return True, "running_on"
        if "> Flow " in tail and "Launch app" in tail:
            return True, "flow_started"
        time.sleep(1.0)
    return False, "ready_timeout"


def terminate_process_tree(pid: int) -> None:
    if pid <= 0:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
        else:
            os.kill(pid, 15)
    except (OSError, subprocess.TimeoutExpired):
        pass


def cleanup_after_startup_failure(
    device_id: str,
    *,
    repo: Path,
    suite_id: str,
    child_pid: int | None = None,
) -> None:
    """Best-effort cleanup after failed Maestro session startup (forwards + child tree)."""
    exe = _adb_exe()
    if exe:
        try:
            subprocess.run(
                [exe, "-s", device_id, "forward", "--remove-all"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    if child_pid:
        terminate_process_tree(child_pid)
    print(f"[ATP] startup_cleanup_done device={device_id} child_pid={child_pid or 0}", flush=True)


class MaestroStartupGate:
    """Context manager: acquire global startup lock until Maestro session is ready."""

    def __init__(
        self,
        *,
        device_id: str,
        flow_name: str,
        suite_id: str,
        repo: Path,
        launch_index: int,
        driver_port: int | None,
    ) -> None:
        self.device_id = device_id
        self.flow_name = flow_name
        self.suite_id = suite_id
        self.repo = repo
        self.launch_index = launch_index
        self.driver_port = driver_port
        self._enabled = startup_gate_enabled()
        self._acquired = False
        self._t_acquire: float | None = None

    def __enter__(self) -> MaestroStartupGate:
        if not self._enabled:
            return self
        self._t_acquire = time.time()
        print(
            f"[ATP] startup_lock_acquire device={self.device_id} flow={self.flow_name} "
            f"driver_port_plan={self.driver_port} thread={threading.current_thread().name}",
            flush=True,
        )
        _startup_lock.acquire()
        self._acquired = True
        return self

    def release_after_session_ready(self, *, log_path: Path, child_pid: int) -> tuple[bool, str]:
        """
        Wait for log-ready while holding lock, apply stabilization delay, then release lock.
        Child process continues running (parallel YAML execution).
        """
        if not self._enabled:
            return True, "gate_disabled"
        try:
            t0 = time.time()
            ready, reason = wait_for_maestro_session_ready(
                log_path=log_path,
                device_id=self.device_id,
            )
            wait_sec = time.time() - t0
            if not ready:
                print(
                    f"[ATP] startup_ready_fail device={self.device_id} flow={self.flow_name} "
                    f"reason={reason} wait_sec={wait_sec:.1f} child_pid={child_pid}",
                    flush=True,
                )
                return False, reason
            print(
                f"[ATP] startup_ready_ok device={self.device_id} flow={self.flow_name} "
                f"reason={reason} wait_sec={wait_sec:.1f} child_pid={child_pid}",
                flush=True,
            )
            delay = parallel_startup_delay_sec()
            if delay > 0:
                print(
                    f"[ATP] startup_stabilization_delay device={self.device_id} "
                    f"sleep_sec={delay:.1f}",
                    flush=True,
                )
                time.sleep(delay)
            held = (time.time() - (self._t_acquire or time.time()))
            print(
                f"[ATP] startup_lock_release device={self.device_id} flow={self.flow_name} "
                f"held_sec={held:.1f}",
                flush=True,
            )
            return True, reason
        finally:
            if self._acquired:
                _startup_lock.release()
                self._acquired = False

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._acquired:
            print(
                f"[ATP] startup_lock_release_abort device={self.device_id} flow={self.flow_name}",
                flush=True,
            )
            _startup_lock.release()
            self._acquired = False
