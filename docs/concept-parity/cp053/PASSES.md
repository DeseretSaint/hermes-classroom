# CP-053 — Home scene parity passes

## G2 re-pin (2026-11-13, t_8db56021)

Binding reference changed by owner ruling G1 (2 — Home only): the Home scene is now pinned to the
adopted textless ground `docs/concept-parity/refs/home-plate-1344-textless.png` (sha256
`806080bb...`), and `docs/concept-parity/refs/home.png` (R-HOME-OLD) is history. `measure.json` was
re-derived in full from the new plate and the regenerated proof: nothing was carried forward, and
the band names now follow the plate's own composition (sky, hero sign, wall, board quads, bench,
ground). Current row: module `f750d8d4...`, `sim_grey` **0.8901** over the full 1344x768 frame,
re-measured by `python3 scripts/cp053-remeasure.py` after LEG-01 moved the module.

The sections below describe the pre-plate measurement history and are kept as history only; their
numbers were taken against R-HOME-OLD and are not comparable with the G2 row.

Binding reference for the history below: `docs/concept-parity/refs/home.png` (R-HOME in
`docs/concept-parity/refs/REFS.md`, 1344x768, sha256
`fd75bed31cd773ab50a5b5ad62daa46566d50b1b7f3ed1582a52915a14f3ffe3`). This is the reference the
owner approved for Home; R-BOARD's Home panel is explicitly not ratified.

## What is measured (this is what changed in round 3)

The measured page is **generated from the shipped module**: `scripts/gen-home-proof.py` mounts the
real `CoursebookHome` at route width 1344 inside the real `CbV3Scope`, then writes
`design/home-scene.html` with the `plugin.js` sha in its header comment.
`tests/test_desktop_home_scene_parity.py` re-runs that generator and fails when the committed page
differs from a fresh render, so the proof cannot drift from the surface. (Rounds 1 and 2 found a
hand-authored proof painting strings the product never ships; that page is gone.)

What it is **not**: a Desktop capture. There is no host and no backend in this render, so the frame
is the scene canvas alone (the app header and window chrome are outside `HomeScene`) and a card with
no host media read paints the product's own typographic cover fallback. The private-Desktop frame
was removed from this card's acceptance by the supervisor (`docs/CP-051-PRIVATE-RIG.md` records the
topologies in which this plugin cannot paint there); Home-cell camera evidence is GM-016c's job on
the frozen module sha.

Metric: `sim_grey = 1 - RMSE(grey)/255` over the full frame, both images at native 1344x768
(`measure.py`, no resize, no crop). `measure.json` records the numbers with the module sha and the
reference sha.

## Passes on the shipped component

Earlier passes (below, table 2) were measured on the old, non-shipping hand-authored proof. They are
kept for history only; they are **not** parity evidence and their numbers are not comparable.

| pass | change | sim_grey | largest remaining deltas |
|---|---|---|---|
| A | first render of the generated proof: reference copy, reference card order, token paint only | 0.8064 | typographic card covers vs painted art; header band empty; placeholder fox |
| B | scene canvas transparent so the scope's grain/vignette layers show through | 0.7812 | **reverted**: the vignette tile composites as a dark centre at this canvas size (centre pixel 178 vs the reference's 245) — the room read grey-brown, not parchment |
| C | canvas flat again; shelf 545, ledge 681, hero sub/CTA gaps corrected | 0.7974 | cards 14 px too high; shelf band mismatch |
| D | cards 370, ledge 34 px | 0.8018 | cards now too high by 14 px (measured: the reference card top is 384) |
| E | **cards 384, shelf 545 behind the card bases, ledge 681, subline gap 24, CTA gap 26** | **0.8089** | cards band 0.7626 (typographic covers vs painted art); header band 0.8835 (no app header in this canvas); placeholder fox |

Stopped at E — the last frame measured, and the one `measure.json` pins.

## Why it stops short of 0.90 — three caps, none of them a layout bug

1. **Cover illustration.** The reference's four covers are painted scenes (grey 72-147 inside each
   176x106 box). The product may only show a real course cover artifact; with no host media read the
   card paints its own `--cb3-terracotta-quiet` typographic plate. The cards band is the largest
   single loss and it is art, not geometry.
