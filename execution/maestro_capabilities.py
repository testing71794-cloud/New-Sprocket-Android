#!/usr/bin/env python3
"""
Runtime Maestro CLI capability detection for true multi-device parallel execution.

Requires Maestro CLI with global --driver-host-port (before test subcommand).
Maestro 1.27.x on Jenkins does NOT support this; upgrade MAESTRO_HOME to a current release.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
from dataclasses import dataclass

_capabilities: MaestroCapabilities | None = None
_capabilities_lock = threading.Lock()
_driver_port_supported_override: bool | None = None


@dataclass(frozen=True)
class MaestroCapabilities:
    cli_version: str
    driver_host_port_supported: bool
    maestro_mode: str  # native_parallel | legacy_compatible
    startup_strategy: str

    def log_summary(self) -> None:
        print(
            f"[ATP] maestro_capability driver_port_supported="
            f"{str(self.driver_host_port_supported).lower()}",
            flush=True,
        )
        print(f"[ATP] maestro_cli_version={self.cli_version}", flush=True)
        print(f"[ATP] maestro_mode={self.maestro_mode}", flush=True)
        print(f"[ATP] startup_strategy={self.startup_strategy}", flush=True)


def _java_prefix() -> list[str]:
    from .maestro_runner import build_maestro_java_cmd_prefix

    return build_maestro_java_cmd_prefix()


def _probe_cli_version(prefix: list[str]) -> str:
    for args in (["--version"], ["-v"], ["--help"]):
        try:
            proc = subprocess.run(
                prefix + args,
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            text = ((proc.stdout or "") + (proc.stderr or "")).strip()
            if not text:
                continue
            if args != ["--help"]:
                return text.splitlines()[0].strip()[:120]
            m = re.search(r"(\d+\.\d+\.\d+)", text)
            if m:
                return m.group(1)
        except (OSError, subprocess.TimeoutExpired):
            continue
    return "unknown"


def _argv_rejects_driver_port(combined: str) -> bool:
    low = combined.lower()
    if "unknown option" not in low:
        return False
    return "driver-host-port" in low or "driver-port" in low


def _probe_driver_host_port_supported(prefix: list[str]) -> bool:
    """
    Probe production argv from run_one_flow_on_device.bat:
      AppKt --driver-host-port <port> --device <id> test ...
    """
    argv = prefix + ["--driver-host-port", "7099", "--device", "127.0.0.1", "test", "--help"]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        combined = (proc.stdout or "") + (proc.stderr or "")
        if _argv_rejects_driver_port(combined):
            return False
        return proc.returncode == 0 or "Usage:" in combined
    except (OSError, subprocess.TimeoutExpired):
        return False


def require_native_parallel() -> bool:
    """Strict: exit if --driver-host-port unavailable (set after Maestro upgrade verification)."""
    return os.environ.get("ATP_REQUIRE_NATIVE_PARALLEL", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def legacy_serialized_allowed() -> bool:
    """
    auto (default): allow serialized legacy when CLI lacks driver ports (Jenkins keeps running).
    0: disable legacy fallback (fails unless native parallel available).
    1: force legacy even if native ports exist (rollback).
    """
    if require_native_parallel():
        return False
    raw = (os.environ.get("ATP_ALLOW_LEGACY_SERIALIZED") or "auto").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    return True  # auto-fallback for Maestro 1.27.x agents


def invalidate_driver_port_support(*, reason: str) -> None:
    global _driver_port_supported_override, _capabilities
    with _capabilities_lock:
        _driver_port_supported_override = False
        if _capabilities is not None:
            _capabilities = MaestroCapabilities(
                cli_version=_capabilities.cli_version,
                driver_host_port_supported=False,
                maestro_mode="legacy_compatible",
                startup_strategy=_legacy_startup_strategy(),
            )
    print(
        f"[ATP] maestro_capability driver_port_supported=false reason=runtime_{reason}",
        flush=True,
    )


def driver_host_port_supported() -> bool:
    with _capabilities_lock:
        if _driver_port_supported_override is False:
            return False
        if _capabilities is not None:
            return _capabilities.driver_host_port_supported
    return False


def native_parallel_active(device_count: int = 1) -> bool:
    """True when per-device driver ports are active (true parallel same-host execution)."""
    if device_count <= 1:
        return False
    detect_maestro_capabilities(device_count=device_count)
    return driver_host_port_supported()


def _native_startup_strategy() -> str:
    return (
        "native_parallel:per_device_driver_ports+adb_hygiene+"
        "no_startup_gate+no_runtime_mutex+worker_pool"
    )


def _legacy_startup_strategy() -> str:
    return "legacy_compatible:host_runtime_mutex+startup_gate+adb_hygiene"


def legacy_runtime_mutex_active(device_count: int) -> bool:
    """Host-wide Maestro serialization — only when legacy explicitly allowed."""
    if device_count <= 1:
        return False
    if driver_host_port_supported():
        return False
    if not legacy_serialized_allowed():
        return False
    raw = (os.environ.get("ATP_MAESTRO_LEGACY_RUNTIME_MUTEX") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def apply_legacy_parallel_env_defaults() -> None:
    """Stable defaults for Maestro without per-device driver ports."""
    os.environ.setdefault("ATP_MAESTRO_STARTUP_GATE", "1")
    os.environ.setdefault("ATP_MAESTRO_LEGACY_RUNTIME_MUTEX", "1")
    os.environ.setdefault("ATP_MAESTRO_DRIVER_PORTS", "0")
    if os.name == "nt":
        os.environ.setdefault("ATP_PARALLEL_DEVICE_STAGGER_SEC", "2")
    os.environ.setdefault("MAESTRO_PARALLEL_STARTUP_DELAY_SEC", "8")


def apply_native_parallel_env_defaults(*, device_count: int) -> None:
    """Set orchestrator defaults for true parallel when driver ports are supported."""
    if device_count <= 1 or not driver_host_port_supported():
        return
    os.environ.setdefault("ATP_MAESTRO_STARTUP_GATE", "0")
    os.environ.setdefault("ATP_PARALLEL_DEVICE_STAGGER_SEC", "0")
    os.environ.setdefault("ATP_MAESTRO_LEGACY_RUNTIME_MUTEX", "0")
    os.environ.setdefault("MAESTRO_PARALLEL_STARTUP_DELAY_SEC", "0")
    os.environ.setdefault("ATP_MAESTRO_DRIVER_PORTS", "1")


def assert_native_parallel_ready(*, device_count: int) -> None:
    """
    Configure native parallel when supported; otherwise auto-fallback to legacy (default)
    or exit 2 when ATP_REQUIRE_NATIVE_PARALLEL=1.
    """
    if device_count <= 1:
        return
    caps = detect_maestro_capabilities(device_count=device_count)
    if caps.driver_host_port_supported:
        apply_native_parallel_env_defaults(device_count=device_count)
        print(
            "[ATP] native_parallel=1 simultaneous multi-device Maestro "
            "(per-device --driver-host-port, no startup gate, no host mutex)",
            flush=True,
        )
        return
    if legacy_serialized_allowed():
        apply_legacy_parallel_env_defaults()
        print(
            "[ATP] native_parallel=0 maestro_mode=legacy_compatible "
            f"(CLI {caps.cli_version} lacks --driver-host-port; serialized host mutex active)",
            flush=True,
        )
        print(
            "[ATP] maestro_upgrade_hint Run scripts\\upgrade_maestro_for_parallel.bat "
            "after upgrading MAESTRO_HOME for true parallel execution",
            flush=True,
        )
        return
    print(
        "\nERROR: True parallel multi-device execution requires Maestro CLI with "
        "--driver-host-port.\n"
        "  Installed CLI does not support it (detected on this agent).\n"
        "  Fix: upgrade MAESTRO_HOME, then: python scripts/verify_maestro_parallel_cli.py\n"
        "  Or allow serialized fallback: set ATP_ALLOW_LEGACY_SERIALIZED=auto (default)\n"
        "  Strict CI gate after upgrade: set ATP_REQUIRE_NATIVE_PARALLEL=1\n",
        flush=True,
    )
    sys.exit(2)


def detect_maestro_capabilities(*, device_count: int = 1) -> MaestroCapabilities:
    global _capabilities, _driver_port_supported_override
    with _capabilities_lock:
        if _capabilities is not None:
            return _capabilities

        raw_force = (os.environ.get("ATP_MAESTRO_DRIVER_PORTS") or "auto").strip().lower()
        prefix = _java_prefix()
        version = _probe_cli_version(prefix)

        if raw_force in ("0", "false", "no", "off"):
            supported = False
        elif device_count <= 1:
            supported = False
        else:
            supported = _probe_driver_host_port_supported(prefix)
            if raw_force in ("1", "true", "yes", "on") and not supported:
                print(
                    "[ATP] WARN ATP_MAESTRO_DRIVER_PORTS=1 but CLI probe failed; "
                    "parallel ports disabled",
                    flush=True,
                )

        if _driver_port_supported_override is False:
            supported = False

        if supported:
            mode = "native_parallel"
            strategy = _native_startup_strategy()
        else:
            mode = "legacy_compatible"
            strategy = _legacy_startup_strategy()

        _capabilities = MaestroCapabilities(
            cli_version=version,
            driver_host_port_supported=supported,
            maestro_mode=mode,
            startup_strategy=strategy,
        )
        _capabilities.log_summary()
        return _capabilities


def maestro_driver_ports_active(device_count: int = 1) -> bool:
    detect_maestro_capabilities(device_count=device_count)
    return driver_host_port_supported()
