# GCP orchestrator scripts (Linux)

Used by **opt-in** `Jenkinsfile.hybrid.gcp-windows` — not the default `Jenkinsfile`.

| Script | Role |
|--------|------|
| `jenkins_ci_install.sh` | pip install `scripts/requirements-python.txt` on GCP |
| `jenkins_ci_post_reports.sh` | Excel merge, build summary, `execution_logs.zip` |

**Windows device agent** uses `scripts/jenkins_ci_install_windows_device.bat` (pip only, no npm).

See `docs/DISTRIBUTED_GCP_WINDOWS_ARCHITECTURE.md` for full migration plan.
