# Brand assets (CP-004)

These are Coursebook's own brand assets, and they travel in the plugin package as
`desktop/cb-assets.generated.js`: the build embeds every file below as a data URL in one frozen
`CB_ASSETS` object, and `scripts/build_plugin.py` concatenates that object straight after the
module header, so `desktop/plugin.js` carries `CB_ASSETS` and the runtime still loads one module.
The standalone generated file stays on disk as the build input; it is never imported. Nothing here
is fetched from a host at run time.

Course covers, scene headers and world plates are **not** here and never will be. They are pack or
world media served by `/media/{artifact_id}` and `/artifacts/{handle}`.

## Layout

| directory | contents | shipped | licence |
| --- | --- | --- | --- |
| `fonts/` | `CBDisplay-VF.woff2`, `CBUI-VF.woff2`, their OFL texts, `manifest.json` | yes | `OFL-1.1` |
| `material/` | six seamless tiles named by `contracts/cb.tokens.v3.json` | yes | `CC0-1.0` |
| `fox/` | seven poses at 128 and 64 px (+ AVIF where the encoder is present) | yes | `CC0-1.0` |
| `objects/` | the seven-piece kit: clock, tag, stamp rim, medallion rim, passport tray, ticket, shelf plank; painted masters live in `art/objects/` | yes | `CC0-1.0` |
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

**AVIF policy.** Every image ships as WebP. An AVIF alternate is added, and exposed as `src_avif`,
for any asset whose WebP is already ≥ 8 KB — currently the object kit. Smaller assets stay WebP-only
because a second encoding would add bytes to the segment without a visible gain. The builder checks
the encoder at build time (`PIL.features.check("avif")`) rather than assuming the host decodes it.

## Determinism and budgets

Two builds from the same masters produce byte-identical output: font `head` dates are pinned to a
fixed instant, encoder parameters are explicit, and masters are committed rather than fetched.
`tests/test_cb_assets.py` rebuilds twice in temp trees and compares bytes with the committed
segment, so a non-deterministic build fails the suite.

Budgets: the generated segment ≤ 2.5 MB, any single shipped asset ≤ 300 KB, `desktop/plugin.js`
≤ 4.5 MB (alone and with the segment it carries). Current build: 1,384,979 B segment, 893,202 B of
shipped files, largest single asset 110,076 B (`CBDisplay-VF.woff2`). The plugin-plus-segment gate is
now the tight one: 4,492,044 B against its 4,500,000 B ceiling, because `plugin.js` embeds the whole
segment and the gate counts it twice. Raising that ceiling is a budget decision, not a build order.

## Art status

The fox masters are the approved A1 pose set (CP-010) and the object masters are the painted A5
blanks (CP-013): `assets/art/objects/*.png` is the object kit's single source, and
`scripts/build_cb_assets.py` encodes it into `assets/objects/*.webp` (+ AVIF past 8 KB). The
procedural SVG kit under `assets/masters/objects/` is kept only as the fallback for an object with no
painted master; `--write-masters` never overwrites a painted blank. The material tiles are CP-011's
and are still provisional until its proof lands.

The fox WebPs under `assets/fox/` are encodes of the owner-signed painted exports under
`assets/art/fox/fox-<pose>-<size>.png` at 512, 256, 128 and 64, alpha preserved, and every
`assets/fox/manifest.json` row names its painted PNG as both `source` and `master` (CP-005f). The
procedural SVG set under `assets/masters/fox/` is kept on disk for rollback only: nothing in the
segment, the manifest or the module reaches it, and `tests/test_cp010_fox_assets.py` fails if it
does. `design/fox-adoption.html` is a generated proof of the painted 208 render, pinned to
`desktop/plugin.js` by that same test module.

The scene plates (`assets/art/scenes/`) are **not** part of this tree's shipped files: they are pack
or world media and travel on the media route.
