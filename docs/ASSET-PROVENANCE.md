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
authorship rather than a licence guess. CP-014 keeps that Press Plate lane as the composed
typographic fallback for any pack that declares no cover. The three bundled packs now ship the
approved CP-012 **painted** plate instead, declared as role `cover` with its own provenance row.

The one third-party *production* step reachable from the surface is the bundled Japanese pack's
narration clip: it is synthetic model output, not a recording, and it is declared as such in the
pack manifest, the pack's `content_notes`, its contributors list and its per-artifact attribution.

## Every asset the surface can show

| asset | path | produced by | licence | bundled | sha256 |
| --- | --- | --- | --- | --- | --- |
| Japanese pack cover, 3:2 master | `bundled/packs/japanese-affection-context-l0/content/cover-3x2.png` | **Painted plate (CP-012)**, generated through the host `image_generate` tool (nous image gateway, media served from `v3b.fal.media`) on 2026-11-10; model id not reported by the host. Copied byte for byte into the pack by `bundled/packs/build_bundled_packs.py::painted_cover("japanese")`. Decorative illustration: cafe counter, lantern, noren; no text, no register fact. Prompt and provenance: `docs/concept-parity/COVERS.md`, `audit/cp012-covers/provenance.json`. | `CC-BY-4.0`, declared per artifact in `pack.json` → `license.per_artifact[]`; pack redistribution `allowed`. Attribution: "Model-generated cover produced for this pack; no third-party source or media." | yes, 842,355 bytes | `66aaf53939cfac93cce0aec7ba33c8b0cfd46360d9aaacd3c4e71a546dd62285` |
| Japanese pack cover, 4:5 crop | `bundled/packs/japanese-affection-context-l0/content/cover-4x5.png` | The master's exact 640x800 centre crop (AE = 0), never a second drawing; recorded in `audit/cp012-covers/provenance.json` | `CC-BY-4.0`, declared per artifact; pack redistribution `allowed` | yes, 693,974 bytes | `d02801477cdfdd8d922f86fdd767ef09819b697268d3ca8cad2e118ed8a77b19` |
| Parent pack cover, 3:2 master | `bundled/packs/parent-measurement-practice/content/cover-3x2.png` | **Painted plate (CP-012)**, same host pipeline and gap; copied byte for byte by `painted_cover("parent")`. Decorative illustration: blank jug, bowl, oranges, field-green linen; no quantity, no text. | `CC-BY-4.0`, declared per artifact; pack redistribution `allowed`. Attribution: "Model-generated cover produced for this pack; no third-party source or media." | yes, 555,452 bytes | `5f57005fb58b3d72f1e377293671e9eb58cff185ee4d05b204bcef4c00798301` |
| Parent pack cover, 4:5 crop | `bundled/packs/parent-measurement-practice/content/cover-4x5.png` | The master's exact 640x800 centre crop (AE = 0) | `CC-BY-4.0`, declared per artifact; pack redistribution `allowed` | yes, 538,942 bytes | `66d485c8c4460febc7f3a8c43d31a183a0056f5677c4ce82bba41fee434d8da1` |
| Technical pack cover, 3:2 master | `bundled/packs/technical-pack-literacy/content/cover-3x2.png` | **Painted plate (CP-012)**, same host pipeline and gap; copied byte for byte by `painted_cover("technical")`. Decorative illustration: blank open manual on a bench edge with loose sheets; no field, count or text. | `CC-BY-4.0`, declared per artifact; pack redistribution `allowed`. Attribution: "Model-generated cover produced for this pack; no third-party source or media." | yes, 617,107 bytes | `36927aabcffa5d8ff49a2c553aa6a9814e9820c337835f9e7709460a048fc85f` |
| Technical pack cover, 4:5 crop | `bundled/packs/technical-pack-literacy/content/cover-4x5.png` | The master's exact 640x800 centre crop (AE = 0) | `CC-BY-4.0`, declared per artifact; pack redistribution `allowed` | yes, 561,177 bytes | `4a03eaa7051318d8ab4f565a39bc8a42d4efa4073d5a91bb6fae856d54c991ff` |
| Relationship and register map (schematic) | `bundled/packs/japanese-affection-context-l0/content/relationship-map.png` | Deterministic geometry drawn by `bundled/packs/build_bundled_packs.py`; no third-party imagery | `CC0-1.0`, declared per artifact in `pack.json` → `license.per_artifact[]` | yes, 6,948 bytes | `8fb84ad3d7797f6b11febd8510b4e2fb5f17be3ed573fd31dcb8fb9468f1093d` |
| Narration of the polite first-confession line | `bundled/packs/japanese-affection-context-l0/content/narration-polite-confession.mp3` | **Kokoro-82M** (`hexgrad/Kokoro-82M`, revision `f3ff3571791e39611d31c381e3a41a3af07b4987`), voice `jf_alpha`, Apache-2.0 model weights, run offline with the `kokoro` package (Apache-2.0). No human speaker. | `Apache-2.0` (model licence; the clip is model output) | yes, 22,272 bytes | `dea7f196f147958a536b41c6ee8f2ff51558f56a74e7f4e8ab86f580db971349` |
| Japanese pack teaching text | `bundled/packs/japanese-affection-context-l0/content/section-0{1,2,3}-*.md`, `source-notes.md` | Original Coursebook-authored prose | pack `license` is `CC-BY-4.0` with `allowed` redistribution under the operator-directed store release of 2026-11-10 | yes | per-file sha256 in `pack.json` → `files[]` (pack `content_hash` `sha256:532a6cda1b9145b0b5a41957afe9c3a5215d7396493a41f5103835395f83da60`) |
| Parent measurement pack | `bundled/packs/parent-measurement-practice/` (5 files, 1,097,873 expanded bytes: 3 prose + 2 cover files) | Original Coursebook-authored prose plus the CP-012 painted cover; no third-party text, image or audio | `CC-BY-4.0`, `allowed`; cover records are `CC-BY-4.0` | yes | per-file sha256 in `pack.json` → `files[]` (pack `content_hash` `sha256:eac9c5c0ca771097dc33dd61d73a3fb26373c32c7793816ba7f527ab79775747`) |
| Technical pack | `bundled/packs/technical-pack-literacy/` (5 files, 1,182,291 expanded bytes: 3 prose + 2 cover files) | Original Coursebook-authored prose plus the CP-012 painted cover, about this repository's own pack contract | `CC-BY-4.0`, `allowed`; cover records are `CC-BY-4.0` | yes | per-file sha256 in `pack.json` → `files[]` (pack `content_hash` `sha256:130a679dd6522aec06e40ccc3a63dc9f3d2d56cfc04927ad5a6653b762afbbb5`) |

