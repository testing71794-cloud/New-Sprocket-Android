"""
CLI entrypoint for the ATP Verification Suite.

Examples (from repo root):
  python "ATP Verification Suite/run_suite.py" --refresh-catalog
  python "ATP Verification Suite/run_suite.py" --stage Splash --device ZA222RFQ75
  python "ATP Verification Suite/run_suite.py" --all --device ZA222RFQ75
  python "ATP Verification Suite/run_suite.py" --dry-report
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SUITE = Path(__file__).resolve().parent
ROOT = SUITE.parent
sys.path.insert(0, str(SUITE))

from lib.parse_atp_excel import parse_workbook, DEFAULT_XLSX  # noqa: E402
from lib.recorder import Recorder, Record  # noqa: E402
from lib.report import write_reports  # noqa: E402


def refresh_catalog(xlsx: Path) -> dict:
    data = parse_workbook(xlsx)
    catalog = SUITE / "catalog"
    catalog.mkdir(parents=True, exist_ok=True)
    slim = {
        "source": data["source"],
        "total_cases": data["total_cases"],
        "stages": data["stages"],
        "cases": data["cases"],
    }
    (catalog / "atp_cases.json").write_text(
        json.dumps(slim, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    stage_dir = catalog / "stages"
    stage_dir.mkdir(exist_ok=True)
    for stage, cases in data["by_stage"].items():
        (stage_dir / f"{stage}.json").write_text(
            json.dumps({"stage": stage, "count": len(cases), "cases": cases}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return data


def dry_report() -> int:
    """Generate sample reports without a device (catalog + synthetic rows)."""
    catalog_path = SUITE / "catalog" / "atp_cases.json"
    if not catalog_path.exists():
        refresh_catalog(DEFAULT_XLSX)
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    rec = Recorder(ROOT, serial="dry-run")
    # Sample first verification from each stage for report shape validation
    seen = set()
    for case in data.get("cases", []):
        stage = case.get("stage")
        if stage in seen:
            continue
        seen.add(stage)
        vers = case.get("verifications") or []
        if not vers:
            continue
        v = vers[0]
        rec.recordPass(
            test_id=case["test_id"],
            module=case["module"],
            description=case.get("description", ""),
            expected=case.get("expected", ""),
            actual="dry-run sample PASS",
            verification=v.get("verification", ""),
            stage=stage,
            elapsed_ms=1,
        )
    # One intentional FAIL sample so report formatting covers both statuses
    rec.rows.append(
        Record(
            test_id="DRY_FAIL",
            module="DryRun",
            description="Sample failure row for report schema",
            expected="N/A",
            actual="simulated failure",
            status="FAIL",
            failure_reason="dry-run sample",
            screenshot="",
            execution_time="1ms",
            verification="schema check",
            stage="General",
        )
    )
    summary = rec.summary()
    xlsx, js = write_reports(ROOT, summary)
    print(json.dumps({k: summary[k] for k in summary if k != "rows"}, indent=2))
    print(f"wrote {xlsx}")
    print(f"wrote {js}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="HP Sprocket ATP Verification Suite")
    ap.add_argument("--refresh-catalog", action="store_true", help="Re-parse Excel into catalog JSON")
    ap.add_argument("--xlsx", default=str(DEFAULT_XLSX))
    ap.add_argument("--dry-report", action="store_true", help="Write sample Excel/JSON reports offline")
    ap.add_argument("--stage", help="Run one stage (delegates to runners/run_module.py)")
    ap.add_argument("--all", action="store_true", help="Run all stages")
    ap.add_argument("--device", help="ADB serial (required for live runs)")
    ap.add_argument("--skip-setup", action="store_true")
    ap.add_argument("--maestro", default="maestro")
    args, unknown = ap.parse_known_args()

    if args.refresh_catalog:
        data = refresh_catalog(Path(args.xlsx))
        print(f"catalog refreshed: cases={data['total_cases']} stages={len(data['stages'])}")
        for s, n in data["stages"].items():
            print(f"  {s}: {n}")
        if not args.dry_report and not args.stage and not args.all:
            return 0

    if args.dry_report:
        return dry_report()

    if args.stage or args.all:
        if not args.device:
            ap.error("--device is required for live runs")
        # Delegate to module runner
        from runners import run_module  # noqa: WPS433

        sys.argv = ["run_module.py", "--device", args.device]
        if args.all:
            sys.argv.append("--all")
        else:
            sys.argv.extend(["--stage", args.stage])
        if args.skip_setup:
            sys.argv.append("--skip-setup")
        sys.argv.extend(["--maestro", args.maestro, "--xlsx", args.xlsx])
        if args.refresh_catalog:
            sys.argv.append("--refresh-catalog")
        return run_module.main()

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
