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
`desktop/plugin.js`), so no typeface is redistributed. A pack cover is either the pack's own
declared media, read at run time through `artifact.get`, or type — the typographic fallback draws
its rule and station from the identity's own tokens.

H-197 opens exactly one illustration lane and no more: a cover plate composed in the Atlas Lamp
language from the token palette by `bundled/packs/build_demo_packs.py`. It is **host-composed, not
model-generated and not stock**: every plate is flat rectangles and one hairline ring drawn from
`contracts/cb.tokens.v2.json`, contains no text (so there is no second type system inside the art),
and no third-party imagery, so its rights answer is authorship rather than a licence guess.

The one third-party *production* step reachable from the surface is the bundled Japanese pack's
narration clip: it is synthetic model output, not a recording, and it is declared as such in the
pack manifest, the pack's `content_notes`, its contributors list and its per-artifact attribution.

## Every asset the surface can show

| asset | path | produced by | licence | bundled | sha256 |
| --- | --- | --- | --- | --- | --- |
| Japanese pack cover, 16:9 master | `bundled/packs/japanese-affection-context-l0/content/cover-16x9.png` | **Press Plate**, printed deterministically by `bundled/packs/build_demo_packs.py::cover_plate_png("japanese")` from the Atlas Lamp token palette: five flat inks, hard edges, no text, no object, no model call, no third-party imagery. Prompt P1 (the model lane) is recorded in `docs/ART-DIRECTION-COVERS.md`. | `CC0-1.0`, declared per artifact in `pack.json` → `license.per_artifact[]` | yes, 3,804 bytes | `fc5760868a5b0bd3044b796cfec81353b25285bf618d0f9391289197f978f3a8` |
| Japanese pack cover, 3:2 crop | `bundled/packs/japanese-affection-context-l0/content/cover-3x2.png` | The master's mechanical centre crop (864x576 of 1024x576), printed by `cover_crop_png`, never a second drawing | `CC0-1.0`, declared per artifact | yes, 3,153 bytes | `41a21b9742c8f8cbd8e020e9f0660ff87dec3e6203688211aaad4f582c0aed2f` |
| Technical pack cover, 16:9 master | `bundled/packs/technical-demo-pack/content/cover-16x9.png` | **Press Plate**, same press (`cover_plate_png("technical")`): paper, ink, the pale grey `rule` plane edge, pale gold flood, gold band. Five flat inks, no text, no model call. Prompt P3 is recorded in `docs/ART-DIRECTION-COVERS.md`. | `CC0-1.0`, declared per artifact | yes, 3,784 bytes | `8e5af33049d3d4a7c01cc14e7611c38c568f773e0fb6de27afa8892fa88cd72a` |
| Technical pack cover, 3:2 crop | `bundled/packs/technical-demo-pack/content/cover-3x2.png` | The master's mechanical centre crop (864x576), from `cover_crop_png` | `CC0-1.0`, declared per artifact | yes, 3,162 bytes | `3eab94e5555241a7bf0556aeedf2e7d1d145daf572e975239d4d6dc4565c0056` |
| Parent pack cover | *(none — typographic plate)* | The cover is type: the pack's first category, a rule and the title at `CB_TYPE.heading`, drawn by `WorkshopCover` in `desktop/plugin.js`. The Press Plate for that pack exists in the builder (`cover_plate_png("parent")`) but ships nothing: the pack is cb.pack v1 and cannot adopt a cover artifact. | n/a — no asset | no asset shipped | n/a |
| Relationship and register map (schematic) | `bundled/packs/japanese-affection-context-l0/content/relationship-map.png` | Deterministic geometry drawn by `bundled/packs/build_demo_packs.py`; no third-party imagery | `CC0-1.0`, declared per artifact in `pack.json` → `license.per_artifact[]` | yes, 6,948 bytes | `8fb84ad3d7797f6b11febd8510b4e2fb5f17be3ed573fd31dcb8fb9468f1093d` |
| Narration of the polite first-confession line | `bundled/packs/japanese-affection-context-l0/content/narration-polite-confession.mp3` | **Kokoro-82M** (`hexgrad/Kokoro-82M`, revision `f3ff3571791e39611d31c381e3a41a3af07b4987`), voice `jf_alpha`, Apache-2.0 model weights, run offline with the `kokoro` package (Apache-2.0). No human speaker. | `Apache-2.0` (model licence; the clip is model output) | yes, 22,272 bytes | `dea7f196f147958a536b41c6ee8f2ff51558f56a74e7f4e8ab86f580db971349` |
| Japanese pack teaching text | `bundled/packs/japanese-affection-context-l0/content/section-0{1,2,3}-*.md`, `source-notes.md` | Original Coursebook-authored prose | pack `license` is `unspecified` with `local_only` redistribution — the operator has not chosen a redistribution licence | yes | per-file sha256 in `pack.json` → `files[]` |
| Parent measurement pack | `bundled/packs/parent-measurement-practice/` (3 files, 3,479 expanded bytes) | Original Coursebook-authored prose; no image, no audio | `unspecified`, `local_only` | yes | per-file sha256 in `pack.json` → `files[]` (pack `content_hash` `sha256:92ee4a79c2ea469c6567ccadbe9fc55290fdd576f28091546372aa87ac36db3d`) |
| Technical demo pack | `bundled/packs/technical-demo-pack/` (4 files, 14,392 expanded bytes) | Original Coursebook-authored prose plus its host-composed cover plate, about this repository's own pack contract | `CC0-1.0` | yes | per-file sha256 in `pack.json` → `files[]` (pack `content_hash` `sha256:01ec0a0b756e0a85cbb8ffb6cadb0d91cfd9aa8e9a3da6017b634cad29905a33`) |

