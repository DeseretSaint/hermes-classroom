# CP-005f review packet — the painted A1 fox adopted into the brand-asset segment

Card: `t_7803e3d1` · branch `wt/t_7803e3d1` · base `0c1729eb` (CP-053 merged, module `251a3948`)
· module now `0112000c418cfcb6815059020857eaf1b8a7299de3d863be1c3b0431cafa0c86`
· scope: source/registry only (UI director override, 2026-11-11 00:34)

## 1. What this card is, stated plainly

**The procedural placeholder is what shipped to the submission.** The owner signed the painted A1 fox
as canonical on 2026-11-10 (`docs/launch/FOX-SIGNOFF.md`), and the product kept shipping a flat SVG
derivative capped at 128 px, because nothing on the board owned the adoption and no test asserted
where the segment's fox bytes came from (`docs/launch/FOX-ASSET-AUDIT.md`).

This card is the adoption of art the owner had **already approved**. No character was generated,
redrawn, retouched, re-exported or re-approved; no pose was added; no palette changed. Every shipped
pixel comes from the committed `assets/art/fox/fox-<pose>-<size>.png` exports.

Home rendering at the reference's 208 px is **not** in this card: that is `t_831137dd` (Home quality
pass), which this card releases. No screen file was touched.

## 2. Changes

| File | Change |
| --- | --- |
| `scripts/build_cb_assets.py` | fox branch reads `assets/art/fox/fox-<pose>-<size>.png` (512/256/128/64), asserts RGBA and exact size, encodes WebP (quality 88, method 6, exact) plus AVIF ≥ 8 KB. Missing export is a hard failure — no silent SVG fallback. |
| `assets/fox/manifest.json` | 28 rows (7 poses × 4 sizes). `source` and `master` are the painted PNG; `master_sha256` is that PNG's hash. |
| `assets/fox/*.webp`, `*.avif` | Regenerated encodes of the painted exports; 256 and 512 added for all seven poses. |
| `desktop/cb-assets.generated.js` | Regenerated segment (deterministic). |
| `desktop/src/85-v3-primitives.js` | `cb3FoxPixels` / `cb3FoxSource` select 512 at ≥416, 256 at ≥208, 128 at ≥128, else 64; `cb3FoxSrcSet` emits a 1x/2x pair; `FoxPose` mounts the srcSet and records `data-cb3-fox-export`. |
| `desktop/src/99-tutor.js` | Exports `cb3FoxPixels`, `cb3FoxSrcSet`, `CB3_FOX_EXPORTS` for the render/probe suites (same seam CP-040 established). |
| `desktop/plugin.js` | Rebuilt with `scripts/build_plugin.py`; `--check` reproduces from `desktop/src`. |
| `tests/test_cp010_fox_assets.py` | New `BrandSegmentAdoption` (7 tests) and `FoxProofPage` (2 tests). |
| `tests/test_cb_assets.py` | Determinism fixture copies `assets/art/fox/` as a pipeline input (as it already did for `assets/art/objects/`); the inputs changed, the gate did not. |
| `scripts/gen-fox-proof.py`, `design/fox-adoption.html` | Generated 208 proof page, pinned to the module by a test. |
| `assets/README.md` | Art-status paragraph and budget figures corrected to what the tree now does and measures. |

`assets/masters/fox/` is **unchanged** (verify: `git status` does not list it). The placeholder set is
intact and the placeholder WebPs remain reproducible from it by reverting the builder. The override's
"do not touch `assets/fox/`" and its "regenerate `assets/fox/manifest.json`" cannot both be literal:
`assets/fox/` is where the segment ships, so its WebPs were necessarily replaced by encodes of the
signed art. Nothing in that directory was hand-edited; every byte came from the builder.

## 3. Registry evidence (measured)

- 28/28 rows name `authored:assets/art/fox/fox-<pose>-<size>.png` as `source` and `master`; each
  `master_sha256` is the painted PNG's actual sha256, each row `sha256`/`bytes` the shipped file's.
- Encode fidelity, measured on all 28 plates: alpha channel **byte-identical** to the painted PNG;
  mean visible RGB delta 0.78–2.45 / 255; worst single channel error 47 / 255. A different drawing
  cannot pass that; a lossy encode of this one does.
- `assets/masters/fox` appears **zero times** in `assets/fox/manifest.json`,
  `desktop/cb-assets.generated.js` and `desktop/plugin.js` (test asserts all three).
