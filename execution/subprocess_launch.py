"""Subprocess launch helpers — argv lists only; never shell=True."""

from __future__ import annotations

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
    """Run a .bat with cmd.exe using separate argv tokens (paths may contain spaces)."""
    return ["cmd.exe", "/d", "/c", str(bat), *args]
