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
    if caps.native_parallel_enabled:
        print(f"OK: native parallel ready mode={caps.parallel_capability} maestro_mode={caps.maestro_mode}")
        print(f"  version={caps.cli_version} driver_port={caps.driver_host_port_supported} isolated={caps.isolated_runtime_supported}")
        return 0
    print("FAIL: native parallel not available on this host.", file=sys.stderr)
    print(f"  version={caps.cli_version}", file=sys.stderr)
    print("  Install: python scripts/install_maestro_parallel.py --target C:\\Tools\\maestro-parallel", file=sys.stderr)
    print("  Set: ATP_MAESTRO_PARALLEL_HOME=C:\\Tools\\maestro-parallel\\bin", file=sys.stderr)
    print("  Or: https://github.com/mobile-dev-inc/Maestro/releases", file=sys.stderr)
    print("  Rollback: set ATP_ALLOW_LEGACY_SERIALIZED=1", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
