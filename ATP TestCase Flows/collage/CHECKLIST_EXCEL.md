# Collage ATP — Excel sheet alignment

Suite uses **one shortest path** (`subflows/excel_launch_to_collage.yaml`) then only the unique sheet steps.

**Runner:** `.\scripts\run_collage_suite.ps1 -Device <SERIAL>`  
**Mapping:** `atp_collage_mapping.csv` (`FlowFile` column — used by `run_atp_module_verify.py`)

Large-collage rows (2–8 photos) need a **3x4 / Studio / Studio Plus** printer: `excel_launch_to_large_collage.yaml`.

Maestro cannot assert pixel values (drop shadow hex/blur, 48px min height, 8px Edit inset, 0.5x–4x zoom). Those rows still exercise the gesture and assert the screen stays on the expected UI.

Duplicate Excel IDs on the sheet are split as: `COL_09b` vs `COL_09b_3x4`; `COL_12e_ios` / `COL_12e_pinch` / `COL_12e_fitfill`.

- [ ] COL_01 | Collage_01 | Launch to Collage selection
- [ ] COL_02 | Collage_02 | Default selection UI
- [ ] COL_03 | Collage_03 | Back button
- [ ] COL_04 | Collage_04 | Folder selection
- [ ] COL_05a | Collage_05 (a) | Gallery scroll
- [ ] COL_05b | Collage_05 (b) | Top bar drop shadow (scroll proxy)
- [ ] COL_06a | Collage_06 (a) | Selected photo in slot
- [ ] COL_06b | Collage_06 (b) | Slot focus advances
- [ ] COL_06c | Collage_06 (c) | Selection count numbers
- [ ] COL_06d | Collage_06 (d) | Duplicate photo counts 1–4
- [ ] COL_06e | Collage_06 (e) | Count markers skip empty slots
- [ ] COL_06f | Collage_06 (f) | Fifth photo replaces slot 4
- [ ] COL_06g | Collage_06 (g) | Large collage carousel snap
- [ ] COL_07 | Collage_07 | Next enables at 2 photos
- [ ] COL_08 | Collage_08 | Deselect shifts remaining photos
- [ ] COL_09a | Collage_09 (a) | 4 photos → Drag & Drop
- [ ] COL_09b | Collage_9 (b) | 2 photos → Drag & Drop
- [ ] COL_09b_3x4 | Collage_9 (b) | 2–8 photos (3x4 / Studio)
- [ ] COL_09c | Collage_9 (c) | 2–8 photos (Studio Plus)
- [ ] COL_10 | Collage_10 | 2-photo layout
- [ ] COL_10b | Collage_10 (b) | 3-photo layout
- [ ] COL_10c | Collage_10 (c) | 4-photo layout
- [ ] COL_10d | Collage_10 (d) | 5-photo layout
- [ ] COL_10e | Collage_10 (e) | 6-photo layout
- [ ] COL_10f | Collage_10 (f) | 7-photo layout
- [ ] COL_10g | Collage_10 (g) | 8-photo layout
- [ ] COL_11 | Collage_11 | Grabbed state (long press)
- [ ] COL_12a | Collage_12 (a) | Drag swap tiles
- [ ] COL_12b | Collage_12 (b) | Cancel drag outside frame
- [ ] COL_12c | Collage_12 (c) | Cancel drag return to original
- [ ] COL_12d | Collage_12 (d) | Android zoom range (gesture proxy)
- [ ] COL_12e_ios | Collage_12 (e) | iOS zoom (skipped on Android)
- [ ] COL_12e_pinch | Collage_12 (e) | Pinch zoom (gesture proxy)
- [ ] COL_12e_fitfill | Collage_12 (e) | Double tap Fit/Fill
- [ ] COL_12f | Collage_12 (f) | Pinch and rotate (gesture proxy)
- [ ] COL_12g | Collage_12 (g) | Reset properties after swap
- [ ] COL_12h | Collage_12 (h) | Reset properties on layout change
- [ ] COL_12i | Collage_12 (i) | Resize tiles by divider
- [ ] COL_12j | Collage_12 (j) | Minimum tile height (gesture proxy)
- [ ] COL_12k | Collage_12 (k) | Divider does not affect unrelated tiles
- [ ] COL_12l | Collage_12 (l) | Full-length divider
- [ ] COL_12m | Collage_12 (m) | Partial dividers independent
- [ ] COL_12n | Collage_12 (n) | Edit button follows tile
- [ ] COL_13 | Collage_13 | Edit icon opens custom SDK
- [ ] COL_14 | Collage_14 | Large collage with listed printer
- [ ] COL_14a | Collage_14 (a) | Large collage minimum 2
- [ ] COL_14b | Collage_14 (b) | Large collage max 8
- [ ] COL_14c | Collage_14 (c) | 8-photo tip toast
- [ ] COL_14d | Collage_14 (d) | Tap dismisses tip toast
- [ ] COL_14e | Collage_14 (e) | Ninth photo replaces slot 8
- [ ] COL_15 | Collage_15 | Edits retained in Print Preview
- [ ] COL_16 | Collage_16 | Save as new photo popup
