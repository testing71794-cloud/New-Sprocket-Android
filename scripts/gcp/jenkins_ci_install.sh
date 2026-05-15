#!/usr/bin/env bash
# GCP orchestrator agent: Python dependencies for report/AI orchestration only.
# Does NOT install Maestro, Android SDK, or Node (unless JENKINS_REQUIRE_NPM=1).
set -euo pipefail
ROOT="${1:?Usage: jenkins_ci_install.sh <repo-root>}"
cd "$ROOT"
export JENKINS_WORKLOAD_PROFILE="${JENKINS_WORKLOAD_PROFILE:-gcp-orchestrator}"
echo "[workload] profile=${JENKINS_WORKLOAD_PROFILE} scope=gcp-orchestrator"

PY="${PYTHON_EXE:-}"
if [[ -z "$PY" ]]; then
  for c in python3.13 python3.12 python3.11 python3; do
    if command -v "$c" >/dev/null 2>&1; then PY="$(command -v "$c")"; break; fi
  done
fi
if [[ -z "$PY" ]]; then
  echo "[gcp-install] ERROR: python3 not found"
  exit 1
fi
echo "[gcp-install] Using PY=$PY"
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -r scripts/requirements-python.txt
mkdir -p build-summary
echo "[gcp-install] done (no Maestro/ADB on GCP orchestrator)"
