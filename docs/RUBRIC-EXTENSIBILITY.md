# Rubric registry extensibility — the gate for a new construct profile (H-24)

| | |
|---|---|
| Card | `H-24` / `t_29e6647c` ("Rubric registry extensibility — decide the gate for new constructs") |
| Branch | `wt/harness-rubric-extensibility` |
| Base | `2e57efa` (current `master`) |
| Author | Atlas (architecture), 2026-11-07 |
| Source findings | `docs/ADVERSARIAL-HARNESS-REVIEW.md` §P1-6 (line 223, "The six-profile rubric registry is static"); `docs/GENERIC-HARNESS-REVIEW.md` §G-07 (line 134, "Rubric profiles are static") |
| Status | **Frozen decision.** No product code, no contract change, no migration. |
| Contract / DB delta | **None.** |
| Related frozen decision | `dd43d82:docs/ASSESSMENT-BREADTH.md` (H-16) — the 0.1.0 construct breadth |

This is a decision card. It changes no Python, no `desktop/plugin.js`, no contract and no database.
It spends no provider money and is not demo copy.

**Provenance.** `docs/ASSESSMENT-BREADTH.md` is not on `master` at `2e57efa`; it lives at
`dd43d82` on `wt/harness-assessment-breadth`. Every citation to it below is written
`dd43d82:docs/ASSESSMENT-BREADTH.md §N` so the reference resolves without depending on a merge.
Note also a numbering collision that would otherwise corrupt a citation: `ADVERSARIAL-HARNESS-REVIEW.md`
§P1-6 is the rubric-registry finding (the source of this card), while `ADVERSARIAL-AUDIT-ROUND2.md`
§P1-6 is the flat cost ceiling. This document cites findings by file and section title, never by a
bare `P1-6`.

---

## 1. Decision: **A — the static registry is sufficient for 0.1.0**

The six profiles cover every construct the 0.1.0 product can collect and can name as an evidence
target. No supported construct is left without a profile, and no profile is missing an evidence
target. The refusal is recorded here rather than left as P1-6's unowned phrase.

**What is refused.** Coursebook does not synthesise a rubric profile at runtime. No plan, lesson,
pack, job, learner action or provider response may create, rename, extend or select a profile
outside the six labels in `coursebook.policy.RUBRIC_PROFILES` (`policy.py:93-100`), and no free-text
rubric may become a profile. A model may write the **criteria text** inside a selected profile —
that is what generation already does — but the profile itself is code and is validated by
`tests/test_rubrics.py`, not by the model.

**The exact list of supported constructs for 0.1.0** (collection surfaces in §3; breadth frozen by
`dd43d82:docs/ASSESSMENT-BREADTH.md` §1 and §9):

1. a written answer, free text (`answer_kind = text`);
2. a selection-shaped answer, which is the same written answer copied into `selection[]` — there is
   no separate selection control;
3. a verification checklist (`check.kind = verification`, `stimulus.format = verification`,
   `stimulus.items[]`), confirmed through the same written-answer surface;
4. a parent observation record (`check.kind = observation`, `evidence_class = parent_reported`);
5. practice-only pronunciation (`pronunciation.attempt`, `model_assessed`, never evidence).

Executable code, recorded performance and submitted artifacts remain **out** of 0.1.0, behind
H-16 §10's gates. They are not reopened by this card.

**The condition that reopens this decision.** Reopen only when all three hold:

1. a construct on the supported list above has **no** existing profile that can score it — proved by
   `rubrics.serves(profile, target) is False` for all six profiles, not by inspection of prose; and
2. that construct is inside the frozen 0.1.0 breadth, or an H-16 amendment has added it to the
   breadth first; and
3. a named collector and grading lane exist for it, so a new profile would attach to something that
   can actually produce a verdict.

A construct that the harness can teach but cannot collect, or can collect but cannot grade, is not a
rubric-registry gap and does not reopen this decision. §2 and §6 keep those two questions apart.

---

## 2. "Coverage" has three layers, and the registry only owns two

The audit's phrase "forced into the nearest angle" is about the first two layers. Stating which
layer a claim belongs to is what keeps this document honest.

