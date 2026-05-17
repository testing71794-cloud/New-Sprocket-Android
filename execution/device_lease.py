#!/usr/bin/env python3
"""
Per-device coarse lease for Maestro runs (filesystem-based, stdlib only).

Avoids overlapping Maestro sessions on the same ADB serial from concurrent
Jenkins jobs or stray processes. Stale locks are removed when the owner PID
is no longer alive (plus optional wall-clock expiry).
"""
from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path


def is_process_alive(pid: int) -> bool:
    """Return True if ``pid`` refers to a running process (Windows-safe)."""
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return False
    if pid_int <= 0:
        return False
    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid_int)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return int(exit_code.value) == STILL_ACTIVE
            return False
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid_int, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _log_lease(msg: str) -> None:
    print(msg, flush=True)


def _read_lease_meta(lock_dir: Path) -> tuple[int | None, str, bool]:
    """
    Read lease.json. Returns (pid, serial_label, parsed_ok).
    ``parsed_ok`` is False for missing, empty, or malformed files.
    """
    meta = lock_dir / "lease.json"
    if not meta.is_file():
        return None, lock_dir.name, False
    try:
        raw = meta.read_text(encoding="utf-8", errors="replace").strip()
        if not raw:
            return None, lock_dir.name, False
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None, lock_dir.name, False
        serial = str(data.get("serial") or lock_dir.name).strip() or lock_dir.name
        pid_raw = data.get("pid")
        if pid_raw is None:
            return None, serial, False
        return int(pid_raw), serial, True
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None, lock_dir.name, False


def _try_remove_stale_lock(lock_dir: Path, *, reason: str) -> bool:
    """Remove lock directory; never raise. Returns True if removed."""
    pid, serial, parsed = _read_lease_meta(lock_dir)
    pid_disp = pid if pid is not None else 0
    try:
        if lock_dir.is_dir():
            shutil.rmtree(lock_dir, ignore_errors=True)
        removed = not lock_dir.exists()
        _log_lease(
            f"[ATP] stale_lease_cleanup device={serial} pid={pid_disp} "
            f"removed={str(removed).lower()} reason={reason}"
        )
        return removed
    except Exception as exc:
        _log_lease(
            f"[ATP] stale_lease_cleanup device={serial} pid={pid_disp} "
            f"removed=false reason={reason} warn={exc!r}"
        )
        return False


def cleanup_stale_device_leases(repo: Path) -> int:
    """
    Scan ``.maestro-locks`` and remove locks whose owner PID is not alive,
    or whose metadata is missing or corrupt.
    """
    root = DeviceLease.lock_root(repo)
    _log_lease("[ATP] stale_lease_scan begin")
    removed = 0
    if not root.is_dir():
        _log_lease("[ATP] stale_lease_scan end removed=0")
        return 0
    try:
        entries = list(root.iterdir())
    except OSError as exc:
        _log_lease(f"[ATP] stale_lease_scan end removed=0 warn=enumerate_failed:{exc!r}")
        return 0
    for entry in entries:
        if not entry.is_dir():
            continue
        try:
            pid, _serial, parsed = _read_lease_meta(entry)
            if not parsed:
                if _try_remove_stale_lock(entry, reason="corrupt_lock"):
                    removed += 1
                continue
            if pid is None or not is_process_alive(pid):
                if _try_remove_stale_lock(entry, reason="dead_pid"):
                    removed += 1
        except Exception as exc:
            _log_lease(f"[ATP] stale_lease_cleanup device={entry.name} warn=scan_error:{exc!r}")
    _log_lease(f"[ATP] stale_lease_scan end removed={removed}")
    return removed


def release_device_lease(lease: DeviceLease | None) -> None:
    """Fail-safe lease release for ``finally`` blocks; never raises."""
    if lease is None:
        return
    try:
        lease.release()
    except Exception as exc:
        _log_lease(
            f"[ATP] lease_release_warn device={lease.serial} "
            f"lock_dir={lease.lock_dir} warn={exc!r}"
        )


@dataclass
class DeviceLease:
    serial: str
    lock_dir: Path
    _acquired: bool = False

    @staticmethod
    def lock_root(repo: Path) -> Path:
        return (repo / ".maestro-locks").resolve()

    @classmethod
    def for_serial(cls, repo: Path, serial: str) -> DeviceLease:
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in serial.strip())
        return cls(serial=serial.strip(), lock_dir=cls.lock_root(repo) / safe)

    def _meta(self) -> Path:
        return self.lock_dir / "lease.json"

    def _stale_age_sec(self) -> float:
        raw = os.environ.get("ATP_DEVICE_LEASE_STALE_SEC", "7200").strip()
        try:
            return max(60.0, float(raw))
        except ValueError:
            return 7200.0

    def is_stale(self) -> bool:
        if not self.lock_dir.is_dir():
            return False
        pid, _serial, parsed = _read_lease_meta(self.lock_dir)
        if parsed and pid is not None:
            return not is_process_alive(pid)
        if not parsed:
            return True
        meta = self._meta()
        if not meta.is_file():
            return True
        try:
            age = time.time() - meta.stat().st_mtime
            return age > self._stale_age_sec()
        except OSError:
            return True

    def force_release(self) -> None:
        try:
            if self.lock_dir.is_dir():
                shutil.rmtree(self.lock_dir, ignore_errors=True)
        except OSError:
            pass
        self._acquired = False

    def _clear_stale_blocking_lock(self) -> bool:
        """If lock dir exists but owner is dead or corrupt, remove it. Returns True if cleared."""
        if not self.lock_dir.is_dir():
            return False
        pid, serial, parsed = _read_lease_meta(self.lock_dir)
        if not parsed:
            _log_lease(
                f"[ATP] stale_lease_cleanup device={serial} pid=0 "
                f"removed=true reason=corrupt_lock"
            )
            self.force_release()
            return True
        if pid is not None and is_process_alive(pid):
            return False
        pid_disp = pid if pid is not None else 0
        _log_lease(
            f"[ATP] stale_lease_cleanup device={serial} pid={pid_disp} removed=true reason=dead_pid"
        )
        self.force_release()
        return True

    def acquire(self, *, owner_pid: int | None = None) -> None:
        owner_pid = owner_pid or os.getpid()
        deadline = time.monotonic() + float(os.environ.get("ATP_DEVICE_LEASE_WAIT_SEC", "300"))
        while True:
            try:
                self.lock_dir.mkdir(parents=True, exist_ok=False)
                self._meta().write_text(
                    json.dumps({"pid": owner_pid, "ts": time.time(), "serial": self.serial}, indent=0),
                    encoding="utf-8",
                )
                self._acquired = True
                return
            except FileExistsError:
                if self._clear_stale_blocking_lock():
                    continue
                if self.is_stale():
                    pid, serial, _ = _read_lease_meta(self.lock_dir)
                    pid_disp = pid if pid is not None else 0
                    _log_lease(
                        f"[ATP] stale_lease_cleanup device={serial} pid={pid_disp} "
                        f"removed=true reason=age_stale"
                    )
                    self.force_release()
                    continue
                if time.monotonic() > deadline:
                    pid, serial, parsed = _read_lease_meta(self.lock_dir)
                    owner = pid if parsed and pid is not None else "unknown"
                    raise TimeoutError(
                        f"Device lease busy: {self.serial} ({self.lock_dir}) owner_pid={owner}"
                    )
                time.sleep(1.0)

    def release(self) -> None:
        if not self._acquired and not self.lock_dir.is_dir():
            return
        self.force_release()
