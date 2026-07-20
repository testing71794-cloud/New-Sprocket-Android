# HP Sprocket — ATP Verification Suite

Continue-on-failure verification framework driven by the ATP Excel sheet.
One Maestro **stage flow** per module; every ATP row becomes sequential verifications that never abort the run.

## Layout

```
ATP Verification Suite/
  catalog/
    Hp_new_sprocket_ATP_Sheet.xlsx   # source ATP
    atp_cases.json                   # parsed cases + verifications
    stages/*.json                    # per-stage catalogs
  flows/
    Splash|Onboarding|Home|Collage|QuickPrint|Connection|Editor|Printing|Settings/
      <Stage>.yaml                   # Maestro navigation / screen reach
      setup.yaml                     # invoked by Python runner
    _common/reach_create_home.yaml
  lib/
    parse_atp_excel.py
    hierarchy.py                     # adb uiautomator dump
    verify.py                        # verifyVisible/Text/Enabled/... (never throw)
    recorder.py                      # recordPass/Fail + screenshots
    report.py                        # execution_report.xlsx + summary.json
  runners/run_module.py
  run_suite.py                       # CLI
```

## Why Python for assertions?

Maestro `assertVisible` **stops the flow** on failure. Requirements demand continue-on-failure with PASS/FAIL rows, so assertions run in Python against an ADB hierarchy dump. Maestro YAML is used for setup/navigation only.

## Helpers (never raise)

| Helper | Role |
|--------|------|
| `verifyVisible` / `verifyNotVisible` | Presence |
| `verifyText` / `verifyEnabled` / `verifyDisabled` | Text & state |
| `verifyImage` / `verifyNavigation` | Logo / screen markers |
| `verifyToast` / `verifyDialog` / `verifyPermission` | Overlays |
| `recordPass` / `recordFail` | Result rows |
| `takeFailureScreenshot` | Screenshot on FAIL only |

Flaky lookups retry **twice** before FAIL.

## Outputs (repo root)

| Path | Content |
|------|---------|
| `logs/verification.log` | Timestamped PASS/FAIL lines |
| `screenshots/` | Failure captures only |
| `reports/execution_report.xlsx` | Full verification table + Summary sheet |
| `reports/summary.json` | Totals, pass %, failed modules |

## Commands

From repo root:

```bash
# Re-parse Excel → catalog
python "ATP Verification Suite/run_suite.py" --refresh-catalog

# Offline sample report (no device)
python "ATP Verification Suite/run_suite.py" --dry-report

# Run one stage on device (continue-on-failure)
python "ATP Verification Suite/run_suite.py" --stage Splash --device ZA222RFQ75

# Run all stages
python "ATP Verification Suite/run_suite.py" --all --device ZA222RFQ75 --skip-setup
```

Skip Maestro setup when the app is already on the target screen:

```bash
python "ATP Verification Suite/run_suite.py" --stage Collage --device SERIAL --skip-setup
```

## Stage map (Excel → module flow)

| Stage flow | ATP areas (normalized) |
|------------|------------------------|
| Splash | Splash screen |
| Onboarding | Onboarding, Sign up, Log in |
| Home | Create / home hub |
| QuickPrint | Gallery / Quick Print |
| Collage | Collage Maker |
| Connection | Bluetooth / printers |
| Editor | Crop, filters, stickers, … |
| Printing | Preview / print / queue |
| Settings | Account / legal / permissions |
| (+ others) | Camera, AI, Alerts, Firmware, … use shared home setup |

## Coexistence

Existing `ATP TestCase Flows/` per-TC Maestro suites remain the Jenkins path.
This suite is **additive** — module-level continue-on-failure reporting from the full Excel ATP.
