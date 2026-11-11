# Asset provenance — the Workshop and the packs it lists

Card: H-196 / H-196a. Branch `wt/h193-workshop` (H-196) continued on `wt/t_5ef6be7f` (H-196a);
H-197 (the one approved illustration lane) on `wt/h197-illustration` adds this file's cover-plate
records and changes nothing recorded by H-196/H-196a.
Surface: the Workshop destination in `desktop/plugin.js`, its catalogue
`catalog/workshop.v1.json`, and the three bundled packs that catalogue lists.

## Verdict up front

**The Workshop surface uses no external assets.** `desktop/plugin.js` fetches no image, icon set,
illustration, font file or stylesheet from any host; it has no `url(http…)`, no `.svg`/`.png`/
`.woff` reference and no `@import`. Serif and sans are system stacks (`CB_SERIF`, `CB_SANS` at
`desktop/plugin.js`). A pack cover is either the pack's own
declared media, read at run time through `artifact.get`, or type — the typographic fallback draws
its rule and station from the identity's own tokens.

CP-004 adds a separate, non-Workshop lane: the v3 brand assets (two OFL typefaces, material tiles,
fox poses, object kit) are embedded as data URLs in `desktop/cb-assets.generated.js`, which
`scripts/build_plugin.py` concatenates into `desktop/plugin.js` after the module header. They are
first-party or openly licensed, they are not fetched from a host, and they are recorded in
[THIRD-PARTY.md](THIRD-PARTY.md). Course covers, scene headers and world plates stay outside that
segment and keep using the media route.

H-197 opened one illustration lane: a cover plate composed in the Atlas Lamp language from the
token palette by `bundled/packs/build_bundled_packs.py`. It is **host-composed, not model-generated
and not stock**: every plate is flat rectangles and one hairline ring drawn from
`contracts/cb.tokens.v2.json`, contains no text, and no third-party imagery, so its rights answer is
authorship rather than a licence guess.

CP-042 (operator note, 2026-11-10) makes that Press Plate generator the **only** cover lane. The host
image model baked garbled titles into painted plates (the live Home shelf rendered `Asttomamy` and
`Repir Fundamentas` inside the art), so a cover is never model output now: every bundled cover is
printed deterministically from flat geometry, released `CC0-1.0`, and OCR-audited to carry no glyph.
The course title is DOM text on the card, never part of the image. The earlier CP-012 painted plates
remain recorded as superseded history, not as shipped files.

The one third-party *production* step reachable from the surface is the bundled Japanese pack's
narration clip: it is synthetic model output, not a recording, and it is declared as such in the
pack manifest, the pack's `content_notes`, its contributors list and its per-artifact attribution.

## Every asset the surface can show