Hashes above were printed by `sha256sum` on the tree this document was written from, and the
manifest-declared hashes beside each file are the ones `coursebook/workshop.py` re-verifies on every
catalogue read; a drifted file is refused rather than rendered.

## The cover lane, in full

- **Icons are unchanged.** `sdk.Codicon` only, 16px, `currentColor`; no icon font and no second
  icon family. A cover plate is content/brand ornament, not UI grammar, and it is the only
  illustration lane in the product.
- **One lane: Press Plate.** One broad flat form, one hard-edged `lamp-soft` flood, one `lamp` band
  full bleed at a fixed y, one heavy ink rule. Five flat inks, no text, no object, no symbol. The
  full brief, the prompts (P1–P3) for the model lane, the finish recipe and the acceptance block are
  in `docs/ART-DIRECTION-COVERS.md`.
- **Licence gate.** Only CC0, MIT, ISC, Apache-2.0, BSD, or CC BY 4.0 with visible attribution may
  enter the lane. Both shipped masters and both crops are `CC0-1.0` and are our own work, so there
  is no upstream creator, upstream commit or upstream URL to record; the record is the generator,
  the palette it draws from, the committed bytes and the hash above.
- **Coherence gate.** One press, one palette, one band y, one type system. The plate carries no text
  at all; the pack title is type rendered by the app beside it, and the plate keeps the paper ground
  in both UI modes because it is a lit page.
- **Accuracy gate.** Every cover is labelled on the surface: the caption reads “Pack visual —
  generated plate; not a diagram of the course.”, and the file record carries a human-written text
  equivalent. No cover carries a measurement, torque, dosage, wiring value, field name or other
  safety-critical fact, and none is labelled a photograph of a procedure. The Japanese pack's
  factual visual remains the deterministic relationship map, which is a schematic, not the cover.
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
- **No model-generated hero ships here.** The art direction measured the host image pipeline, found
  it ignores "exactly five flat inks" and invents objects, and recommended Press Plate — material,
  not depiction. These plates are printed by the pack builder to that same brief and acceptance
  block, so nothing in this tree claims a model made them. The prompts P1–P3 are recorded verbatim
  in `docs/ART-DIRECTION-COVERS.md` for a host that does expose `image_generate`.
- **The parent pack keeps the typographic cover on purpose.** It is cb.pack v1, the repository's
  only v1 fixture, and a v1 document may not carry `media[]`, so an imported copy can never adopt a
  cover artifact. Rather than convert the fixture and lose the v1 compatibility gate, its cover is
  the composed typographic plate. That is a fallback, and it is stated as one.
- **No external asset was used, so no external licence is relied on** beyond the model licence
  named above for the one generated audio fixture.
