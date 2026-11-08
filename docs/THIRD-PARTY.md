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

No npm package, font file, icon set, stylesheet or script tag ships inside the pack or the plugin
bundle. `bash scripts/validate-plugin.sh` refuses an export that carries anything outside the
declared allowlist.

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
