# Asset provenance — the Workshop and the packs it lists

Card: H-196 / H-196a. Branch `wt/h193-workshop` (H-196) continued on `wt/t_5ef6be7f` (H-196a).
Surface: the Workshop destination in `desktop/plugin.js`, its catalogue
`catalog/workshop.v1.json`, and the three bundled packs that catalogue lists.

## Verdict up front

**The Workshop surface uses no external assets.** `desktop/plugin.js` fetches no image, icon set,
illustration, font file or stylesheet from any host; it has no `url(http…)`, no `.svg`/`.png`/
`.woff` reference and no `@import`. Serif and sans are system stacks (`CB_SERIF`, `CB_SANS` at
`desktop/plugin.js`), so no typeface is redistributed. A pack cover is either the pack's own
declared media, read at run time through `artifact.get`, or type — the typographic fallback draws
its rule and station from the identity's own tokens.

The one third-party *production* step reachable from the surface is the bundled Japanese pack's
narration clip: it is synthetic model output, not a recording, and it is declared as such in the
pack manifest, the pack's `content_notes`, its contributors list and its per-artifact attribution.

## Every asset the surface can show

| asset | path | produced by | licence | bundled | sha256 |
| --- | --- | --- | --- | --- | --- |
| Relationship and register map (schematic) | `bundled/packs/japanese-affection-context-l0/content/relationship-map.png` | Deterministic geometry drawn by `bundled/packs/build_demo_packs.py`; no third-party imagery | `CC0-1.0`, declared per artifact in `pack.json` → `license.per_artifact[]` | yes, 6,948 bytes | `8fb84ad3d7797f6b11febd8510b4e2fb5f17be3ed573fd31dcb8fb9468f1093d` |
| Narration of the polite first-confession line | `bundled/packs/japanese-affection-context-l0/content/narration-polite-confession.mp3` | **Kokoro-82M** (`hexgrad/Kokoro-82M`, revision `f3ff3571791e39611d31c381e3a41a3af07b4987`), voice `jf_alpha`, Apache-2.0 model weights, run offline with the `kokoro` package (Apache-2.0). No human speaker. | `Apache-2.0` (model licence; the clip is model output) | yes, 22,272 bytes | `dea7f196f147958a536b41c6ee8f2ff51558f56a74e7f4e8ab86f580db971349` |
| Japanese pack teaching text | `bundled/packs/japanese-affection-context-l0/content/section-0{1,2,3}-*.md`, `source-notes.md` | Original Coursebook-authored prose | pack `license` is `unspecified` with `local_only` redistribution — the operator has not chosen a redistribution licence | yes | per-file sha256 in `pack.json` → `files[]` |
| Parent measurement pack | `bundled/packs/parent-measurement-practice/` (3 files, 3,479 expanded bytes) | Original Coursebook-authored prose and schematic | `unspecified`, `local_only` | yes | per-file sha256 in `pack.json` → `files[]` |
| Technical demo pack | `bundled/packs/technical-demo-pack/` (3 files, 4,007 expanded bytes) | Original Coursebook-authored prose about this repository's own pack contract | `CC0-1.0` | yes | per-file sha256 in `pack.json` → `files[]` (pack `content_hash` `sha256:603c0b7de57110ff31ec58f8e7d1dab7211c3312e369f880000deac7fda66174`) |

Hashes above were printed by `sha256sum` on the tree this document was written from, and the
manifest-declared hashes beside each file are the ones `coursebook/workshop.py` re-verifies on every
catalogue read; a drifted file is refused rather than rendered.

## Frames (screenshots) — produced here, never sourced

`audit/visual/h196-workshop/` holds 18 PNGs and their serialized HTML, rendered from the shipped
`desktop/plugin.js` by `scripts/h196-workshop-frames.py` → `scripts/h196-workshop-render.mjs` →
`scripts/h196-workshop-shot.mjs` (headless Chromium over CDP). They contain no third-party
imagery, no photographs and no stock art; every pixel is our own module, our own tokens and the
pack's own declared media.

## Sources cited by the Japanese pack, not bundled

The pack links six sources for specific wording and curriculum facts. None of their text, audio or
images is bundled; each is cited by URL in `pack.json` → `sources[]` and in
`content/source-notes.md`, with a licence note.

| source | publisher | URL | licence position | support status |
| --- | --- | --- | --- | --- |
| Marugoto Starter (A1) — table of contents | The Japan Foundation | <https://marugoto.jpf.go.jp/en/assets/docs/about/starter_activities_contents_en.pdf> | © The Japan Foundation; cited as a curriculum reference, no text copied | `authoritative_documentation` |
| How to teach with Marugoto (teacher FAQ) | The Japan Foundation | <https://marugoto.jpf.go.jp/en/teacher/qateaching/> | © The Japan Foundation; read for the romaji/script policy fact only | `authoritative_documentation` |
| Wiktionary — 好き (suki) | Wikimedia Foundation | <https://en.wiktionary.org/wiki/%E5%A5%BD%E3%81%8D> | CC BY-SA 4.0; no text copied | `model_assessed` |
| Wiktionary — 愛する (aisuru) | Wikimedia Foundation | <https://en.wiktionary.org/wiki/%E6%84%9B%E3%81%99%E3%82%8B> | CC BY-SA 4.0; no text copied | `model_assessed` |
| "Learn how to say 'I love you' in Japanese" | Shinjuku Japanese Language Institute (SNG) | <https://www.sng.ac.jp/sng-news/learn-say-love-japanese/> | Linked, not bundled; secondary usage source | `model_assessed` |
| Honorific speech in Japanese | Wikimedia Foundation | <https://en.wikipedia.org/wiki/Honorific_speech_in_Japanese> | CC BY-SA 4.0; used for general framing only | `model_assessed` |

## What this document does not claim

- **No native-speaker review exists and none is claimed.** The narration is synthetic; the pack
  says so on the surface, in its manifest and in this file.
- **A matching hash is not a rights verdict and not a safety verdict.** It says the bytes are the
  bytes the manifest declared, no more. The Workshop's `Validated` badge means two machine checks
  passed; it is not a human review and it says nothing about whether the teaching is right.
- **No external asset was used, so no external licence is relied on** beyond the model licence
  named above for the one generated audio fixture.
