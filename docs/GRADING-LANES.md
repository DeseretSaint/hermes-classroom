# Grading lanes — H-20 decision record

| | |
|---|---|
| Card | `H-20` / `t_673155b0` ("Grading lane gap — generated checks store no reference kind") |
| Branch | `wt/harness-grading-lanes` |
| Base | `4dd68cb` (current master) |
| Authority | `docs/ASSESSMENT-BREADTH.md` §2.2, §8, §11 B-1 (H-16, Atlas) — this document implements finding B-1 and records the lane decision in that document's terms |
| Contract / DB delta | **None.** No `cb.rpc` bump, no migration, no new check kind, answer kind, evidence class or RPC method |

## 1. Defect as measured

`coursebook/grading.py` routed an answer by the reference's `kind`. A closed kind
(`exact|numeric|selection`) took the deterministic lane; **anything else, including a missing
kind**, took the open lane. The shipped runtime never configures the open lane's aux adapter, so:

* `generation._check_payloads` wrote `reference_answer`, `accepted_answers` and
  `accepted_alternatives` with **no `kind`** — every generated lesson check was ungradeable;
* `pack_flow.check_spec_from_pack_check` wrote `{"kind": "rubric_only"}` for `production` and
  `transfer` targets — those checks were ungradeable too.

Both persisted `needs_retry` on `attempt.submit` and advanced nothing. The failure looked like a
deliberate open response, which is why it survived review.

## 2. Frozen decision

### 2.1 A stored reference always declares a lane

`validators.REFERENCE_KINDS = (exact, numeric, selection, rubric_only)` — the existing closed
vocabulary plus the open lane's own tag. `validators.seal_reference(spec)` is the only sanctioned
constructor for `checks.reference_json`: it raises `ReferenceSpecError` when `kind` is missing or
unknown, so an unsealed reference cannot be written by construction.

Three gates enforce it:

| Gate | Behaviour |
|---|---|
| `generation._reference_payload` | every generated check calls `seal_reference`; the writer cannot emit a reference without a lane |
| `pack_flow.check_spec_from_pack_check` | every imported check calls `seal_reference` |
| `domain.check.open` / `progression.challenge_out` | refuse a spec whose reference declares no lane, `VALIDATION_FAILED` / `check_not_gradable`, before any check row is created |
| `grading.grade` | a missing/unknown kind raises `GradingUnavailable` (a grader failure — `needs_retry`), never a silent fallthrough to the open lane |

`REFERENCE_KINDS` gained one value after this record was written: `conversation` (H-120, `cb.rpc`
v16). It is a **closed** kind — graded from the stored transcript by deterministic code — so it is
listed with the closed lanes, not with `rubric_only`:

| Reference kind | Routed by `grading.grade` | Provider | What it reads |
|---|---|---|---|
| `conversation` | `coursebook.conversation.grade_transcript`, **before** the open lane is considered | **none** — `configure_aux_grader` is never called, and its result is never consulted | the stored **learner** turns only, against the declared targets, match clauses and turn range |

A conversation reference is written by `practice.end`, never by `attempt.submit`: grading the whole
bounded transcript at once is the only way a practice verdict stays honest, so `attempt.submit` on a
practice check is refused `POLICY_VIOLATION` / `error.details.reason =
"practice_requires_practice_end"`. Tutor text is never inspected, so nothing the model said during
the session can produce a pass; a reference the grader cannot read raises, and `practice.end`
persists `needs_retry` and advances nothing, exactly like every other lane that cannot finish.

### 2.2 Generated checks: `exact` over the declared answer forms

The learner answers every generated check through `answer.text`: the pane prints choices and
checklist items as text and submits what the learner typed. A generated quiz — `text` **or**
`selection` format — is therefore closed-form, and its stored reference is:

```json
{"kind": "exact", "answers": [<reference_answer>, <accepted_answers...>, <accepted_alternatives...>]}
```

All of those strings are correct by the author's own declaration; the union is the accepted set.
The legacy keys (`reference_answer`, `accepted_answers`, `accepted_alternatives`) stay in
`reference_json` because the answer-guide export and the answer-leak re-check read them.
`reference_json` is internal storage and never projected (`check.get` withholds it), so no
contract change is needed.

A generated `production` check is a **closed** check: `plan_ja` declares a selection quiz with an
accepted phrase set for a `production` target, and it now grades deterministically. Evidence
target is not what decides the lane — the reference vocabulary is.

### 2.3 Verification checklists and parent observations: `rubric_only`, recorded, not graded

