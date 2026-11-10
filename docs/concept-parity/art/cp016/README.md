# CP-016 live world proof

Two topics that are **not** in the demo set, run through the shipping
`coursebook.world` prompt builder (`world.build_style_boards` + `world.build_kit_prompts`)
and the host's own `image_generate` tool. No test double, no re-hosted art.

| Topic | Grammar | Plates | Contact sheet |
|---|---|---|---|
| Bleed a bicycle hydraulic brake (technical) | `workshop_manual` | 3 style boards, hero, cover, 2 sections | `technical-brake-bleed/contact-sheet.png` |
| Fingerpicking patterns for acoustic guitar (creative) | `studio_bench` | 3 style boards, hero, cover, 2 sections | `creative-fingerpicking/contact-sheet.png` |

- Prompt version: `world-prompt-v4` (v4 adds the emission class of ART-BIBLE §4.4 and rewrites the
  two grammars that made a lit fixture the light source; v3 added the notation/diagram negatives
  and the "place and mood only" section fence for **every** grammar). Each plate records the
  version it was actually rendered from; the packet carries a mix of v2, v3 and v4 plates, listed
  per plate in `provenance.json`. All seven technical plates are v4; the creative set exercises
  the shipping v3 prompt in all four repaired roles and was measured clean on the new light gate,
  so it was not re-rendered for a light rule it does not break.
- Provider: the host's `image_generate` tool over the managed Nous tool gateway (`fal-queue`).
- Model: `fal-ai/flux-2-pro`. The catalog's fast default (`flux-2/klein/9b`) rendered flat
  vector and pseudo-text on the first pass, so it is not used for this proof. The model is
  recorded per plate; the runtime uses whatever model the profile selects.
- Aspect: the host clamps to `landscape` / `square` / `portrait`; the plate's own ratio (3:2,
  16:9, 4:5, 1:1) is recorded in the prompt and in `provenance.json`, and the contact sheet
  applies the mechanical crop the layout uses. Nothing is stretched.

## Three gates, three results

All three are recorded per plate in `provenance.json`: `ocr`, `notation` and `light_gate`. They
measure different classes and none is a plate verdict on its own. `notation` and `light_gate`
come from **one** vision read per plate (`GATE_QUESTION`), so a frame costs one read, not two.