| asset | path | produced by | licence | bundled | sha256 |
| --- | --- | --- | --- | --- | --- |
| Japanese pack cover, 3:2 plate | `bundled/packs/japanese-affection-context-l0/content/cover-3x2.png` | **Deterministic Press Plate (CP-042)**, flat geometry printed by the pack builder from the token palette; no model call, no stock imagery, no text (864x576) | `CC0-1.0`, declared per artifact in `pack.json` → `license.per_artifact[]`; pack redistribution `allowed`. Attribution: "Deterministic cover printed by the Coursebook bundled pack builder from flat geometry; no model output, no text, no third-party source or media. CC0-1.0." | yes, 3,153 bytes | `41a21b9742c8f8cbd8e020e9f0660ff87dec3e6203688211aaad4f582c0aed2f` |
| Japanese pack cover, 4:5 crop | `bundled/packs/japanese-affection-context-l0/content/cover-4x5.png` | **Deterministic Press Plate (CP-042)**, the 3:2 plate's exact 4:5 centre crop (no resampling), never a second drawing (460x575) | `CC0-1.0`, declared per artifact in `pack.json` → `license.per_artifact[]`; pack redistribution `allowed`. Attribution: "Deterministic cover printed by the Coursebook bundled pack builder from flat geometry; no model output, no text, no third-party source or media. CC0-1.0." | yes, 2,194 bytes | `5ae6ea8007db3d034e6b21b4b9fea865530c93c43c9b9d23e4e0dd4bd310e7e6` |
| Parent pack cover, 3:2 plate | `bundled/packs/parent-measurement-practice/content/cover-3x2.png` | **Deterministic Press Plate (CP-042)**, flat geometry printed by the pack builder from the token palette; no model call, no stock imagery, no text (864x576) | `CC0-1.0`, declared per artifact in `pack.json` → `license.per_artifact[]`; pack redistribution `allowed`. Attribution: "Deterministic cover printed by the Coursebook bundled pack builder from flat geometry; no model output, no text, no third-party source or media. CC0-1.0." | yes, 3,119 bytes | `95e8f7b0f6e44bec6ece917e4b74e502445e7f0a7ec70a2993a97f79333de825` |
| Parent pack cover, 4:5 crop | `bundled/packs/parent-measurement-practice/content/cover-4x5.png` | **Deterministic Press Plate (CP-042)**, the 3:2 plate's exact 4:5 centre crop (no resampling), never a second drawing (460x575) | `CC0-1.0`, declared per artifact in `pack.json` → `license.per_artifact[]`; pack redistribution `allowed`. Attribution: "Deterministic cover printed by the Coursebook bundled pack builder from flat geometry; no model output, no text, no third-party source or media. CC0-1.0." | yes, 2,061 bytes | `82505bf4730e2c465bdba91877a7baab6b8b8da9a8f04ff0606ebb35a08cabe6` |
| Technical pack cover, 3:2 plate | `bundled/packs/technical-pack-literacy/content/cover-3x2.png` | **Deterministic Press Plate (CP-042)**, flat geometry printed by the pack builder from the token palette; no model call, no stock imagery, no text (864x576) | `CC0-1.0`, declared per artifact in `pack.json` → `license.per_artifact[]`; pack redistribution `allowed`. Attribution: "Deterministic cover printed by the Coursebook bundled pack builder from flat geometry; no model output, no text, no third-party source or media. CC0-1.0." | yes, 3,162 bytes | `3eab94e5555241a7bf0556aeedf2e7d1d145daf572e975239d4d6dc4565c0056` |
| Technical pack cover, 4:5 crop | `bundled/packs/technical-pack-literacy/content/cover-4x5.png` | **Deterministic Press Plate (CP-042)**, the 3:2 plate's exact 4:5 centre crop (no resampling), never a second drawing (460x575) | `CC0-1.0`, declared per artifact in `pack.json` → `license.per_artifact[]`; pack redistribution `allowed`. Attribution: "Deterministic cover printed by the Coursebook bundled pack builder from flat geometry; no model output, no text, no third-party source or media. CC0-1.0." | yes, 2,348 bytes | `668a63a9c38d07ca810d5b4f1a16bfd520ca23e668fdf5040836edbea94f8416` |
| Relationship and register map (schematic) | `bundled/packs/japanese-affection-context-l0/content/relationship-map.png` | Deterministic geometry drawn by `bundled/packs/build_bundled_packs.py`; no third-party imagery | `CC0-1.0`, declared per artifact in `pack.json` → `license.per_artifact[]` | yes, 6,948 bytes | `8fb84ad3d7797f6b11febd8510b4e2fb5f17be3ed573fd31dcb8fb9468f1093d` |
| Narration of the polite first-confession line | `bundled/packs/japanese-affection-context-l0/content/narration-polite-confession.mp3` | **Kokoro-82M** (`hexgrad/Kokoro-82M`, revision `f3ff3571791e39611d31c381e3a41a3af07b4987`), voice `jf_alpha`, Apache-2.0 model weights, run offline with the `kokoro` package (Apache-2.0). No human speaker. | `Apache-2.0` (model licence; the clip is model output) | yes, 22,272 bytes | `dea7f196f147958a536b41c6ee8f2ff51558f56a74e7f4e8ab86f580db971349` |
| Japanese pack teaching text | `bundled/packs/japanese-affection-context-l0/content/section-0{1,2,3}-*.md`, `source-notes.md` | Original Coursebook-authored prose | pack `license` is `CC-BY-4.0` with `allowed` redistribution under the operator-directed store release of 2026-11-10; covers are `CC0-1.0` | yes (whole pack: 8 files, 44,957 expanded bytes) | per-file sha256 in `pack.json` → `files[]` (pack `content_hash` `sha256:3e4fc6459aa1319e926267793d315f6cddcb5e62f133192a9632c4e1a21e8116`) |
| Parent measurement pack | `bundled/packs/parent-measurement-practice/` (5 files, 8,659 expanded bytes: 3 prose + 2 cover files) | Original Coursebook-authored prose plus the deterministic Press Plate cover; no third-party text, image or audio | `CC-BY-4.0`, `allowed`; cover records are `CC0-1.0` | yes | per-file sha256 in `pack.json` → `files[]` (pack `content_hash` `sha256:40c56aeb6514fc44f86c89f421594396d7eff859ea3e232a2fb8b0ab0ba858e5`) |
| Technical pack | `bundled/packs/technical-pack-literacy/` (5 files, 9,508 expanded bytes: 3 prose + 2 cover files) | Original Coursebook-authored prose plus the deterministic Press Plate cover, about this repository's own pack contract | `CC-BY-4.0`, `allowed`; cover records are `CC0-1.0` | yes | per-file sha256 in `pack.json` → `files[]` (pack `content_hash` `sha256:a700ee6bf263c70d1bbccd8a0d6075b1e5ca4fe65ba778359133d90570b03992`) |

Hashes above were printed by `sha256sum` on the tree this document was written from, and the
manifest-declared hashes beside each file are the ones `coursebook/workshop.py` re-verifies on every
catalogue read; a drifted file is refused rather than rendered.

## The cover lane, in full