| Layer | Question | Owner | State at `2e57efa` |
|---|---|---|---|
| 1. Registry | Does a profile declare that it can score this evidence target? | `coursebook/rubrics.py` | Complete: all 16 declared pairs are valid; `registry_problems()` is empty |
| 2. Selection | Does a 0.1.0 path actually choose that profile for that target? | `coursebook/policy.py`, `rubrics.resolve_profile` | Complete: every declared pair is reachable (proved in §4) |
| 3. Scoring | Does an answer get a verdict scored against that profile's criteria? | `coursebook/grading.py` | **Not reached by any profile.** The open lane is unconfigured (B-1) |

Layer 3 is the load-bearing fact for this decision, so it is cited rather than asserted:

- `grading.grade` routes on the **reference** the check stores (`grading.py:201-227`). A closed kind
  (`exact`, `numeric`, `selection` — `validators.py:29`) takes `grade_closed`, which reads only
  `rubric.pass_rule` and never inspects a criterion (`grading.py:82-104`).
- Anything else — including a missing kind, or `rubric_only` — takes `grade_open`, the only lane
  that receives rubric criteria (`grading.py:165-190`). That lane stays unconfigured in the shipped
  runtime (`configure_aux_grader` is called only from tests; `docs/ARCHITECTURE.md:80`), so the
  attempt is persisted as `needs_retry` and nothing advances (`domain.py:1184-1204`).
- Generated checks store no reference `kind` at all (`generation.py:3731-3735`), so every generated
  check takes the open lane.
- Pack import writes `rubric_only` for `production`/`transfer` and `exact` otherwise
  (`pack_flow.py:253-261`). Only `exact` is produced by product code; the `numeric` and `selection`
  reference kinds exist in `validators.py:11-14` and in tests, not in a producer.

So the six profiles are **authoring and validation constraints**, not scoring engines, in 0.1.0.
They are injected into the lesson prompt (`generation.py:1414-1421`) and they gate the stored
criteria at authoring time (`generation.py:1863-1864`, `packs.py:375-376`). Adding a seventh profile
would add authoring vocabulary and would not make one more answer gradable. That asymmetry is the
core reason Option A is the correct verdict rather than the timid one.

---

## 3. The constructs 0.1.0 can actually collect

Measured from the contract and the Desktop renderer, not from the design docs.

| # | Construct | Collection surface | What is stored | Profile used at authoring | Scored in 0.1.0? |
|---|---|---|---|---|---|
| 1 | Written answer | `attempt.submit`, answer `kind: "text"`; one textarea (`desktop/plugin.js:4271-4279`, answer object `:4049-4053`) | `attempts.answer_json` / `answer_kind` | the target's profile (§4) | **No** — generated reference has no kind → open lane → `needs_retry` (B-1) |
| 2 | Selection-shaped answer | the same textarea; answers ≤200 characters are also copied into `selection[]` (`plugin.js:4049-4053`); choices are display-only (`:4227-4234`) | same attempt row | the target's profile | A pack-imported `exact` check grades the answer text deterministically (`validators.py:224-237`); the closed lane reads only `pass_rule` from the rubric, never a criterion |
| 3 | Verification checklist | `check.kind = verification`, `stimulus.format = verification`, `items[]` printed once, read-only (`plugin.js:4236-4256`); the learner still answers in the textarea | `stimulus_json.items` plus one attempt answer | `procedural`, or `language_production` for a language oral/written brief (`policy.py:612-634`) | **No** — no closed reference kind |
| 4 | Parent observation | `check.kind = observation`; the only recorder is `domain.record_observation` (`domain.py:2998-3033`) | a layer-1 evidence row, `self_reported`/`parent_reported`; never advances an objective | `observation` (`policy.py:620-624`) | **No** — no RPC method, handler or UI (B-2) |
| 5 | Practice-only pronunciation | `pronunciation.attempt` (`contracts/rpc.v10.json:68`), local recogniser | `pronunciation_attempts`, `model_assessed`; never an `attempts` row, never evidence | `language_production` at authoring; no rubric is applied to the practice result | **No, by design** — practice is not evidence (`dd43d82:docs/ASSESSMENT-BREADTH.md` §2.3) |

Refused constructs (no collection surface at all): executable code, recorded performance, submitted
artifact. `dd43d82:docs/ASSESSMENT-BREADTH.md` §1 and §9; not reopened here.

The Japanese demo pack was not used as evidence for anything in this document. The inventory is
derived from the registry and policy functions by direct evaluation and from source citations only.

