# Video / video — 7 Excel-generated flows (CR_05A–CR_05E)

Implementation updated 2026-07-29 to match Figma Video Frames design.
See `FIGMA_VIDEO_ALIGNMENT.md` for screen-by-screen checklist.

## Subflows

- `reach_module_screen.yaml` — cold launch → Quick Print gallery
- `reach_quick_print_gallery.yaml` — gallery ready asserts
- `scroll_to_gallery_video_cell.yaml` — scroll grid below Recent
- `select_video_only.yaml` — long-press video via `rightOf` first photo thumbnail; asserts not photo-only
- `tap_gallery_video_cell.yaml` — add video in mixed Select Mode via same `rightOf` rule
- `assert_video_only_selected.yaml` — not `1 Photo Selected` / `Photos Selected`
- `enter_select_mode.yaml` — **photo cell only** (mixed flows VD_02/VD_04)
- `long_press_video_thumbnail.yaml` — delegates to `select_video_only.yaml`
- `select_mixed_photo_and_video.yaml` — CR_05B mixed selection
- `open_print_preview.yaml` — Print Preview navigation
- `reach_video_frames_print_preview.yaml` — single-video frames preview
- `tap_ai_tool_button.yaml` / `assert_ai_unavailable_for_video.yaml`
- `toggle_video_playback.yaml` / `scrub_video_playback_bar.yaml`
- `open_copies_and_tiles_tabs.yaml` / `assert_tiles_mode_video_ui.yaml`
- `swipe_print_preview_carousel.yaml`

- [ ] VD_01 | Video frame 01 | Verify video thumbnails indicate video content
- [ ] VD_02 | Video frame 02 | Verify mixed media selection
- [ ] VD_03 | Video frame 03 | Verify AI tool restrictions for video frames
- [ ] VD_04 | Video frame 04 | Verify full E2E flow (multi-select, AI, playback, edit)
- [ ] VD_05 | Video frame 05 | Verify video playback and scrubbing
- [ ] VD_06 | Video frame 06 | Verify frame editing and discard behavior
- [ ] VD_07 | Video frame 07 | Verify UI restrictions during playback in Tiles mode
