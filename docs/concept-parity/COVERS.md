# A3 pack covers — the workshop kit

Card: CP-012 (`wt/cp-012-covers`). Owner `easel`, reviewer `quill`.
Binds: the three bundled packs. The four demo course covers are **not** drawn here — they come from
the product's own world pipeline (CP-015/CP-016) and must pass the same swap check there.
Style authority: `docs/concept-parity/ART-BIBLE.md` (opaque gouache, one upper-left key light, one
warm-brown line, one paper). Subject authority: `docs/GM-SUBJECT-WORLDS.md` (grammar, motifs,
`must never become`).
Machine record: `audit/cp012-covers/provenance.json` (hashes, sizes, prompts).
Judgement record: `audit/cp012-covers/vision.json`, `audit/cp012-covers/swap-check.json`.
Review artifact: `docs/concept-parity/covers/cover-contact-sheet.png` (unsigned).

## Verdict up front

Three plates were generated, one per bundled pack, on the first round each; none was rejected. All
three are textless, sit on the same measured paper, share one saturation temper and one line family,
and each carries at least four subject motifs whose `mark` sets are pairwise disjoint. The machine
half is `python3 scripts/cp012-cover-accept.py` (67 checks, exit 0). The human half is the contact
sheet, which is **submitted for owner approval and is not yet signed**.

The four demo course covers are out of scope by the card and are absent from this kit.

## The lane this belongs to

Two cover lanes exist in this repository and they are not interchangeable.

- **Press Plate** (`docs/ART-DIRECTION-COVERS.md`, H-197): a deterministic, host-composed flat
  field. No objects, no symbols. It is what `bundled/packs/*/content/cover-*.png` carry today.
- **Painted plate** (`docs/concept-parity/ART-BIBLE.md` §1): model-generated opaque gouache, textless,
  for character and orientation only. CP-012's plan row A3 selects this lane for pack covers: "one
  painted gouache kit, same light (upper left) and line weight; subject motifs from
  `docs/GM-SUBJECT-WORLDS.md`".

This card therefore draws the painted lane. It **does not** replace the pack files; CP-014 integrates
an approved cover into each pack as role `cover` and re-hashes the catalogue. Until CP-014 lands, the
packs keep their press plates and nothing here claims otherwise.

## The kit

| Pack | Grammar | Accent | Motifs (mark) | Master sha256 (16) |
|---|---|---|---|---|
| `japanese-affection-context-l0` | `field_atlas` (lantern variant) | `lamp` | lantern, noren, stools, cup | `4ba7531f0aa26033` |
| `parent-measurement-practice` | `kitchen_table` | `plum` | jug, bowl, oranges, table | `fd309a4367392f3d` |
| `technical-demo-pack` | `workshop_manual` | none | manual, parcel, sheets, bench | `3f89e666ed9ec1c9` |

Composition, all three: the mass sits in the middle of the frame on a table/counter plane across the
lower third, and the upper-right quadrant is quiet paper — measured 78 %, 95 % and 92 % paper
respectively, against the 35 % floor `docs/GM-SUBJECT-WORLDS.md` sets for the type field. The plates
are textless; the cover window's title and subject are DOM text.

Why each motif is the course's own and not a stock scene:

- **Japanese** — the pack is a café-register dialogue. The lantern is the district, the noren the
  threshold, the stools the situation, the cup the act being practised. It is not a Japan skin: no
  torii, no temple, no kana, no shop sign.
- **Parent measurement** — the learner page is "read the jug, double the recipe". The jug is drawn
  **blank**: no graduations, no numbers, no scale. The bowl, the oranges and the plum linen carry the
  fruit drink and the parent identity. No finished dish implies a tested recipe.
- **Technical** — the pack teaches "read the manifest before you install". The open manual with blank
  pages is the manifest as authority, the sealed parcel is the pack as a closed object, the sheet
  stack is `files[]`. No step list, no table of values, no barcode, no version label.

## Anti-generic swap check

`docs/GM-SUBJECT-WORLDS.md` §5: swapping the caption to an unrelated subject must change the grammar
**and** at least two motifs, and the swap must be rejected. Full matrix, with the reason for every
row, is in `audit/cp012-covers/swap-check.json`. Each cover is tested against both sibling covers
and one further world (head gasket / sourdough); all nine swaps are `rejected`.

The machine part is not a re-statement of that judgement: it proves the three `mark` sets are
**pairwise disjoint**, so no caption can be swapped between two shipped covers and survive on shared
marks. The judgement part (does the plate still read as the other subject?) is the reviewer's, and
`audit/cp012-covers/vision.json` records what the vision passes actually reported.

## How each plate was made

1. Text prompt per pack from the ART-BIBLE template family, recorded verbatim with a sha256 in
   `audit/cp012-covers/prompts.json`.
2. Generated through the host image tool (`image_generate`), which answers through the nous image
   gateway and serves media from `v3b.fal.media`. Round 1 for all three.
3. `scripts/cp012-cover-prep.py`: one shared temper `-modulate 97,78,100`, then a corner paper match
   scaled onto the contract's `card-stock` `#f7f1e4` (gain clamped 0.90–1.10), then a centre crop to
   864x576 and a Lanczos resize to the 1200x800 master (1.389x, inside the 1.5x ceiling).
