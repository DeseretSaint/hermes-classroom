# Fox asset audit — canonical art exists; the live UI is wired to the placeholder

Corrected 2026-11-10 after the owner's sign-off. The earlier version of this memo compared the live
128 px WebP to the painted 512 and concluded the art was missing. That was wrong: the painted A1 set
is in the repo and on master. The product simply never adopted it.

Approved references: `docs/concept-parity/art/fox-signoff-2up.png` (M1 model sheet + A1 seven-pose
sheet) and `docs/concept-parity/art/home-reference.png`. Owner's decision: the painted A1 fox is
canonical and will appear throughout the product.

## What is canonical

- `assets/art/fox/fox-model-sheet-512.png` — M1: front, three-quarter, side, back.
- `assets/art/fox/fox-<pose>.png` — 660×660 RGBA masters for the seven poses.
- `assets/art/fox/fox-<pose>-{512,256,128,64}.png` — alpha-preserving exports.
- Poses and their assigned surfaces, per the A1 sheet: `wave` Home trailhead, `point` Discover
  feature, `clock` Home/New course, `read` Classroom lesson, `cheer` check correct, `think` wrong
  answer (kind), `sleep` empty/offline.
- CP-010 is merged: `git merge-base --is-ancestor 68da9251 master` returns 0. The source hashes are
  recorded in `docs/concept-parity/ART-PROVENANCE.md`.

## What the live product uses

The brand-asset segment does not read the painted set.

- `scripts/build_cb_assets.py:255` defines `_fox_svg`; the fox branch at `:655-705` reads
  `assets/masters/fox/fox-<pose>.svg` and encodes `assets/fox/fox-<pose>-{64,128}.webp`.
- `assets/fox/manifest.json` records every fox `source` as `authored:assets/masters/fox/...svg`.
- `desktop/cb-assets.generated.js:58,70` ships `assets/fox/fox-clock-128.webp` and `...-64.webp`;
  the other six poses are the same.
- `desktop/src/85-v3-primitives.js:73-80` caps the fox at 128: `const want = Number(size) >= 128 ?
  128 : 64`. `FoxPose` at `:725-750` therefore never requests 256 or 512.
- Home asks for 128 at wide and 112 below 900: `desktop/src/30-home.js:870` (`wave`) and `:944`
  (`clock`). The reference renders the painted clock pose at 208.

So the live mascot is a flat procedural SVG derivative, capped at 128 and displayed at 112–128,
while the approved reference is a painted 660 px master displayed at 208. That is the entire
quality gap.

Evidence: `docs/concept-parity/art/fox-canonical-vs-live-2up.png` — left, the canonical 512 painted
export; right, the live 128 WebP upscaled. Same pose, different animal.

## Why it slipped

`assets/README.md:62-64` says the fox WebPs are still drawn from the procedural SVG masters and that
wiring the painted fox into the segment is CP-020a's card. CP-020a is marked done on the board, but
the fox branch was never switched. The done stamp measured scope, fonts and materials, not the fox
source. No test asserts that the segment's fox comes from `assets/art/fox/`.

## Consequence

There is no art production left for the fox. The owner has approved the character and all seven
poses. The remaining work is asset adoption: point the segment builder at the painted masters,
regenerate the registry, lift `FoxPose` past 128, render Home at 208, and lock it with a source/hash
test. No new generation, no second sign-off.

## Home pose note

The Home mockup shows a sitting fox beside a separate mantel clock. The A1 `clock` pose is standing
with a pocket watch, and the sheet labels it for Home/New course. Use the approved `clock` pose at
208 on the ledge (and `wave` on the empty shelf); do not invent a sitting variant for the UI. If the
owner wants the mockup's exact sitting composition later, that is a scene plate, not a UI asset and
not a reason to block the screen.

## Adoption card — exact work

1. **Source.** In `scripts/build_cb_assets.py`, read `assets/art/fox/fox-<pose>.png` (660×660 RGBA)
   as the fox master instead of `assets/masters/fox/*.svg`. Preserve alpha; encode WebP/AVIF at 512,
   256, 128 and 64. The SVG path stays only as a fallback for a pose with no painted master, and
   none of the seven has one.
2. **Registry.** Regenerate `assets/fox/manifest.json`, `desktop/cb-assets.generated.js` and
   `desktop/plugin.js`. Every fox entry's `source` is `assets/art/fox/fox-<pose>.png`; no fox entry
   may name `assets/masters/fox`.
3. **Primitive.** `cb3FoxSource` serves the smallest export at least 2x the box (208 → 512, 128 →
   256, 64 → 128), so the file the capture measures carries the visual-quality gate's 2x; emit a
   `srcSet` for 1x/2x only while a larger export exists. `FoxPose` accepts 208 and 512.
4. **Home.** Ledge `clock` at 208, empty shelf `wave` at 208 (or the design's accepted size, never
   112/128 for a 208 reference). Natural size must be ≥ rendered size.
5. **Tests.** Extend `tests/test_cp010_fox_assets.py` with a segment test: every fox asset's source
   is the painted PNG, the encoded bytes/hash match the derivative, `FoxPose` `currentSrc` resolves
   to a painted derivative, and no `assets/masters/fox` path is reachable for the seven poses.
6. **Visual gate.** Home crop at 2× against the A1 clock pose: ears, muzzle, eyes, chest, legs, tail,
   palette, line weight. Asset hash and natural size recorded. A "fox present" check is not a pass.

## Acceptance

- The live fox at Home is the painted A1 character, 208 px, natural size ≥ rendered.
- All seven poses come from `assets/art/fox/`; the procedural SVG fox is unreachable.
- Home, Discover, Classroom, correct/wrong, and empty states each use their assigned pose, with no
  repeated pose in one viewport.
- No new art generation and no owner re-approval: the A1 sheet is signed.
