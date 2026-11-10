# Third-party notices

Scope: the Workshop destination, its catalogue and the harness that photographs it (H-196 /
H-196a). Companion file: [ASSET-PROVENANCE.md](ASSET-PROVENANCE.md) covers media and rights.

## Ported patterns

**None.** No interaction, layout or copy pattern in the Workshop was ported from another product,
another codebase or another repository. The surfaces are drawn from this repository's own identity
tokens (`--cb-*`, `CB_TYPE`) and from the host's own SDK primitives. Where the Workshop resembles a
store, that is the ordinary vocabulary of a catalogue — category, title, one outcome, a trust label
with its sentence, one primary action — not a copied design system.

This also means no third-party licence attaches to any pattern here: there is nothing to attribute
because nothing was taken.

## Runtime code the module depends on (supplied by the host, not bundled)

| dependency | how it arrives | licence note |
| --- | --- | --- |
| `@hermes/plugin-sdk` | the Hermes Desktop host provides it; `desktop/plugin.js` imports it, it is not vendored | first-party Hermes distribution; this repository ships no copy |
| `react`, `react-dom`, `react/jsx-runtime` | host-provided, same as above | not redistributed here |

## Bundled brand assets (CP-004)

Coursebook now ships its own brand assets in the plugin package: two typefaces, six material
tiles, seven fox poses at two exports and a seven-piece object kit. They are embedded as data URLs
by `scripts/build_cb_assets.py` into `desktop/cb-assets.generated.js`; nothing is fetched from a
host at run time and no course cover, scene header or world plate is in that segment. The
generated object is concatenated into `desktop/plugin.js` by `scripts/build_plugin.py`
immediately after the module header, so the runtime's single module carries `CB_ASSETS` while
the package still keeps the generated file as its build input.

| asset group | upstream / authorship | licence | shipped as |
| --- | --- | --- | --- |
| `CB Display` | **Fraunces**, The Fraunces Project Authors, `google/fonts` @ `5bb28733cec313b63fbd415b574b5ae35c8aa8b8`, `ofl/fraunces/Fraunces[SOFT,WONK,opsz,wght].ttf`, sha256 `177ff6c0f14e5550a3c624247cd1189611d4eb65d000b14944c63d967958abbb` | `OFL-1.1`; no Reserved Font Name declared | subset to Latin + punctuation, renamed, `assets/fonts/CBDisplay-VF.woff2` |
| `CB UI` | **Source Sans 3**, © 2010-2020 Adobe, `google/fonts` @ `5bb28733cec313b63fbd415b574b5ae35c8aa8b8`, `ofl/sourcesans3/SourceSans3[wght].ttf`, sha256 `042fe2cc0b933e328410d7acbd0aa6a1873dca5aef81875f4bc214b08825c7b9` | `OFL-1.1`; **Reserved Font Name `Source`** | subset to Latin + punctuation, renamed, `assets/fonts/CBUI-VF.woff2` |
| material tiles | our own work, drawn by `scripts/build_cb_assets.py --write-masters` from the v3 role palette | `CC0-1.0` | six 96 px WebP tiles, ≤ 1.3 KB each |
| fox poses | our own work, drawn by the same script (provisional masters; CP-010 replaces the SVG masters it owns) | `CC0-1.0` | seven poses at 128 and 64 px WebP |
| object kit | our own work, drawn by the same script (provisional masters; CP-013 owns the final kit) | `CC0-1.0` | seven 256 px WebP, plus AVIF where Pillow's encoder is present |

### Reserved Font Name decision

The OFL text was read before any subsetting, and the decision below is the one the build enforces:

- **Fraunces** — the copyright line declares no Reserved Font Name, so the family *could* keep its
  name. It is renamed to `CB Display` anyway because the v3 test refuses any family name that does
  not start with `CB `.
- **Source Sans 3** — the copyright line declares **Reserved Font Name `Source`**. Subsetting is a
  Modified Version under OFL clause 3, so the modified font may not use that name. We rename the
  font names (IDs 1, 2, 3, 4, 6, 16, 17) to `CB UI` and keep the copyright (ID 0), licence text
  (ID 13) and licence URL (ID 14) byte-for-byte. `tests/test_cb_assets.py` fails if `Source`,
  `SourceSans` or `Fraunces` appears in a font name, so the rename cannot silently regress.

Both licence texts ship verbatim beside the fonts in `assets/fonts/licenses/`, and both outputs keep
the OFL notice inside the WOFF2 name table. Subsetting drops CJK on purpose: Japanese lines use the
system CJK stack (`CB Serif JP`, `Hiragino Mincho ProN`, `Yu Mincho`), not a bundled face.

Font masters are committed under `assets/masters/fonts/` (sha256 pinned above) so a rebuild is
offline and reproducible; they are inputs, not shipped assets, and are excluded from the 300 KB
per-asset budget. `Pillow` and `rsvg-convert` are development tools: neither is imported by the
plugin.

The release gate carries **no file-admission rule**: `bash scripts/validate-plugin.sh` exports the
commit and runs `hermes plugins validate`, `node --check desktop/plugin.js`, the desktop contract
tests and `hermes plugins doctor`; `hermes plugins validate` does not police how many
`desktop/*.js` files the package carries. What does police the desktop file set is
`tests/test_desktop_surface.py::test_single_module_only`, widened by this card to admit exactly
`plugin.js` plus the generated segment, with `test_generated_segment_is_inert` proving the segment
is concatenation input rather than a second module.


## Model output used to produce a fixture (not code, not a runtime dependency)

The bundled Japanese pack contains one 2.8-second narration clip of the polite first-confession
line. It is **model output**, generated offline by the pack maintainer on 2026-11-07:

- engine **Kokoro-82M** (`hexgrad/Kokoro-82M`, revision `f3ff3571791e39611d31c381e3a41a3af07b4987`),
  weights **Apache-2.0**, used through the `kokoro` Python package (Apache-2.0);
- Japanese G2P via `misaki` / `pyopenjtalk` + UniDic; resolved versions and the exact commands are
  recorded in [REVIEW_H72.md](REVIEW_H72.md);
- voice `jf_alpha`, a synthetic voice embedding shipped with the model. **No human speaker was
  recorded, and no native speaker reviewed the pronunciation.** The pack, the catalogue entry and
  every surface that shows the clip say so.

Nothing from the model's training data is redistributed; the clip is generated audio.

## Harness-only tools (development, never shipped)

- `jsdom` — mounts the shipped module so effects and clicks run (`scripts/h196-workshop-render.mjs`).
- A local `chromium` binary — paints each frame and reads the laid-out DOM over CDP
  (`scripts/h196-workshop-shot.mjs`).

Both are test/evidence tooling. Neither is imported by `desktop/plugin.js` and neither is part of a
Plugin export.

## Evidence of absence

`grep -n "\.svg\|\.png\|\.woff\|fonts.googleapis\|@import\|url(http" desktop/plugin.js` returns
nothing on the shipping module, and the Workshop's only `<img>` src is the data URL the host returns
from `artifact.get` for a pack's own declared media.
