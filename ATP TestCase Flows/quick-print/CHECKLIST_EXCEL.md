# Quick Print — Excel ATP (31 cases)

Suite is **only** these Excel rows. Extra QP_/QPX_/matrix flows were removed.

**Print:** Any case that opens the Print Preview screen (`QP_006a`, `QP_006b`, `QP_006c`) connects HP Sprocket 200 if needed (Add Printer → Skip to Connection), taps Print, and asserts Print Complete. `QP_006d` does not print — Preview is disabled at 0 selected. `QP_006e` stops at the max-10 toast.

**Runner:** Jenkins `RUN_ATP_QUICK_PRINT` or `python scripts/run_atp_module_verify.py --module quick-print`

| ID | Excel | Flow |
|----|-------|------|
| QP_001 | QUICK PRINT _001 | Navigate to Gallery via Quick Print |
| QP_002 | QUICK PRINT _002 | Gallery permission popup first open |
| QP_003a | QUICK PRINT_003 (a) | Allow all opens Gallery |
| QP_003b | QUICK PRINT_003 (b) | Allow limited access selected photos |
| QP_003c | QUICK PRINT_003 (c) | Don't allow restricts Gallery |
| QP_003d | QUICK PRINT_003 (d) | Open Settings grant permission |
| QP_004 | QUICK PRINT_004 | Gallery screen user interface |
| QP_005a | QUICK PRINT_005 (a) | Select Mode toast first visit |
| QP_005b | QUICK PRINT_005 (b) | Select Mode toast not on second visit |
| QP_006a | QUICK PRINT_006 (a) | Select Mode user interface **and print** |
| QP_006b | QUICK PRINT_006 (b) | Enter Select Mode one photo **and print** |
| QP_006c | QUICK PRINT_006 (c) | Select photos and videos **and print** |
| QP_006d | QUICK PRINT_006 (d) | Unselect all photos and videos |
| QP_006e | QUICK PRINT_006 (e) | Maximum selection limit of 10 |
| QP_007 | QUICK PRINT_07 | Facebook option on Select Gallery |
| QP_007a | QUICK PRINT_07 (a) | Facebook Gallery folders after login |
| QP_007b | QUICK PRINT_07 (b) | Open Facebook folder images |
| QP_008 | QUICK PRINT_08 | Unlink option in overflow menu |
| QP_008a | QUICK PRINT_08 (a) | Unlink confirmation popup UI |
| QP_008b | QUICK PRINT_08 (b) | Sign out from Facebook |
| QP_008c | QUICK PRINT_08 (c) | Cancel unlink stays signed in |
| QP_009 | QUICK PRINT_09 | No Internet popup Facebook Gallery |
| QP_010 | QUICK PRINT_10 | Open Settings Wi-Fi restore Facebook |
| QP_011 | QUICK PRINT_11 | Wi-Fi Direct No Internet HP600 |
| QP_012 | QUICK PRINT_12 | Facebook Tag icon UI |
| QP_013a | QUICK PRINT_13 (a) | Filter Facebook photos valid tag |
| QP_013b | QUICK PRINT_13 (b) | Invalid tag No Tagged Photos |
| QP_013c | QUICK PRINT_13 (c) | No Internet tag search |
| QP_013d | QUICK PRINT_13 (d) | Tag search after internet restored |
| QP_014 | QUICK PRINT_14 | Sort Newest and Oldest |
| QP_015 | QUICK PRINT_15 | No Photos Found empty folder |

- [ ] QP_001
- [ ] QP_002
- [ ] QP_003a
- [ ] QP_003b
- [ ] QP_003c
- [ ] QP_003d
- [ ] QP_004
- [ ] QP_005a
- [ ] QP_005b
- [ ] QP_006a
- [ ] QP_006b
- [ ] QP_006c
- [ ] QP_006d
- [ ] QP_006e
- [ ] QP_007
- [ ] QP_007a
- [ ] QP_007b
- [ ] QP_008
- [ ] QP_008a
- [ ] QP_008b
- [ ] QP_008c
- [ ] QP_009
- [ ] QP_010
- [ ] QP_011
- [ ] QP_012
- [ ] QP_013a
- [ ] QP_013b
- [ ] QP_013c
- [ ] QP_013d
- [ ] QP_014
- [ ] QP_015
