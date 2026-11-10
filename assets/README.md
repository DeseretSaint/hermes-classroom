# Brand assets (CP-004)

These are Coursebook's own brand assets, and they travel **inside the plugin module**: the build
embeds every file below as a data URL in one frozen `CB_ASSETS` object in
`desktop/cb-assets.generated.js`. Nothing here is fetched from a host at run time.

Course covers, scene headers and world plates are **not** here and never will be. They are pack or
world media served by `/media/{artifact_id}` and `/artifacts/{handle}`.

## Layout

| directory | contents | shipped | licence |
| --- | --- | --- | --- |
| `fonts/` | `CBDisplay-VF.woff2`, `CBUI-VF.woff2`, their OFL texts, `manifest.json` | yes | `OFL-1.1` |
| `material/` | six seamless tiles named by `contracts/cb.tokens.v3.json` | yes | `CC0-1.0` |
| `fox/` | seven poses at 128 and 64 px (+ AVIF where the encoder is present) | yes | `CC0-1.0` |
| `objects/` | the seven-piece kit: clock, tag, stamp rim, medallion rim, passport tray, ticket, shelf plank | yes | `CC0-1.0` |
| `masters/` | the inputs: upstream font masters, SVG fox/object masters, PNG material masters, `manifest.json` | no — build inputs | `OFL-1.1` / `CC0-1.0` |

Each shipped directory's `manifest.json` carries one row per file: `role`, `source`, `licence`
(SPDX), `sha256`, `width`, `height`, `bytes`, `provenance_id`, `path`, `kind`, plus the master and
its sha256. The row is the provenance record; the test recomputes every hash.

## Rebuild

```sh
uv venv --python 3.12 .venv-cb-assets
uv pip install --python .venv-cb-assets/bin/python "fonttools[woff]==4.59.2" "brotli==1.1.0" "numpy==2.5.4" "pillow==13.0.0"
.venv-cb-assets/bin/python scripts/build_cb_assets.py --check     # build + budgets
.venv-cb-assets/bin/python scripts/build_cb_assets.py --write-masters   # redraw the art masters
```

The venv is private, git-ignored, and never installed into the system interpreter. `rsvg-convert`
rasterises the SVG masters; Pillow encodes WebP (and AVIF when its encoder is built in).

## Determinism and budgets

Two builds from the same masters produce byte-identical output: font `head` dates are pinned to a
fixed instant, encoder parameters are explicit, and masters are committed rather than fetched.
`tests/test_cb_assets.py` rebuilds twice in temp trees and compares bytes with the committed
segment, so a non-deterministic build fails the suite.

Budgets: the generated segment ≤ 2.5 MB, any single shipped asset ≤ 300 KB, `desktop/plugin.js`
≤ 4.5 MB (alone and with the segment it will carry). Current build: ~462 KB segment, ~200 KB of
shipped files, largest asset ~110 KB.

## Art status

The fox and object masters are **provisional** first-party geometry drawn by the build script so
this card could prove the pipeline and the budget. CP-010 replaces the fox masters with the
approved model-sheet poses, and CP-013 replaces the object kit; rerunning the build is the whole
migration. The material tiles are procedural and are also provisional until CP-011's proof lands.
