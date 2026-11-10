# CP-016 live world proof

Two topics that are **not** in the demo set, run through the shipping
`coursebook.world` prompt builder (`world.build_style_boards` + `world.build_kit_prompts`)
and the host's own `image_generate` tool. No test double, no re-hosted art.

| Topic | Grammar | Plates | Contact sheet |
|---|---|---|---|
| Bleed a bicycle hydraulic brake (technical) | `workshop_manual` | 3 style boards, hero, cover, 2 sections | `technical-brake-bleed/contact-sheet.png` |
| Fingerpicking patterns for acoustic guitar (creative) | `studio_bench` | 3 style boards, hero, cover, 2 sections | `creative-fingerpicking/contact-sheet.png` |

- Prompt version: `world-prompt-v3` (v3 adds the notation/diagram negatives for domains where
  those are the natural illustration and the "place and mood only" section fence for **every**
  grammar, not only service worlds). Each plate records the version it was actually rendered
  from; the packets carry a mix of v2 and v3 plates, listed per plate below. The creative set
  exercises the shipping v3 prompt in all four repaired roles; the technical set was re-rendered
  where its own gates failed and, in round 3, where a board had recorded the wrong direction's
  prompt (`01-style_board-authored`).
- Provider: the host's `image_generate` tool over the managed Nous tool gateway (`fal-queue`).
- Model: `fal-ai/flux-2-pro`. The catalog's fast default (`flux-2/klein/9b`) rendered flat
  vector and pseudo-text on the first pass, so it is not used for this proof. The model is
  recorded per plate; the runtime uses whatever model the profile selects.
- Aspect: the host clamps to `landscape` / `square` / `portrait`; the plate's own ratio (3:2,
  16:9, 4:5, 1:1) is recorded in the prompt and in `provenance.json`, and the contact sheet
  applies the mechanical crop the layout uses. Nothing is stretched.

## Two gates, two results

Both gates are recorded per plate in `provenance.json`: `ocr` and `notation`. They measure
different classes and neither is a plate verdict on its own.

1. **Lettering (OCR, CP-010 standard).** A token of two or more characters at >= 70 Tesseract
   confidence (psm 11). Result of *this gate*: **twelve of fourteen** plates return no token.
   Two plates return one token each, and both are cleared by crop, not by the gate:
   - `technical-brake-bleed/04-hero-authored.png`: `/‘I_I` at 75.9 in a 579x73 band at
     `+176+477`; structured painted detail (Canny edge density 0.052 against 0.009 in a quiet
     field). `easel` cropped the box in review round 1 and cleared it as bench slats and grain.
   - `creative-fingerpicking/05-cover-authored.png`: `€/` at 91.5 in a 37x46 box at `+462+687`.
     The committed crop `creative-fingerpicking/crops/05-cover-mark.png` (enlarged, 4x) shows
     the fox's ear edge and painted texture; the reader reports no readable letter, numeral,
     logo or label. Symbol-only tokens are outside the CP-010 "word" intent, which is why the
     crop is the deciding evidence.
2. **Notation/diagram (vision read, one per plate).** The OCR gate cannot see this class by
   construction: a staff, a chord box, a tick box or a single glyph is not a two-character word.
   A vision read per plate asks for a JSON verdict on musical notation, staves, chord boxes,
   tablature, fret numbers, code, equations, tick boxes, tables, diagrams, charts, letters,
   numerals, brand names, and hands performing a technique. Result: **fourteen of fourteen
   plates clean**. Fail-closed: an unparsed or errored answer, and — since review round 3 — any
   answer whose `evidence` field is empty or the literal word `none`, is recorded as `unchecked`,
   never as clean. Every `clean` in this packet carries a described observation naming the
   objects inspected; `SUMMARY.json` counts `notation_gate_unchecked` separately from
   `notation_gate_clean`, and
   `tests/test_cp016_world_art_bible.py::ProofPacketIntegrityTest` fails if a `clean` row has no
   evidence. (Round 2 recorded four `clean` rows with `evidence: "none"` — empty reads counted as
   passes. Those four plates, technical 02/04 and creative 01/06, were re-read in round 3 and now
   carry their readings.)

The earlier "thirteen of fourteen plates are clean" line was an OCR-gate result quoted as a
plate verdict. It is restated above: twelve OCR-clean, two crop-cleared, fourteen notation-clean.

## Repairs in this round

Every re-render is listed in `provenance.json` with `repair_round` and `repair_method`
(`regenerate` or `edit`). Only frames that failed a gate were touched.

