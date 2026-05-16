#!/usr/bin/env python3
"""Verify installed Maestro supports per-device --driver-host-port (true parallel on one host)."""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from execution.maestro_capabilities import detect_maestro_capabilities  # noqa: E402


def main() -> int:
    caps = detect_maestro_capabilities(device_count=2)
    if caps.driver_host_port_supported:
        print("OK: Maestro CLI supports --driver-host-port (native parallel ready).")
        print(f"  version={caps.cli_version} mode={caps.maestro_mode}")
        return 0
    print("FAIL: Maestro CLI does not support --driver-host-port.", file=sys.stderr)
    print(f"  version={caps.cli_version}", file=sys.stderr)
    print("  Upgrade MAESTRO_HOME: https://github.com/mobile-dev-inc/Maestro/releases", file=sys.stderr)
    print("  Then: python scripts/verify_maestro_parallel_cli.py", file=sys.stderr)
    print("  Rollback: set ATP_ALLOW_LEGACY_SERIALIZED=1", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
