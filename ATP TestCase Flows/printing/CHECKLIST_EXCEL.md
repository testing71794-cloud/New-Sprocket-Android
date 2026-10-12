# Print Preview ATP — supplied testcase alignment

This module is aligned 1:1 with the supplied Print Preview cases. The source list contains
**25 rows** because `Print Preview_06` is duplicated. Those rows are preserved as
`PR_06a` (Studio Plus) and `PR_06b` (Sprocket Select).

Hardware flows require the named physical printer to be powered on. HP200 discovery and
connection use the physical printer identifier `DC:A8`. `PR_02` and `PR_06a` use the
supplied CAGlobal test-network password. Low-resolution cases require the documented
native/social fixture; `PR_24` reuses the Facebook login module and its credentials.

Maestro supports single-touch swipes and double-taps, but not native multi-touch pinch or
two-finger rotation. `PR_15` and `PR_17` therefore retain explicit manual multi-touch checks.
Canvas dimensions and colored snap guides are captured as screenshots for visual validation.

- [ ] PR_01 | Print Preview_01 | BLE printer connection and Quick Print navigation
- [ ] PR_02 | Print Preview_02 | HP600 Wi-Fi connection and Quick Print navigation
- [ ] PR_03 | Print Preview_03 | HP200 2 x 3 preview canvas
- [ ] PR_04 | Print Preview_04 | Original HP Sprocket 2 x 3 preview canvas
- [ ] PR_05 | Print Preview_05 | HP Sprocket Studio 2 x 3 preview canvas
- [ ] PR_06a | Print Preview_06 | HP Sprocket Studio Plus 2 x 3 preview canvas
- [ ] PR_06b | Print Preview_06 | HP Sprocket Select 2.3 x 3.4 preview canvas
- [ ] PR_07 | Print Preview_07 | HP Sprocket Plus 2.3 x 3.4 preview canvas
- [ ] PR_08 | Print Preview_08 | HP Sprocket 3x4 3.5 x 4.25 preview canvas
- [ ] PR_09 | Print Preview_09 | Connected and disconnected printer status
- [ ] PR_10 | Print Preview_10 | Copies controls from 1 to 10
- [ ] PR_11 | Print Preview_11 | Tiles options and default 2x2 grid
- [ ] PR_12 | Print Preview_12 | Apply an AI tool from Print Preview
- [ ] PR_13 | Print Preview_13 | Apply a Frame from Edit Options
- [ ] PR_14 | Print Preview_14 | Edit one of four selected photos
- [ ] PR_15 | Print Preview_15 | Print Preview image gestures and Fit Fill
- [ ] PR_16 | Print Preview_16 | Fit Fill toast session behavior
- [ ] PR_17 | Print Preview_17 | Image rotation snap guide
- [ ] PR_18 | Print Preview_18 | Image center reposition snap
- [ ] PR_19 | Print Preview_19 | Image edge reposition snap
- [ ] PR_20 | Print Preview_20 | Back navigation without changes
- [ ] PR_21 | Print Preview_21 | Save as new photo popup after editing
- [ ] PR_22 | Print Preview_22 | Save or discard edited image
- [ ] PR_23 | Print Preview_23 | Low-resolution warning from native Gallery
- [ ] PR_24 | Print Preview_24 | Low-resolution warning from social media Gallery
