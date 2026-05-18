"""
Detect current Git branch for ATP runtime logs and report metadata (read-only).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

_CACHED_BRANCH: str | None = None

_BRANCH_ENV_KEYS = (
    "ATP_GIT_BRANCH",
    "GIT_BRANCH",
    "BRANCH_NAME",
    "GIT_LOCAL_BRANCH_NAME",
    "CHANGE_BRANCH",
)


def _git_executable() -> str | None:
    found = shutil.which("git")
    if found:
        return found
    if os.name == "nt":
        for candidate in (
            r"C:\Program Files\Git\cmd\git.exe",
            r"C:\Program Files\Git\bin\git.exe",
            r"C:\Program Files (x86)\Git\cmd\git.exe",
        ):
            if Path(candidate).is_file():
                return candidate
    return None


def _branch_from_file(repo: Path) -> str:
    for rel in ("build-summary/atp_git_branch.txt", "atp_git_branch.txt"):
        path = repo / rel
        if not path.is_file():
            continue
        try:
            line = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
            if line and line[0].strip() and line[0].strip().lower() != "unknown":
                return line[0].strip()
        except OSError:
            pass
    return ""


def write_git_branch_file(repo: Path, branch: str) -> None:
    """Persist branch for later report/email stages (display metadata only)."""
    b = (branch or "").strip()
    if not b or b.lower() == "unknown":
        return
    out = repo / "build-summary" / "atp_git_branch.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(b + "\n", encoding="utf-8")


def detect_git_branch(repo: Path | None = None) -> str:
    """Return branch name from env, persisted file, or git; else ``unknown``."""
    global _CACHED_BRANCH
    if _CACHED_BRANCH is not None:
        return _CACHED_BRANCH

    for key in _BRANCH_ENV_KEYS:
        v = (os.environ.get(key) or "").strip()
        if v and v.lower() != "unknown":
            _CACHED_BRANCH = v
            return _CACHED_BRANCH

    root = (repo or Path.cwd()).resolve()
    from_file = _branch_from_file(root)
    if from_file:
        _CACHED_BRANCH = from_file
        return _CACHED_BRANCH

    git = _git_executable()
    if git:
        git_argv_base = [git, "-C", str(root)]
        for git_args in (
            ["branch", "--show-current"],
            ["rev-parse", "--abbrev-ref", "HEAD"],
        ):
            try:
                proc = subprocess.run(
                    [*git_argv_base, *git_args],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=15,
                    check=False,
                    shell=False,
                    cwd=str(root),
                )
                if proc.returncode == 0:
                    branch = (proc.stdout or "").strip()
                    if branch and branch != "HEAD" and branch.lower() != "unknown":
                        _CACHED_BRANCH = branch
                        return _CACHED_BRANCH
            except (OSError, subprocess.TimeoutExpired):
                continue

    _CACHED_BRANCH = "unknown"
    return _CACHED_BRANCH
