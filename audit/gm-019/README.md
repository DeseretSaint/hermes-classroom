# GM-019 evidence — world plate fence: non-frozen imperative verbs and passive voice

Branch: `wt/gm-019-fence`, forked from GM-003's reviewed tip `7ff9f4a` (`wt/gm-003-world`,
0 behind / 19 ahead of `origin/master` `e1f8e6e` at fork). No master merge, no push, no gateway
restart, and no edit to the migration, `contracts/*.json` or the shared contract manifest.

## What GM-003 left open

`_plate_text_problems()` / `_names_procedure_or_spelled_value()` was a token scan over a frozen
verb list (`_PROCEDURE_VERB_TOKENS` + `_DETERMINER_ONLY_PROCEDURE_VERBS`). Two shapes escaped it:

1. **A verb outside the frozen list.** `world.generate(stage='concepts',
   brief_patch={'motifs': ['Scrub the head']})` was ACCEPTED on a real head-gasket course — 3
   provider calls, `scrub the head` in 3/3 prompts.
2. **Passive voice.** `The head is removed`, `The intake manifold was drained` carry a completed
   action on the equipment with no imperative verb at all.

Both reached every plate prompt because the same predicate gates the patch refusal and every
`_plate_safe()` interpolation site.

## Fix — shape, not more verbs

Two vocabulary-independent shapes, plus one closed form class where morphology cannot help:

- `_object_taking_clause(value, grammar)` — the phrase opens (after leading discourse words and
  leading `-ly` adverbs) with a content word, then a determiner/possessive, then a noun: `Scrub
  the head`, `Swap the gasket`, `Degrease the block`, `Scrub his hands`, `Then scrub the head`,
  `Probably scrub the head`. Closed-class function words are never the opening content word, so
  native place cues cannot match: `bench under the lamp` (relation word), `the break room` / `a
  clean service bay` (determiner first), `car on a lift` / `clean service bay` (no determiner
  after the noun).
  - The shape is **scoped to the procedure grammar** (`_PROCEDURE_GRAMMARS =
    {"workshop_manual"}`, which `technical_procedure`/`trades` select — the card's repro). On a
    non-procedure grammar the same shape is how the course names its lesson (`Cook a simple meal
    at home`, `Ordering a drink`), and F4 requires those titles to survive. The frozen verb
    vocabulary still refuses a procedure verb — and every listed gerund, e.g. `Removing the
    head` — in every grammar, so no round-12/13 fence is loosened.
- `_passive_construction(value)` — a be-auxiliary (`is/are/was/were/be/been/being/am/get/
  gets/got`) followed by a past participle. The participle is recognised **morphologically**
  (`-ed`, length ≥ 4) or from `_IRREGULAR_PAST_PARTICIPLES`, a closed form class that cannot be
  derived from the present stem (`is taken off`, `was held`). Closed-class intervening adverbs
  are allowed (`was not drained`, `The head is now removed`). This shape is **not** grammar
  scoped: no authored motif or lesson title is a be-auxiliary + participle, and a passive names
  a completed action in any grammar.
- Both are appended as `presentation_names_procedure_or_value` in `_plate_text_problems`, after
  the frozen/number fences and before the N1 bare-object branch. The frozen checks are untouched.

The existing grammar-owned-scene carve-outs stay legal by construction rather than by a new
carve-out branch: no authored motif or native cue has the object-clause or passive shape, so a
procedure-bearing motif cannot claim a carve-out it did not earn. The false-positive sweep
(`probe_falsepositives.py`) walks all 83 authored values.

## Tests (red → green)

| Test | Class | What it proves |
|---|---|---|
| `test_plate_fence_covers_non_frozen_and_passive_shapes` | `WorldPolicyTest` | Predicate table: 9 imperative strings refused on `workshop_manual`, 6 passive strings × 8 grammars refused, `Removing the head` still refused on `field_atlas`, and the grammar-owned/native legal table (including `Cook a simple meal at home`, `Ordering a drink`) still passes |
| `test_presentation_motifs_cannot_name_a_non_frozen_imperative_or_passive` | `WorldFailureAndModeTest` | Through the real `world.generate` handler: 8 hostile motifs refused on concepts with 0 provider calls / 0 worlds / 0 jobs; kit path after an approved style refused with 0 extra calls (still 3) and 1 job; `clean service bay` + `car on a lift` still spend 3; a course titled `The head is removed` falls back in 3/3 prompts with the stored brief verbatim |

Red: `audit/gm-019/red-attempt13.txt` — 2 tests, **66 intended failures** (predicate subcases
plus handler subcases), workspace clean and 0 spend.

Green: `audit/gm-019/green-attempt13.txt` — 2 OK.
Named suite: `audit/gm-019/test_world.txt` — `tests.test_world` **46 OK** (was 44; +2).
Predicate probe: `audit/gm-019/probe_round13.py`, red output `predicate-red.txt` (57 FAIL,
legal rows PASS), green output `predicate-green.txt` (**probe OK**, 57 refused rows + 12 legal
rows). False-positive sweep: `audit/gm-019/probe_falsepositives.py` → `falsepositives.txt`
(83 authored values, probe OK; the one pre-existing frozen-gerund over-refusal is expected and
annotated). Full suite: `audit/gm-019/full-attempt13.log`.

Run the probes from the repo root:

```
PYTHONPATH=. python3 audit/gm-019/probe_round13.py
PYTHONPATH=. python3 audit/gm-019/probe_falsepositives.py
```

## Residual paths (unchanged unless named)

- Token-level heuristics, not a semantic classifier: a procedure phrased as a bare noun phrase
  with no digit, unit, spelled quantity, fraction or procedure-shaped clause
  (`valve clearance table`) is still not detected; the workshop hard negatives remain the second
  line of defence.
- A non-frozen **bare-object** imperative with no determiner (`Scrub head`) is not closed by this
  card; N1 closes that shape only for the ambiguous scene verbs. A bare-object phrase is
  indistinguishable from a place cue at token level (`clean service bay`), so closing it needs a
  subject-aware rule, not another word list.
- A **non-procedure grammar keeps an imperative lesson title** (`Cook a simple meal at home`,
  `Ordering a drink`) by design: the object-clause shape is scoped to `workshop_manual`. A
  procedure phrased as an object clause on, say, `kitchen_table` would not be refused by this
  shape (the frozen vocabulary still applies); technical courses select the procedure grammar.
- **Pre-existing, not introduced here:** `cutting mat` (an authored `studio_bench` motif) is
  refused by the frozen gerund rule (`cutting` → `cut`) at the GM-003 base `7ff9f4a` as well.
  GM-019 neither introduces nor widens it; it is recorded so the next fence card owns it.
- Passive over-refusal is possible for a stative scene description (`the bench is cluttered`);
  the plate falls back rather than refusing a stored brief.
- `world.*` is still absent from the published `rpc.v23.json` — the additive wire/manifest bump
  remains the integration card's work; this branch does not edit `contracts/*.json`.
- The media seam is a deterministic fake; the `world_assets` role vocabulary follows the frozen
  0013 CHECK; create-time auto-queue is owned by GM-002.
