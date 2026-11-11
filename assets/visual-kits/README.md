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

## The seven VQ-008 grammars

`workshop_manual/`, `observatory/`, `kitchen_table/`, `archive_desk/`, `studio_bench/`, `lab_bench/`
and `instrument_board/` are kit version 1, built by `scripts/vq008-kits.py`, one directory each.

| role | assets per kit |
| --- | --- |
| `hero` | one 1344x768 plate plus a 2688x1536 `@2x` sibling |
| `cover` | one 3:2 1200x800 plate and one 4:5 640x800 crop of the same frame |
| `section` | one 1344x768 section plate |
| `lesson_scene` | one 1344x768 lesson scene plus a 2688x1536 sibling |
| `object`, `frame`, `badge`, `material` | the shared kernel, referenced by repo path and hash |
| `fox` | the seven painted poses at 256 px, from the same shared kernel |

Grammar vocabulary is **imported from `coursebook/world.py`**, not retyped: `--check` compares each
`kit.json`'s palette, medium, composition, motifs and subject cues against `GRAMMARS[grammar]` and
fails on drift. The script reads that module and never edits it.

### Provider-free by construction

Every plate is a committed file. A curated world gets these bytes with no image provider, which is
the program's coverage bar (`VISUAL-QUALITY-PROGRAM.md` §7 step 8). The shared objects, frames,
badges, materials and fox poses are one kernel (`coursebook-kernel@1`) referenced from every kit
rather than copied seven times, so the character and the object kit cannot drift between grammars.

### What the judge checks on these kits

`python3 scripts/vq008-kits.py --check` recomputes, for all eight grammars: sha256, byte count and
pixel size of every shipped plate; OCR with the calibrated readable-text rule; grayscale minima
(no pure black); the dominant ground against the grammar's own palette, so the observatory's deep
field-green night is accepted where a warm-only test would fail its own art direction; the hero's
quiet field, measured against **both** contract ink and cream paper and recording which tone the
headline must use; the 3:2 and 4:5 cover arithmetic, recomputed from the sizes the manifest records;
the shared-kernel bytes; the generation budget and the per-asset cap; the fallback chain (never a
Press Plate); and the absence of fictional proof titles, placeholder names and Press Plate references.

### Two honesty items

1. **The prompt is recorded as canonical-plus-delta, not byte-exact.** Each `kit.json` records the
   composer prompt for its grammar and role, and each attempt in `generation.json` records the delta
   that was actually appended (`prompt_delta`), e.g. "no reference image; ruler removed from the
   scene". `prompt_provenance` states this in every plate. A byte-exact transcript of 44 attempts was
   not kept; inventing one would be worse than saying so.
2. **`@2x` is native only when the provider returned 2688x1536.** The seam returned 2048x1152 on
   fifteen of the twenty-eight plates. Where that happened, the 2688x1536 sibling is a resampled
   frame, and `source_frame.native_2x` is `false` with the provider frame recorded beside it. The
   3:2 cover is cut from the largest 3:2 crop the provider frame allows (1728x1152 on those plates,
   not 2304x1536), and the note names that plate's own crop size.

### Reference images caused interface leakage

Passing `refs/home.png` as `reference_image_urls` made the model reproduce the mockup: one archive
attempt came back with a red Coursebook shop sign, a standing person and a menu board, and another
with the Coursebook wordmark composited into the corner. Both were rejected. From `archive_desk`
onward the plates are text-only prompts, and `reference_image` is `null` in the manifest for them.

### Budget

44 attempts across the seven kits, ceiling 50, at most four on any one asset. `attempts_used` is read
from `generation.json` by the judge; rejected attempts are kept with their reason and their media
URL, including the ones that produced lettering, `PLACE` burned into a corner, a grid on a chart, or
a rise of `1uU` under OCR at the 4:5 crop.

### Contact sheets

`docs/visual-review/vq-008/<grammar>-contact-sheet.png` — one per kit, captioned with the grammar's
medium, palette and composition, showing every plate and every shared-kernel row. These are the
sheets the owner reviews; passing `--check` is a contract verdict, not art acceptance.

