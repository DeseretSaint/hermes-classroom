# Visual kits

A visual kit is a **product asset**, not a prompt: it is curated once, reviewed once, and reused by
every course that selects its grammar. The registry is the manifest — a screen card reads
`kit.json`, it does not invent a path.

Contract: `docs/launch/VISUAL-QUALITY-PROGRAM.md` §3, `docs/launch/GAME-MODE-VISUAL-KIT.md` §3, and
the manifest shape in `docs/launch/VISUAL-ASSET-AUDIT.md` §5. Medium, palette and line are bound by
`docs/concept-parity/ART-BIBLE.md`.

## `field_atlas/` — kit version 2

| role | assets | origin |
| --- | --- | --- |
| `hero` | `hero/home-hero.png` 1344x768, plus `hero/home-hero@2x.png` 2688x1536 | generated |
| `cover` | one 4:5 640x800 and one 3:2 1200x800 per real Home course | generated, 4:5 derived by crop |
| `lesson_scene` | `lesson-scene/lesson-room.png` 1344x768, plus a 2688x1536 sibling | generated |
| `object` | the seven approved A5 blanks, 256 px | carried from `assets/art/objects/` |
| `fox` | the seven approved A1 poses at 256 px plus the model sheet at 512 px | carried from `assets/art/fox/` |
| `specimens` | `specimens/contact-sheet.png`, the owner's review sheet against `refs/home.png` and `refs/classroom.png` | drawn by ImageMagick |

Version 2 is the owner-directed rebuild. v1's contact sheet was rejected on 2026-11-11 as below
reference quality — a still-life hero on bare paper, sparse vignette covers, a flat lesson wall — so
v1 is retained under `rejected-v1/` as evidence and is **not** a consumer fallback. See
`rejected-v1/README.md` for what survived and what the rebuild replaced.

### The field-atlas grammar is a place

The v1 failure was a grammar error, not only a taste call: the hero prompt asked for a still life on
a bare-paper field, while the grammar is a *place* — a street or cafe of paper lanterns with depth.
Version 2 is therefore built on three rules:

1. **Generated against the reference, never from text alone.** Every plate was called with
   `reference_image_urls` pointing at `docs/concept-parity/refs/home.png` (hero, covers) or
   `refs/classroom.png` (lesson scene). The reference used is recorded per plate.
2. **Full-bleed places in three depth planes.** Foreground props, a midground counter or bench, and
   an architectural background with a window or open street. No bare margin, no isolated prop on
   paper, no empty wall standing in for scenery. The hero's quiet field is painted sky, not blank
   parchment.
3. **Textless and unpainted by rule.** No lettering in any script, no emblem or mon on a lantern, no
   notice board, no dial, no label with a mark. Three of the ten v2 attempts were rejected for
   exactly these (a framed notice with pseudo-text, a glyph inside a gate plaque, a lantern crest);
   a fourth was rejected because default OCR read the window lattice as "8 3 -".

### Resolution and pipeline

The provider returns 2688x1536 through the host upscale pass, so every shipped size has a real 2x
source: the hero and lesson scene ship beside their 2688x1536 frames, and the covers are 2x their
render size **at the plate that ships** — the 4:5 plate is 640x800 against a 320x400 render, the 3:2
plate is 1200x800 against a 600x400 render, both exactly 2x. The 3:2 plate is cut from a 2304x1536
natural crop of the 2688x1536 frame; that crop is **1.92x the shipped plate and 3.84x the render**.
State the referent every time: 2x is the relationship between the shipped plate and what Home draws,
not between the natural crop and the render. Gate 2 reads natural-vs-rendered size out of provenance,
so a note that mixes the referents makes it fail a cover that actually passes. `--check` recomputes
all three ratios from the recorded sizes and refuses the two sentences that carried the wrong
referent.

One deterministic pipeline is recorded per plate: `-modulate 105,75,100` on the raw, then the crop
and resize, then `-clamp +level 4%,100%` as the ART-BIBLE §9 print-safety lift. The clamp matters:
the downscale filter's ringing goes negative, and without it the lift leaves pure black behind.

Carried assets are copies, and the manifest records the source path **and** the source sha256, so a
drift between the kit and the approved original is detectable. Generated assets record the provider,
the reference image, the verbatim prompt with its sha256, the provider media URL, the raw file's
sha256, the pipeline, the OCR result with every token and confidence, and the measured palette.