> **CP-042 (2026-11-10) closes the model cover lane.** The paragraphs below describe the H-197 Press
> Plate lane, which is now the only shipped cover lane. The CP-012 painted plates were model output;
> the image model baked garbled titles into them (`Asttomamy`, `Repir Fundamentas`), so the operator
> directed that no cover carry AI text. Every bundled cover is the deterministic Press Plate, the
> course title is DOM text, and a shipped-still gate asserts the committed bytes are the generator's
> own output and that OCR finds no glyph. The painted plates remain in `audit/cp012-covers/` as
> superseded history.

- **Icons are unchanged.** `sdk.Codicon` only, 16px, `currentColor`; no icon font and no second
  icon family. A cover plate is content/brand ornament, not UI grammar, and it is the only
  illustration lane in the product.
- **One lane: Press Plate.** One broad flat form, one hard-edged `lamp-soft` flood, one `lamp` band
  full bleed at a fixed y, one heavy ink rule. Five flat inks, no text, no object, no symbol. The
  full brief, the prompts (P1–P3) for the model lane, the finish recipe and the acceptance block are
  in `docs/ART-DIRECTION-COVERS.md`.
- **Licence gate.** The cover lane is deterministic, so it ships `CC0-1.0`: the per-artifact record is
  `CC0-1.0` with the attribution "Deterministic cover printed by the Coursebook bundled pack builder
  from flat geometry; no model output, no text, no third-party source or media. CC0-1.0.", and the
  packs declare `redistribution: allowed` under the operator-directed store release recorded on
  2026-11-10. A future pack without that direction stays `local_only`.
- **Coherence gate.** One plate family, one light, one line family, one paper. The plate carries no text
  at all; the pack title is type rendered by the app beside it, and the plate keeps the paper ground
  in both UI modes because it is a lit page.
- **Accuracy gate.** Every cover is labelled on the surface: the caption reads "Cover plate — printed
  geometry, not a diagram of the course.", and the file record carries a human-written text
  equivalent. No cover carries a measurement, torque, dosage, wiring value, field name or other
  safety-critical fact, none is labelled a photograph of a procedure, and none carries a glyph — the
  course title is UI text beside the plate. The Japanese pack's factual visual remains the
  deterministic relationship map, which is a schematic, not the cover.
- **No second icon or illustration system, no hotlink.** There is no remote `src`, no stock-photo
  link, no per-pack art direction and no third-party style in the lane.
- **The optional CC0 set is not shipped.** One CC0 human set is permitted (Open Peeps only:
  `peep-92.svg` as an optional cover cameo, `peep-sitting-1.svg` for the no-courses empty state —
  never both, never a second style). This pass ships none: the card forbids network access, so no
  CC0 SVG could be fetched and verified, and the cameo is optional. Humaaans is held (the 2019
  mirror is CC BY 4.0); Open Doodles, Kenney, Game-icons, Health Icons, Reactome, unDraw, DrawKit,
  Fresh Folk, Illlustrations and Simple Icons are rejected for this lane.


## Frames (screenshots) — produced here, never sourced

`audit/visual/h196-workshop/` holds 18 PNGs and their serialized HTML, rendered from the shipped
`desktop/plugin.js` by `scripts/h196-workshop-frames.py` → `scripts/h196-workshop-render.mjs` →
`scripts/h196-workshop-shot.mjs` (headless Chromium over CDP). They contain no third-party
imagery, no photographs and no stock art; every pixel is our own module, our own tokens and the
pack's own declared media.

`audit/visual/h197-covers/` is the additive H-197 pass: 12 PNGs, their HTML, `frames.json`,
`recorded.json` and `evidence.json`, produced by `scripts/h197-cover-frames.py` and
`scripts/h197-cover-shot.mjs` from the same shipped module and the same renderer. It records the
storefront at 1049/900/460 in light and dark, at 200 % text and with reduced motion, the cover
detail in three postures, and the parent pack's typographic fallback. The only imagery in those
frames is the two cover plates tabulated above, served as data URLs by the real
`media.preview_artifact` route; there is no external `src` in any frame. H-196's frames are left
intact as the earlier record.

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
- **A cover plate is not evidence and not a diagram.** It is ornament. No cover in this tree states
  a register, a quantity, a field name or a procedure step, and none is labelled as a photograph of
  a real procedure.
- **No model-generated hero was used for the Press Plate lane.** The art direction measured the host
  image pipeline, found it ignores "exactly five flat inks" and invents objects, and recommended
  Press Plate — material, not depiction. CP-014's painted covers are a separate, approved CP-012
  lane: model output, measured against the ART-BIBLE and the swap check, and recorded above.
- **The parent pack now carries a cover.** CP-014 moves it to cb.pack v2 so the approved painted
  plate can be adopted as role `cover`; the v1 import path is covered by in-memory v1 fixtures, and a
  pack that declares no cover still falls back to the composed typographic plate.
- **The three bundled courses are store courses.** Their titles, subtitles and licence notes carry
  no demo/sample/fixture label; they are added to the library from the Workshop like any other pack.
- **No external asset was used, so no external licence is relied on** beyond the model licence
  named above for the one generated audio clip; every shipped cover plate is the deterministic
  Press Plate, released `CC0-1.0` under the packs' `redistribution: allowed` store release.