2. **Type ceiling.** Display is `clamp(2.5rem, 1.5rem + 3cqi, 4rem)` -> 64 px at 1344, where the
   reference draws ~72 px. Recovering it needs a seventh type step, which
   `contracts/cb.tokens.v3.json` forbids.
3. **Fox and header.** `FoxPose pose="clock"` currently resolves to the procedural placeholder under
   `assets/fox/`; the painted A1 set is canonical and its adoption is `docs/launch/FOX-ASSET-AUDIT.md`
   step 1, a different card. The reference's header band has no counterpart inside this canvas.

## Frame files

- `home-sheet-1344.png` — shipped render | binding reference, side by side (2688x796).
- `home-scene-1344.png` — the pass-E render at native size.
- `home-1344-diff.png` — absolute difference, x2.2 gain.
- `measure.json` — numbers + module sha + reference sha.

Reproduce:

```
python3 scripts/build_plugin.py
python3 scripts/gen-home-proof.py
chromium --headless=new --no-sandbox --disable-gpu --hide-scrollbars \
  --window-size=1344,768 --force-device-scale-factor=1 --virtual-time-budget=15000 \
  --screenshot=docs/concept-parity/cp053/home-scene-1344.png "file://$PWD/design/home-scene.html"
python3 docs/concept-parity/cp053/measure.py docs/concept-parity/cp053/home-scene-1344.png \
  docs/concept-parity/refs/home.png docs/concept-parity/cp053 home-1344
python3 docs/concept-parity/cp053/sheet.py docs/concept-parity/cp053/home-scene-1344.png \
  docs/concept-parity/refs/home.png docs/concept-parity/cp053/home-sheet-1344.png
```

## Table 2 — historical passes on the retired hand-authored proof (not evidence)

| pass | change | sim_grey | largest remaining deltas |
|---|---|---|---|
| 0 (baseline, before this card's work) | shipped proof: 278 px cards, shelf at 640, pale Atlas Lamp covers, 17.5 px subline | 0.7586 | card block 80 px too low and 100 px too wide; catalogue covers ~60 grey lighter than the reference's; headline 20 px narrow |
| 1 | geometry rewritten from pixel measurements: hero 128/72/32, cards 176x175 at (273, 384), shelf 219..1134 at 559, ledge 130..1280 at 684, tag/clock/fox re-placed, real pack covers | 0.8200 | card 3 cover 170 vs 72 grey (bright plate where the reference is a night sky); headline ink 25 grey lighter; card 1 cover right third 232 vs 108 |
| 2 | headline 68 px, subline 28/500, card stock darkened to #f4e7d2, CTA padding 22, cover order | 0.8222 | card 3 (170 vs 72); card 4 plate nearly black at its right edge (24 vs 151); headline still light |
| 3 | four distinct real plates chosen by slot (japanese 4x5, technical 3x2, parent 4x5, japanese 3x2) | 0.8310 | card 2 plate 24 vs 174; card 3 right edge 232 vs 106; headline 12 grey light |
| 4 | headline 72/-1.2, subline 32, brand 34, fox 208 px at (1088, 526), card 2 -> course-map plate | 0.8449 | card 1 cover 162 vs 108; card 3/4 boundary 185 vs 119; card 2/3 boundary 184 vs 138 |
| 5 | scene tones hand-tuned to the frame: card stock #efe3cd, shelf lip #b09a84, ledge face #ad8663, tag #f4e6cd | 0.8489 | card 1 cover 162 vs 108 (0.9% of the frame); card 3 cover 185 vs 119; card 2/3 boundary 184 vs 138 |
| 6 | sweep of every scene colour onto the token contract (no raw hex, no gradient) | 0.8437 | card 1 cover 162 vs 108; card 3 cover 185 vs 119; card 2/3 boundary 184 vs 138 |
| 7 | master reverted `471e7c96` for gate reasons: all paint, spacing, rotation and typography moved out of inline styles into the v3 stylesheet behind `data-cb-home-scene-*` hooks | 0.8303 | headline 64 px vs the reference's 72 px — the display step caps at 4 rem (hero band 0.805); card 1 cover 162 vs 108; card 3 cover 185 vs 119 |