`generation_log` records every attempt, including the rejected ones, with the reason. Rejected bytes
are deleted, never kept as a fallback (`ART-BIBLE.md` §7.3). Every accepted row **of the current kit**
also carries the `raw_sha256` it consumed and the `produces` list of shipped plates it yields — a 4:5
cover is produced by its 3:2 master's accepted generation, so a derived plate still traces to a real
generation and is never counted as a generation attempt.

An accepted row from a superseded kit keeps its evidence — the provider media URL, the `raw_sha256`
it consumed, the reason it was accepted and then rejected on art — and `superseded_by`, but it names
**no** shipped path. Two accepted rows claiming the same shipped plate is a provenance contradiction:
the bytes came from one generation, and the next gate cannot tell which. `--check` enforces both
directions: a current-kit accepted row must produce something that ships, and a superseded accepted
row may not name any path that ships today.

The budget is the owner's: 33 attempts across both kits, at most four on any one asset within v2.
The ceiling is a checked claim in the manifest, not a narrative.

`fallbacks` names the chain a screen walks when a plate is absent. It never includes a Press Plate
pack cover (`UI-DECISIONS` D-006): a display cover falls back to the course's own approved master,
then to a textless material field. The judge asserts this, so the forbidden substitution cannot
return through a table edit.

## Judge

```sh
python3 scripts/vq002-kit-audit.py --write       # rewrite kit.json from the declarative table
python3 scripts/vq002-kit-audit.py --check       # recompute every claim
python3 scripts/vq002-kit-audit.py --calibrate   # prove the textless detector on real-text mockups
bash scripts/vq002-contact-sheet.sh              # rebuild the owner's sheet
bash scripts/vq002-kit-audit-selftest.sh         # mutation-test the judge itself
```

`--check` is the acceptance run. It recomputes each sha256, byte count and pixel size, re-reads the
real Home shelf from the coursebook database (never a proof HTML), proves every course has both cover
aspects, proves the hero is 1344x768 with a 2688x1536 source, proves the covers are 2x their render
size and that the 3:2 source note states the right referent (shipped plate vs render, not natural crop
vs render), measures the hero's quiet field against the contract ink, measures that no plate is out of
the warm palette outside the one ratified noren region, re-runs OCR and compares it with the recorded
tokens, checks the budget and the per-asset cap, refuses any fictional proof title, refuses a
fallback chain that names a pack cover, and requires every generated or derived plate to trace to
exactly one accepted generation row. Exit 0 means every claim in `kit.json` reproduces from the bytes
on disk.

The textless rule is calibrated, not guessed. OCR cannot tell painted pseudo-lettering from line art
— measured on this provider's output, a notice board of gibberish scored 7–54 % while a window
lattice scored 30–52 % — so the judge fails a plate that yields a token of three or more alphanumeric
characters at 60 % confidence or better, records every token it saw, and `--calibrate` proves the
rule catches the real UI strings on `refs/home.png` and `refs/classroom.png` (74–95 %). Painted
pseudo-lettering is caught by the recorded vision pass instead; both passes are in the manifest.

`--check` passing means nothing if the judge cannot fail. `scripts/vq002-kit-audit-selftest.sh` breaks
each load-bearing claim in a throwaway manifest — a pack-cover fallback, a spelling that dodges the
fixed list, a cover chain that does not lead with `course-master`, a dropped `raw_sha256`, an emptied
`produces`, an injected fictional title, a raised and a lowered budget ceiling, a fifth attempt on one
asset, a changed hero size, a forged OCR record, a wrong 2x hash, a derived plate that traces to
nothing, v1 art back in the consumer path, v1 relabelled as approved, a 3:2 note that names the wrong
referent again, a `source_frame.scale` stating the crop-to-plate ratio, dropped cover ratios, a dropped
natural-crop block in `resolution`, a superseded row that reclaims a shipped plate, and a superseded
row without `superseded_by` — and requires the judge to exit 1 on each: 21 cases.

## Adding a kit

Copy this directory's shape, keep one `kit.json`, and register it in the same judge. A new plate is
recorded with its prompt and hash before it ships; a plate that cannot state its provenance does not
enter `roles`. Generate against a reference, describe a place, and count every attempt.
