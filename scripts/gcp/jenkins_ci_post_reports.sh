#!/usr/bin/env bash
# Post-run processing on GCP (Excel merge, summary, zip). Same Python entrypoints as Windows .bat wrappers.
set -euo pipefail
ROOT="${1:?Usage: jenkins_ci_post_reports.sh <repo-root>}"
cd "$ROOT"
export JENKINS_WORKLOAD_PROFILE="${JENKINS_WORKLOAD_PROFILE:-gcp-orchestrator}"
echo "[gcp-post] profile=${JENKINS_WORKLOAD_PROFILE} starting post-run processing"

PY="${PYTHON_EXE:-}"
if [[ -z "$PY" ]]; then
  for c in python3.13 python3.12 python3.11 python3; do
    if command -v "$c" >/dev/null 2>&1; then PY="$(command -v "$c")"; break; fi
  done
fi
if [[ -z "$PY" ]]; then
  echo "[gcp-post] ERROR: python3 not found"
  exit 1
fi

if [[ -f build-summary/atp_suite_labels.json ]]; then
  echo "[gcp-post] merge ATP excel reports"
  "$PY" scripts/generate_atp_excel_reports.py . || echo 1 >atp_report_failed.flag
else
  echo "[gcp-post] no atp_suite_labels.json — skip ATP excel merge"
fi

echo "[gcp-post] build summary"
mkdir -p build-summary
"$PY" scripts/generate_build_summary.py status build-summary || echo 1 >summary_failed.flag
if [[ -f scripts/generate_final_report.py ]]; then
  "$PY" scripts/generate_final_report.py . status build-summary/final_execution_report.xlsx
fi

echo "[gcp-post] materialize execution_logs.zip"
"$PY" -c "import sys; from pathlib import Path; r=Path('.').resolve(); sys.path.insert(0, str(r)); from mailout.send_email import build_execution_logs_zip; z=build_execution_logs_zip(r); print('execution_logs.zip =>', z)"

echo "[gcp-post] done"
