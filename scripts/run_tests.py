#!/usr/bin/env python3
"""Local ATP module runner.

Selects WHAT to run, then hands each folder to the existing Jenkins orchestrator
(scripts/jenkins_atp_stage.py → execution.atp_jenkins_orchestrator). Parallel
device behaviour is unchanged (ATP_DEVICE_EXECUTION / ATP_SCHEDULER).

Examples:
  python scripts/run_tests.py --module signup
  python scripts/run_tests.py --module signup,precut,gallery
  python scripts/run_tests.py --module all
  python scripts/run_tests.py --module all --plan-only
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from execution.atp_module_selection import (  # noqa: E402
    UnknownModuleError,
    build_execution_plan,
    log_execution_plan,
)


def _parse() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Run selected ATP TestCase Flows modules")
    ap.add_argument(
        "--module",
        "--modules",
        dest="module",
        default="all",
        help="ALL, one folder, or comma-separated folders (signup,precut,gallery)",
    )
    ap.add_argument("--app", default=os.environ.get("APP_PACKAGE", "com.hp.impulse.sprocket"))
    ap.add_argument("--clear-state", default=os.environ.get("CLEAR_STATE", "true"))
    ap.add_argument("--maestro", default=os.environ.get("MAESTRO_CMD", "maestro.bat"))
    ap.add_argument("--plan-only", action="store_true", help="Validate modules and print plan; do not execute")
    return ap.parse_args()


def main() -> int:
    args = _parse()
    try:
        plan = build_execution_plan(REPO, args.module)
    except UnknownModuleError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    log_execution_plan(plan)
    if args.plan_only:
        return 0
    last_rc = 0
    stage = REPO / "scripts" / "jenkins_atp_stage.py"
    for folder in plan.modules:
        print(f"\n########## START MODULE {folder} ##########\n", flush=True)
        rc = subprocess.call(
            [
                sys.executable,
                str(stage),
                "all",
                folder,
                args.app,
                str(args.clear_state),
                args.maestro,
            ],
            cwd=str(REPO),
        )
        print(f"\n########## END MODULE {folder} rc={rc} ##########\n", flush=True)
        if rc != 0:
            last_rc = rc
    print("\n########## FINAL EXCEL ##########\n", flush=True)
    excel = subprocess.call(
        [sys.executable, str(REPO / "scripts" / "generate_atp_excel_reports.py"), str(REPO)],
        cwd=str(REPO),
    )
    if excel != 0 and last_rc == 0:
        last_rc = excel
    print(
        f"Execution Summary\nTotal: {plan.total}\nModules: {', '.join(plan.modules)}\n"
        f"Excel: {REPO / 'build-summary' / 'final_execution_report.xlsx'}",
        flush=True,
    )
    return last_rc


if __name__ == "__main__":
    raise SystemExit(main())
