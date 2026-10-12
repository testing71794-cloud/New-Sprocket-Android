# Print Preview live verification

Date: 2026-09-01  
Device: `PVFM5L7LTGHUNZA6` (Vivo, Android 12 / API 31)  
Maestro: `2.2.0`

## Verified

- **PR_01 — PASS**: HP Sprocket 200 (`DC:A8`) discovered and connected; Finish Connection,
  Create, Quick Print, photo selection, and Print Preview were reached successfully.
- **PR_02 — PASS**: HP600 / Studio Plus connected through CAGlobal using the supplied
  test-network password; Quick Print reached Print Preview successfully.
- **Print Preview entry helper — PASS**: clean launch through onboarding, guest flow,
  gallery permission, one-photo selection, and preview UI assertions.
- **Copies `+` interaction calibration — PASS**: after the Fit/Fill toast clears,
  tapping `66%,72%` changes the count from 1 to 2.

## Blocked or pending

- **PR_10 full boundary loop**: reruns were interrupted by the Vivo Maestro driver closing
  its `localhost:7001` transport during hierarchy reads. The live run exposed and fixed the
  Fit/Fill toast overlap and copy-control coordinate.
- **PR_24 Facebook low-resolution warning**: Facebook OAuth advanced using the existing
  signup/login credential subflows, then the same Maestro driver transport disconnected.
- **PR_03–PR_09 printer-specific canvas checks** still require each named printer model;
  DCA8 only validates the HP Sprocket 200 path.
- Multi-touch rotation/pinch and pixel-level canvas/guide validation remain manual as
  documented in `CHECKLIST_EXCEL.md`.

The CAGlobal test-network password is stored in the HP600 connection subflow as requested.
