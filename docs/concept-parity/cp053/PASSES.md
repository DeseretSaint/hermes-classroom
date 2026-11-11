# CP-053 — Home scene parity passes

Binding reference: `docs/concept-parity/refs/home-concept-owner.png` (1344x768).
Surface measured: `design/home-scene.html` rendered at exactly 1344x768 in a private headless
Chromium (`Emulation.setDeviceMetricsOverride` 1344x768, DSF 1). The page carries the same scene
markup and the same numbers as the shipped `HomeScene` in `desktop/src/30-home.js`; a test
(`tests/test_desktop_home_scene_geometry.py`) fails if the two disagree.

Metric: `sim_grey = 1 - RMSE(grey)/255` over the full frame, both images at native 1344x768
(`measure.py`, no resize, no crop). This is the "grey similarity" the card names.

| pass | change | sim_grey | sim_rgb | largest remaining deltas |
|---|---|---|---|---|
| 0 (baseline, before this card's work) | shipped proof: 278 px cards, shelf at 640, pale Atlas Lamp covers, 17.5 px subline | 0.7586 | — | card block 80 px too low and 100 px too wide; catalogue covers ~60 grey lighter than the reference's; headline 20 px narrow |
| 1 | geometry rewritten from pixel measurements: hero 128/72/32, cards 176x175 at (273, 384), shelf 219..1134 at 559, ledge 130..1280 at 684, tag/clock/fox re-placed, real pack covers | 0.8200 | 0.8122 | card 3 cover 170 vs 72 grey (bright plate where the reference is a night sky); headline ink 25 grey lighter; card 1 cover right third 232 vs 108 |
| 2 | headline 68 px, subline 28/500, card stock darkened to #f4e7d2, CTA padding 22, cover order | 0.8222 | 0.8159 | card 3 (170 vs 72); card 4 plate nearly black at its right edge (24 vs 151); headline still light |
| 3 | four distinct real plates chosen by slot (japanese 4x5, technical 3x2, parent 4x5, japanese 3x2) | 0.8310 | 0.8225 | card 2 plate 24 vs 174; card 3 right edge 232 vs 106; headline 12 grey light |
| 4 | headline 72/-1.2, subline 32, brand 34, fox 208 px at (1088, 526), card 2 → course-map plate | 0.8449 | 0.8360 | card 1 cover 162 vs 108; card 3/4 boundary 185 vs 119; card 2/3 boundary 184 vs 138 |
| 5 | scene tones: card stock #efe3cd, shelf lip #b09a84, ledge face #ad8663, tag #f4e6cd | **0.8489** | 0.8401 | card 1 cover 162 vs 108 (0.9% of the frame); card 3 cover 185 vs 119; card 2/3 boundary 184 vs 138 |

Stopped after five passes with `sim_grey = 0.8489`, below the 0.90 stop line.

## Why it stops short

The residue is not layout any more — every measured edge (headline 411..926, buttons 498..837,
cards 273..1046, shelf 219..1134, ledge 130..1285, tag/clock/fox bases) is within a few pixels.
It is illustration: the reference's four covers are painted scenes (grey 72–147, painted
gradients inside each card) and the shipped product may only show real course/pack cover
artifacts, never a generated plate. Each of the four cover boxes is 176x106 and carries a
~60–100 grey RMSE at its own painted texture, which alone bounds the frame near 0.92 even with
perfect geometry, and the remaining wall lighting (a painted vignette with a soft shadow under
each card) supplies the rest.

## Frame

- `home-sheet-1344.png` — render | binding reference, both at 1344x768.
- `home-diff-1344.png` — absolute difference, ×2.2 gain.
- `home-scene-1344-pass5.png` — the pass-5 render at native size.
