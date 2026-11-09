# H-40 evidence packet — arbitrary-topic end-to-end proof, re-run on blueprint v2

Status: **3/3 scenarios PASS** on `wt/h09-e2e-rerun`, base `origin/master` **`c588e4a`**.
Auditor: sentinel (independent). Date: 2026-11-07.

> **Latest re-run: H-46b (base `cd818fa`, the H-46 validator line, with H-45 merged) — see the
> H-46b section at the end.** The H-40/H-45 numbers below are kept as history; the packet on disk
> and the focused/full counts in that section are the current ones.

This packet replaces H-09's `wt/harness-e2e-proof` packet, which measured a harness three
generations old (`00b502f`-era: before H-21 blueprint v2 units, before H-36 validator independence,
before H-19's review queue and before H-27/H-26b). Nothing from that branch was merged; this packet
is authored against the shipped tree and adapts the runner to the current
plan → unit sections → lesson → check.open → attempt.submit path instead of reverting it.

Scope: harness completion, not demo polish. No prepared Japanese pack, no Japanese fixture, no
Japanese content in any generated plan, lesson or served page. No product code changed. No
provider was called, no credential was used and no network request was made.

## What is live and what is recorded

| half | status | evidence |
|---|---|---|
| cb.rpc envelope + `coursebook.api.dispatch` (contract v13) | **live** | every step in `evidence/*.json` is an RPC response |
| SQLite migrations, kernel, plan/unit/section/lesson rows | **live** | throwaway `HERMES_HOME` per scenario |
| `generation.run_plan_job` (research seam, blueprint rules, independent validation, preflight) | **live** | prompts, rules and results captured |
| `plan.approve` with the kernel digest (H-12 fail-closed) | **live** | early + stale-hash refusals captured |
| `generation.run_unit_sections_job`, `generation.run_lesson_job` per unit | **live** | one job per unit, no executor chaining |
| `course.outline`, `lesson.page`, `check.open`, `attempt.submit` | **live** | two attempts per committed course |
| model responses | **RECORDED TRANSCRIPT**, hand-authored | `transcripts/*.json`, `labels.model` |
| validator identity | **RECORDED TRANSCRIPT**, a distinct recorded identity (`recorded-validator-h40`) | H-36 compares the reported model names; a same-name validator can only ever be `same_model` |
| research pages | **RECORDED PAGES**, fetched through the real search seam | `research` in each transcript: `bicycle_single`/`music_short` record one page, `soldering_full` a six-page result set really fetched for the queries the full-scope research floor derives (H-175) |
| provider calls / spend | **none** | `labels.provider_calls = 0`, `provider_spend_usd = 0.0` |

The replay engine reads every property of the *request* (schema constant, capability policy, rubric
profile, unit ordinals, objective titles) from the live payload and takes only authored content
from the recording; a request the recording cannot answer is a hard failure, never a fallback. Each
`evidence/*.json` stores the plan document, the per-unit results, the plan request rules, every
lesson row state, the check lanes and the grading verdicts it actually read.

## Scenarios

| id | scope / recipe | goal | units | objectives | checks | lessons | grading |
|---|---|---|---|---|---|---|---|
| `bicycle_single` | `single` / `one_off` | "Walk me through replacing the inner tube on my road bike and checking the brakes before I ride it today." | 1 | 1 | 1 `verification` (`rubric_only`) | 1 validated | all 3 items ticked → `pass`, `self_reported`, `review_objective` |
| `music_short` | `short` / `committed` | "Understand intervals, triads and the circle of fifths well enough to analyse a pop song." | 2 | 4 | 4 `quiz` (`exact`) | 4 validated | correct → `pass`/`cold`/`complete_objective`; wrong → `not_yet`/`cold`/`retry_attempt` |
| `soldering_full` | `full` / `committed` | "Prepare for a first soldering repair on a through-hole PCB: safety, component placement, joints, inspection and desoldering." | 6 | 12 | 12 `quiz` (`exact`) | 12 validated | correct → `pass`; wrong → `not_yet` |

All three are subjects the Japanese fixture never saw. `soldering_full` declares prerequisite edges
unit *n* → unit *n−1*; `course.outline` projects a `prerequisite_state` for every unit and the
later units are `unmet` until the earlier objectives are independently shown.

### Plan ceiling, accepted and rejected at the declared bound

`SCOPE_EXPECTATIONS["full"]["blueprint_units"] = (2, 12)` and
`["blueprint_objectives"] = (12, 40)`; the schema pins the same maxima (`objectives.ordinal`
max 40, `check_plan` maxItems 40).

* **at bound** — 12 units / 40 objectives: schema-valid, every deterministic rule passes,
  independently validated (`pass`), plan state `draft` and therefore approvable.
* **over bound** — 12 units / 41 objectives: `GenerationRejected` —
  `plan violates its schema at check_plan: [...] is too long`.

Recorded in `evidence/soldering_full.json` under `ceiling_probe`.

## Assertions actually checked (all PASS)

Common to all three:

- no Japanese characters in the plan document, the lessons, or the run record;
- the plan is **independently validated** (`validation.outcome = independently_validated`,
  `independence = independent`) and `validation_verdict = pass` *before* approval;
- `plan.approve` with the correct digest succeeds (state `approved`); a wrong revision and a stale
  digest are both refused and the plan stays `draft`;
- one owner section per objective; every `gen_lessons` row is `validated`;
- prerequisite edges point strictly backwards and the outline projects a state for every unit;
- every unit/lesson stage is **user-enqueued**: no stage created a follow-on job;
- the served `lesson.page` never contains a check reference answer.

Per shape:

- `single`: exactly 1 unit, 1 objective, 1 check; the check is `verification` +
  `rubric_only` (the confirmation lane) and **no exact-lane quiz exists**; the tick-list grades
  `pass` with `evidence_class = self_reported`.
- `short`: 2 units, 4 objectives; every check is an `exact`-lane `text` quiz; the correct answer
  grades `pass` and the wrong answer `not_yet` — neither is `needs_retry`.
- `full`: multi-unit with declared prerequisite edges; every check is graded on the exact lane;
  both grading verdicts observed; the plan bound accepted at 40 objectives and rejected at 41.

## Differences from the pre-blueprint-v2 (H-09) run, and why

| H-09 (`111c7e9`, `00b502f`-era) | this run (`c588e4a`) | why |
|---|---|---|
| plan document had `sections`; 1 section = 1 lesson | plan document has `units` + `objectives` + `check_plan`; sections are authored by a per-unit stage **after approval** | H-21 blueprint v2 made units the authoring, budget and cancel checkpoint |
| `bicycle_single` = 4 objectives / 4 lessons | **1 unit / 1 objective / 1 lesson**, `verification` check | v2 `single` contract is exactly one unit and one objective; a 4-objective single is now refused by the rules |
| `music_short` = 5 objectives / 5 sections | **2 units / 4 objectives** | v2 `short` bounds are 1–3 units, 3–6 objectives, 1–6 per unit |
| `soldering_full` = 6 objectives / 6 sections | **6 units / 12 objectives**, prerequisite edges | v2 `full` requires 2–12 units, 12–40 objectives, 2–6 per unit |
| checks were document-level only; H-09 explicitly did **not** submit an attempt | `check.open` + `attempt.submit` through the real grading lanes, for every course | the lane split (H-34) and the check store landed after H-09; this was H-09's largest honest gap |
| validation identity was not a claim | author and validator report **different** recorded models; independence is read from the verdict | H-36 requires a real cross-model pass before anything may be called independently validated |
| export (`course.export.read` / `course.export`) was asserted | **not exercised in this packet** | export moved (H-08b authored export at v13); it is covered by `tests/test_course_export.py` and the authored-export packet, and re-running it here would need a different approval surface. This is a deliberate scope reduction, not a pass |

## H-30b's four P3 findings, re-checked on `c588e4a`

| id | finding | status here | evidence observed this run |
|---|---|---|---|
| D1 | a unit stage that fails its own rules persists a partial batch with `state: needs_review` | **open** — reproduced | `evidence/partial_unit_batch.json`: unit 2 authored 1 of 2 owner sections; job state `needs_review` with reasons `objective 4 has no owner section; author exactly one owner section per objective` and `unit 2 targets 2 lesson(s); this batch would leave 1 section(s)`; the lesson stage refuses (`unit 2 owner sections cover objectives [3] but the unit has objectives [3, 4]`); `course.outline` reports `check_state: none`; `lesson.page` returns `state: not_started` with `check_id: null` (H-30b saw `empty`; the state name changed, the behaviour did not). Nothing imperfect is served, but the partial row is durable. |
| D2 | the one-off verification check completes as `evidence_class: self_reported` / `next_action: review_objective`, not independent evidence | **open by design** — reproduced | `evidence/bicycle_single.json`: grading result `verdict: pass`, `evidence_class: self_reported`, `next_action: review_objective`. This is the honest H-34 confirmation lane (a tick-list is self-report); the acceptance prose must not call it independent. |
| D3 | the `full` prompt still says "a full course; the standard objective range stands" beside the v2 `12 to 40` band | **open** — reproduced | `SCOPE_EXPECTATIONS["full"]["note"]` at `coursebook/generation.py:214`, rendered into the v2 prompt by `_plan_instructions_v2`; the captured plan request rules on `soldering_full` read `objective_count [12, 40]`. Numbers correct, sentence stale. |
| D4 | `SCOPE_EXPECTATIONS[scope]["objectives"]` still carries v1 ranges (4–5 / 4–6 / 4–8) beside `blueprint_objectives` | **open** — reproduced | `coursebook/generation.py:193-215`: `single.objectives = (4, 5)` while `single.blueprint_objectives = (1, 1)`. Only the v1 prompt path reads it, but any audit that reads `objectives` instead of `blueprint_objectives` reports the wrong contract. |

No P0/P1/P2 defect was found. All four remain P3 honesty/clarity items; D1 is owned by H-21 and
is worth a follow-up card because a retry could misread the partial batch as authored.

## Not exercised / honest gaps

1. **Live provider.** No spend was authorised for this card. The model half is a recorded
   transcript; this proves the pipeline path, not model quality or how often a live model authors a
   contract-valid plan.
2. **Live web research.** The search seam is recorded; the budget arithmetic, ledger and failure
   handling around it are real.
3. **Course export.** Deliberately out of scope here (see the differences table). H-09's export row
   is not re-established by this packet.
4. **A language goal's audio/pronunciation path.** None of the three goals is a language goal.
5. **Thirty-nine of the forty ceiling objectives.** Only plan acceptance is proven at the bound;
   no 40-objective course was authored end to end.
6. **Desktop renderer, accessibility, responsive layout.** Covered by other cards, not run here.

## Reproduce

```bash
cd /home/deseretsaint/Projects/hermes-classroom/.worktrees/t_e32900ef   # base c588e4a
python3 audit/adversarial/harness-e2e/build_transcripts.py              # regenerate the recording
PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py       # drive all three shapes
PYTHONPATH=. python3 -m unittest tests.test_harness_e2e -v              # same runner + packet guard
PYTHONPATH=. python3 -m unittest discover -s tests -t .                 # full suite
```

Expected runner output (`evidence/run-output.txt`):

```text
bicycle_single: PASS  scope=single units=1 objectives=1 checks=1 lessons=1 validation=independently_validated
music_short: PASS  scope=short units=2 objectives=4 checks=4 lessons=4 validation=independently_validated
soldering_full: PASS  scope=full units=6 objectives=12 checks=12 lessons=12 validation=independently_validated
overall: PASS  (3/3 scenarios)
```

Focused test run: **11 tests OK** (`tests.test_harness_e2e`).
Full suite on `c588e4a` + this branch: **1422 tests OK** in 218.674s
(`evidence/full-suite.txt`; the 11 tests above are included).

> The counts above describe the H-40 run on `c588e4a`. The H-45 section below supersedes the
> focused/full counts and the "ids change between runs" paragraph in `docs/HARNESS-E2E.md`.

## H-45 — scope against the declared contract, packet content-addressed (base `be08495`)

Two H-30 P2 findings that survived the H-40 merge are closed. No product code changed, no provider
was called, no credential or network request was used.

### D6 — `scope_matches_documented_bounds` can now fail

The check no longer compares the plan to the table that generated it. It reads the declared bound
from three places and refuses a plan that leaves any of them:

* `contracts/rpc.v13.json` — the published scope vocabulary (`single`/`short`/`full`);
* `PLAN_SCHEMA_V2` — objectives `minItems 1` / `maxItems 40`, units `minItems 1` / `maxItems 12`;
* `SCOPE_EXPECTATIONS[scope]["blueprint_objectives"|"blueprint_units"]` — the per-scope band.

`declared_scope_bounds()` also fails when those three declarations disagree, so editing one of them
cannot silently loosen the assertion. Every run records the bound it used and any violation under
`scope_bounds` in its evidence JSON, and adds two PASS assertions:
`scope_matches_documented_bounds` and `scope_contract_is_coherent`.

The negative tests (in `ScopeBoundsContractTest`) are the proof the check is not tautological:

| plan handed to the assertion | result |
|---|---|
| committed 1-objective `single`, 4-objective `short`, 12-objective `full` | PASS |
| 40-objective `full` (the declared ceiling) | PASS |
| 41-objective `full` | FAIL — outside the schema and the scope band |
| 6-objective plan labelled `full` (the H-30 repro) | FAIL — outside the `full` band |
| 4-objective plan labelled `single` (the padded one-off) | FAIL — outside the `single` band |
| plan whose `scope` contradicts the brief | FAIL |

### D7 — the packet is content-addressed and byte-reproducible

* **Deterministic ids.** `run_scenario`, `run_ceiling_probe` and `run_partial_unit_probe` mint ids
  from a counter (uuid4 / `secrets.token_hex` / `os.urandom` are scoped and restored), and
  `coursebook.job_service` is imported before the first replay so a lazy import cannot shift the
  sequence. Two full runs of `harness_e2e.py` now write byte-identical evidence, and a scenario
  replayed alone produces the same bytes as the same scenario replayed fourth.
* **`manifest.json`** records a sha256 per evidence file, the harness sha256, and each harness
  input: transcript sha256, the capability brief and its hash, the scope, and the recorded model /
  validator transcript ids.
* **`harness_e2e.py --verify`** recomputes those hashes and prints `FRESH` or `STALE`. The packet
  test's guard compares hashes, not verdicts; a changed transcript or a changed evidence file reads
  stale (both are negative tests in `PacketManifestTest`).

Manifest hash list (`manifest.json`, generated on base `be08495`):

```text
harness  e7abd7c40171ab48ed0fad2d467f7ec63e2fbd74c5555ae9c25968f78e0a868c  harness_e2e.py
input    aca77120320bb1047d808d2bbfea3295876ac8abdd93553e81abf5770e6ca4f7  transcripts/bicycle_single.json  scope=single
input    c14afea32603a20bf39be4a513e586a262ba9ada02b4d94e00f36cf9cb4cb28c  transcripts/music_short.json     scope=short
input    0ba1d8acfc7d46556123c078c03076e914cd4ad9e97562a2cf260c2f5e6d9604  transcripts/soldering_full.json  scope=full
evidence 0a86195e547f3cdaf777195092e64b154e3b806d2b7e271e11a2ebe896bc6db6  evidence/bicycle_single.json
evidence c89aafbfea73afcf2fa710a02c46a6e6bc0b0061779e6093a13281741550c824  evidence/focused-tests.txt
evidence eab31c01fcd0a057cb9445f3164bc8f2ee6b3b9641cea4204b2dcca1fc101d45  evidence/full-suite.txt
evidence ef13e4f3379ffdd6177328dcaee812d14ed97da577b7499d2b51a0190c89b82a  evidence/music_short.json
evidence f828f19d8570c2337cf7fd935951ba3bea9a786c861c67207cb07a1e593b98ff  evidence/partial_unit_batch.json
evidence 79f7f61e6feba83bd4bedae6d301fd6138a8364ba593fc2ecec255f5d28254d8  evidence/run-output.txt
evidence adeae3d66a9d21d53358c8b56b7026c66a519034f1ab4fb7d40c2e7ab600a143  evidence/soldering_full.json
evidence ea566e9a1f0d195fdfef9f054894820aa640d955d8f46305839003730c687a87  evidence/summary.json
```

### Evidence files whose hash changed against the H-40 packet, and why

| file | why the bytes changed |
|---|---|
| `bicycle_single.json`, `music_short.json`, `soldering_full.json` | new `scope_bounds` block and the two scope assertions; ids are now deterministic, so `plan_hash` and every id are stable across runs |
| `partial_unit_batch.json` | H-42 made the unit stage transactional on the merged head: the probe now records `unit_stage_refusal` and `persisted_sections: 0`, where H-40 (pre-H-42) recorded one persisted section and `state: needs_review` |
| `focused-tests.txt` | regenerated on `be08495`: 21 tests OK (was 11) |
| `full-suite.txt` | regenerated on `be08495`: 1494 tests OK in 218.262s (was 1422 on `c588e4a`) |
| `run-output.txt` | the D1 probe line names the H-42 refusal and the run ends with the manifest line |
| `summary.json` | unchanged (3/3 PASS) |

### Reproduce

```bash
cd <worktree at wt/h45-e2e-honesty, base be08495>
PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py          # rewrite evidence + manifest
PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py --verify # FRESH or STALE per file
PYTHONPATH=. python3 -m unittest tests.test_harness_e2e -v                 # 21 tests
```

A second `harness_e2e.py` run is byte-identical (verified by `sha256sum` before/after). No provider
call, no spend, no network: the model and research halves remain recorded.

## H-46b — the harness authors complete-sentence shorts (base `cd818fa` + H-45)

H-46 (`cd818fa`) made the lesson validator judge the shape of a text's ending. On that line the
recorded H-40 packet stopped replaying: the replay engine synthesised every `segments[].short`,
`worked_example.short` and `learner_explanation_short` as a 2/3 word-boundary prefix, so each short
was a clipped sentence — the exact D8 defect the new gate refuses. All three scenarios landed in
`needs_review` and the harness never reached `attempt.submit`. The validator was not touched, and
`tests/test_text_completeness.py` still passes on this head.

### What changed

* **The recording authors the shorts.** `build_transcripts.py` now carries a `SHORTS` table with
  `practice_short` / `criterion_short` / `explanation_short` for every lesson (17 lessons, 51
  fields), and the replay engine serves those. A provider writing under the guided-writing contract
  authors a compressed sentence; it does not emit a truncated prefix.
* **`_shorten` is the fallback and now cuts on a boundary.** It still returns a strict prefix (so
  every claim atom it carries is already in the deep text), but it lands on a sentence end, a
  punctuation clause boundary, or a coordinating/subordinating conjunction, keeps the terminal mark,
  and only accepts a candidate the product's own `text_completeness` predicate reads as finished and
  the lesson schema accepts (`minLength 8`). `worked_example.short` still comes from it (the first
  complete sentence of `"The step is done and checked. …"`).
* **New tests** (`ShortCompletenessTest`, 5 tests) assert every authored short is strictly shorter
  than its deep text, carries no atom its deep text lacks (`generation._short_problems`), and is a
  finished text (`text_completeness.completeness_problems`), plus the fallback contract and the D8
  regression shape.
* **H-45 merged** so the regenerated packet is content-addressed: `manifest.json` now pins this
  run's bytes and `harness_e2e.py --verify` prints `FRESH`. H-45 was done but unmerged; without it
  the card's "freshness hash" step has no mechanism on this line.

Example shorts now served (`evidence/*.json`):

| deep (recorded) | short (authored) |
|---|---|
| "Deflate the tyre fully, open the brake quick-release, and lift the wheel out of the dropouts without levering the bead." | "Deflate the tyre fully and lift the wheel out of the dropouts." |
| "The home chord is the one the song resolves to; name it before the key." | "Name the home chord before the key." |
| "Fresh solder and alternating heat keep the part and the pads alive." | "Fresh solder and alternating heat keep the pads alive." |

The former synthesiser produced `"…lift the wheel out"`, `"…the song resolves."` and
`"…keep the part."` for those three, which is what the gate refused.

### Verification (real output)

```text
python3 audit/adversarial/harness-e2e/build_transcripts.py
  wrote transcripts/{bicycle_single,music_short,soldering_full}.json
PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py
  bicycle_single: PASS  scope=single units=1 objectives=1 checks=1 lessons=1 validation=independently_validated
  music_short: PASS  scope=short units=2 objectives=4 checks=4 lessons=4 validation=independently_validated
  soldering_full: PASS  scope=full units=6 objectives=12 checks=12 lessons=12 validation=independently_validated
  overall: PASS  (3/3 scenarios)
  packet: 8 evidence file(s) content-addressed in manifest.json; 3 transcript input(s)
PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py --verify
  packet: FRESH — every evidence file and harness input matches manifest.json
PYTHONPATH=. python3 -m unittest tests.test_harness_e2e -v
  Ran 26 tests ... OK        (evidence/focused-tests.txt)
PYTHONPATH=. python3 -m unittest discover -s tests -t .
  Ran 1521 tests in 148.358s ... OK   (evidence/full-suite.txt)
```

Manifest pins for this run (`--verify` output, `manifest.json`):

```text
harness  354be9ca5f31bf42aa6e40100692ca6edd6ca640e47d21547f6ad5afe9e63daf  harness_e2e.py
input    9be57663269cf5ae3cbdedf638cb6273dff7e40d998cc51eb6a814834031e938  transcripts/bicycle_single.json  scope=single
input    542687d37f2501ef96b1cfcd35174d396f85e052cea44e8ac930188ba004d1e5  transcripts/music_short.json  scope=short
input    7151d880e981d6ae2c8eef50e91ef7e17f9fa4ba2fdc7af10ba690817bf4a816  transcripts/soldering_full.json  scope=full
evidence 666326df17752329d406395eb2b87696822e52a0fd7a82ef84421da4d5587dd1  evidence/bicycle_single.json
evidence 3241bae9706f0954d97f0b8581ca134bb6c1d1747b5ef525c575d01ee7f621cc  evidence/focused-tests.txt
evidence 0d13301851caa24a304d8fcad939ce312d3f7709518c82930a1df30a40e6691b  evidence/full-suite.txt
evidence 0de2a3c53ea6e76b8b69bf1789676915b312cf350766702e1078b0da462d34e0  evidence/music_short.json
evidence f828f19d8570c2337cf7fd935951ba3bea9a786c861c67207cb07a1e593b98ff  evidence/partial_unit_batch.json
evidence 7e47d683ddaf5427d4ab69b21eb6a06aad9812610fca8727a3bed14c2d00d498  evidence/run-output.txt
evidence f65e748b04f6c715af579381e0d3b1f7eca5e31a19e5f98065f4aef3e591ff7f  evidence/soldering_full.json
evidence ea566e9a1f0d195fdfef9f054894820aa640d955d8f46305839003730c687a87  evidence/summary.json
```

### H-175: the soldering recording was re-fetched against the research floor

H-168 (`3d378a1`) floors research depth by course scope: a `full` course runs `deep` whatever
depth the dial declares. For this scenario that means **10 derived queries** where the H-40
recording answered a goal-only `survey`/`working` pass with one placeholder page. The packet's
claim is byte reproduction, so the recording — not the product — had to move.

`soldering_full.json` now holds a **recorded result set** (`research.mode =
"recorded_result_set"`, six `pages`), each page really fetched through the host extract seam on
2026-11-08 for one of the six queries the floor adds:

| `recorded_for` | publisher | URL |
|---|---|---|
| reference documentation | STMicroelectronics | `st.com/resource/en/technical_note/tn1225-mounting-instructions-for-thd-throughhole-device-packages-stmicroelectronics.pdf` |
| official guidance | Purdue University | `engineering.purdue.edu/ece477/.../9-AssemblyAndSoldering.pdf` |
| common mistakes | University of Colorado Boulder | `physicslabs.colorado.edu/courses/phys-3330/resources/soldering/` |
| examples and practice | iFixit | `ifixit.com/News/97850/soldering-simplified-a-newbies-guide-to-through-hole-soldering` |
| step by step | Instructables | `instructables.com/Soldering-Through-Hole-Components/` |
| glossary | iFixit | `ifixit.com/Wiki/Soldering_Glossary_of_Terms` |

The replay returns the fixed set for every derived query and the pipeline's own dedupe,
source-type ranking and page budget decide what is fetched; a fetch for a URL the recording does
not hold raises rather than inventing a page. Page text is the seam's own output, never authored
at replay time. `build_transcripts.py` preserves this block instead of writing a placeholder over
it (`preserve_recorded_result_set`), and fails loudly if the recording is missing.

Two consequences worth recording rather than hiding:

* the validation request for the 12-unit / 40-objective ceiling plan now exceeds 24,000 bytes when
  spelled with `indent=1`, and `_bounded_input` used to cut that text mid-token — handing the
  recorded validator invalid JSON and failing `plan_at_declared_bound_accepted`. It now falls back
  to the compact encoding of the same document (20,364 bytes here) and raises a typed
  `GenerationRejected` only if even that cannot fit. The request byte bound is unchanged.
* the two single-page recordings now carry no `publisher`, so the ledger derives it from the URL
  (`example.invalid`) instead of the old hard-coded `"Recorded publisher"`. That is the only byte
  change in `bicycle_single`/`music_short`, and their verdicts are unchanged.

`labels.provider_calls` stays `0`: nothing here called a provider. The pages were fetched once,
at recording time; the replayed run is offline and spends nothing.

Current pins (`--verify`, this tree):

```text
harness  366d4456eaf279212957a7a3939ba90b381ae0a81e254d98dd2a23316c721a7e  harness_e2e.py
input    9be57663269cf5ae3cbdedf638cb6273dff7e40d998cc51eb6a814834031e938  transcripts/bicycle_single.json  scope=single
input    542687d37f2501ef96b1cfcd35174d396f85e052cea44e8ac930188ba004d1e5  transcripts/music_short.json  scope=short
input    05933d564cec4ad51e0af3104746229150cc6a892a931be0cc324100a1d12644  transcripts/soldering_full.json  scope=full
evidence a780008490fc2a716901a153b179059b74a277109454be0f32721d6ff7d75635  evidence/bicycle_single.json
evidence 729e1c642d90f317c2b0c8bccbd82282d184f55e1e09e0203466ab46963938c8  evidence/music_short.json
evidence 06dba5cf350f6e3e5c3bca813a00a41385307a60a95f62099daa0608c2a92a88  evidence/run-output.txt
evidence 3e9eef77aff04d77f1b80181d4704b94291af9f7d37cb4a66fa40302567a6fd9  evidence/soldering_full.json
```

The packet reports 10 queries, 6 fetches, 6 sources and `status: ok` on `soldering_full`, and the
three scenarios are 3/3 PASS. `evidence/focused-tests.txt` and `evidence/full-suite.txt` are the
H-45 runs and were not regenerated here, so the manifest still pins those older bytes; this card
ran `tests.test_harness_e2e` (26 tests), `tests.test_research_floor` (5 tests) and
`tests.test_generation` (87 tests) and all passed.


### Finding raised rather than fixed (P3, gate false positive) — resolved by H-51

**Current rule (H-51 `2620c95`, 2026-11-07).** `_DANGLING_WORDS` no longer carries prepositions.
A terminal preposition is judged structurally: it is dangling unless the word immediately before it
is the finite verb of its clause and at least one token precedes that verb as the clause's subject.
"The home chord is the one the song resolves to." therefore passes, while "…becomes the reference
for." and a bare "resolves to." still fail. Verb-hood is decided by shape (`-s`/`-ed`/`-ing`, a
closed set of auxiliaries and irregular past forms), not by a content-verb lexicon. The rule and
its accepted false-negative risk (a strand after a bare infinitive is still refused) are the
*stranded prepositions* paragraph of the `coursebook/text_completeness.py` module docstring. The
H-49 evidence packet is byte-identical after the change.

