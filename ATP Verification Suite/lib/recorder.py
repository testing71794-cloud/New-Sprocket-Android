"""Pass/fail recorder and failure screenshots."""
from __future__ import annotations

import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@dataclass
class Record:
    test_id: str
    module: str
    description: str
    expected: str
    actual: str
    status: str
    failure_reason: str
    screenshot: str
    execution_time: str
    verification: str = ""
    stage: str = ""
    timestamp: str = field(default_factory=_utc_now)


class Recorder:
    def __init__(self, repo_root: Path, serial: str, adb: str = "adb"):
        self.repo_root = repo_root
        self.serial = serial
        self.adb = adb
        self.rows: list[Record] = []
        self.started = time.time()
        (repo_root / "logs").mkdir(parents=True, exist_ok=True)
        (repo_root / "screenshots").mkdir(parents=True, exist_ok=True)
        (repo_root / "reports").mkdir(parents=True, exist_ok=True)

    def takeFailureScreenshot(self, test_id: str, label: str = "fail") -> str:
        try:
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in f"{test_id}_{label}")[:80]
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = self.repo_root / "screenshots" / f"{safe}_{ts}.png"
            remote = "/sdcard/atp_fail.png"
            subprocess.run(
                [self.adb, "-s", self.serial, "shell", "screencap", "-p", remote],
                capture_output=True,
                timeout=15,
                check=False,
            )
            subprocess.run(
                [self.adb, "-s", self.serial, "pull", remote, str(path)],
                capture_output=True,
                timeout=15,
                check=False,
            )
            return str(path) if path.exists() else ""
        except Exception:  # noqa: BLE001
            return ""

    def recordPass(
        self,
        *,
        test_id: str,
        module: str,
        description: str,
        expected: str,
        actual: str,
        verification: str = "",
        stage: str = "",
        elapsed_ms: int = 0,
    ) -> Record:
        rec = Record(
            test_id=test_id,
            module=module,
            description=description,
            expected=expected,
            actual=actual,
            status="PASS",
            failure_reason="",
            screenshot="",
            execution_time=f"{elapsed_ms}ms",
            verification=verification,
            stage=stage,
        )
        self.rows.append(rec)
        self._log(rec)
        return rec

    def recordFail(
        self,
        *,
        test_id: str,
        module: str,
        description: str,
        expected: str,
        actual: str,
        failure_reason: str,
        verification: str = "",
        stage: str = "",
        elapsed_ms: int = 0,
        screenshot: Optional[str] = None,
    ) -> Record:
        shot = screenshot if screenshot is not None else self.takeFailureScreenshot(test_id)
        rec = Record(
            test_id=test_id,
            module=module,
            description=description,
            expected=expected,
            actual=actual or failure_reason,
            status="FAIL",
            failure_reason=failure_reason,
            screenshot=shot,
            execution_time=f"{elapsed_ms}ms",
            verification=verification,
            stage=stage,
        )
        self.rows.append(rec)
        self._log(rec)
        return rec

    def _log(self, rec: Record) -> None:
        line = (
            f"{rec.timestamp} | {rec.status} | {rec.stage}/{rec.module} | {rec.test_id} | "
            f"{rec.verification or rec.description} | {rec.failure_reason}\n"
        )
        try:
            with (self.repo_root / "logs" / "verification.log").open("a", encoding="utf-8") as f:
                f.write(line)
        except Exception:  # noqa: BLE001
            pass

    def summary(self) -> dict:
        total = len(self.rows)
        passed = sum(1 for r in self.rows if r.status == "PASS")
        failed = sum(1 for r in self.rows if r.status == "FAIL")
        failed_modules = sorted({r.module for r in self.rows if r.status == "FAIL"})
        elapsed = time.time() - self.started
        return {
            "total_verifications": total,
            "passed": passed,
            "failed": failed,
            "pass_percent": round((passed / total) * 100, 2) if total else 0.0,
            "execution_time_sec": round(elapsed, 2),
            "failed_modules": failed_modules,
            "rows": [asdict(r) for r in self.rows],
        }
