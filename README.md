# Kodak Smile — Maestro + Jenkins + Python (ready-to-test)

Automation for the **Kodak Smile** Android app: **Maestro** flows, **parallel multi-device** runs, **Python** reports and **OpenRouter**-backed analysis, **Jenkins** pipeline.

## What you need installed

| Requirement | Notes |
|-------------|--------|
| **Python 3.10+** | On `PATH` as `python` |
| **Node.js 18+** | For `npm ci` / optional `ai-doctor` |
| **Android SDK** | `ANDROID_HOME` and `platform-tools` (`adb`) on `PATH` for device runs |
| **JDK 17** (recommended) | Maestro; `JAVA_HOME` optional if precheck cannot find it |
| **Maestro CLI** | `maestro` or `maestro.bat` on `PATH` (or set `MAESTRO_HOME` in Jenkins / local scripts) |
| **USB device** | Developer options + USB debugging; authorize RSA prompt |

## One-shot local verification (start here)

From the **repository root**:

```bat
scripts\ready_to_test.bat
```

This installs Python + Node dependencies and runs `pytest` for `intelligent_platform`.

**With a phone connected** (one Maestro flow on the first `adb` device):

```bat
scripts\ready_to_test.bat -WithDeviceSmoke
```

Optional (PowerShell):

```powershell
powershell -File scripts\ready_to_test.ps1 -WithDeviceSmoke -AppPackage com.kodaksmile
```

## OpenRouter (optional)

Copy `.env.example` to `.env` and set `OPENROUTER_API_KEY`, or set the variable in the shell / Jenkins.

- Check: `python scripts\test_ai_connection.py` (writes `build-summary\ai_status.txt`)

## Full parallel suite (local)

Non-printing:

```bat
call scripts\run_suite_parallel_same_machine.bat nonprinting "Non printing flows" "" com.kodaksmile true maestro.bat
```

Printing:

```bat
call scripts\run_suite_parallel_same_machine.bat printing "Printing Flow" "" com.kodaksmile true maestro.bat
```

## New: per-device parallel orchestration (AI + incremental Excel)

Runs **all devices in parallel**, **flows one-by-one on each device**, JUnit after each flow, **AI on failures**, **append** rows to `build-summary\final_execution_report.xlsx`, optional **email** when done.

```bat
python execution\run_parallel_devices.py
python execution\run_parallel_devices.py --send-email
```

Details: `execution\README.md`. (Email helper lives in `mailout\` so Python’s stdlib `email` package is not shadowed.)

## Jenkins

Use the root `Jenkinsfile` (Pipeline from SCM). Parameters include `DEVICES_AGENT`, `APP_PACKAGE`, `MAESTRO_HOME`, `OPENROUTER_CREDENTIALS_ID`, and run toggles.

**Hybrid GCP + Windows (opt-in):** `Jenkinsfile.hybrid.gcp-windows` — Maestro on Windows USB agent; report/zip/archive on GCP. See `docs/DISTRIBUTED_GCP_WINDOWS_ARCHITECTURE.md`.

More detail: `README_PRODUCTION_SETUP.md`, `docs/PIPELINE_EXECUTION_AND_EMAIL.md`.

## Layout

- `Non printing flows/`, `Printing Flow/` — Maestro flows
- `flows/`, `elements/` — Shared subflows and element maps
- `config.yaml` — Maestro includes (repo root)
- `scripts/` — Runners, reports, `ready_to_test.bat` / `ready_to_test.ps1`
- `execution/` — `run_parallel_devices.py` (multi-device + incremental Excel + AI)
- `ai/`, `excel/`, `mailout/` — Orchestration helpers for that runner
- `intelligent_platform/` — Failure analysis and reporting
- `Jenkinsfile` — CI
- `automation_with_testcases/` — Optional ATP (run locally if needed)

## npm

- `npm start` — Short usage (see `index.mjs`)
- `npm run doctor:junit` — Node `ai-doctor` JUnit path

## Maestro docs

- [docs.maestro.dev](https://docs.maestro.dev/)
- [Maestro CLI commands and options](https://docs.maestro.dev/maestro-cli/maestro-cli-commands-and-options) — verify flags when changing runners or YAML.