- The segment carries `cb.asset.fox.<pose>.<{64,128,256,512}>` for all 28 pose/size pairs, each with
  the manifest's path and sha256.

## 4. Primitive evidence (built module, not a copy)

Probed through `desktop/plugin.js` in node with the suite's SDK stub. Sizes 16–768:

| box | export | srcSet 1x | srcSet 2x |
| --- | --- | --- | --- |
| 64 / 96 / 112 | 64 | 64 | 128 |
| 128 / 160 / 207 | 128 | 128 | 256 |
| **208** / 220 / 256 | **256** | 256 | 512 |
| 415 | 256 | 256 | 512 |
| **416** / **512** / 768 | **512** | 512 | 512 |

`cb3FoxSource` returns exactly the manifest WebP of the selected export, and the two srcSet
candidates are exactly the 1x and 2x painted WebPs (hashes compared, not names). `FoxPose` at
`size={208}` renders a 208 px box with `data-cb3-fox-export="256"` and the 256/512 srcSet;
`size={512}` renders the 512 export.

`srcSet` is emitted with a data-URL pair. The HTML srcset parser collects a URL up to whitespace, so
the comma inside `data:image/webp;base64,…` is legal; the captured frame (below) shows all nine
images decoded with `naturalWidth > 0`, which is the empirical confirmation.

## 5. Pose-per-surface assignment, checked against the A1 sheet

The A1 sheet's assignments (`docs/launch/FOX-ASSET-AUDIT.md` §"What is canonical") against the call
sites that exist in the tree today:

| pose | assigned surface | actual call site | verdict |
| --- | --- | --- | --- |
| wave | Home trailhead | `30-home.js:1008` (v3 hub ledge) | matches |
| point | Discover feature | `96-workshop.js:1727` (Discover grid), `90-course.js:3135` (course home) | matches; `point` is also used on the course home — pre-existing, screen-file scope |
| clock | Home / New course | `30-home.js:635` (HomeScene ledge), `30-home.js:1082` (hub New course ledge) | matches |
| read | Classroom lesson | `70-learning.js:3722` default (`verdict == null`) → `:3969` | matches |
| cheer | Check correct | `70-learning.js:3722` (`verdict === 'pass'`) | matches |
| think | Wrong answer (kind) | `70-learning.js:3722` (any non-pass verdict) | matches |
| sleep | Empty / offline | **no call site** — the empty/offline surface does not render a fox yet | **gap, outside this card** |

The `sleep` plate ships and is selectable, but no surface mounts it. Building that surface is a screen
file, so it belongs to the UI program, not here; it is recorded rather than quietly declared done.

Sizes at those call sites are unchanged by this card (`128`/`112`, `96`/`88`, scene `220`). The
primitive now serves them the nearest painted export instead of an upscale of the 128. Moving Home's
ledges to 208 is `t_831137dd`.

## 6. The frame (one frame, one vision check — SPEND GUARD §17)

`docs/launch/fox-captures/fox-adoption.png` (1100×560) + `.stamp.json`, captured by
`scripts/cp-capture.mjs --fixture design/fox-adoption.html --expect-sha 0112000c…`:

- gates: `plugin_sha_match`, `route_present`, `no_render_error`, `fonts_loaded`, `images_decoded`
  (9/9), `no_host_overlay`, `no_unpainted_region`, `zoom_neutral`, `no_react_key_warning` — all true.
- frame sha256 `ac5a8f94d76890f96eaab83b0f6edc0801419d42290c021d168327af61c2ec76`, 890,323 B.
- contents: `wave` and `clock` at 208 (the acceptance's two plates), then all seven poses at 96 with
  their assigned surfaces.
- one vision check: painted illustration (not flat vector), alpha clean on the canvas ground, same
  character across the 208 plates and the 96 strip.

This is a plate sheet on the route ground, **not** a v3-parity frame: it was captured without
`--require-v3` and the page does not claim `data-cb-v3-ready`. Home parity remains CP-053's record and
`t_831137dd`'s work.

`design/fox-adoption.html` is generated by `scripts/gen-fox-proof.py` from `desktop/plugin.js`;
`tests/test_cp010_fox_assets.FoxProofPage` re-renders it and fails on any difference, so the frame
cannot outlive the module it was shot from.

## 7. Determinism

- `python3 scripts/build_cb_assets.py --check` → `VERDICT: within budget`, exit 0.
- `tests/test_cb_assets.Determinism` (two temp builds + committed bytes) → passes.
- `python3 scripts/build_plugin.py --check` → `matches desktop/src (0112000c…)`, exit 0.

## 8. Budgets — green, and tight

| gate | measured | ceiling |
| --- | --- | --- |
| generated segment | 1,384,979 B | 2,500,000 B |
| any single shipped asset | 110,076 B (font) / 33,268 B (largest fox WebP) | 300,000 B |
| `desktop/plugin.js` alone | 3,107,065 B | 4,500,000 B |
| plugin + segment | **4,492,044 B** | 4,500,000 B |

The last gate has **7,956 B** of headroom and it counts the segment twice: `plugin.js` embeds
`CB_ASSETS`, and the gate adds the segment file on top. Any further asset growth — including
`t_831137dd`'s work — trips it. Raising the ceiling (or deleting the double count, which is the
honest fix now that the segment really is inlined) is a budget decision for the supervisor; this card
did not move a number to make its own change fit.