Hashes above were printed by `sha256sum` on the tree this document was written from, and the
manifest-declared hashes beside each file are the ones `coursebook/workshop.py` re-verifies on every
catalogue read; a drifted file is refused rather than rendered.

## The cover lane, in full

> **Second lane added by the v3 concept-parity direction (CP-012, `wt/cp-012-covers`), integrated
> by CP-014.** The paragraphs below describe the H-197 Press Plate lane, which now remains the
> composed typographic fallback. CP-012 draws the **painted** lane `docs/concept-parity/ART-BIBLE.md`
> §1 defines — opaque gouache, model-generated, one upper-left light, warm-brown line — for the three
> bundled packs; the files are in `assets/art/covers/`, the provenance rows are in
> `docs/concept-parity/COVERS.md`, and CP-014 copies each approved plate into its pack byte for byte
> as role `cover`. The painted plates carry only the pigments `docs/GM-SUBJECT-WORLDS.md` §0 allows
> (paper, ink, cream, lamp, field); the state hues ochre, coral and plum are absent by measurement,
> and a shipped-plate gate enforces it.

- **Icons are unchanged.** `sdk.Codicon` only, 16px, `currentColor`; no icon font and no second
  icon family. A cover plate is content/brand ornament, not UI grammar, and it is the only
  illustration lane in the product.
- **One lane: Press Plate.** One broad flat form, one hard-edged `lamp-soft` flood, one `lamp` band
  full bleed at a fixed y, one heavy ink rule. Five flat inks, no text, no object, no symbol. The
  full brief, the prompts (P1–P3) for the model lane, the finish recipe and the acceptance block are
  in `docs/ART-DIRECTION-COVERS.md`.
- **Licence gate.** The Press Plate lane allowed only CC0, MIT, ISC, Apache-2.0, BSD, or CC BY 4.0
  with visible attribution. The CP-012 painted plates are model output: their per-artifact record is
  `CC-BY-4.0` with the attribution "Model-generated cover produced for this pack; no third-party
  source or media.", and the packs declare `redistribution: allowed` under the operator-directed
  store release recorded on 2026-11-10. A future pack without that direction stays `local_only`.
- **Coherence gate.** One plate family, one light, one line family, one paper. The plate carries no text
  at all; the pack title is type rendered by the app beside it, and the plate keeps the paper ground
  in both UI modes because it is a lit page.
- **Accuracy gate.** Every cover is labelled on the surface: the caption reads “Cover plate — painted
  illustration, not a diagram of the course.”, and the file record carries a human-written text
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
  named above for the one generated audio fixture; the model-produced cover plates are redistributed
  under the packs' own CC-BY-4.0.