---

## 4. Inventory: every `evidence_target` × profile pair

36 pairs. Status definitions:

- **covered** — the registry declares the pair (`serves()` true) **and** at least one 0.1.0 selector
  reaches it. This is layers 1–2 of §2, not a claim that an answer is scored.
- **unsupported** — the registry refuses the pair by design; `validate_rubric` returns a problem
  naming the pair (`rubrics.py:495-499`). The "selector in 0.1.0" column carries the profile's own
  recorded limitation (`rubrics.py:112-284`) as the reason.
- **missing** — the registry declares the pair but no 0.1.0 selector reaches it.

| # | `evidence_target` | profile | status | selector in 0.1.0 |
|---|---|---|---|---|
| 1 | `recall` | `concept_explanation` | unsupported | Explaining a concept is not recalling a label and not performing a procedure. |
| 2 | `comprehension` | `concept_explanation` | covered | default for `comprehension` |
| 3 | `production` | `concept_explanation` | unsupported | Explaining a concept is not recalling a label and not performing a procedure. |
| 4 | `discrimination` | `concept_explanation` | unsupported | Explaining a concept is not recalling a label and not performing a procedure. |
| 5 | `procedure` | `concept_explanation` | unsupported | Explaining a concept is not recalling a label and not performing a procedure. |
| 6 | `transfer` | `concept_explanation` | covered | default for `transfer` |
| 7 | `recall` | `procedural` | unsupported | A procedure is not scored on describing it; the observed steps carry the evidence. |
| 8 | `comprehension` | `procedural` | unsupported | A procedure is not scored on describing it; the observed steps carry the evidence. |
| 9 | `production` | `procedural` | unsupported | A procedure is not scored on describing it; the observed steps carry the evidence. |
| 10 | `discrimination` | `procedural` | unsupported | A procedure is not scored on describing it; the observed steps carry the evidence. |
| 11 | `procedure` | `procedural` | covered | default for `procedure`; also `one_off` verification |
| 12 | `transfer` | `procedural` | covered | `one_off` verification (`check_angle=verification`) |
| 13 | `recall` | `language_production` | unsupported | Reading comprehension is not production; a romaji-only answer is not script reading. |
| 14 | `comprehension` | `language_production` | unsupported | Reading comprehension is not production; a romaji-only answer is not script reading. |
| 15 | `production` | `language_production` | covered | default for `production` |
| 16 | `discrimination` | `language_production` | unsupported | Reading comprehension is not production; a romaji-only answer is not script reading. |
| 17 | `procedure` | `language_production` | unsupported | Reading comprehension is not production; a romaji-only answer is not script reading. |
| 18 | `transfer` | `language_production` | covered | language domain + spoken intent; `one_off` language brief |
| 19 | `recall` | `recall_accuracy` | covered | default for `recall` |
| 20 | `comprehension` | `recall_accuracy` | unsupported | Recognition is not production, and a cued answer is not unaided recall. |
| 21 | `production` | `recall_accuracy` | unsupported | Recognition is not production, and a cued answer is not unaided recall. |
| 22 | `discrimination` | `recall_accuracy` | covered | default for `discrimination` |
| 23 | `procedure` | `recall_accuracy` | unsupported | Recognition is not production, and a cued answer is not unaided recall. |
| 24 | `transfer` | `recall_accuracy` | unsupported | Recognition is not production, and a cued answer is not unaided recall. |
| 25 | `recall` | `source_analysis` | unsupported | A source analysis is not a summary; an assumed provenance is not a cited one. |
| 26 | `comprehension` | `source_analysis` | covered | history domain + source-analysis intent |
| 27 | `production` | `source_analysis` | unsupported | A source analysis is not a summary; an assumed provenance is not a cited one. |
| 28 | `discrimination` | `source_analysis` | unsupported | A source analysis is not a summary; an assumed provenance is not a cited one. |
| 29 | `procedure` | `source_analysis` | unsupported | A source analysis is not a summary; an assumed provenance is not a cited one. |
| 30 | `transfer` | `source_analysis` | covered | history domain + source-analysis intent |
| 31 | `recall` | `observation` | covered | `recipe=parent` only |
| 32 | `comprehension` | `observation` | covered | `recipe=parent` only |
| 33 | `production` | `observation` | covered | `recipe=parent` only |
| 34 | `discrimination` | `observation` | covered | `recipe=parent` only |
| 35 | `procedure` | `observation` | covered | `recipe=parent` only |
| 36 | `transfer` | `observation` | covered | `recipe=parent` only |