## 9. Known red, by design — the evidence pins, which the supervisor owns

Three tests fail on this branch and only these three, all because the module sha changed:

| test | says |
| --- | --- |
| `test_desktop_home_scene_parity.test_the_committed_proof_is_a_fresh_render_of_the_shipped_module` | `design/home-scene.html` no longer matches a render of `plugin.js` |
| `test_desktop_home_scene_parity.test_the_recorded_measurement_names_the_module_it_was_taken_on` | `measure.json` names `251a3948`, module is `0112000c` |
| `test_m4_visual_audit.test_evidence_is_not_stale_against_the_shipped_module` | M4 evidence captured on `251a3948` |

Per the supervisor's unblock ("I re-pin once more after the last UI commit, so there is exactly one
extra pin, not a matrix"; "do not regenerate `audit/visual/m4-visual/audit.json` yourself"), this card
left CP-053's proof page, its captured PNG, `measure.json` and the M4 audit **untouched**. Editing
only `design/home-scene.html` would have produced a page whose PNG and measured parity no longer
depict it — a half-updated evidence set that has to be redone anyway. The re-pin should regenerate
`design/home-scene.html`, re-capture `home-scene-1344.png`, re-measure `measure.json` and re-pin the
M4 audit as one step on the final module.

The frame's *content* also changes with this card: HomeScene's fox box is 220, so it now mounts the
painted `clock` at the 256 export rather than the placeholder. That improvement is real and it is
also why the old frame cannot simply be reused.

## 10. Tests run (named modules, no second `unittest discover`)

| command | result |
| --- | --- |
| `python3 -m unittest tests.test_cp010_fox_assets tests.test_cb_assets` | Ran 69, OK (skipped=1) |
| `python3 -m unittest tests.test_cp010_fox_assets` | Ran 34, OK |
| `... test_cp_022_home_v3 test_cp_022_geometry test_desktop_gm002_home test_desktop_h86_wayfinding test_cp_021_workshop_v3 test_cp_023_classroom test_cp_024_course_home_v3 test_cp_025a_homework_game_v3 test_cp_025b_v3_studio` | Ran 109, OK |
| `... test_desktop_tokens test_desktop_tokens_v3 test_desktop_type_scale test_desktop_h152_motion test_desktop_gate_scope test_desktop_field_desk test_desktop_a11y_structure test_desktop_contracts test_desktop_control_paths test_desktop_surface` | Ran 206, OK (skipped=2) |
| `... test_v3_primitives test_cp013_scene_objects test_cp_spec test_desktop_home_scene_geometry test_desktop_font_wiring test_h197_covers test_plugin_build test_v3_scope` | Ran 133, OK |
| `... test_cp016_world_art_bible test_cp_capture_stamp test_cp_capture_route` | Ran 49, OK |
| `... test_desktop_home_scene_parity test_m4_visual_audit test_v3_visual_audit` | Ran 28, **3 failures** (§9), 1 skip |

## 11. What a reviewer should check

1. `git status` — `assets/masters/fox/` absent from the diff; the placeholder masters are untouched.
2. `python3 scripts/build_cb_assets.py --check && python3 scripts/build_plugin.py --check`.
3. `python3 -m unittest tests.test_cp010_fox_assets tests.test_cb_assets`.
4. Open the frame and confirm the 208 plates are the painted character, not a 128 upscale.
5. Confirm the §9 red set is exactly three pins and that no other suite is red on this branch.
