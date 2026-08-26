# Maestro Project Review Report — Pre-Cut module (iteration 1)

**Date:** 2026-08-03  
**Scope completed this iteration:** Pre-Cut module + High-severity project fixes  
**Project size:** ~1205 YAML files under `ATP TestCase Flows/`  
**Device:** ZA222RFQ75  

---

## Executive summary

A full deep rewrite of all 1205 flows is not practical in one pass. This iteration:

1. Static-audited the whole project for broken refs, stubs, and inconsistencies  
2. Fully reviewed and improved the **Pre-Cut** module (`PC_01`–`PC_11`)  
3. Fixed **High** defects (broken permission path, Verification Suite PreCut → Collage)  

**Physical re-run:** blocked — Maestro driver cannot install (`INSTALL_FAILED_INSUFFICIENT_STORAGE` / invalid UID). No `maestro` packages currently listed on device.

---

## Files reviewed (this iteration)

| Area | Files | Depth |
|------|-------|--------|
| `ATP TestCase Flows/precut/**` | 18+ YAML | Full rewrite of stubs |
| `ATP Verification Suite/flows/PreCut/**` | 2 | Fixed wiring |
| `permission/subflows/open_quick_print_gallery_for_pm01.yaml` | 1 | Broken ref fix |
| Project-wide static audit | ~1205 | Search only |

---

## Files modified

### Pre-Cut flows
- `PC_01` … `PC_09` — replaced optional-assert stubs with real assertions / selection logic  
- `PC_10`, `PC_11` — already real; left as check-only printer tests  

### New / updated Pre-Cut subflows
- `reach_create_hub_for_precut.yaml` (new)  
- `open_precut_from_create_hub.yaml` (new)  
- `allow_gallery_if_prompted.yaml` (new)  
- `dismiss_precut_info_popup_if_visible.yaml` (new)  
- `assert_precut_selection_screen.yaml` (new)  
- `select_two_unique_precut_photos.yaml` (new)  
- `reach_module_screen.yaml` (refactored)  
- `reach_precut_print_preview.yaml` (refactored to reuse helpers)  
- `CHECKLIST.md` (updated)  

### Project High fixes
- `permission/subflows/open_quick_print_gallery_for_pm01.yaml` — `allow_photos_all_permission_strict.yaml` → `allow_photos_all_permission.yaml`  
- `ATP Verification Suite/flows/PreCut/PreCut.yaml` — no longer runs Collage; uses precut `reach_module_screen`  

---

## Issues found & fixes

| # | Issue | Why | Fix |
|---|--------|-----|-----|
| 1 | PC_01–PC_09 were stubs | Excel generator only wired `reach_module_screen` + optional assert | Implemented selection, popup, permission-deny, exit paths |
| 2 | Soft `optional: true` assertions | Failures were silent | Strict asserts on Select 2 Photos / Next / preview |
| 3 | `reach_module_screen` weak signup wait | `"Sign up"` only | Broader regex + Get Started handling |
| 4 | Got It dismissed before PC_07 could assert | Popup handled inside open | Split `reach_create_hub_for_precut` vs full reach |
| 5 | Broken `runFlow` to missing `_strict` photos helper | File never existed | Point to `allow_photos_all_permission.yaml` |
| 6 | Verification Suite PreCut → Collage | Generator reused wrong stage | Wire to real Precut setup |
| 7 | Duplicate gallery/popup logic | Copy-paste across subflows | Shared `allow_gallery_if_prompted`, `dismiss_precut_info_popup_if_visible` |

---

## Remaining issues (project-wide)

| Severity | Item |
|----------|------|
| **Blocker** | Maestro driver install fails on ZA222RFQ75 — reboot / reinstall Maestro APKs before device validation |
| **High** | Tile-print TP_01–16 still stubs; Verification Suite `TilePrint.yaml` → Printing |
| **High** | Printing PR_* first wave largely stubs |
| **Med** | `back` vs `pressKey: back` inconsistency (tile-print, quick-print, settings) |
| **Med** | Coordinate taps remain in Precut gallery grid (Compose; no stable IDs yet) |
| **Med** | Connection / AI modules (~450 files) not deeply reviewed this pass |
| **Low** | PC_10/PC_11 need unsupported printer already connected (by design) |

---

## Suggestions for further improvement

1. Recover Maestro on device, then run `.\scripts\run_precut_suite.ps1 -Mode Positive` and fix any selector drift.  
2. Next module: **tile-print** (mirror Precut stub → real implementation + fix Verification Suite).  
3. Prefer resource IDs once app exposes them for Pre-Cut gallery cells.  
4. Add CI gate: fail build on broken `runFlow` paths (script).  
5. Normalize all `back` → `pressKey: back`.  

---

## Scores (estimates)

| Metric | Score | Rationale |
|--------|-------|-----------|
| **Automation stability (Pre-Cut module)** | **72%** | Real flows + sync waits; device not re-validated; grid still coordinate-based |
| **Maintainability (Pre-Cut module)** | **80%** | Shared subflows, clear checklist, printer matrix documented |
| **Automation stability (whole project)** | **45%** | Large stub surface (printing/tile-print/Excel generators) |
| **Maintainability (whole project)** | **55%** | Good folder layout; inconsistent patterns across modules |

---

## Next module recommended

**Tile Print** — same stub pattern as Pre-Cut; TP_17 already implements printer gating well.

---

## How to validate Pre-Cut after Maestro is fixed

```powershell
# Positive PC_01–PC_09 (2x3 printer or no printer)
.\scripts\run_precut_suite.ps1 -Device ZA222RFQ75 -Mode Positive

# Negative PC_10–PC_11 (unsupported printer already connected)
.\scripts\run_precut_suite.ps1 -Device ZA222RFQ75 -Mode Negative
```
