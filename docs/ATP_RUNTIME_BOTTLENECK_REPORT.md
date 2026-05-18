# ATP Maestro Runtime Bottleneck Report & Optimization (2026-05)

Production-grade runtime optimization for the Kodak Step Print Android Maestro ATP framework. **Functional coverage, assertions, Jenkins stages, USB execution, and report paths are unchanged.**

---

## 1. Executive summary

| Area | Finding | Action taken |
|------|---------|--------------|
| **Collage ATP (21 flows)** | Highest wait density (~25–28 `waitForAnimationToEnd` + 16 `assertVisible` per file) | Shared subflows + removed 9 inter-`runFlow` waits per file |
| **Cold-start onboarding** | Repeated in every ATP file (`launchApp` + 6–8 subflows) | Kept per-test isolation; removed redundant waits *between* subflows only |
| **Printer connection** | 4× animation wait on “Searching…”; duplicate Connect blocks in `findAndConnectPrinter` | Targeted `extendedWaitUntil` + deduplicated Connect path |
| **Orchestration** | No per-flow wall-clock in reports | `duration_ms` in status + `reports/<suite>/flow_timing.jsonl` |
| **Screenshots** | Only `waitForPrinting.yaml` uses `takeScreenshot` on success | No change (failures still use Maestro default screenshots) |

**Estimated savings (Collage suite, single device, physical phone):**

| Optimization | Est. per flow | × 21 flows | Notes |
|--------------|---------------|------------|-------|
| Remove wait before `runFlow` (~9/flow) | 9–27 s | 3–9 min | ~1–3 s each animation poll |
| Collage shared swipe/photos/home blocks | 2–6 s | 1–2 min | Less YAML parse + fewer duplicate polls |
| `handlePrinterConnection` search wait | 3–12 s | When printer flows run | 4 polls → 1 targeted wait |
| `findAndConnectPrinter` dedup | 2–8 s | Printer-dependent tests | Removed duplicate Connect block |

**Total Collage-only estimate: ~5–15 minutes per full Collage stage** (device/app speed dependent). Full ATP (107 flows): **~15–40 minutes** potential once all folders are exercised with the same wait-stripping pattern.

---

## 2. Bottleneck analysis (quantitative)

### 2.1 Repository scale

- **183** Maestro YAML files
- **107** ATP testcase flows under `ATP TestCase Flows/`
- **51** reusable flows under `flows/`
- **~175** files use `waitForAnimationToEnd` (dominant wait primitive)
- **0** uses of `waitUntilVisible` (project uses `extendedWaitUntil` + `assertVisible`)
- **25** files use `extendedWaitUntil` (mostly Collage home @ 25s)

### 2.2 Top consumers (wait + assert density)

| Rank | File | wait | assert | ext | Total |
|------|------|------|--------|-----|-------|
| 1 | `TC_COL_18_Max_Four_Image_Limit.yaml` | 28 | 16 | 1 | 45 |
| 2–5 | Other Collage four-image layouts | 27 | 16 | 1 | 44 |
| 6 | `flows/Settings.yaml` | 19 | 23 | 0 | 42 |
| 7 | `TC_COL_01_One_Image_Layout_1.yaml` | 25 | 16 | 1 | 42 |

**Collage** is the primary suite cost: cold launch + full onboarding + album + multi-select + layout + save on every test.

### 2.3 Structural bottlenecks

1. **Per-test cold start** — `launchApp: clearState: true` on most ATP files (required for isolation; not removed).
2. **Repeated onboarding chain** — `loadElements` → skip signup → terms → permissions → welcome → swipe → skip → home (necessary for coverage; optimized by removing padding waits).
3. **Animation polling** — `waitForAnimationToEnd` after nearly every tap/swipe (Maestro hierarchy refresh cost).
4. **Printer BT search** — up to 8 retries in `findAndConnectPrinter.yaml` (kept for reliability; removed only duplicate Connect handling).
5. **ADB + driver IPC** — mitigated in `run_one_flow_on_device.bat` (7001 retry, device wait); not YAML-optimizable.
6. **No parallel same-device** — sequential orchestrator by design (constraint honored).

### 2.4 What was NOT changed (by design)

- Maestro version / CLI
- Jenkins stage names or architecture
- `scripts/run_one_flow_on_device.bat` entry contract (only timing lines added)
- Excel / `build-summary` report schema
- Assertions, test steps, or skipped tests
- Emulator / wireless ADB
- Parallel execution on one device

---

## 3. Optimizations implemented

### 3.1 Shared flows (low risk)

| File | Change | Risk | Rollback |
|------|--------|------|----------|
| `flows/handlePrinterConnection.yaml` | `extendedWaitUntil` until search ends vs 4× `waitForAnimationToEnd` | Low–medium on slow BT | `git checkout -- flows/handlePrinterConnection.yaml` |
| `flows/findAndConnectPrinter.yaml` | Removed duplicate trailing Connect block | Low | `git checkout -- flows/findAndConnectPrinter.yaml` |
| `flows/Swipe to continue.yaml` | Removed leading animation wait (callers retain post-tap waits) | Low | `git checkout -- flows/Swipe\ to\ continue.yaml` |
| `flows/FilterHandling.yaml` | Removed duplicate trailing wait | Low | `git checkout -- flows/FilterHandling.yaml` |
| **New** `flows/swipeOnboardingIfShown.yaml` | Collage swipe intro (same steps as inline) | Low | Delete file + revert Collage YAMLs |
| **New** `flows/grantPhotosAccess.yaml` | Photos permission dialogs | Low | Delete file + revert Collage YAMLs |
| **New** `flows/waitForHomeScreen.yaml` | `extendedWaitUntil` + home asserts | Low | Delete file + revert Collage YAMLs |