**Counts: 16 covered, 20 unsupported, 0 missing.**

How the table was produced, deterministically: `RUBRICS`, `serves()`,
`DEFAULT_PROFILE_BY_EVIDENCE_TARGET` and each profile's `limitation` were read from
`coursebook/rubrics.py`, not transcribed by hand; the `covered` rows were then checked against the
selector, because a declared pair is not covered until a path reaches it. Reachability was measured
by evaluating `plan_lesson_capability` for all 6 targets × 5 recipes × 3 domains (`general`,
`language`, `history`) with one probe intent per domain, then applying
`rubrics.resolve_profile(plan.rubric_profile, target)`. Result: for every target, the set of
effective profiles equals the set of declared profiles. No declared pair is unreachable and no
selected profile falls back to a target it cannot serve (§12 records the output).

---

## 5. Per-profile inventory

| profile | construct | criteria | targets it serves | selected by | 0.1.0 note |
|---|---|---|---|---|---|
| `concept_explanation` | explains a concept in their own words | 4 | `comprehension`, `transfer` | default for both | the policy's catch-all angle when no other construct matches; the target default for `comprehension`/`transfer` |
| `procedural` | performs or verifies a procedure | 3 | `procedure`, `transfer` | default for `procedure`; `one_off` verification | the checklist profile (`policy.py:626-634`) |
| `language_production` | produces a spoken or written target phrase | 4 | `production`, `transfer` | default for `production`; language spoken/production intent | also the authoring angle for practice-only pronunciation |
| `recall_accuracy` | retrieves the answer without the key in view | 3 | `recall`, `discrimination` | default for both | the only profile with no `transfer` claim |
| `source_analysis` | analyses a source's claim, evidence and provenance | 4 | `comprehension`, `transfer` | history domain + source-analysis intent (`policy.py:646-651`) | never a default; needs the intent detector to fire |
| `observation` | records what a child did, without grading the child | 4 | all six | `recipe=parent` only (`policy.py:620-624`) | declared for every target, but the recorder is unreachable (B-2) |

Every profile carries 3–6 distinct criteria, and no criterion states a mental state
(`rubrics.py:382-389`; `tests/test_rubrics.py::test_every_profile_has_three_to_six_distinct_observable_criteria`).

---

## 6. What is missing, what is unsupported, and what is a different problem

**Missing: none.** Zero pairs are declared-but-unreachable, and zero supported constructs lack a
profile. That is the answer to the audit's actual worry: for the 0.1.0 surface, no discipline is
"forced into the nearest angle" — the nearest angle is a declared, validated angle for every target
the product can name.

**Unsupported: 20 pairs, all by design.** They are the construct-level refusals the registry exists
to make: a recall check is not scored as an explanation, a production check is not scored as recall.
The refusal is executable — `validate_rubric` names the profile, the target and the targets the
profile does serve (`rubrics.py:495-499`) — which is stronger than a comment in a design doc.

**Not a registry gap, but a real delivery gap.** Two delivery gaps mean that covered pairs cannot
produce a record or a verdict in the product today, for reasons outside the registry:

- **B-1 (High, Cinder, `t_673155b0`).** Generated checks store no closed reference kind, so every
  generated check routes to the unconfigured open lane and persists `needs_retry` with nothing
  advanced. Measured in `dd43d82:docs/ASSESSMENT-BREADTH.md` §2.2.
- **B-2 (High, Cinder, `t_74d99ca5`).** `domain.record_observation` has no RPC method, handler or
  UI, so `self_reported`/`parent_reported` are unreachable. `grep -rn record_observation` finds only
  the definition (`domain.py:2998`) and two test call sites; `dd43d82:docs/ASSESSMENT-BREADTH.md`
  §2.3 and §11.

The important consequence for this card: **neither is fixed by adding a profile**, and neither
reopens Option A. A seventh profile attached to a lane that cannot grade would be the exact
"partially functional control" `PREBUILD_SPEC.md` §2 forbids.

---

