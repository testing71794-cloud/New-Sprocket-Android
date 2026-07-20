"""UI hierarchy helpers via adb uiautomator dump (never raises to callers)."""
from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class NodeHit:
    text: str
    content_desc: str
    enabled: bool
    clickable: bool
    bounds: str


class Hierarchy:
    def __init__(self, serial: str, adb: str = "adb", repo_root: Path | None = None):
        self.serial = serial
        self.adb = adb
        self.repo_root = repo_root or Path.cwd()
        self.raw = ""
        self.nodes: list[NodeHit] = []

    def _run(self, args: list[str], timeout: float = 30.0) -> tuple[int, str]:
        try:
            p = subprocess.run(
                [self.adb, "-s", self.serial, *args],
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            # Prefer bytes decode — dump XML can include non-utf8 noise on some devices
            out = (p.stdout or b"") + (p.stderr or b"")
            text = out.decode("utf-8", errors="ignore")
            return p.returncode, text
        except Exception as exc:  # noqa: BLE001 — must never throw to callers
            return 1, str(exc)

    def refresh(self, retries: int = 2) -> bool:
        """Capture hierarchy. Prefer exec-out (no sdcard write); fall back to tmp dump+pull."""
        local_dir = self.repo_root / "logs" / "hierarchy"
        local_dir.mkdir(parents=True, exist_ok=True)

        for attempt in range(retries + 1):
            # 1) Streaming dump — most reliable on modern Android
            code, out = self._run(["exec-out", "uiautomator", "dump", "/dev/tty"], timeout=45.0)
            xml = self._extract_xml(out)
            if xml:
                self.raw = xml
                self._parse()
                try:
                    (local_dir / f"{self.serial}_{int(time.time() * 1000)}.xml").write_text(
                        xml, encoding="utf-8", errors="ignore"
                    )
                except Exception:  # noqa: BLE001
                    pass
                return True

            # 2) Dump to world-writable tmp then pull
            remote = "/data/local/tmp/atp_hierarchy.xml"
            self._run(["shell", "rm", "-f", remote])
            code, dump_out = self._run(["shell", "uiautomator", "dump", remote])
            local = local_dir / f"{self.serial}_{int(time.time() * 1000)}.xml"
            pull_code, _ = self._run(["pull", remote, str(local)])
            if pull_code == 0 and local.exists() and local.stat().st_size > 50:
                try:
                    self.raw = local.read_text(encoding="utf-8", errors="ignore")
                    self._parse()
                    return True
                except Exception:  # noqa: BLE001
                    pass

            # 3) Default window_dump.xml on sdcard
            self._run(["shell", "uiautomator", "dump"])
            local2 = local_dir / f"{self.serial}_window_{int(time.time() * 1000)}.xml"
            pull_code, _ = self._run(["pull", "/sdcard/window_dump.xml", str(local2)])
            if pull_code == 0 and local2.exists() and local2.stat().st_size > 50:
                try:
                    self.raw = local2.read_text(encoding="utf-8", errors="ignore")
                    self._parse()
                    return True
                except Exception:  # noqa: BLE001
                    pass

            # Keep last dump_out for debugging in logs
            if attempt == retries:
                try:
                    (local_dir / "last_dump_error.txt").write_text(
                        f"code={code}\n{dump_out[:2000] if dump_out else out[:2000]}",
                        encoding="utf-8",
                    )
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(0.6)

        self.raw = ""
        self.nodes = []
        return False

    @staticmethod
    def _extract_xml(blob: str) -> str:
        if not blob:
            return ""
        start = blob.find("<?xml")
        if start < 0:
            start = blob.find("<hierarchy")
        if start < 0:
            return ""
        end = blob.rfind("</hierarchy>")
        if end < 0:
            return ""
        return blob[start : end + len("</hierarchy>")]

    def _parse(self) -> None:
        self.nodes = []
        for m in re.finditer(r"<node\b([^>]*)/?>", self.raw):
            attrs = m.group(1)

            def attr(name: str) -> str:
                mm = re.search(rf'{name}="([^"]*)"', attrs)
                return mm.group(1) if mm else ""

            self.nodes.append(
                NodeHit(
                    text=attr("text"),
                    content_desc=attr("content-desc").replace("&#10;", "\n"),
                    enabled=attr("enabled").lower() == "true",
                    clickable=attr("clickable").lower() == "true",
                    bounds=attr("bounds"),
                )
            )

    def find(self, selector: str) -> list[NodeHit]:
        if not selector:
            return []
        sel = selector.strip()
        try:
            if sel.startswith(".*") or "(?i)" in sel:
                rx = re.compile(sel, re.I | re.S)
                return [
                    n
                    for n in self.nodes
                    if (n.text and rx.search(n.text)) or (n.content_desc and rx.search(n.content_desc))
                ]
        except re.error:
            pass
        low = sel.lower()
        hits = []
        for n in self.nodes:
            blob = f"{n.text}\n{n.content_desc}".lower()
            if low in blob:
                hits.append(n)
        return hits
