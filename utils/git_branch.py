"""
Detect current Git branch for ATP runtime logs and report metadata (read-only).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

_CACHED_BRANCH: str | None = None


def detect_git_branch(repo: Path | None = None) -> str:
    """Return branch name from env or ``git rev-parse --abbrev-ref HEAD``; else ``unknown``."""
    global _CACHED_BRANCH
    if _CACHED_BRANCH is not None:
        return _CACHED_BRANCH
    for key in ("ATP_GIT_BRANCH", "GIT_BRANCH", "BRANCH_NAME"):
        v = (os.environ.get(key) or "").strip()
        if v:
            _CACHED_BRANCH = v
            return _CACHED_BRANCH
    root = (repo or Path.cwd()).resolve()
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=15,
            check=False,
        )
        if proc.returncode == 0:
            branch = (proc.stdout or "").strip()
            if branch and branch != "HEAD":
                _CACHED_BRANCH = branch
                return _CACHED_BRANCH
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        pass
    _CACHED_BRANCH = "unknown"
    return _CACHED_BRANCH
