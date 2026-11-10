# A3 pack covers — the workshop kit

Card: CP-012 (`wt/cp-012-covers`). Owner `easel`, reviewer `quill`.
Binds: the three bundled packs. The four demo course covers are **not** drawn here — they come from
the product's own world pipeline (CP-015/CP-016) and must pass the same swap check there.
Style authority: `docs/concept-parity/ART-BIBLE.md` (opaque gouache, one upper-left key light, one
warm-brown line, one paper). Subject authority: `docs/GM-SUBJECT-WORLDS.md` (grammar, motifs,
`must never become`, the GM §0 palette ban).
Machine record: `audit/cp012-covers/provenance.json` (hashes, sizes, prompts, pipeline).
Measurement records: `audit/cp012-covers/motif-retention.json`, `audit/cp012-covers/motif-map.png`.
Judgement records: `audit/cp012-covers/swap-check.json`, `audit/cp012-covers/vision.json`.
Review artifact: `docs/concept-parity/covers/cover-contact-sheet.png` (unsigned).

## Round 2 — what the review changed

Round 1 was rejected on two measured contract breaches. Both are closed here, and the art was
regenerated rather than re-labelled.

1. **Forbidden pigment (plum).** `docs/GM-SUBJECT-WORLDS.md` §0 bans `ochre`, `coral` and `plum` in
   art; `ART-BIBLE.md` §2 has no pigment for plum. Round 1's parent plate asked for a "muted plum
   #6a3e74" cloth and shipped **7.08 % of its frame** in the plum hue band, and the round-1 acceptance
   script had a `HUE_PLUM = (270, 340)` allowance that let it pass — the artifact was defining its own
   oracle. Round 2: the plum is gone from the prompt, the art and the pipeline; `HUE_PLUM` is deleted;
   the accept script now fails any plate with more than **0.5 % of the frame** in a state hue. The
   parent's cloth is now **field green `#2f6047`**, a pigment the ART-BIBLE table binds to cloth.
   Measured on the shipped frames: plum hue 0.0004 % / 0.0004 % / 0.0029 %; ochre ≤ 0.0079 %; coral
   0 %. The round-1 acceptance script's per-pack loop also skipped every pack after the first
   failure; that is fixed (it now only skips a pack whose files are missing).
   *Why ochre and coral are gated by pigment distance, not by hue family:* lamp gold `#e8a93a` is hue
   39 and ochre `#7b4b0a` is hue 36 — a broad "ochre hue family" would ban the lamp token the kit
   needs. Ochre, coral and plum are therefore gated at **ΔE*ab ≤ 12** from their exact values, with
   the plum hue band kept as a second, independent leg because no legitimate plate pigment lives in
   hue 270–340.
2. **The 4:5 crop dropped the subject.** Round 1 shipped the full 16:9 raw as the master; the
   mechanical 640x800 centre crop kept only **46 of the lantern's 256 ink columns (18 %)** and
   severed it at the frame edge, and the parent crop lost most of the oranges and the linen. Round 1's
   vision note claimed the crop "cuts only frame elements" — false, and retracted in `vision.json`.
   Round 2 composes a **square plate** and lets `scripts/cp012-cover-prep.py` fit its measured ink box
   inside the 4:5 window with 16 px of paper to spare, then sets it on the 1200x800 sheet. The crop
   stays mechanical and single: the 4:5 file is still the master's exact centre crop (AE = 0), and
   every declared motif now keeps **100 %** of its painted ink inside it.
3. **Minor.** The round-1 accept docstring advertised a "left 4 % of the frame stays clear of the
   form" check that was never implemented. The check does not belong to a painted plate (it is the
   H-197 Press Plate clearance), so the claim is removed from the docstring and from `vision.json`
   V6 rather than implemented.

## Verdict up front

Three plates were generated again for round 2, one per bundled pack; the first round-2 attempts were
used for two of the three packs and the technical plate was regenerated once for a tighter
composition. All three are textless, sit on the same measured paper, share one saturation temper and
one line family, and each carries subject motifs whose `mark` sets are pairwise disjoint. The machine
half is `python3 scripts/cp012-cover-accept.py` (**88 checks, exit 0**). The human half is the contact
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

| Pack | Grammar | Accent | Motifs (mark) | Plate px | Master sha256 (16) |
|---|---|---|---|---|---|
| `japanese-affection-context-l0` | `field_atlas` (lantern variant) | none (see note) | lantern, noren, counter | 800 | `66aaf53939cfac93` |
| `parent-measurement-practice` | `kitchen_table` | `field` (linen `#2f6047`) | jug, bowl, oranges, table | 630 | `5f57005fb58b3d72` |
| `technical-demo-pack` | `workshop_manual` | none | manual, sheets, bench | 686 | `36927aabcffa5d8f` |

