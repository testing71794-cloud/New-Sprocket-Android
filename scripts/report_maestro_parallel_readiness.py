#!/usr/bin/env python3
"""Full Maestro parallel readiness report (install inventory + capability probes)."""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from execution.maestro_capabilities import detect_maestro_capabilities  # noqa: E402
from execution.maestro_install_resolver import resolve_maestro_for_parallel  # noqa: E402
from execution.maestro_runtime_diagnostics import emit_parallel_readiness_report  # noqa: E402


def main() -> int:
    selected = resolve_maestro_for_parallel(maestro_cmd=None, device_count=2)
    emit_parallel_readiness_report(maestro_cmd=None, device_count=2, selected=selected)
    caps = detect_maestro_capabilities(device_count=2, resolve_installs=False)
    print(
        f"\nSummary: driver_port_supported={caps.driver_host_port_supported} "
        f"mode={caps.maestro_mode} cli={caps.cli_version}",
        flush=True,
    )
    return 0 if caps.driver_host_port_supported else 1


if __name__ == "__main__":
    sys.exit(main())