| Plate | Why | Round | Method | After |
|---|---|---|---|---|
| `creative-fingerpicking/02-style_board-warm-paper` | staves, noteheads, chord/tab grids in three open booklets | 2 | regenerate | OCR clean, notation clean |
| `creative-fingerpicking/02-style_board-warm-paper` | round 3: the prompt the plate was made from was the **deep-pigment** board's (lookup key bug, §"Packet integrity"); re-rendered from its own warm-paper request. Round 4: that render carried pseudo-text (`fox while @1`) | 3, 4 | regenerate with the direction prompt, then regenerate with the blank-surface hardening | OCR clean, notation clean |
| `creative-fingerpicking/03-style_board-deep-pigment` | two chord-box cards with finger dots; round-2 reroll then produced a printed UI bar | 2, 3, 4 | regenerate, regenerate, edit | OCR clean, notation clean |
| `creative-fingerpicking/05-cover-authored` | brand name on the headstock (found by this card's notation gate, not by round-1 review); round-2 and round-3 rerolls left jar labels | 2, 3, 4 | regenerate, regenerate, edit | notation clean; one symbol-only OCR token, crop-cleared |
| `creative-fingerpicking/07-section-s2-authored` | fretting/plucking hands, sheet music, can label | 2 | regenerate | OCR clean, notation clean |
| `technical-brake-bleed/01-style_board-authored` | `SHIMANO` on the brake lever (found by the notation gate) | 2 | regenerate | OCR clean, notation clean |
| `technical-brake-bleed/01-style_board-authored` | round 3: recorded and rendered with the **deep-pigment** prompt (lookup key bug); re-rendered from the authored request, which left one token `\'Ii`. Round 4: hardened re-roll | 3, 4 | regenerate with the direction prompt, then regenerate with the blank-surface hardening | OCR clean, notation clean |
| `technical-brake-bleed/03-style_board-deep-pigment` | brand lettering on the frame, labels on two jars | 2 | regenerate | OCR clean, notation clean |

`edit` is the model's own edit endpoint on the existing plate: it keeps the approved composition
and removes the printed mark, where a fresh generation re-rolls every other detail.

## Packet integrity

Review round 3 found the render path recording a prompt a plate was never made from:
`scripts/cp016-world-proof.py` looked its prompt up by `(role, section_id)`, and all three style
boards share `role="style_board"` and `section_id=None`, so the dict kept only the last direction
and handed the **deep-pigment** prompt to any board a repair pass re-rendered. Technical
`01-style_board-authored` and creative `02-style_board-warm-paper` therefore carried the
deep-pigment `prompt_hash` while their rows still said `style_id: …--authored` / `…--warm-paper`.
The packet proved neither the authored (technical) nor the warm-paper (creative) direction.

Fixed in the same round:

- the lookup is keyed `(style_id, role, section_id)` and the repair path also writes
  `row["style_id"]`, so a row cannot keep one direction's id beside another's prompt;
- `--slug` now filters the repair loop, so `--only 01-style_board-authored` no longer matches the
  same-named plate in both topics;
- `--no-harden` renders the plain direction prompt when the re-render is for identity, not for a
  defect;
- both affected plates were re-rendered from their own direction prompt, and the packet now has
  three distinct style-board hashes per topic. Verify from the code, not from this page:

```
python3 -m unittest tests.test_cp016_world_art_bible.ProofPacketIntegrityTest
```

That test reads both `provenance.json` files and rebuilds every current-version prompt from the
recorded brief with `world.build_style_boards` / `world.build_kit_prompts`; it fails if two style
boards share a `prompt_hash`, if a rebuilt prompt's hash, text or `style_id` differs from the
row's, or if a `clean` notation verdict has no evidence. It failed on the round-2 packet (8
failures) and passes on this one.

## Prompt contract this proof exercises

- Every style board, hero, cover, section and card prompt carries the one gouache medium, the
  upper-left key, the five-pigment ceiling and the dark-brown ink contour (`world-prompt-v3`).
- Textless negatives and the fox rule ("no mascot other than the fox") are kept verbatim.
- A music/`studio_bench` brief carries the notation class in every role: "no musical notation,
  no staves, no clefs and no noteheads", "no chord diagrams or chord boxes, no finger-dot
  charts", "no tablature, no fret numbers and no string grids", "no sheet music, no open
  songbooks and no printed pages". Code, maths and checklist domains carry their own groups.
- Every section prompt, in every grammar, carries "place and mood only, no procedure, sequence
  or tool action depicted" plus "no hands mid-technique". The typed section title travels only
  as a suppression instruction (`no lettering of the words ...`), never as positive prose.
- Tests: `tests/test_cp016_world_art_bible.py::NotationHazardContractTest`.

- Known limit: brush work is carried more by paper tooth and ink line than by heavy impasto;
  the reviewer (`easel`) is the art judge on that dimension.

`provenance.json` per topic carries the brief, grammar, selected style, and for every plate the
full prompt, negative prompt, prompt hash, prompt version, aspect, provider source (inline
data-URL hash), file sha256, byte count, OCR words, notation read and timestamp. `SUMMARY.json`
carries the per-topic gate counts. `probe/` is a throwaway diagnostic frame and is not evidence.

Reproduce the gates without spending a provider call (run with the Hermes runtime interpreter,
which supplies Pillow, `httpx` and `tools.*`; the script bootstraps itself when it can):

```
python3 scripts/cp016-world-proof.py --notation-only --slug creative-fingerpicking --only 06-section-s1-authored
python3 scripts/cp016-world-proof.py --summary-only
```

`--notation-only` re-reads the plates on disk and rewrites each `notation` result; `--only`
narrows it to named plates; `--summary-only` rebuilds `SUMMARY.json` from the per-topic
provenance files.
