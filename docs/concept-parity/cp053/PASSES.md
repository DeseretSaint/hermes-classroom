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
| 5 | scene tones hand-tuned to the frame: card stock #efe3cd, shelf lip #b09a84, ledge face #ad8663, tag #f4e6cd | 0.8489 | 0.8401 | card 1 cover 162 vs 108 (0.9% of the frame); card 3 cover 185 vs 119; card 2/3 boundary 184 vs 138 |
| 6 | sweep of every scene colour onto the token contract (no raw hex, no gradient): canvas, card-stock, forest, ink, terracotta, rule, wood, wood-edge, elev-1; the hand-tuned tones in pass 5 are retired because they left the scene outside the token table | 0.8437 | 0.8345 | card 1 cover 162 vs 108; card 3 cover 185 vs 119; card 2/3 boundary 184 vs 138 |
| 7 | **master reverted `471e7c96` for gate reasons: all paint, spacing, rotation and typography moved out of inline styles into the v3 stylesheet behind `data-cb-home-scene-*` hooks; type now comes from the scale (display 64 px at 1344, heading 32.64 px)** | **0.8303** | 0.8213 | headline 64 px vs the reference's 72 px — the display step caps at 4 rem (hero band 0.805); card 1 cover 162 vs 108; card 3 cover 185 vs 119 |

Stopped at pass 7 with `sim_grey = 0.8303`, below the 0.90 stop line.

## Why it stops short, and what the last two passes cost

Three caps apply, each a product rule rather than a rendering problem.

1. **Colour.** The scene may only paint with `var(--cb3-*)`. Pass 5's hand-tuned tones scored 0.8489
   and were retired: 0.005 of similarity is the price of the contract the rest of the product obeys.
2. **Shape.** Inline paint, shadows and font sizes are what made `471e7c96` unshippable (six gates,
   then the whole suite). Pass 7 moves all of it behind hooks in the v3 stylesheet, so the shipped
   module carries hooks and dynamic progress widths and nothing else.
3. **Type.** The display step is `clamp(2.5rem, 1.5rem + 3cqi, 4rem)`, so the headline tops out at
   64 px where the reference draws 72 px. That 8 px costs about 0.014 of the frame
   (hero band 0.8462 -> 0.805). Recovering it needs a seventh type step, which the contract forbids.

What is left is illustration: the reference's four covers are painted scenes (grey 72-147 inside each
176x106 box) and the product may only show a real course/pack cover artifact. Each card box carries a
60-100 grey RMSE against its painted texture, which alone bounds the frame near 0.92 even with
perfect geometry and perfect type.

## Frame

- `home-sheet-1344.png` — render | binding reference, both at 1344x768.
- `home-diff-1344.png` — absolute difference, ×1.8 gain.
- `home-scene-1344-token-layer.png` — the pass-7 render at native size.