## 7. Finding while deciding: the lesson prompt carries two profile identities

Not a registry-coverage gap; recorded because it is the same drift the registry's docstring claims
cannot happen (`rubrics.py:12-16`).

`run_lesson_job` resolves the effective profile at `generation.py:3928`, then passes both the
resolved `rubric_profile` **and** the raw `capability` into `build_lesson_request`
(`generation.py:3942-3955`). The prompt builder then emits two statements from different values:

- `generation.py:1266` prints `- rubric profile: {capability.rubric_profile}.` — the **unresolved**
  policy value;
- `generation.py:1414-1421` prints `Rubric profile: {profile} ({construct}). Score only these
  observable aspects: …` — the **resolved** value.

A deterministic probe (no provider):

```
plan_lesson_capability(recipe="one_off", evidence_target="recall",
    lesson_intent="Recall the three safety labels for the pressure vessel.",
    subject_domain="technical_procedure")
  capability.rubric_profile        : procedural
  resolve_profile(...)             : recall_accuracy
  _capability_prompt_lines(cap)[2] : - rubric profile: procedural.
  serves("procedural", "recall")   : False
```

When the two differ, the model is told to score a construct the validator will reject. This is
fail-closed: `enforce_lesson_rules` validates against the resolved profile
(`generation.py:1863-1864`), the section regenerates once, and if the mismatch survives the second
attempt the lesson is parked with `verdict = reject` and stored as `needs_review` with the rule
reasons attached (`generation.py:3992-3996`, `:4030-4041`). The check is stored closed with
`audit_state = "failed"` (`generation.py:4092-4093`) and `attempt.submit` refuses it
(`domain.py:1129-1133`), so the mismatched rubric cannot be graded. The cost is generation churn and
a section the learner cannot progress past until it is repaired. Of the 90
`(target × recipe × domain)` probe combinations in §4, 42 differ between the advisory and the
effective profile.

Filed as **`t_2801b1cc`** (Cinder, Medium). H-24 does not fix it: this card is docs-only.

---

## 8. The gate for any future construct profile

Nothing here authorises a new profile. It is the checklist a proposal must pass before one is added,
whichever card eventually does it.

