# UI context pack — Home

Generated for the UI design lead. This is the substitute for reading the codebase. Keep it open; do
not open the source files it summarises.

## 1. Token rules (non-negotiable — the v3 gates enforce them)

Roles, read through `var(--cb3-*)`: canvas, canvas-edge, card-stock, ink, ink-soft, rule, forest,
on-forest, terracotta, on-terracotta, terracotta-quiet, gold, sage, wood, wood-edge, plum, alert,
focus. Light mode values include canvas `#f5e3c8`, card-stock `#f4ecd9`, ink `#1a1713`, forest
`#0d281b`, terracotta `#b4532f`, gold `#a1741f`, wood `#a5763f`, wood-edge `#7d5529`.

Forbidden in product code: literal hex colours, literal font sizes (px/rem numbers outside the token
scale), inline `boxShadow` strings, viewport units, looping animation. Type comes from six steps:
caption 0.75, meta 0.875, body 1, lead 1.25, heading clamp(1.5–2.25), display clamp(2.5–4). Display
weight 600. Motion ≤600 ms, transform/opacity only.

Materials are object-kit images: `cb.asset.object.shelf-plank`, `clock`, `tag`, `stamp-rim`,
`medallion-rim`, plus grain and vignette tiles. The fox has seven poses at 128/64 px; Home uses
`clock`.

## 2. The scene contract

- Stage authored at 1344×768, scaled to the route with `min(w/1344, h/768)`; centred.
- Layers, back to front: paper grain and vignette (route ground), hero type, upper shelf cards,
  upper plank, lower ledge objects, lower plank, brackets.
- Hero: display line, one subline, two pill CTAs; centred; top edge about 104 px on the stage.
- Upper shelf: four cards, 278 px wide, 170 px cover, bottom-aligned on a 26 px plank at 640 px.
- Lower ledge: tag at (886, 626), clock at (1052, 590) 152 px, fox at (1150, 520) 196 px, plank at
  714 px.
- Cards carry `data-cb-home-scene-card`, cover art from the course's artifact, and a progress bar
  from `sections_done/sections_total`; no ratings.
- The scene is `data-cb-home="scene"`; the compact Home stays for narrow routes.

## 3. Current measured state (2026-11-10 23:00 MST)

- Installed module `4087908c`; the first scene attempt was reverted (`ed61d708`) for raw hex,
  literal type sizes and an inline shadow — 23 gate tests failed.
- `wt/cp-053-home-scene` holds the token-compliant attempt (`a07b99ea`, cinder) and
  `design/home-scene.html` (0.866 grey similarity to the owner concept).
- The Desktop tab route is ~560 px wide; the full-window route is ≥1344 px. The owner judges the
  full-window frame; the tab must still read as the same product.
- Covers currently render as 56 px strips in the compact card; the reference cover is 170 px.
- Known visual gaps: cover art differs from the reference illustrations; fox is a 128 px sprite
  where the reference has a large seated character; header is the host shell, not the reference's.

## 4. Gate commands the worker must run

```
python3 -m unittest tests.test_desktop_tokens tests.test_desktop_tokens_v3 \
  tests.test_desktop_gate_scope tests.test_desktop_type_scale \
  tests.test_desktop_h152_motion tests.test_desktop_gm002_home \
  tests.test_desktop_h86_wayfinding tests.test_v3_visual_audit
python3 scripts/build_plugin.py && node --check desktop/plugin.js
bash scripts/validate-plugin.sh
node visual/audit.mjs            # health, geometry, fonts, axe; fails on a crash dialog
bash scripts/compare-ref.sh --ref docs/concept-parity/refs/home.png --shot <frame.png>
```

## 5. Definition of a rejected card

A frame that looks close but fails a token gate, an axe check, the font load, or the element
checklist is rejected. A card whose evidence omits measured geometry or the gate result is rejected
without review.
