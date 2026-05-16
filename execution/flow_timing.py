#!/usr/bin/env python3
"""Append-only per-flow wall-clock telemetry (does not alter Excel/JUnit report schema)."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

_timing_lock = threading.Lock()


def timing_jsonl_path(repo: Path, suite_id: str) -> Path:
    p = repo / "reports" / suite_id / "flow_timing.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def append_timing(
    repo: Path,
    suite_id: str,
    *,
    flow: str,
    device: str,
    duration_ms: int,
    status: str,
    exit_code: int,
    reason: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    rec: dict[str, Any] = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "suite": suite_id,
        "flow": flow,
        "device": device,
        "duration_ms": duration_ms,
        "status": status,
        "exit_code": exit_code,
        "reason": reason,
    }
    if extra:
        rec.update(extra)
    path = timing_jsonl_path(repo, suite_id)
    line = json.dumps(rec, ensure_ascii=False) + "\n"
    with _timing_lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)


def read_status_fields(status_file: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not status_file.is_file():
        return out
    for line in status_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    return out
