# Material textures (A2) — CP-011

Four material families in light and dark: **paper grain**, **card-stock fibre**, **parchment
vignette** and **wood plank**. Eight tiles, each seamless, each under 60 KB, each painted by a
deterministic host generator rather than a model. This folder holds the proofs and the evidence;
the tiles themselves live in `assets/art/material/` with their provenance manifest.

| tile | mode | px | bytes | alpha ceiling | ink worst-case | seam (col/row) |
|---|---|---|---|---|---|---|
| `paper-grain` | light | 256 | 40,787 | 14 | 12.84:1 | 0.95 / 0.99 |
| `paper-grain` | dark | 256 | 38,569 | 16 | 12.76:1 | 0.95 / 0.99 |
| `card-stock-fibre` | light | 256 | 9,399 | 9 | 14.24:1 | 0.22 / 0.88 |
| `card-stock-fibre` | dark | 256 | 10,032 | 10 | 12.09:1 | 0.08 / 1.02 |
| `parchment-vignette` | light | 512 | 25,407 | 30 | 12.01:1 | 0.95 / 0.97 |
| `parchment-vignette` | dark | 512 | 28,102 | 46 | 14.71:1 | 1.04 / 1.02 |
| `wood-plank` | light | 256 | 27,218 | — | 5.73:1 (informational) | 0.77 / 0.92 |
| `wood-plank` | dark | 256 | 26,747 | — | 7.25:1 (informational) | 0.82 / 0.75 |

"Seam" is the mean pixel step across the wrap divided by the mean step of the two neighbour pairs
immediately inside it. At or below ~1 there is no discontinuity: the seam looks exactly like the
texture's own adjacent-pixel change. The test suite recomputes it from the committed bytes, and it
also proves the metric catches a broken tile by forcing a mismatch on a copy.

## How the tiles are used

Compose in this order, and only in this order (CP-020a implements it):

1. **Ground** — the v3 token (`canvas` or `card-stock`), flat.
2. **Tile overlay** — `background-repeat` repeat, `aria-hidden`, `pointer-events: none`, at the
   alpha ceiling below. The tile is an *overlay* (RGBA) except wood.
3. **Vignette** — once, `background-size: cover`, `no-repeat`, on the canvas only.
4. **Text.**

Under `@media (forced-colors: active)` both layers are hidden and the system colour wins. A tile
that fails to decode leaves the flat token ground — never a half-painted route.

**Alpha ceilings are the legibility argument, not a style choice.** Each is the highest alpha the
tile may place under type: `ink` over the darkest pixel the tile can produce on its ground still
measures ≥ 4.5:1 at 16 px. Raising a ceiling without re-measuring breaks that guarantee, so the
ceiling lives in the manifest and the test re-derives the contrast from it.

**Wood never carries text.** It is the shelf plank face and the evidence tray only. The plank's top
lip, cut end and contact shadow are drawn by `ShelfPlank` (CP-020b) over this tile — they are
deliberately *not* baked into the tile, because a baked lip would repeat as a dark band at every
vertical wrap.

## Where the colours came from

Light values are measured: `canvas #f5e3c8` and `card-stock #f4ecd9` are the values named in
`docs/concept-parity/PLAN.md` §2, sampled against the ratified frames in
`docs/concept-parity/refs/` (dominant parchment `#f2e2ce`, card `#faf5e5`, shelf wood `#ad8c6b` /
`#997454`). Grain and vignette inks are warm brown (`#3a2318` / `#6b492c`), never black: the art
bible's line colour, not `#000`.

Dark values are **authored**. No ratified dark frame exists yet, so `canvas #171410`,
`card-stock #221d17`, ink `#f2e2ce` and the walnut ramp are a derivation inside the "night atlas"
range that CP-002 will freeze as tokens. This is recorded in every manifest row rather than
presented as a measurement.

Overlays are alpha-only, so a later token change to `canvas` or `card-stock` needs no repaint. The
**wood tile is baked colour**: if `--cb3-wood` lands on a different value, repaint with

```bash
python3 scripts/build_cb_material.py build && python3 scripts/build_cb_material.py prove
python3 scripts/cp_material_sheet.py
```

The generator is deterministic: repainting reproduces the committed bytes exactly, and
`tests/test_cp_material_textures.py` asserts that per tile.

## Provenance

`assets/art/material/manifest.json` carries one row per tile, in the `docs/GM-ART-PLATES.md` §4
shape: `role`, `provider: host`, `model: none`, no `prompt_hash` (there was no model call, so
inventing one would be a lie), seed, palette source, `licence: CC0-1.0`, `provenance_id`,
`text_check`, `sha256`, `bytes`, `width`/`height`, seam figures and the contrast pair.

The text check is tesseract at `--psm 11`, counting only tokens at confidence ≥ 70 — a texture
always yields some low-confidence OCR noise, and a threshold is what separates "grain looks like a
speck" from "someone baked a word into the art". The suite proves the check can actually see a word
by stamping `PACK` onto a copy of a tile and requiring a hit.

## Evidence in this folder

| file | what it proves |
|---|---|
| `proof-3x3-<tile>-<mode>.png` | 3×3 composite of each tile on its own ground, including the vignette: its wrap carries no discontinuity. |
| `proof-once-parchment-vignette-<mode>.png` | the vignette as the route actually paints it — one application across a 3× canvas at cover size |
| `texture-sheet-light.png`, `texture-sheet-dark.png` | every tile behind real body text at 16 px, each beside a flat control carrying the identical paragraph |
| `texture-sheet-<mode>.stamp.json` | commit, branch, engine, tile hashes and sizes, seam and contrast rows, text source and hash, sheet hash |

The sheet's body text is the bundled technical pack's own teaching prose
(`bundled/packs/technical-demo-pack/content/section-01-anatomy.md`), not copy written for the
sheet. The stamp records its hash.

## Honesty note on the evidence

These are **proof sheets**, not UI captures. `scripts/cp-capture.mjs` is CP-000's deliverable and is
not on this branch, so no frame here claims to be the live route, and no stamp claims a plugin sha.
When CP-000 lands, CP-020a is the card that captures the real route on this ground; these sheets
remain the material-level proof beneath it.
