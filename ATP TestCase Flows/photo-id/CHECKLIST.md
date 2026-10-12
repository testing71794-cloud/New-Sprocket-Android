# PhotoID / photo-id — Excel-aligned flows (PhotoID_01 … Photo ID_12)

Excel IDs match the ATP Photo ID sheet. File prefix remains `PID_` (Jenkins `RUN_ATP_PHOTO_ID`).

**Note:** Excel reuses `Photo ID_05` / `05 (a)` / `05 (b)` for both camera-permission and Timer cases. Timer rows are filed as `PID_05c`–`PID_05f` so paths stay unique; Excel ID is preserved in each flow header.

## Navigation & Mode popup

- [ ] PID_01 | PhotoID_01 | Navigation Flow
- [ ] PID_02 | PhotoID_02 | Mode Information Popup UI
- [ ] PID_02a | PhotoID_02 (a) | Mode Information Popup Back Button
- [ ] PID_02b | PhotoID_02 (b) | Mode Information Popup Display Again
- [ ] PID_02c | PhotoID_02 (c) | Don’t Show Again Functionality

## Flash & camera

- [ ] PID_03 | Photo ID_03 | Flash functionality for Front Camera
- [ ] PID_03a | Photo ID_03 (a) | Flash screen acts as flash (Front)
- [ ] PID_03b | Photo ID_03 (b) | Flash functionality for Rear Camera
- [ ] PID_04 | Photo ID_04 | Front camera opens by default
- [ ] PID_04a | Photo ID_04 (a) | Switch front camera to rear camera

## Camera permission

- [ ] PID_05 | Photo ID_05 | camera permission deny
- [ ] PID_05a | Photo ID_05 (a) | Open Settings Button Functionality
- [ ] PID_05b | Photo ID_05 (b) | granting Camera permission

## Timer (Excel also labeled Photo ID_05*)

- [ ] PID_05c | Photo ID_05 (Timer) | Timer selection
- [ ] PID_05d | Photo ID_05 (a) (3s Timer) | 3s Timer selection
- [ ] PID_05e | Photo ID_05 (b) (5s Timer) | 5s Timer selection
- [ ] PID_05f | Photo ID_05 (c) (10s Timer) | 10s Timer selection

## Print Preview by size / timer

- [ ] PID_06 | Photo ID_06 | Print Preview (2×2) for 3 seconds
- [ ] PID_06b | Photo ID_06 (b) | Print Preview (2×2) for 5 seconds
- [ ] PID_06c | Photo ID_06 (c) | Print Preview (2×2) for 10 seconds
- [ ] PID_07 | Photo ID_07 | Print Preview (1×1) for 3 seconds
- [ ] PID_07b | Photo ID_07 (b) | Print Preview (1×1) for 5 seconds
- [ ] PID_07c | Photo ID_07 (c) | Print Preview (1×1) for 10 seconds
- [ ] PID_08a | Photo ID_08 (a) | Print Preview (1.4×1.8) for 3 seconds
- [ ] PID_08b | Photo ID_08 (b) | Print Preview (1.4×1.8) for 5 seconds
- [ ] PID_08c | Photo ID_08 (c) | Print Preview (1.4×1.8) for 10 seconds
- [ ] PID_09a | Photo ID_09 (a) | Print Preview (1.3×1.9) for 3 seconds
- [ ] PID_09b | Photo ID_9 (b) | Print Preview (1.3×1.9) for 5 seconds
- [ ] PID_09c | Photo ID_9 (c) | Print Preview (1.3×1.9) for 10 seconds

## Edit toast, Print, Stop

- [ ] PID_10 | Photo ID_10 | Edit toast message at Print Preview
- [ ] PID_11 | Photo ID_11 | Print
- [ ] PID_12 | Photo ID_12 | Timer Countdown Stop button
