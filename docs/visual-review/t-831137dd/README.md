# t_831137dd — Home kit round 2 evidence

Module under test: `desktop/plugin.js` sha256 `71d940ce0398220fe1d25d1ec39b1e4bdfbc2a1c257eb7eb42292c628ac4d4b8`
(`python3 scripts/build_plugin.py --check` matches `desktop/src`).

## What this round changed from `3cdfa1d0`

1. Fox and clock seated ON plank two (top edge y=684): clock `top` 588 -> 568 (painted base 683.7),
   fox `top` 526 -> 481 (painted feet 684.1), both inside the card's +/-2 px.
2. Fox moved right, `left` 1088 -> 1110: opaque fox art now clears the opaque clock art by 11.4 px
   (clock right 1142.5, fox left 1153.9), where round 1 overlapped by 10.6 px.
3. Hero contrast: the question paints `var(--cb3-ink)` (was `var(--cb3-forest)`, which measured
   4.45:1 on the plate) and the panel scrim is `--cb3-canvas` at opacity 0.60 (was 0.55).
4. `data-cb-home-cover` on the narrow hub card no longer says `type` for a painted kit cover.
5. New pins: seating + separation arithmetic, hero ink + scrim floor, and per-course cover mapping
   (technical / japanese / parent / lesson-room) instead of "any approved row".

## Files

- `home-scene-1344-proof.png` — `design/home-scene.html` (generated from the built module by
  `scripts/gen-home-proof.py`) at 1344x768, chromium headless. This is the composition frame.
- `home-1344-light.png` / `.json` — the installed plugin's `[data-cb-route]` box at exactly
  1344x768, light scope, with per-element read-back (module sha, scope, fonts, rects, covers).
- `home-900-light.png` / `.json` — the same camera at 900x768.

## Not passing, stated as such

The installed 1344/900 frames show the plugin's **empty-library Home**, not the shelf: this rig
window issued **no coursebook RPC at all** (zero `performance` entries for the plugin), so it never
saw the three enrolled courses that are in the rig database
(`~/.hermes/coursebook-test-t831137dd/home/plugin-data/coursebook/data.db`, 3 enrollments). The
frames are the right size and scope, but they are not composition evidence. The previous installed
frames (module `3cdfa1d0`) were taken before the plugin was reinstalled into this rig home; after
reinstall the host renders the plugin but does not bind its runtime context. That harness defect is
routed with `t_92878d65`; this card does not fake around it.
