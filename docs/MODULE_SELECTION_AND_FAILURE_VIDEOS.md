# Module selection, failure videos, and Excel

This layer sits **above** the existing parallel Maestro engine. It does not change
`ATP_DEVICE_EXECUTION`, `ATP_SCHEDULER`, native parallel, startup gate, or device locking.

```text
MODULE SELECTION  →  EXECUTION PLAN  →  EXISTING PARALLEL ORCHESTRATOR
        → per-device results/status/logs/videos → FINAL EXCEL MERGE
```

## How to run modules

Local (same Jenkins orchestrator per folder):

```bat
python scripts/run_tests.py --module signup
python scripts/run_tests.py --module signup,precut,gallery
python scripts/run_tests.py --module all
python scripts/run_tests.py --module all --plan-only
```

Invalid names fail immediately:

```text
ERROR: Unknown module 'xyz'
Available modules:
  ...
```

Legacy local helper (recovery-oriented, separate from Jenkins parallel):

```bat
python scripts/run_all_modules_sequential.py ZA222RFQ75 --modules collage,home
```

## Jenkins

- Keep using `RUN_ATP_*` checkboxes, **or**
- Set `ATP_MODULES`:
  - `all` — every known ATP folder
  - `signup,precut,gallery` — those folders only
- Leave `ATP_MODULES` empty to use checkboxes.

Each selected folder still runs as today: `python scripts/jenkins_atp_stage.py all <folder> ...`
which calls `execution.atp_jenkins_orchestrator` (unchanged scheduler).

A failure in one YAML does not skip remaining YAMLs in that folder. A failure in one
Jenkins module stage does not skip later modules (`catchError`).

## Failure video

For each flow, after Maestro has started, the runner starts `adb shell screenrecord`
on that device only. Paths are unique:

`reports/videos/<device>/<suite>/<device>_<suite>_<case>_FAIL_<timestamp>.mp4`

- **PASS** — recording is discarded (not archived).
- **FAIL / timeout** — video is pulled and `video_path=` is appended to the status file.

Stock Android `screenrecord` stops at **180 seconds**. Longer flows keep the first three minutes.

Disable: `ATP_SCREENRECORD=0`.

`maestro record` is a different CLI subcommand and is **not** used here (it would replace `maestro test`).

## Excel

Per-module `reports/atp_<folder>_summary/summary.xlsx` is written after that folder.
`build-summary/final_execution_report.xlsx` is merged **once after all selected modules**
(`scripts/generate_atp_excel_reports.py` from Build Summary / GCP post).

Existing columns are unchanged. Added:

| Column | PASS | FAIL |
|--------|------|------|
| Failure Video | `-` | relative path; clickable **Open Video** when the file exists |

## Artifacts

Jenkins archives `reports/videos/**` plus the existing Excel, logs zip, and screenshots.

## Adding a module

1. Add `ATP TestCase Flows/<folder>/` YAML (not under `subflows/`).
2. Add a `RUN_ATP_*` checkbox and folder name in `Jenkinsfile` / `jenkins/hybrid_gcp_windows_body.groovy` `known` list.
3. No orchestrator or scheduler changes required. `list_atp_modules()` picks up the folder for `run_tests.py --module all`.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Unknown module | Folder name under `ATP TestCase Flows` (hyphens: `signup-later`, `quick-print`) |
| No video on fail | `adb shell screenrecord` support; `ATP_SCREENRECORD`; device storage |
| Final Excel missing rows | Status files under `status/`; `build-summary/atp_suite_labels.json` |
| One device overwrote another | Videos/status already include device id; do not use a shared `failure.mp4` |