4. The 4:5 file is a 640x800 centre crop of the master with no resampling — verified pixel-identical
   by `magick compare -metric AE` (AE = 0), so it cannot be a second drawing.
5. Checks: `scripts/cp012-cover-accept.py` (size, mode, crop identity, paper, palette family, no black
   contour, quiet field, tesseract textless, provenance hashes, kit motif disjointness) and the
   vision pass in `vision.json`.

Paper after the pipeline measures **#f7f1e4** on all three (247/246, 241/240, 228; deltas 0–1). The
temper is one value for the whole kit — no plate can drift in saturation alone.

## Provenance rows

Provider: host `image_generate` → nous image gateway → `v3b.fal.media`. **Model id: not reported by
the host tool** (recorded as unknown, not guessed — the same gap A1 records). Generated 2026-11-10.

| Pack | prompt sha256 (16) | raw | raw bytes | media URL |
|---|---|---|---|---|
| japanese | `94dba9083ad60b16` | `audit/cp012-covers/raw/japanese-r1.png` | 891,768 | `https://v3b.fal.media/files/b/0ab1eced/gBNvs9EFPBcdqpEfkidv5_uBaT3VC1.png` |
| parent | `c16c84276b1ac403` | `audit/cp012-covers/raw/parent-r1.png` | 541,890 | `https://v3b.fal.media/files/b/0ab1eced/nX5JgSP7f5d2m8sTxmdmm_AebGU7QI.png` |
| technical | `64dbe0be0717c1d9` | `audit/cp012-covers/raw/technical-r1.png` | 813,364 | `https://v3b.fal.media/files/b/0ab1eced/pMB756g4VFjeTuQMakG2m_eEHY880b.png` |

Full hashes, byte counts and per-file rows: `audit/cp012-covers/provenance.json`. Media URLs are the
provider's returned URLs; no plate was re-hosted.

## Files

| Pack | File | Bytes | sha256 (16) |
|---|---|---|---|
| japanese | `japanese-master-1200x800.png` | 1,016,619 | `4ba7531f0aa26033` |
| japanese | `japanese-crop-3x2-1200x800.png` | 1,016,619 | `4ba7531f0aa26033` |
| japanese | `japanese-crop-4x5-640x800.png` | 572,506 | `5dd7476cb83d798b` |
| parent | `parent-master-1200x800.png` | 626,641 | `fd309a4367392f3d` |
| parent | `parent-crop-3x2-1200x800.png` | 626,641 | `fd309a4367392f3d` |
| parent | `parent-crop-4x5-640x800.png` | 379,700 | `8371a5892b3b7eb8` |
| technical | `technical-master-1200x800.png` | 921,824 | `3f89e666ed9ec1c9` |
| technical | `technical-crop-3x2-1200x800.png` | 921,824 | `3f89e666ed9ec1c9` |
| technical | `technical-crop-4x5-640x800.png` | 490,931 | `e59c74b4f9b4b182` |

All nine are RGB, no alpha. The 3:2 export is byte-identical to the master by construction; a consumer
that needs one file uses the master.

## Evidence spend

No UI frame is captured on this card: the deliverable is a file set, so `scripts/cp-capture.mjs`
does not apply. The frames that exist are the raws, the masters, the 4:5 crops and the contact sheet.
There is **no baseline matrix** of the old press plates and no re-capture of unchanged cells.
Vision was run once per frame family while the kit was being built (raws, masters, 4:5 crops, left
strips, contact sheet), all recorded in `audit/cp012-covers/vision.json`; after the operator's spend
guard was raised mid-run, no further pass was taken, and every acceptance claim is a measurement from
`scripts/cp012-cover-accept.py`, not a second look.

## Known gaps

1. **No model id.** The host tool does not return one. Closing this needs the host to name the model
   or an operator to record it in `hermes config`.
2. **No owner signature.** The contact sheet is submitted for approval. The plates were generated
   before that approval, which is the order the A1 gate already records as a deviation
   (`OI-2` / `D-CP010-A`); if the owner rejects a plate it is regenerated (3-round budget), not kept.
3. **Not integrated into the packs.** CP-014 owns `bundled/packs/*` and the catalogue re-hash. This
   card ships files plus rows; it does not edit a pack.
4. **Shopped at 240 px only.** The card window cell was inspected at 240 px; no claim is made about
   64 px legibility, which no surface in v3 uses for a cover.
5. **The 4:5 crop is 640x800.** It is the master's exact centre crop at 1:1, not a larger portrait
   re-draw. A surface that needs a bigger 4:5 must be given a bigger master, not an upscale.
6. **Vision wording, corrected by measurement.** One vision pass called the contours "black". The
   pixel count refutes it (≤ 0.017 % near-black on any plate); the warm-brown line is what shipped.
7. **Old lane still shipped.** `bundled/packs/*/content/cover-*.png` are still the H-197 press
   plates. Until CP-014, the shelf shows those, and this kit is not what the learner sees.

## What this document does not claim

- No human illustrator, native-speaker, accessibility or colour-professional review exists.
- A matching hash is not a rights verdict and not a quality verdict. The plates are model output; the
  provider terms and the repository's licence position for model-generated art apply
  (`docs/ASSET-PROVENANCE.md`).
- No claim that the art depicts the learner's own city, kitchen or workshop.
