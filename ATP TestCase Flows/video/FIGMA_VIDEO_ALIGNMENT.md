# Video module — Figma CR_05 alignment checklist

Mapped from Figma screens CR_05A–CR_05E and annotation notes (Dec 2025–May 2026).

## CR_05A — Gallery with Videos (VD_01)

- [x] Quick Print gallery opens (`Recent`, `Create` nav)
- [x] Video cell enters Select Mode (`select_video_only.yaml` — View wrapper + nested ImageView play overlay)
- [ ] **Visual play icon** bottom-right — not assertable without image/OCR (documented limitation)
- [x] Cancel returns to gallery browse mode

## CR_05B — Select Mode with Videos (VD_02)

- [x] Cancel + Print Preview footer in Select Mode
- [x] Numbered selection badges (`1`, `2`, `3`)
- [x] Mixed counter text (`Photo.*Video`) — optional regex (label varies by build)
- [x] Any combination photos + videos selectable

## CR_05C — Print Preview Photos & Videos (VD_03, VD_04)

- [x] Navigate to Print Preview from selection
- [x] Carousel swipe for mixed items (`swipe_print_preview_carousel.yaml`)
- [x] AI tool tap + tooltip text variants — optional (icon-only AI on device)
- [ ] **Exact tooltip 5s duration** — not timed in Maestro (manual verify)
- [x] `Photo & Video x of x` counter — optional assert

## CR_05D — Video Frames Print Preview (VD_05, VD_06)

- [x] Single-video Print Preview (`reach_video_frames_print_preview.yaml`)
- [x] Play/pause toggle on main frame — optional text assert
- [x] Playback bar scrubbing (`scrub_video_playback_bar.yaml`)
- [x] Copies / Tiles tabs (`open_copies_and_tiles_tabs.yaml`)
- [x] Edit frame entry + return (`VD_06`)
- [x] Frame change after edit (scrub discards — behavior asserted by staying on preview)
- [ ] **Resize/rotate disabled while playing** — not automatable without gesture probes

## CR_05E — Video Frames Tile Print (VD_07)

- [x] Tiles tab opens
- [x] Play hidden in Tiles — optional `assertNotVisible`
- [x] Scrub bar works in Tiles mode
- [ ] **Copy count locked while playing** — partial (tabs exercised; strict lock not verified)

## Figma annotations — coverage notes

| Instruction | Automation |
|-------------|------------|
| First frame selected by default | Implicit in preview open |
| Main frame matches thumbnail on entry | Not visually verified |
| Scrub on playback bar | VD_05, VD_06, VD_07 |
| Edit only paused frame | VD_06 edit tap |
| Edits discarded on frame change | VD_06 scrub after edit |
| Playing blocks Tiles/Copies/copy changes | VD_07 partial |
| Tiles/Copies tap pauses video | VD_07 toggle + tab switch |
| Play hidden in Tiles | VD_07 optional assert |
| AI disabled on video (May 14 2026) | VD_03, VD_04 |

## Open questions / assumptions

1. **Video folder** — Figma shows folder chip; device v3.0.202 uses `Recent` with mixed media (no separate Video album in Select Gallery).
2. **Video locator** — Video cells sit **right of the first photo thumbnail** below `Recent` (relational `rightOf`, not x/y coordinates). Photos are plain `ImageView`; videos use a `View` wrapper with play-icon overlay. Duration mm:ss is visual-only (not in accessibility tree).
3. **AI button** — Icon-only (no `AI` text); coordinate tap `12%,88%` used as fallback.
4. **Tooltip exact copy** — Figma: `AI Edit is not available for Video.` — asserted optional pending stable locator.

## Related flows (unchanged — reuse candidates)

- `quick-print/QP_04` — photo select mode (video-aware regex kept)
- `quick-print/QPX_08`, `QPX_09` — still Excel stubs; can wire to `video/subflows` later
- `custom-sdk/CS_13`, `CS_14` — video preview stubs
