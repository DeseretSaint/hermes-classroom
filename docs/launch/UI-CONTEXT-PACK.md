# UI context pack — Home

Generated for the UI design lead. This is the substitute for reading the codebase. Keep it open; do
not open the source files it summarises.

**Canonical numbers live in `docs/launch/UI-CONTEXT-PACK.generated.md`, produced by
`scripts/gen-ui-pack.py` from `design/home-scene.html` at `a07b99ea` (hash `216c7998d4db4960`).**
If this page and that file disagree, the generated file wins.

## 1. Token rules (non-negotiable — the v3 gates enforce them)

Roles, read through `var(--cb3-*)`: canvas, canvas-edge, card-stock, ink, ink-soft, rule, forest,
on-forest, terracotta, on-terracotta, terracotta-quiet, gold, sage, wood, wood-edge, plum, alert,
focus. Light values: canvas `#f5e3c8`, card-stock `#f4ecd9`, ink `#1a1713`, forest `#0d281b`,
terracotta `#b4532f`, gold `#a1741f`, wood `#a5763f`, wood-edge `#7d5529`.

Forbidden in product code: literal hex, literal font sizes outside the scale, inline `boxShadow`,
viewport units, looping animation. Fixed type steps are 12 / 14 / 16 / 20 px; heading and display
use their clamp tokens (24–36 and 40–64); display weight 600. Motion ≤600 ms, transform/opacity
only.

Materials are object-kit images: shelf planks, clock, tag, grain, vignette. The fox sprite is
`assets/art/fox/fox-clock-256.png`; the clock is `assets/art/objects/clock.png`.

## 2. The scene contract

- Stage authored at 1344×768, scaled by `min(w/1344, h/768)`, centred.
- Layers, back to front: grain and vignette, hero, upper cards, upper plank, lower objects, lower
  plank, brackets.
- Measured boxes: header 86 px; brand 94/30; nav 388/42; studio 1102/40; hero top 128; card shelf
  top 384; card 176×175, cover 106; plank one 219/559 (915×18); tag 880/606 (164×88); clock
  1042/588 (118); fox 1088/526 (208); plank two 130/684 (1150×30); brackets 736 (54×32).
- Cards carry `data-cb-home-scene-card`, cover art from the course artifact, and a progress bar from
  `sections_done/sections_total`; no ratings.
- The scene is `data-cb-home="scene"`; compact Home stays for narrow routes.

## 3. The reconciliation problem (Gate 0)

The reference uses seven off-scale type selectors: brand 34, nav 17, studio 17, h1 72, subline 32,
card title 15, tag 23. The token system has no step for any of them, and the h1 exceeds the 64 px
display ceiling. A worker told to "match the reference" and "use no literal sizes" cannot comply.
The owner must extend the scale or accept nearest steps before implementation. This is the decision
that killed the first attempt.

## 4. Current measured state (2026-11-10 23:00 MST)

- Installed module `4087908c`; the first scene attempt was reverted (`ed61d708`) for raw hex,
  literal type sizes and an inline shadow — 23 gate tests failed.
- `wt/cp-053-home-scene` holds the token-compliant attempt (`a07b99ea`, cinder) and
  `design/home-scene.html` (0.866 grey similarity to the owner concept).
- The Desktop tab route is ~560 px wide; the full-window route is ≥1344 px. The owner judges the
  full-window frame; the tab must still read as the same product. Who owns the 86 px header is
  unresolved (Gate 0).
- Covers currently render as 56 px strips in the compact card; the reference cover is 106 px.
- Known visual gaps: concept cover art differs from the shipped pack covers; the live fox is a
  128 px procedural WebP where the reference places the painted 208 px A1 plate; the header is the
  host shell in the docked pane.

## 5. Gate commands the worker must run

```
python3 -m unittest tests.test_desktop_tokens tests.test_desktop_tokens_v3 \
  tests.test_desktop_gate_scope tests.test_desktop_type_scale \
  tests.test_desktop_h152_motion tests.test_desktop_gm002_home \
  tests.test_desktop_h86_wayfinding tests.test_v3_visual_audit
python3 scripts/build_plugin.py && node --check desktop/plugin.js
bash scripts/validate-plugin.sh
node visual/audit.mjs
bash scripts/compare-ref.sh --ref docs/concept-parity/refs/home.png --shot <frame.png>
```

## 6. Definition of a rejected card

A frame that looks close but fails a token gate, an axe check, the font load, the DOM geometry audit
(±2 px) or the element checklist is rejected. A card whose evidence omits measured geometry or the
gate result is rejected without review.
