# H-189 — Living home: real covers, quiet notes, one authored movement

Evidence for the P0 Home defect (owner feedback, 2026-11-08): the shelf's generated contour read as
code art, the Field Notes strip made Home an audit feed, and the page was static. The shipped module
under test is `desktop/plugin.js`, sha256
`3681c505ce518c1ca5c310aa9cd53f4d98afe5e344dc7c3e9abeb956da09f27e`.

This is product-line evidence for one card, not release evidence. Nothing was pushed, installed into
the root profile, or published.

## What changed

1. **Classroom covers.** `CourseContour` is gone from every shelf card and from the switch header.
   A classroom now paints one of exactly two covers:
   - **artifact** — only when a `library.list` row declares `cover = { artifact_id, caption,
     text_equivalent, provenance }` and the one media route returns an image. The `<img>` carries the
     authored caption as its `alt`, and the authored text equivalent is visible in a `figcaption`.
   - **typographic** — the classroom's own name, the subject the backend recorded
     (`level_label`/`locale`), and its monogram, on paper. No ridge, no equalizer, no invented image.
   A missing cover cannot become `<img alt="">`: `cbCoverMedia` returns null without a caption, and
   type is the fallback.
2. **Field Notes on Home.** `FieldNotesLine` replaces `FieldNotesStrip` in the Home column: one
   tertiary control reading `Field notes · 11 saved` (or `nothing saved yet` / `reading` /
   `could not be read`), whose whole line opens the Notebook. No row list, no tag badges.
3. **Technical labels.** The learner's note row is the note, the lesson title, the course and one
   `Open in textbook`. Kind enum, tag enums, objective id, source ids, raw entry id and the
   saved-at timestamp all moved behind the existing **Technical detail** disclosure.
4. **Movement, one authored layer.**
   - The trailhead route/plate settles once on mount on the 280 ms `route` beat (inside the card's
     240–320 ms window); it re-arms on a course switch, so the new card has one visible consequence.
   - The current stop's ring runs exactly two opacity cycles 0.55 → 0.9 (four finite `setTimeout`
     legs, then cleared). No interval, no loop.
   - The learner's own pet uses the existing `stateRows`/`framesByState` idle frames at 420 ms,
     pauses on `visibilitychange`, and paints frame 0 (no timer) under reduced motion.
   - Reduced motion returns the resting frame immediately; every effect has a static equivalent.
5. **Hierarchy.** The duplicate `DeskFacts` strip under the plate and the twelve-bar `EvidenceTally`
   above the route are gone; the recorded count is now one caption line, and the route is the one
   object. The shelf at 460 px keeps normal document flow (no horizontal overflow, no row overlap at
   200 % text).

## Before / after

`before/` is the H-176 baseline (`discovery` checkout `473471b`) rendered through the same pipeline at
the same widths, copied from `audit/visual/h176-trailhead/before/`. Before: two contour drawings above
the shelf and the dense Field Notes strip. After: typographic covers and one Field Notes line.

| Width / mode | Before | After |
|---|---|---|
| 1049 light | `before/01-real-light-1049.png` | `01-living-light-1049.png` |
| 1049 dark | `before/02-real-dark-1049.png` | `02-living-dark-1049.png` |
| 900 light | `before/03-real-light-900.png` | `03-living-light-900.png` |
| 900 dark | `before/04-real-dark-900.png` | `04-living-dark-900.png` |
| 460 light | `before/05-real-light-460.png` | `05-living-light-460.png` |
| 460 dark | `before/06-real-dark-460.png` | `06-living-dark-460.png` |
| 200 % text @ 460 | `before/07-real-200pct-460.png` | `07-living-200pct-460.png` |
| reduced motion @ 460 | same as static | `08-living-reduced-motion-460.png` |

## Live-module frames (client mount, shipped plugin bundled with the Desktop's React)

