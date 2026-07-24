# Priority Excel sections → ATP modules

| Excel section | Folder | Prefix | Jenkins flag |
|---------------|--------|--------|--------------|
| AI TOOLS SDK | `ai/` | `AI_` | `RUN_ATP_AI` |
| PHOTO ID | `photo-id/` | `PID_` | `RUN_ATP_PHOTO_ID` |
| PHOTOBOOTH | `photobooth/` | `PB_` | `RUN_ATP_PHOTOBOOTH` |
| TILES MODULES | `tile-print/` | `TP_` | `RUN_ATP_TILE_PRINT` |
| PRINT PREVIEWS SCREEN | `printing/` | `PR_` | `RUN_ATP_PRINTING` |
| VIDEO FRAMES | `video/` | `VD_` | `RUN_ATP_VIDEO` |
| MAIN HOME SCREEN (QUICK) | `home/` | `HM_` | `RUN_ATP_HOME` |
| ONBOARDING SPLASH SCREEN | `onboarding-splash/` | `OSS_` | `RUN_ATP_ONBOARDING_SPLASH` |

Regenerate:

```bat
python "ATP Verification Suite\run_suite.py" --refresh-catalog
python scripts\generate_atp_modules_from_excel.py
```
