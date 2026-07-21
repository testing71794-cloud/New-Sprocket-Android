"""Subprocess launch helpers — argv lists only; never shell=True."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Mapping, Sequence


def log_subprocess_launch(
    argv: Sequence[str],
    *,
    cwd: str | Path,
    shell: bool = False,
    label: str = "subprocess",
    extra: Mapping[str, Any] | None = None,
) -> None:
    """Log argv, cwd, and shell mode before Popen/run (Jenkins path-with-spaces diagnostics)."""
    print(f"[ATP] {label} argv={list(argv)!r}", flush=True)
    print(f"[ATP] {label} cwd={str(cwd)!r}", flush=True)
    print(f"[ATP] {label} shell={shell}", flush=True)
    if extra:
        for key, value in extra.items():
            print(f"[ATP] {label} {key}={value!r}", flush=True)


def windows_cmd_bat_argv(bat: Path, *args: str) -> list[str]:
    """
    argv for ``subprocess.run(..., shell=False)`` to execute a Windows ``.bat``.

    On Windows, CreateProcess can launch ``.bat`` files directly when the .bat path
    is argv[0] and each argument is a separate list element. **Do not** wrap with
    ``cmd.exe /c`` and multiple tokens — that splits paths at spaces
    (``'C:\\...\\Kodak' is not recognized``).
    """
    return [str(bat.resolve()), *args]


def resolve_adb_executable() -> str | None:
    """Resolved adb.exe path for argv-list subprocess (never bare ``adb`` on Windows)."""
    for env in ("ADB_HOME",):
        root = os.environ.get(env, "").strip().strip('"')
        if root:
            exe = Path(root) / ("adb.exe" if os.name == "nt" else "adb")
            if exe.is_file():
                return str(exe.resolve())
            # ADB_HOME may already point at adb.exe
            if Path(root).is_file() and Path(root).name.lower() in ("adb.exe", "adb"):
                return str(Path(root).resolve())
    for root_env in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        root = os.environ.get(root_env, "").strip().strip('"')
        if root:
            exe = Path(root) / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
            if exe.is_file():
                return str(exe.resolve())
    if os.name == "nt":
        for candidate in (
            Path(r"C:\Tools\platform-tools\adb.exe"),
            Path(r"C:\Android\platform-tools\adb.exe"),
            Path(r"C:\Android\Sdk\platform-tools\adb.exe"),
            Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe",
        ):
            if candidate.is_file():
                return str(candidate.resolve())
    found = shutil.which("adb")
    return found