| Frame | What it proves |
|---|---|
| `10-live-pet-1049.png` | the learner's real pet sheet (`boba`, 192×208, idle row) paints on canvas; `data-cb-companion-motion="idle"`, 2237 lit pixels |
| `11-live-no-pet-1049.png` | no pet configured → no companion element at all |
| `12-live-real-artifact-cover-1049.png` | one classroom paints the demo pack's `relationship-map.png`; `alt` is the authored caption and the text equivalent is visible; the other classroom falls back to type |
| `13-live-typographic-cover-1049.png` | no declared cover → type only |
| `14-motion-arrival-1049.png` | `data-cb-trailhead-motion="arriving"` at 29 ms (one frame; the capture browser slows only that frame so it is observable) |
| `15-motion-beacon-1049.png` | current-stop ring at the high end of its cycle |
| `16-motion-rest-1049.png` | ring back at rest, no further leg |
| `17-reduced-motion-460.png` | reduced motion → `trailhead-motion="static"`, `pulse="rest"`, 0 animations |
| `18-live-pet-460.png` | 460 px with the pet; no horizontal overflow |
| `19-reduced-motion-pet-460.png` | reduced motion with a real pet → `companion-motion="static"`, frame 0 painted, 0 animations |
| `10-notebook-learner-rows-light-1049.png` | Notebook row's learner-visible text has no `cb-loop-note-*`, `loop_segment`, `loop-proof-*`, objective id or saved-from metadata; those stay in the closed Technical detail |

Measured in `evidence.json` (static) and `motion.json` (client mount):

- `shelf_contours: 0` on every frame; `slot_covers` are `typographic` (or one `artifact` + one
  `typographic` when the pack artifact is declared); `empty_alt_images: 0`.
- `field_notes_line: "Field notes · 11 saved"`, `field_note_rows: 0` on every Home frame.
- `horizontal_overflow: false` at 1049/900/460 and at 200 % text at 460; `path_row_overlaps: 0`.
- Motion samples: `arriving @29 ms` → `settled @179 ms`; ring `0.55 @179` → `0.9 @318` →
  `0.55 @592` → `0.9 @875` → `0.55 @1154`, then no further change through 2600 ms.
- Reduced motion: `trailhead_motion: static`, `pulse: rest`, `animations: 0`, pet `static` frame 0.

## How these were produced

```
# static composition (writes frames.json + payloads.json; H189_PACK_DIR is a real installed pack)
H189_PACK_DIR="$HOME/.hermes/coursebook-test-h176a/home/plugin-data/coursebook/pack-library/packs/japanese-affection-context-l0/1.0.0" \
  python3 scripts/h189-frames.py
node scripts/m2fd-shot.mjs audit/visual/h189-living-home

# client mount: real pet sheet, real packaged artifact, motion capture, reduced motion
H189_PET_JSON=/path/to/real-pet-info.json node scripts/h189-live.mjs
```

`h189-live.mjs` bundles the shipped `desktop/plugin.js` with the Desktop's own React through esbuild
and mounts `FieldDeskHome` in headless Chromium over a local HTTP origin. It never edits the module.
The pet payload is a real `pet.info` answer for the rig profile (`boba`), and the artifact bytes,
caption and text equivalent come from the installed pack manifest.

## Verification

- `node --check desktop/plugin.js` — OK
- `python3 -m unittest tests.test_desktop_home_hub tests.test_desktop_field_desk tests.test_desktop_h147_home_settings tests.test_desktop_h152_motion tests.test_desktop_h148_path_truth tests.test_desktop_tokens tests.test_desktop_type_scale` — 140 tests OK
- `python3 -m unittest tests.test_desktop_h189_living_home` — 12 tests OK
- `python3 -m unittest tests.test_desktop_field_notes tests.test_desktop_h94_single_primary` — 23 tests OK

## Known limits

- These frames are module renders in Chromium, not the installed Desktop. The H-176 test rig
  (`~/.hermes/coursebook-test-h176a`, CDP 9376) is still running the pre-change plugin and its local
  gateway is down; reloading it would need a gateway restart, which is operator-gated.
- M4 was not re-run or re-pinned. `scripts/h146-capture.mjs` now records `slotCovers`, the surviving
  trailhead `contours`, `shelfContours`, `fieldNotesLine` and `fieldNoteRows`, so M4 reads the new host
  pet/cover as intended rather than as the old seal/avatar regression.
- `CourseContour` survives only as the trailhead's own identity band and the first-run ghost; the
  card's scope was the classroom cards.