### 3.2 ATP YAML batch optimization

Script: `scripts/apply_atp_runtime_optimizations.py`

- **All ATP folders:** strip `- waitForAnimationToEnd` when the next command is `- runFlow:` (subflow already waits).
- **Collage only:** replace inline swipe / photos / home blocks with shared flows above.

**Applied totals:** 35 files, **207** inter-runFlow waits removed, **21** swipe + **21** photos + **21** home consolidations (Collage).

Re-run safely:

```bat
python scripts\apply_atp_runtime_optimizations.py --dry-run
python scripts\apply_atp_runtime_optimizations.py
python scripts\apply_atp_runtime_optimizations.py --folder Editing
```

### 3.3 Performance instrumentation (additive)

| Artifact | Location | Purpose |
|----------|----------|---------|
| Log lines | `reports/<suite>/logs/<flow>_<device>.log` | `[TIMING] flow_start_ms` / `duration_ms` |
| Status field | `status/<suite>__<flow>__<device>.txt` | `duration_ms=<ms>` |
| JSONL | `reports/<suite>/flow_timing.jsonl` | Per-flow wall clock for bottleneck charts |
| Lifecycle | `reports/<suite>/orchestrator_lifecycle.log` | `duration_ms` on success |

Disable telemetry: `set ATP_FLOW_TIMING=0` before orchestrator.

Summarize after a run:

```bat
python scripts\summarize_flow_timing.py atp_collage
```

---

## 4. Before vs after (example: `TC_COL_01`)

**Before (excerpt):** 8× `waitForAnimationToEnd` between onboarding `runFlow` calls + inline swipe (11 lines) + inline photos (12 lines) + inline home wait (5 lines).

**After (excerpt):** onboarding `runFlow` chain without padding waits + 3 shared subflows (`swipeOnboardingIfShown`, `waitForHomeScreen`, `grantPhotosAccess`).

Assertions and ATP steps (All Photos → Collage → layout → Save) are **unchanged**.

---

## 5. Risk assessment & fallback

| Change | Risk | Symptom | Fallback |
|--------|------|---------|----------|
| Wait before `runFlow` removed | Medium on very slow devices | Flaky subflow entry | Re-add single `waitForAnimationToEnd` before failing subflow |
| `handlePrinterConnection` search wait | Medium | BT search timeout | Revert file; restore 4× wait block |
| Collage shared home flow | Low | Home assert timeout | Increase `timeout: 25000` in `waitForHomeScreen.yaml` |
| Instrumentation | None | N/A | `ATP_FLOW_TIMING=0` |

**Full rollback (one command):**

```bat
git checkout -- flows/ "ATP TestCase Flows/" scripts/run_one_flow_on_device.bat execution/
```

---

## 6. Files modified (this optimization pass)

### New files

- `flows/swipeOnboardingIfShown.yaml`
- `flows/grantPhotosAccess.yaml`
- `flows/waitForHomeScreen.yaml`
- `scripts/apply_atp_runtime_optimizations.py`
- `scripts/summarize_flow_timing.py`
- `execution/flow_timing.py`
- `docs/ATP_RUNTIME_BOTTLENECK_REPORT.md`

### Modified shared flows

- `flows/handlePrinterConnection.yaml`
- `flows/findAndConnectPrinter.yaml`
- `flows/Swipe to continue.yaml`
- `flows/FilterHandling.yaml`

### Modified orchestration

- `scripts/run_one_flow_on_device.bat` (timing only)
- `execution/maestro_runner.py`
- `execution/atp_jenkins_orchestrator.py`

### Modified ATP (via script)

- **21** `ATP TestCase Flows/Collage/*.yaml`
- **14** additional ATP files (Camera, Precut, Printing, SignUp_Login) with inter-runFlow wait stripping

---

## 7. Recommended validation

1. Run **Collage** stage only on USB device (`RUN_ATP_COLLAGE=true`, others false).
2. Compare `reports/atp_collage/flow_timing.jsonl` total wall time vs previous Jenkins build (if archived).
3. Confirm Excel report path unchanged: `build-summary/final_execution_report.xlsx`.
4. On any flake, check log for step before failure; apply targeted wait on that transition only.

---

## 8. Future safe wins (not implemented)

- **Editing / Settings / Onboarding** — run `apply_atp_runtime_optimizations.py --folder <name>` after Collage stabilizes.
- **assertVisible timeout** — Maestro supports shorter timeouts on fast-fail paths (needs per-screen tuning).
- **Optional `MAESTRO_DRIVER_STARTUP_TIMEOUT`** env on agent (driver IPC, not YAML).
- **Do not** share printer session across ATP files without explicit product sign-off (breaks isolation).

---

*Generated as part of the ATP runtime optimization initiative. Rollback-safe; re-run the apply script only on a clean git branch.*