A verification checklist is a **self-report**, not a comparable answer (`PREBUILD_SPEC.md` §5:
"completion means instruction_complete plus an explicit verification checklist, which may be
`self_reported`"). Its `accepted_answers` describe a confirmation ("all three steps ticked
honestly"), not a string a learner types, and 0.1.0 has no seam that collects which items were
ticked. Grading a typed string against that prose would manufacture a verdict.

Decision: generated `verification` checks and `observation` checks declare `{"kind":
"rubric_only"}` **explicitly**, so a missing kind is never mistaken for an open response.

The checklist no longer stays ungraded (H-34, `docs/CHECKLIST-CONFIRMATION.md` §4). A `rubric_only`
**verification** check with a non-empty `{id, label}` item list, answered with
`{"kind": "selection", "selection": [<declared item ids>]}`, takes the **confirmation lane** in
`grading.grade_confirmation`: deterministic, provider-free, membership only.

* every declared item ticked → `pass`, `evidence_class = self_reported`, `review_objective`, check
  `closed`, objective `introduced` if `not_started`, **no layer-2 row**;
* ≥1 but not all → `partial`, `retry_attempt`, check stays `open`, objective `needs_review`;
* `selection: []` → `VALIDATION_FAILED` `checklist_no_items_confirmed`; an undeclared id →
  `VALIDATION_FAILED` `unknown_check_item`, both before any row is written;
* `criteria[]` is one entry per declared item, in declared order, `met` = the item's id was ticked.

The reference is never rewritten to a closed kind, a `text` answer on the checklist stays
`needs_retry`, and a parent-recipe course is excluded (`observation.record` is its path,
`CHECKLIST-CONFIRMATION.md` §6). This is a kernel reading of the existing `selection` answer, not a
contract change.

### 2.4 Pack `production` / `transfer`: `rubric_only` behind the CB-QA-11 gate

`ASSESSMENT-BREADTH.md` §11 B-1 preferred option (a): a closed reference with accepted
alternatives where the check is **genuinely** closed-form. A pack manifest gives one
`reference_answer` plus optional alternatives and no statement that the answer is closed. For a
production or transfer item ("write a polite request", "apply this to a new situation") one model
answer is a sample, not the accepted set; `exact` comparison would fail correct work. So option (a)
does not apply to the pack shape as it stands.

Option (b) — the aux lane — is **not** enabled: `DEFECTS.md` CB-QA-11 (an injection-bearing
"pass" accepted with no structural cross-check) is still open, and `PREBUILD_SPEC.md` §8 requires
a measured per-slice lane before a model-assessed verdict can ship.

Decision: keep `{"kind": "rubric_only"}` for `production`/`transfer`, declared explicitly, with the
gate named. No new evidence class is invented for a model-assessed verdict; `model_assessed` stays
outside the evidence vocabulary.

## 3. Chat directive (frozen copy, `ASSESSMENT-BREADTH.md` §7.4)

`coursebook/prompts.py` holds the verbatim rule once, and it is appended to both prompt constants:

* the lesson author instructions (`generation._lesson_instructions`, prompt label bumped
  `lesson-prompt.v6` → `lesson-prompt.v7` because the instruction text changed);
* the continuation prompt (`turn.continuation_prompt`).

It is prompt text only — it never enters `checks.reference_json`, the check schema or the contract.

## 4. Tests

`tests/test_grading_lanes.py` (15 cases, real migrated DB, real `check.open` → `attempt.submit`):

* generated text quiz, right answer → `pass` / `complete_objective` / `evidence_class=cold`;
* generated text quiz, wrong answer → `not_yet`, check stays `open`, objective never reaches
  `independent_evidence`;
* generated selection quiz (incl. `production` target) grades the typed choice;
* an accepted alternative (`konnichiwa`) also passes;
* every generated check's `reference_json` declares a known kind;
* generated verification checklist → `rubric_only`; a `text` submission stays `needs_retry`, while
  a `selection` of declared item ids takes the confirmation lane (H-34, below);
* a spec without a lane is refused at `check.open` (`check_not_gradable`, no row written);
* `grading.grade` with a missing kind raises `GradingUnavailable`;
* `seal_reference` refuses an unsealed spec;
* pack import: closed target → `exact`, `production`/`transfer` → explicit `rubric_only`;
* the §7.4 directive is present in the lesson-author and continuation prompts.

`tests/test_checklist_confirmation.py` (12 cases, real migrated DB, real `check.open` →
`attempt.submit`, one-off verification fixture) pins the confirmation lane: full tick → `pass` /
`self_reported` / `review_objective` / `closed` / `introduced` / zero layer-2 / one `met:true`
criterion per item; answer persisted verbatim and inspectable; subset → `partial` / `retry_attempt` /
`open` / `needs_review`; unknown id and empty selection → `VALIDATION_FAILED` with no attempt row and
no revision bump; `text` stay `needs_retry`; hint then full tick stays `self_reported` with the hint
row inspectable; pack `production` selection stays `needs_retry`; a parent-recipe enrollment does not
take the lane. `tests/test_contracts.py` pins that the selection payload is wire-legal and that an
extra key inside `answer` is refused.

## 5. Out of scope / follow-ups

* Enabling the aux lane for open responses — blocked on CB-QA-11 and the `PREBUILD_SPEC.md` §8
  measurement.
* No UI, no `desktop/plugin.js`, no merge/push in this card.

The checklist-confirmation lane is no longer a follow-up: it landed as H-34 (`grading.grade`'s
confirmation rule + `tests/test_checklist_confirmation.py`) with **zero** `cb.rpc` / `cb.db` delta,
because the answer object already carried `selection`.