**Accent note.** `GM-SUBJECT-WORLDS.md` §1 permits a `lamp` accent on the Japanese world; the round-2
plate paints the lantern in paper-cream and ships **no lamp pigment** (measured: no pixel within ΔE 12
of `#e8a93a`), so the cover declares **no accent** rather than claiming one it does not carry. The
lit-lantern accent stays with the world hero plate (CP-016). `GM §2` sets the workshop grammar's accent
to none, and the technical plate measures warm paper/brown only.

Composition, all three: a square painted plate centred on the contract paper, the mass on a
table/counter/bench plane across the lower part, and the upper-right quadrant quiet — measured
**57.8 % / 92.4 % / 89.5 %** paper, against the 35 % floor `GM-SUBJECT-WORLDS.md` §1 sets for the type
field. The plates are textless; the cover window's title and subject are DOM text.

Why each motif is the course's own and not a stock scene:

- **Japanese** — the pack is a café-register dialogue. The lantern is the district, the noren the
  threshold, the counter with its stools and cup the situation and the act being practised. It is not
  a Japan skin: no torii, no temple, no kana, no shop sign.
- **Parent measurement** — the learner page is "read the jug, double the recipe". The jug is drawn
  **blank**: no graduations, no numbers, no scale. The bowl, the oranges and the field-green linen
  carry the fruit drink and the parent identity. No finished dish implies a tested recipe.
- **Technical** — the pack teaches "read the manifest before you install". The open manual with blank
  pages is the manifest as authority; the sheet stack is `files[]`; the bench edge is orientation
  only. No step list, no table of values, no barcode, no version label. The sealed parcel the prompt
  asks for is **not declared as a motif**: the round-2 plate merges it into the manual's mass and no
  vision pass was available to place its zone honestly (see *Evidence*), so the declaration stops at
  what the pixels can be checked against.

## The 4:5 crop — measured, motif by motif

The master is 3:2. The 4:5 file is its **640x800 centre crop**, pixel-identical (AE = 0). For each
declared motif zone, `scripts/cp012-motif-map.py` measures the painted ink inside the zone and how
much of it survives the crop; `scripts/cp012-cover-accept.py` fails anything under 60 %.

| Pack | Motif | Painted px in zone | Kept by the 4:5 crop |
|---|---|---|---|
| japanese | lantern | 23,041 | 100 % |
| japanese | noren | 66,509 | 100 % |
| japanese | counter | 142,452 | 100 % |
| parent | jug | 29,316 | 100 % |
| parent | bowl | 48,801 | 100 % |
| parent | oranges | 43,475 | 100 % |
| parent | table | 38,843 | 100 % |
| technical | manual | 66,263 | 100 % |
| technical | sheets | 20,608 | 100 % |
| technical | bench | 32,231 | 100 % |

`audit/cp012-covers/motif-map.png` draws those zones on the shipped masters with the crop edges ruled.
It is the artifact to check a zone against the object it names.

## Anti-generic swap check

`docs/GM-SUBJECT-WORLDS.md` §5: swapping the caption to an unrelated subject must change the grammar
**and** at least two motifs, and the swap must be rejected. Full matrix, with the reason for every
row, is in `audit/cp012-covers/swap-check.json`. Each cover is tested against both sibling covers
and one further world (head gasket / sourdough); all nine swaps are `rejected`.

The machine part is not a re-statement of that judgement: it proves the three `mark` sets are
**pairwise disjoint**, so no caption can be swapped between two shipped covers and survive on shared
marks. The judgement part (does the plate still read as the other subject?) is the reviewer's.

## How each plate was made

1. Text prompt per pack from the ART-BIBLE template family, recorded verbatim with a sha256 in
   `audit/cp012-covers/prompts.json`. The prompt now names only GM §0 pigments (paper, ink, cream,
   lamp, field) and asks for a square plate composed inside the central 76 % of its width.
2. Generated through the host image tool (`image_generate`), which answers through the nous image
   gateway and serves media from `v3b.fal.media`. Round 2 for all three.
3. `scripts/cp012-cover-prep.py`: one shared temper `-modulate 97,78,100`, then a corner paper match
   scaled onto the contract's `card-stock` `#f7f1e4` (gain clamped 0.90–1.10), then the square plate
   is scaled so its **measured ink box** fits the 640x800 crop window less 16 px, and centred on a
   1200x800 sheet of `#f7f1e4`. Plate sizes: 800 px (japanese), 630 px (parent), 686 px (technical) —
   the parent and technical plates are smaller because their table/bench plane runs wide, and the fit
   step refuses to let a painted mark cross the 4:5 edge.
4. The 4:5 file is a 640x800 centre crop of the master with no resampling — verified pixel-identical
   by `magick compare -metric AE` (AE = 0), so it cannot be a second drawing. The 3:2 export is the
   master byte for byte.
5. Checks: `scripts/cp012-cover-accept.py` — size, mode, crop identity, paper, palette family, no
   black contour, **no state hue**, **per-motif 4:5 retention**, quiet field, tesseract textless,
   provenance hashes, kit motif disjointness. Plus `tests/test_cp012_covers.py` (19 tests), which
   re-derives the state-hue and retention results from the shipped bytes rather than importing the
   acceptance script's verdict, and includes two negative controls that run the real script on a
   temporary copy of the tree — a painted plum patch must fail, and a motif zone moved outside the
   crop window must fail.