**G1 — Construct, not topic.** The proposal names an observable construct ("labels a wiring harness
from a schematic"), not a subject ("electronics"). It must state which collection surface in §3
carries the evidence. "The topic does not fit" is not a gate failure; a topic is not a construct.

**G2 — Bounded declarative data.** A profile is five fields, no prose template:
`name` (snake_case, unique, ≤48 characters), `construct` (one sentence), `criteria` (3–6 records of
`{key, label, observation}`), `evidence_targets` (a non-empty subset of the six), `limitation` (one
sentence naming what the profile must not be used for). The existing registry
(`rubrics.py:54-103`) is the schema; a new profile is the same shape, not a new mechanism.

**G3 — Observable criteria only.** Every `label` and `observation` must pass the registry's
mental-state rule (`rubrics.py:309-324`, `:388-389`). Each observation names an action a scorer can
see in the stored answer: "names the stop condition", not "understands the risk".

**G4 — Distinct criteria.** 3–6 criteria; labels distinct after case, spacing and punctuation
normalisation (`rubrics.py:357-360`); no criterion restates another. The floor is
`policy.MIN_RUBRIC_CRITERIA = 3`; the ceiling is `MAX_RUBRIC_CRITERIA = 6`.

**G5 — Explicit profile ↔ target compatibility.** `evidence_targets` is declared, not inferred, and
`validate_rubric` must refuse every target outside it (`rubrics.py:495-499`). The default table
(`rubrics.py:293-302`) must stay total: every evidence target still resolves to a profile that
serves it, or `registry_problems()` fails (`rubrics.py:395-401`).

**G6 — A deterministic registry test, not a demo.** Adding a profile requires, in
`tests/test_rubrics.py`: `registry_problems()` empty; the profile present in both the policy
vocabulary and the registry in the same order; its labels equal to the policy copy; its own criteria
accepted for each declared target and rejected for at least one undeclared target; the default table
still total; the JSON projection free of an answer. No provider call, no fixture pack, no demo.

**G7 — A model may propose criteria; it may not add a profile.** Criteria text may come from a model
and is then validated deterministically — that path already exists (`generation.py:1414-1421` asks
for criteria; `generation.py:1863-1864` validates them). A profile is different: it is a vocabulary
change and lands as reviewed code, approved by the architecture owner (`x-owner` pattern,
`contracts/vocabulary.v1.json:7`). There is no "profile proposal" RPC and there must not be one.

**G8 — No free-text profile, no runtime trust policy.** A pack cannot name a profile: pack manifests
carry no construct and `packs.py:375` derives the default from the check's evidence target. A
generated lesson's profile comes from `policy` and `resolve_profile`, and the model's echoed
`policy` object is overwritten (`generation.py:3960`). No stored profile can be edited by a
learner, parent or pack.

**G9 — Adding a profile never widens grading.** A profile adds authoring and validation vocabulary
only. It cannot add a check kind, an answer kind, an evidence class, an RPC method or a grading lane,
and it cannot make the open lane live. If a proposal needs any of those, it is an H-16 amendment
first, with H-16 §10's evidence, and it is not a rubric-registry change.

---

## 9. The seam this decision does not authorise (Option B, costed)

Option B was considered and rejected for 0.1.0: there is no construct it would serve, and it would
add a trust boundary with nothing behind it. Recording what it would have required makes the refusal
checkable later and prevents a future proposal from re-deriving it.

- **Schema.** The five fields in G2, plus a stable `schema_version` and a closed
  `evidence_targets` enum. Free-text criteria inside a profile are allowed; free-text *profiles* are
  not — a profile is data with a fixed shape.
- **Validation.** `registry_problems()` extended to the new profile, `validate_rubric` unchanged,
  and a JSON Schema for the on-disk form if one is ever introduced. Validation runs at load time, so
  a bad profile is a refusal, never a degraded rubric.
- **Storage.** In-code, in `coursebook/rubrics.py`, or at most a bundled, read-only data file shipped
  with the plugin and validated on import. Never a database table, never a directory the learner,
  parent or a pack can write. There is no runtime-editable trust policy.
- **Who may add one.** The architecture owner approves; the implementation is a code change with
  tests (G6). A model may draft criteria; it cannot add a profile (G7).
- **Contract / migration.** None is required today. The profile name is not persisted: checks store
  `rubric_json` with criteria only (`domain.py:842`, `generation.py:4081`), no migration mentions a
  profile, and the capability plan is not a stored column. A version of the seam that *persisted*
  profile identity on a check would need a `cb.db` migration and a `cb.rpc` revision; that is a
  reason to avoid it, not a reason to design it now.

## 10. The H-16 boundary, restated

This decision does not widen assessment, and the following stay exactly as frozen:

- no code execution, recorded performance or submitted-artifact construct;
- no new `check.kind`, `stimulus.format`, `answer_kind`, `evidence_target` or `evidence_class`;
- no `artifact.submit`, `code.run`, `performance.submit` or `observation.record` method;
- no enablement of the open lane, and no provider spend on rubric synthesis or grading;
- no learner-upload or retained-audio path;
- no free-text rubric at runtime, and no profile outside the six labels.

Authority: `dd43d82:docs/ASSESSMENT-BREADTH.md` §1, §9 and §10, unchanged.

---

## 11. Follow-ups

This card creates **no** Option-B implementation cards, because Option A is the decision. The only
card filed from this work is the defect in §7:

| Card | Owner | Why |
|---|---|---|
| `t_2801b1cc` | Cinder | Lesson prompt states two rubric profiles when the advisory construct is off-target (§7) |

Pre-existing and untouched by this card: `t_673155b0` (B-1 grading lane), `t_74d99ca5` (B-2
observation unreachable). Neither is a rubric-registry gap and neither reopens §1.

---

## 12. Verification

All commands run from the worktree root at `2e57efa` with a docs-only working tree.

```
$ python3 -m unittest tests.test_rubrics -v
Ran 30 tests in 0.004s
OK
```

```
$ python3 ~/.hermes/profiles/atlas/cache/scratch/rubric_matrix.py
registry_problems: []
targets: ('recall', 'comprehension', 'production', 'discrimination', 'procedure', 'transfer')
profiles: ('concept_explanation', 'procedural', 'language_production', 'recall_accuracy',
           'source_analysis', 'observation')

recall        | default: recall_accuracy      | serves: ['recall_accuracy', 'observation']
comprehension | default: concept_explanation  | serves: ['concept_explanation', 'source_analysis', 'observation']
production    | default: language_production  | serves: ['language_production', 'observation']
discrimination| default: recall_accuracy      | serves: ['recall_accuracy', 'observation']
procedure     | default: procedural           | serves: ['procedural', 'observation']
transfer      | default: concept_explanation  | serves: ['concept_explanation', 'procedural',
                                                          'language_production', 'source_analysis', 'observation']
```

```
$ python3 ~/.hermes/profiles/atlas/cache/scratch/rubric_effective.py
fallbacks: 42
recall         -> effective: ['observation', 'recall_accuracy']                         | declared: same
comprehension  -> effective: ['concept_explanation', 'observation', 'source_analysis']  | declared: same
production     -> effective: ['language_production', 'observation']                     | declared: same
discrimination -> effective: ['observation', 'recall_accuracy']                         | declared: same
procedure      -> effective: ['observation', 'procedural']                              | declared: same
transfer       -> effective: ['concept_explanation', 'language_production', 'observation',
                              'procedural', 'source_analysis']                          | declared: same
```

`fallbacks: 42` is the count of combinations where the policy's advisory profile is not the
effective one — the §7 finding, not a coverage failure: every fallback lands on a profile that
serves the target.

The commit that adds this document contains one file, `docs/RUBRIC-EXTENSIBILITY.md`. That is the
only tree change in it, and `git show --stat HEAD` on the branch is the record.

```
$ bash scripts/validate-plugin.sh --worktree
== 1/3 plugin admission: PASS ==
== 2/3 desktop module parses as ESM (node --check) ==
desktop/plugin.js: syntax OK
== 2/3 desktop module: PASS ==
== 3/3 desktop contract tests (unittest) ==
Ran 7 tests in 0.005s
OK
== 3/3 desktop contract tests: PASS ==
Release gate passed: 3/3 checks on 2e57efac6c85256c469b8c966ab10a6a5750c116 (1229 files).
```

The gate exports tracked files, so `--worktree` gated this document before it was committed; the
commit that adds this file is docs-only and changes none of the gated surfaces.

---

## 13. Citation map

| Claim | Authority |
|---|---|
| Six profiles, their criteria and limitations | `coursebook/rubrics.py:112-284` |
| Profile ↔ target declarations | `coursebook/rubrics.py:288-290` |
| Default profile per target | `coursebook/rubrics.py:293-302` |
| Registry consistency rules | `coursebook/rubrics.py:367-402` |
| Pair refusal | `coursebook/rubrics.py:471-532` |
| Advisory → effective resolution | `coursebook/rubrics.py:428-437` |
| Profile vocabulary and labels | `coursebook/policy.py:93-112` |
| Profile selection rules | `coursebook/policy.py:612-668` |
| Capability plan | `coursebook/policy.py:671-735` |
| Profile injected into the authoring prompt | `coursebook/generation.py:1414-1421` |
| Stored rubric validated at authoring time | `coursebook/generation.py:1863-1864` |
| Generated check reference (no `kind`) | `coursebook/generation.py:3731-3735` |
| Pack rubric validated against the target default | `coursebook/packs.py:375-376` |
| Pack reference kinds | `coursebook/pack_flow.py:253-261` |
| Grading lane routing | `coursebook/grading.py:201-227` |
| Closed lane ignores criteria | `coursebook/grading.py:82-104` |
| Open lane receives criteria; unconfigured | `coursebook/grading.py:165-190`; `docs/ARCHITECTURE.md:80` |
| `needs_retry` persists and advances nothing | `coursebook/domain.py:1184-1204` |
| Observation recorder, layer 1 only | `coursebook/domain.py:2998-3033` |
| Desktop answer object and single textarea | `desktop/plugin.js:4049-4053`, `:4271-4279` |
| Checklist rendered read-only | `desktop/plugin.js:4236-4256` |
| Answer/evidence vocabularies | `contracts/vocabulary.v1.json:18-53` |
| Construct breadth for 0.1.0 | `dd43d82:docs/ASSESSMENT-BREADTH.md` §1, §2, §8, §9, §10 |
| Source findings | `docs/ADVERSARIAL-HARNESS-REVIEW.md:223`; `docs/GENERIC-HARNESS-REVIEW.md:134` |
