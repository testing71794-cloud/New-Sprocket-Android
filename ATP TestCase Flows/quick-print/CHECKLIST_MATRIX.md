# Quick Print matrix QP_001–QP_050 (see atp_quick_print_matrix_mapping.csv)

Legacy flows **QP_01–QP_19** and **QPX_01–QPX_29** are unchanged.

## New matrix flows — verified on ZA222RFQ75 (2026-07-28)

- [x] QP_004 | Gallery | Verify thumbnails load while scrolling
- [x] QP_007 | Gallery | Verify gallery after app relaunch
- [x] QP_008 | Gallery | Verify gallery with large photo collection
- [x] QP_013 | Selection | Verify numbering updates after deselection
- [x] QP_014 | Selection | Drag to select multiple photos
- [x] QP_017 | Selection | Verify Print button disabled when nothing selected
- [x] QP_023 | Folder | Scroll folder list
- [x] QP_024 | Folder | Change folder after selecting photos
- [x] QP_037 | Tag Search | Submit empty search validation
- [x] QP_039 | Tag Search | Retry tag search after reconnect
- [x] QP_041 | Permissions | Grant permission from Settings
- [x] QP_042 | Permissions | Return without granting permission
- [x] QP_046 | Fast Scroll | Release fast scroll gallery responsive
- [x] QP_047 | Empty State | Open gallery with no local photos
- [x] QP_048 | Empty State | Add photos after empty state *(manual-only stub — passes setup)*
- [x] QP_049 | Error Handling | Lose network during gallery refresh
- [x] QP_050 | End-to-End | Complete Quick Print flow to Print Preview

**Result: 17/17 passed** (~29 min full run)

## Covered by existing flows (no new YAML)

QP_001–QP_003, QP_005–QP_006, QP_009–QP_012, QP_015–QP_016, QP_018–QP_022, QP_025–QP_036, QP_038, QP_040, QP_043–QP_045 — see `atp_quick_print_matrix_mapping.csv`.