Paper after the pipeline measures **#f7f1e4** on all three (corner delta 0). The temper is one value
for the whole kit — no plate can drift in saturation alone.

## Provenance rows

Provider: host `image_generate` → nous image gateway → `v3b.fal.media`. **Model id: not reported by
the host tool** (recorded as unknown, not guessed — the same gap A1 records). Generated 2026-11-10.

| Pack | prompt sha256 (16) | chars | raw | raw bytes | media URL |
|---|---|---|---|---|---|
| japanese | `956785080a5af779` | 1625 | `audit/cp012-covers/raw/japanese-sq.png` | 1,530,965 | `https://v3b.fal.media/files/b/0ab1eded/nidnNEIUfI7rdXbqWiLkK_YybM3OX5.png` |
| parent | `fc2c260fa2a6c4f1` | 1696 | `audit/cp012-covers/raw/parent-sq.png` | 1,552,258 | `https://v3b.fal.media/files/b/0ab1eded/HlRGCkxFwbhNYbf-_yu_h_Sqt9z03h.png` |
| technical | `7f2323c2b42907cf` | 1721 | `audit/cp012-covers/raw/technical-sq.png` | 1,522,566 | `https://v3b.fal.media/files/b/0ab1eded/d-UqXS8DNxUoCe0dQzUuy_K1dmQ7Nb.png` |

The round-1 raws (`*-r1.png`) are kept as history and listed as `superseded` in `prompts.json` with the
reason each was replaced. Full hashes, byte counts and per-file rows:
`audit/cp012-covers/provenance.json`. Media URLs are the provider's returned URLs; no plate was
re-hosted.

## Files

| Pack | File | Bytes | sha256 (16) |
|---|---|---|---|
| japanese | `japanese-master-1200x800.png` | 842,355 | `66aaf53939cfac93` |
| japanese | `japanese-crop-3x2-1200x800.png` | 842,355 | `66aaf53939cfac93` |
| japanese | `japanese-crop-4x5-640x800.png` | 693,974 | `d02801477cdfdd8d` |
| parent | `parent-master-1200x800.png` | 555,452 | `5f57005fb58b3d72` |
| parent | `parent-crop-3x2-1200x800.png` | 555,452 | `5f57005fb58b3d72` |
| parent | `parent-crop-4x5-640x800.png` | 538,942 | `66d485c8c4460feb` |
| technical | `technical-master-1200x800.png` | 617,107 | `36927aabcffa5d8f` |
| technical | `technical-crop-3x2-1200x800.png` | 617,107 | `36927aabcffa5d8f` |
| technical | `technical-crop-4x5-640x800.png` | 561,177 | `4a03eaa7051318d8` |

All nine are RGB, no alpha. The 3:2 export is byte-identical to the master by construction; a consumer
that needs one file uses the master.

## Evidence spend

No UI frame is captured on this card: the deliverable is a file set, so `scripts/cp-capture.mjs`
does not apply. The frames that exist are the raws, the masters, the 4:5 crops, the contact sheet and
the motif map. There is **no baseline matrix** of the old press plates and no re-capture of unchanged
cells.

**No round-2 vision pass exists.** Three attempts — the three masters in one frame, the three 4:5 crops
in one frame, and the motif map — each returned HTTP 429 ("model temporarily at capacity upstream").
Nothing in this packet is a round-2 vision claim, and no defect was closed on a vision read: the two
round-2 fixes were verified by measurement first. The single round-2 exploratory read that did return
was refuted by pixels (it reported a painted border and a paper step that do not exist), and that
refutation is recorded in `vision.json` so the next reader does not inherit it.

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
6. **Plate scale differs across the kit.** 800 / 630 / 686 px, because the fit step keeps every
   painted mark inside the 4:5 window and the parent and technical planes run wide. Same light, line
   and paper; not the same plate footprint.
7. **The technical sealed parcel is not declared.** It was asked for and may be painted inside the
   manual's mass, but with no vision pass available its zone could not be placed honestly, so the
   declaration stops at manual/sheets/bench.
8. **Motif zones are declared regions, not segmentation.** Each zone is a rectangle measured against
   the painted ink density map; the retention check is real, but a zone is a reviewable claim, not a
   per-object segmentation. `motif-map.png` is the artifact to audit it.
9. **Old lane still shipped.** `bundled/packs/*/content/cover-*.png` are still the H-197 press
   plates. Until CP-014, the shelf shows those, and this kit is not what the learner sees.

## What this document does not claim

- No human illustrator, native-speaker, accessibility or colour-professional review exists.
- A matching hash is not a rights verdict and not a quality verdict. The plates are model output; the
  provider terms and the repository's licence position for model-generated art apply
  (`docs/ASSET-PROVENANCE.md`).
- No claim that the art depicts the learner's own city, kitchen or workshop.
