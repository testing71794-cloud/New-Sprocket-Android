#!/usr/bin/env python3
"""
Download and install a Maestro CLI build that supports --driver-host-port (native parallel).

Does not modify Jenkins or ATP flows. After install, set:
  ATP_MAESTRO_PARALLEL_HOME=<target>\\bin
or point MAESTRO_HOME at <target>\\bin
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from execution.maestro_install_resolver import probe_install  # noqa: E402

DEFAULT_URL = "https://github.com/mobile-dev-inc/Maestro/releases/latest/download/maestro.zip"
DEFAULT_TARGET = Path(r"C:\Tools\maestro-parallel")


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url} -> {dest}", flush=True)
    try:
        urllib.request.urlretrieve(url, dest)  # noqa: S310
        return
    except Exception as e:
        print(f"[WARN] urllib download failed ({e}); trying curl", flush=True)
    curl = shutil.which("curl") or shutil.which("curl.exe")
    if not curl:
        raise
    cmd = [curl, "--ssl-no-revoke", "-fsSL", "-o", str(dest), url]
    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"curl download failed exit={proc.returncode}")


def _find_bin_dir(root: Path) -> Path:
    direct = root / "bin"
    if (direct / "maestro.bat").is_file() or (direct / "maestro.cmd").is_file():
        return direct
    nested = root / "maestro" / "bin"
    if (nested / "maestro.bat").is_file() or (nested / "maestro.cmd").is_file():
        return nested
    for bat in root.rglob("maestro.bat"):
        if bat.parent.name.lower() == "bin":
            return bat.parent
    raise RuntimeError(f"No maestro bin/ under {root}")


def _extract(zip_path: Path, target: Path) -> Path:
    staging = target.parent / f".{target.name}_staging"
    if staging.is_dir():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(staging)
    bin_dir = _find_bin_dir(staging)
    app_root = bin_dir.parent
    if target.is_dir():
        shutil.rmtree(target, ignore_errors=True)
    shutil.move(str(app_root), str(target))
    return _find_bin_dir(target)


def main() -> int:
    ap = argparse.ArgumentParser(description="Install Maestro CLI for native parallel ATP")
    ap.add_argument("--url", default=DEFAULT_URL, help="maestro.zip download URL")
    ap.add_argument("--target", type=Path, default=DEFAULT_TARGET, help="Install root (contains bin/)")
    ap.add_argument("--dry-run", action="store_true", help="Probe existing target only, no download")
    args = ap.parse_args()
    target: Path = args.target.resolve()
    bin_dir = target / "bin"

    if args.dry_run:
        if not bin_dir.is_dir():
            print(f"FAIL: {bin_dir} does not exist", file=sys.stderr)
            return 1
        cand = probe_install(bin_dir, label="dry_run")
        if cand and cand.driver_host_port_supported:
            print(f"OK: {bin_dir} supports --driver-host-port ({cand.cli_version})")
            print(f"Set ATP_MAESTRO_PARALLEL_HOME={bin_dir}")
            return 0
        print(f"FAIL: {bin_dir} lacks --driver-host-port", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as td:
        zip_path = Path(td) / "maestro.zip"
        _download(args.url, zip_path)
        installed_bin = _extract(zip_path, target)

    cand = probe_install(installed_bin, label="installed")
    if cand is None:
        print("FAIL: install layout invalid", file=sys.stderr)
        return 1
    print(f"Installed: {target}")
    print(f"  version={cand.cli_version}")
    print(f"  driver_port={'yes' if cand.driver_host_port_supported else 'no'} ({cand.probe_detail})")
    if cand.driver_host_port_supported:
        print(f"\nSet on Jenkins agent:")
        print(f"  ATP_MAESTRO_PARALLEL_HOME={installed_bin}")
        print(f"  (or MAESTRO_HOME={installed_bin})")
        print(f"\nVerify: python scripts/verify_maestro_parallel_cli.py")
        return 0
    print(
        "\nWARN: Installed build still lacks --driver-host-port. "
        "Maestro may not have shipped this flag in latest release yet; "
        "track https://github.com/mobile-dev-inc/maestro/pull/2821",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
