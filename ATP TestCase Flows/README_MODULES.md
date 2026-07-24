# ATP TestCase Flows — module map (HP Sprocket Android)

Generated / maintained from the ATP Excel sheet via:

```bat
python scripts\generate_atp_modules_from_excel.py
python scripts\generate_atp_modules_from_excel.py --remaining-only
```

## Hand-tuned modules (kept as-is)

| Folder | Prefix | Notes |
|--------|--------|--------|
| splash | SP_ | Splash / welcome |
| onboarding | ON_ | Carousel |
| signup | SG_ | Sign up |
| login | LO_ | Log in |
| signup-later | SL_ | Sign Up Later |
| connection | CO_ | Printer connection (CO_01–04) |
| permission | PM_ | Runtime permissions |
| gallery | GA_ | Gallery home |
| quick-print | QP_ | Quick Print gallery |
| collage | COL_ | Collage Maker |

## Excel-generated modules (new folders)

| Folder | Prefix | Excel stage | Flows |
|--------|--------|-------------|------:|
| home | HM_ | Home | 5 |
| camera | CA_ | Camera | 28 |
| editor | ED_ | Editor | 24 |
| printing | PR_ | Printing | 75 |
| precut | PC_ | PreCut | 6 |
| video | VD_ | Video | 8 |
| tile-print | TP_ | TilePrint | 8 |
| settings | SE_ | Settings | 25 |
| firmware | FW_ | Firmware | 51 |
| ai | AI_ | AI | 81 |
| alerts | AL_ | Alerts | 49 |
| general | GN_ | General | 166 |

## Excel extensions inside hand-tuned folders

These **add** flows next to hand-tuned ones (do not overwrite SP_/ON_/QP_/COL_/CO_):

| Folder | Excel prefix | Excel stage | Added flows |
|--------|--------------|-------------|------------:|
| splash | SPX_ | Splash | 1 |
| onboarding | ONX_ | Onboarding | 18 |
| quick-print | QPX_ | QuickPrint | 45 |
| collage | COLX_ | Collage | 11 |
| connection | COX_ | Connection | 256 |

Setup helper for these: `subflows/reach_excel_screen.yaml`  
Mapping: `atp_*_excel_mapping.csv` + `CHECKLIST_EXCEL.md`

## Priority Excel sections (fully covered)

See [PRIORITY_SECTIONS.md](PRIORITY_SECTIONS.md) for:

AI TOOLS SDK · PHOTO ID · PHOTOBOOTH · TILES MODULES · PRINT PREVIEWS SCREEN · VIDEO FRAMES · MAIN HOME SCREEN (QUICK) · ONBOARDING SPLASH SCREEN

## Feature modules from Excel sections (e.g. PHOTO ID)

| Folder | Prefix | Excel section | Flows |
|--------|--------|---------------|------:|
| photo-id | PID_ | PHOTO ID | 23 |
| photobooth | PB_ | PHOTOBOOTH | 17 |
| custom-sdk | CS_ | CUSTOM SDK | 14 |
| tile-print | TP_ | TILES MODULES | 16 |
| precut | PC_ | PRECUT | 9 |
| video | VD_ | VIDEO FRAMES | 7 |

Jenkins: `RUN_ATP_PHOTO_ID`, `RUN_ATP_PHOTOBOOTH`, `RUN_ATP_CUSTOM_SDK` (default false).