*H-46b's note, kept as the record of why the change was made:* on `cd818fa` (2026-11-07)
`text_completeness._DANGLING_WORDS` contained `to`, so a complete English sentence with preposition
stranding was refused: **"The home chord is the one the song resolves to."** ended on `to` and was
rejected as `dangling_terminal_word` even though it was finished. The recorded short for that lesson
was therefore authored as "Name the home chord before the key." rather than the truer compression.
That was a false positive in the H-46 signal, not a reason to relax it; it belonged to H-46's owner.

Known limitation of the fallback: mechanical prefixing still cannot guarantee a grammatical short
for a one-clause sentence that offers no boundary (e.g. "Fresh solder and alternating heat keep the
part and the pads alive." has no clause cut that keeps the object). That is exactly why the packet
now serves authored shorts and treats `_shorten` as a fallback only. Nothing in the current
evidence packet depends on a mechanically cut short except `worked_example.short`, whose first
sentence is complete by construction.

## H-49 — packet re-run on the merged tree (base `90e1f0d` + H-44/H-45/H-46/H-46b/H-47)

The isolated H-46b packet was byte-reproducible on its own line but **not** on the merged tree: H-44
adds `domain_provenance`, `locale` and `target_language` to the plan-stage record, so the three
scenario evidence files no longer matched `manifest.json` (3 failures in
`PacketManifestTest.test_fresh_evidence_reproduces_the_committed_bytes`). This is the manifest doing
its job, not a harness defect.

Regenerated on the merged tree and re-pinned. The complete evidence diff is 24 added lines: the
provenance block (`source: declared`, `resolved_domain`, `declared_subject_domain`,
`declared_locale`, `target_language`) plus `locale`/`target_language` on each plan record. No
verdict, lesson text, check or grading row changed.

```text
PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py
  overall: PASS (3/3 scenarios)
PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py --verify
  packet: FRESH — every evidence file and harness input matches manifest.json
PYTHONPATH=. python3 -m unittest tests.test_harness_e2e -v
  Ran 26 tests ... OK        (evidence/focused-tests.txt)
PYTHONPATH=. python3 -m unittest discover -s tests -t .
  Ran 1524 tests in 145.706s ... OK   (evidence/full-suite.txt)
```

The P3 gate false positive above (preposition stranding on `to`) was still open at H-49 — it is
H-46's signal, not this packet's. H-51 `2620c95` has since made the judgement structural, so the
packet's bytes are unchanged and the false positive is closed; see the H-46b note above.

## H-191 follow-up — packet re-run after the validator shape repair (`wt/h191-item-label`, base `883cdfe`)

`coursebook.generation._call_llm` now records how many schema re-asks a structured answer took and
surfaces it as `validation.shape_violations`. That key is part of the plan-stage record the packet
embeds, so the three scenario evidence files no longer matched `manifest.json` (3 failures in
`PacketManifestTest.test_fresh_evidence_reproduces_the_committed_bytes`) — the manifest doing its
job, as in H-49.

Regenerated on this tree and re-pinned. The complete evidence diff is **additive only**:
`shape_violations: 0` on each embedded `validation` block (2 sites in `bicycle_single`,
5 in `music_short`, 4 in `soldering_full`, plus the ceiling-probe line in `run-output.txt`).
No verdict, outcome, independence, lesson text, check or grading row changed; each scenario is
still `independence: independent` / `outcome: independently_validated`.

```text
PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py
  overall: PASS  (3/3 scenarios)
PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py --verify
  packet: FRESH — every evidence file and harness input matches manifest.json
```

Why the packet was re-derived rather than the key dropped: an operator reads a repaired validation
in the plan-stage record (`coursebook/executor.py` carries `result["validation"]`), and a re-asked
answer must never read as a first-time one.

## GM-005 re-run — packet re-derived under contract v21 (`wt/gm-005-takehome`)

Registering `cb.rpc` v21 for the take-home pack backend changed the version every recorded
`api.dispatch` response echoes, so the three scenario evidence files no longer matched
`manifest.json` (3 failures in `PacketManifestTest.test_fresh_evidence_reproduces_the_committed_bytes`,
`contract_version: 20` on disk vs `21` from a fresh run) — the manifest doing its job, as in H-49 and
H-191. No transcript, verdict, lesson text, check, grading row or assertion changed.

Re-derived by the packet's own runner, not hand-edited:

```text
PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py
  overall: PASS  (3/3 scenarios)
PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py --verify
  packet: FRESH — every evidence file and harness input matches manifest.json
```

The complete evidence diff is `contract_version: 20 -> 21` (8 sites across the three scenario files)
plus the manifest hashes those bytes determine. GM-015 re-audits this packet on the integrated tree;
the re-run preserves provenance because the harness, transcripts and assertions are unchanged and
the diff is the live contract constant only.