1. **Lettering (OCR, CP-010 standard).** A token of two or more characters at >= 70 Tesseract
   confidence (psm 11). Result of *this gate*: **twelve of fourteen** plates return no token.
   Two plates return one token each, and both are cleared by crop, not by the gate:
   - `technical-brake-bleed/04-hero-authored.png` (round-5 render): `/\` at 75.6 in a 150x32
     band at `+334+434`. The committed crop `technical-brake-bleed/crops/04-hero-token-band.png`
     (magnified three times) is the base of a tripod stand on a wooden surface with its cast
     shadow — no letter, numeral, glyph or writing-like mark. Recorded in the plate's
     `lettering_crop` field.
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
   plates clean**, each with a described observation. Fail-closed: an unparsed or errored answer,
   and any answer whose `evidence` field is empty or the literal word `none`, is recorded as
   `unchecked`, never as clean. `SUMMARY.json` counts `notation_gate_unchecked` separately from
   `notation_gate_clean`, and
   `tests/test_cp016_world_art_bible.py::ProofPacketIntegrityTest` fails if a `clean` row has no
   evidence. (The pre-round-4 read of technical `07-section-s2` reported a brand logo on a
   bicycle crank; that frame was re-rendered under v4 and the logo is gone.)
3. **Light (vision read, one per plate, added in round 4).** Fields `fixture_visible`,
   `fixture_emits`, `glow`, `key` and `evidence`, judged by which side of each mass is lit and
   which way shadows fall. A plate is `suspect` if any fixture is the light source, if there is
   any bloom/halo/radial glow, or if the key is not upper-left. Result: **fourteen of fourteen
   clean, every key upper-left, no fixture emitting anywhere**. Before the round-4 rewrite the
   same gate read **seven of seven technical plates as suspect** (`fixture_emits` + `glow`; two
   style boards also read a top key) while the creative set was already clean — one grammar, not
   the model. That is the measurement `easel` asked for; see §"The light rule".

The earlier "thirteen of fourteen plates are clean" line was an OCR-gate result quoted as a
plate verdict. It is restated above: twelve OCR-clean, two crop-cleared, fourteen notation-clean,
fourteen light-clean.

## The light rule

ART-BIBLE §Light (l.33) requires one soft key from the **upper left**, and §4.4 (l.330) forbids
"no bloom, no halo, no radial glow around a light source ... A lit lantern is a hard-edged
lamp-yellow mass."

Round 3 shipped seven technical plates that break both, because one grammar composed the scene
against the light clause it also emitted:

- `coursebook/world.py` (v3) composed `workshop_manual` as *"a centered bench under one overhead
  lamp"* while the same prompt ended *"Light comes from one soft key light from the upper left"*.
  A self-contradicting instruction; the model followed the fixture.
- Every technical style board, hero, cover and section then painted a lit pendant casting a warm
  cone onto the bench and wall. Neither existing gate measures light, so the packet passed two
  review rounds on lettering and notation while every technical plate broke this rule.

The round-4 fix is in the shipping builder, not only in the proof:

- `workshop_manual` composition: "a centered bench and tool wall with no ceiling fixture; the only
  light is the single upper-left key; ...".
- `field_atlas` composition: a street of **unlit** paper lanterns "hung as flat hard-edged props;
  the only light is the single upper-left key"; its medium also says the lanterns are painted
  unlit. The audit found no other grammar composing a fixture as the light (the observatory's
  "night field" and the kitchen's "warm overhead table" are camera/temperature, not fixtures).
- Motif vocabulary that named a fixture was renamed so it cannot be interpolated as scene light:
  `bench light` -> `bench vice`, `reading lamp` -> `reading chair`.
- `_NEGATIVE` gains the emission class on **every** plate: "no light cone or visible beam", "no
  glowing bulb or lamp", "no bloom, halo or radial glow", "no second light source", "no key light
  from the right", "no lit fixture acting as a light source". The class is worded without any
  other grammar's distinctive token, so the GM-019 foreign-scene fence still holds.
- `PROMPT_VERSION = "world-prompt-v4"`; the hash moves because the composition and negatives are
  in the hashed payload.

The gate read before the rewrite: technical 7/7 `suspect` (`fixture_emits` and `glow` on all
seven; `key=top` on `01` and `03`), creative 7/7 `clean`. After the rewrite and re-render:
technical 7/7 `clean`, `key=upper-left` on every plate, `fixture_visible`, `fixture_emits` and
`glow` all false. All seven technical plates were re-rendered in round 4 (and `01`/`04` once more
with the blank-surface hardening in round 5) because the v4 prompt changes every one of them;
the creative plates were left as they are — the light gate found nothing to fix in that grammar
and a re-roll would spend art the reviewer already cleared.

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
| `technical-brake-bleed/01-style_board-authored` | round 4: prompt rewrite (v4, no ceiling fixture, emission negatives); the first v4 render painted lettering (`Storybook`, `Home`, `Biecycle`, `Mechanic.`), so it was re-rolled with the blank-surface hardening | 4, 5 | regenerate, then regenerate hardened | OCR clean, notation clean, light clean |
| `technical-brake-bleed/02-style_board-warm-paper` | round 4: lit pendant / warm cone (light gate) | 4 | regenerate | all three gates clean |
| `technical-brake-bleed/03-style_board-deep-pigment` | round 4: lit pendant / warm cone (light gate) | 4 | regenerate | all three gates clean |
| `technical-brake-bleed/04-hero-authored` | round 4: lit pendant / warm cone; the v4 render was light-clean but painted lettering (`Hreo`, `ogansit`, `tlure.`), so it was re-rolled hardened | 4, 5 | regenerate, then regenerate hardened | notation and light clean; one symbol-only OCR token `/\`, crop-cleared |
| `technical-brake-bleed/05-cover-authored` | round 4: lit pendant / warm cone (light gate) | 4 | regenerate | all three gates clean |
| `technical-brake-bleed/06-section-s1-authored` | round 4: lit pendant / warm cone (light gate) | 4 | regenerate | all three gates clean |
| `technical-brake-bleed/07-section-s2-authored` | round 4: lit pendant / warm cone, plus a brand logo on a bicycle crank found by the notation gate | 4 | regenerate | all three gates clean |

`edit` is the model's own edit endpoint on the existing plate: it keeps the approved composition
and removes the printed mark, where a fresh generation re-rolls every other detail. Round 4 used
`--no-harden` for the seven technical re-renders: the plate was not being repaired for a defect
of its own, it was being re-rendered from a rewritten prompt, and a repair suffix would have
mixed two instructions. The two frames that then failed a gate were re-rolled with the hardening
suffix under `--repair`.

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
  upper-left key, the five-pigment ceiling and the dark-brown ink contour (`world-prompt-v4`).
- Textless negatives and the fox rule ("no mascot other than the fox") are kept verbatim.
- A music/`studio_bench` brief carries the notation class in every role: "no musical notation,
  no staves, no clefs and no noteheads", "no chord diagrams or chord boxes, no finger-dot
  charts", "no tablature, no fret numbers and no string grids", "no sheet music, no open
  songbooks and no printed pages". Code, maths and checklist domains carry their own groups.
- Every section prompt, in every grammar, carries "place and mood only, no procedure, sequence
  or tool action depicted" plus "no hands mid-technique". The typed section title travels only
  as a suppression instruction (`no lettering of the words ...`), never as positive prose.
- Tests: `tests/test_cp016_world_art_bible.py::NotationHazardContractTest`.
- **No grammar may make a lit fixture the light source** (v4). Every emitted prompt, in every
  grammar and every role, carries "one soft key light from the upper left" and the whole emission
  class; no grammar composition, medium or motif contains a lit-fixture phrase (`overhead lamp`,
  `lantern-lit`, `lit by`, `bench light`, `reading lamp`, ...); and the two grammars that did are
  pinned to naming the key as the only light. Tests:
  `tests/test_cp016_world_art_bible.py::LightRuleContractTest` (four tests, 52 failing subtests on
  the v3 builder before the rewrite).

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
python3 scripts/cp016-world-proof.py --light-only
python3 scripts/cp016-world-proof.py --summary-only
```

`--notation-only` and `--light-only` re-read the plates on disk and rewrite each `notation` and
`light_gate` result from the same single vision read; `--only` narrows it to named plates;
`--summary-only` rebuilds `SUMMARY.json` from the per-topic provenance files.
