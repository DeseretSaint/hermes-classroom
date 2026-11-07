# Verification checklist confirmation — frozen decision for 0.1.0

| | |
|---|---|
| Card | `H-33` / `t_6aafc7f2` ("verification checklist has no self-report submission seam") |
| Branch | `wt/harness-checklist-confirmation` |
| Base | `f17ec54` (current master at pickup) |
| Author | Atlas (architecture), 2026-11-07 |
| Source finding | `docs/GRADING-LANES.md` §2.3 / §5 (H-20, `t_673155b0`), which implements `docs/ASSESSMENT-BREADTH.md` §11 B-1. `GRADING-LANES.md` lives on `wt/harness-grading-lanes` at `ce6c8c1` and is not merged to this base. |
| Related | B-2 / `t_74d99ca5` (observation recording, H-21) — **not duplicated here** |
| Status | **Frozen.** Authorises one implementation card (kernel + test) and one UI card (Vellum). |
| Contract / DB delta | **None.** No `cb.rpc` bump, no `cb.db` migration, no new check kind, answer kind, evidence class, verdict, next-action or RPC method. |

This card is a decision card. It writes no product code, changes no contract, calls no provider,
spends no money and is not demo copy. It applies `PREBUILD_SPEC.md` §2 ("a coherent working
vertical slice, not a wide set of partially functional controls") to the one check family that
0.1.0 can collect but currently cannot finish.

---

## 1. Decision

**Option (a), narrowed to its actual wire shape: a verification checklist is submitted as a
`selection` answer whose entries are the check's declared item ids.**

The answer rides the existing, already-closed `attempt.submit.answer` object. No field is added.
A confirmation that ticks every declared item yields `verdict = pass` with
`evidence_class = self_reported` — never `cold`, never `independent_evidence`, never
`complete_objective`. A partial confirmation yields `partial` and advances nothing.

| Question | Frozen answer |
|---|---|
| Does the contract need a revision? | **No.** `answer` is closed (`additionalProperties: false`) and already carries `kind: "selection"` + `selection: string[]` (max 40, 200 chars each). Item ids are ≤64 chars and items ≤24. Measured in §2.1. |
| New answer kind? | **No.** `selection` is existing vocabulary. |
| New check kind? | **No.** The check stays `kind: verification` in generation and `reference.kind: rubric_only` in storage. |
| New evidence class? | **No.** `self_reported` is already in `contracts/vocabulary.v1.json`. |
| New RPC method? | **No.** `attempt.submit` is the submission path. |
| Does this duplicate B-2? | **No.** B-2/H-21 exposes `observation.record` for `self_reported`/`parent_reported` *observations* with no attempt row. This decision covers the checklist **inside a check**, which must produce an attempt, criteria and a check state. Parent courses use `observation.record`, not this lane (§6). |
| Does it let a learner claim mastery? | **No.** The only layer-2 evidence row is written for a `cold` pass (`domain.attempt_submit`, existing rule). `_objective_state_after` keeps a non-cold pass at `introduced` or the current state. |

What this buys: a one-off brief can finally reach the completion `PREBUILD_SPEC.md` §5 already
promises — "completion means `instruction_complete` plus an explicit verification checklist, which
may be `self_reported`". Today the checklist is displayed, answered with free text, and persisted
as `needs_retry` forever. The product would ship a recipe that can never complete.

**What is *not* claimed.** A ticked checklist is not an assessment. It records *which steps the
learner says they confirmed*, in the learner's own answer, and labels the evidence
`self_reported`. The check closes because it was answered, not because the skill was demonstrated.
That distinction is carried by the evidence class and is pinned by test, not by copy alone.

---

## 2. Measured state at `f17ec54` (facts, not assumptions)

### 2.1 The wire already carries the confirmation (no revision)

`contracts/rpc.v10.json`, `$defs.methods["attempt.submit"].request`:

```json
"answer": {
  "type": "object",
  "additionalProperties": false,
  "required": ["kind"],
  "properties": {
    "kind":      { "$ref": "…/vocabulary/v1#/$defs/answer_kind" },
    "text":      { "type": "string", "maxLength": 8000 },
    "selection": { "type": "array", "maxItems": 40,
                   "items": { "type": "string", "maxLength": 200 } }
  }
}
```

`check_stimulus` already serves `format: "text" | "selection" | "verification"` and
`items: [{id, label}]` (1–24 entries; id `^[A-Za-z0-9][A-Za-z0-9_.:-]*$`, ≤64; label ≤200).
`check.get` already projects them (`domain._stimulus_items`, `tests/test_check_items_authoring.py`).

Executable measurement (throwaway probe, `probe_contract.py`, run against this base):

```
$ PYTHONPATH=. python3 -m unittest probe_contract -v
test_answer_is_closed ... ok
test_rubric_only_checklist_cannot_grade_today ... ok
test_selection_of_item_ids_is_wire_legal_today ... ok
----------------------------------------------------------------------
Ran 3 tests in 0.002s
OK
```

* `{"kind": "selection", "selection": ["item_1","item_2","item_3"]}` validates against
  `cb.rpc` v10 `attempt.submit`;
* adding a `confirmations` key to `answer` is **refused** by the schema — the object is closed;
* a `rubric_only` reference with `format: "verification"` raises `GradingUnavailable` today.

So the missing piece is not a wire field. It is the kernel's refusal to read an existing field as a
confirmation.

### 2.2 The kernel refuses the lane by design, not by accident

`coursebook/grading.py:grade` routes by `reference.kind`: `exact|numeric|selection` take the
deterministic lane; anything else, including `rubric_only`, takes the open lane, which 0.1.0 never
configures, so `GradingUnavailable` → `needs_retry`. H-20 made that explicit and pinned it:

```
$ python3 -m unittest tests.test_grading_lanes -v     # on ce6c8c1 (wt/harness-grading-lanes)
test_a_self_report_answer_is_not_graded_and_advances_nothing ... ok
test_verification_reference_declares_rubric_only ... ok
… 15 tests, OK (5.056s)
```

That behaviour is correct given no collection seam. This decision supplies the seam.

### 2.3 The pane cannot express a confirmation today

`desktop/plugin.js:4049-4053` (`attemptAnswer`):

```js
const payload = { kind: 'text', text: answer }
if (answer.length <= SELECTION_MAX_CHARS) payload.selection = [answer]
```

The pane submits `kind: "text"` and a one-element selection containing the typed sentence. The
checklist is a read-only list. **A confirmation is therefore impossible from the current pane even
though the wire accepts it** — the UI half is a separate card (§9), and the kernel rule must be
gated on `answer.kind == "selection"` precisely so today's text submissions are not misread as
confirmations.

### 2.4 What the storage side would record

`attempts.answer_json` is the verbatim submitted answer, hashed into `answer_hash`. A confirmation
submission therefore persists exactly which items were ticked — the collection the finding says is
missing — under the existing `answer_kind = "selection"`.

---

## 3. Alternatives considered

### 3.1 Option (b) — leave checklists ungraded and say so on the check surface

**Rejected.** It is honest but contradicts a frozen spec promise. `PREBUILD_SPEC.md` §5 defines
one-off completion as instruction completion plus a self-reported checklist; a check that can never
complete makes that sentence false. A one-off course would remain the one recipe whose completion
the spec defines through a checklist while the kernel refuses to close the check. Stating "this
check cannot be completed" is a product defect described politely. Option (b) remains the correct
answer **only** if the wire could not express a confirmation. It can (§2.1).

### 3.2 Option (c1) — reuse `observation.record` for the checklist

**Rejected, and this is the B-2 boundary.** `observation.record` (H-21, `cb.rpc` v12) writes a
layer-1 evidence event with **no attempt row, no check state change and no revision bump**. That is
right for a parent's observation of a child, and for a learner's free-standing remark. It is wrong
for a checklist that is the objective's check: the check would never close, `attempt.submit` would
still be the only thing the pane calls, and we would have two competing notions of "the check was
answered". A checklist is a check; a check is answered through `attempt.submit`.

### 3.3 Option (c2) — a new `answer.kind = "confirmations"` or a new `check.kind`

**Rejected.** It would require a contract revision for zero semantic gain: `selection` is already
"structured selections only" and already carries a bounded string array. A new kind would also
break every existing contract test and force every client to learn a field that means what
`selection` means. Same argument against a new reference kind: the reference is `rubric_only`
because there is no comparable answer, and this decision does not change that.

### 3.4 Option (c3) — a model-assessed lane for checklists

**Rejected, and not authorised.** Grading "did you really do all three steps" from prose is exactly
the model-assessed verdict that `docs/GRADING-LANES.md` §2.4 keeps behind CB-QA-11 and the
`PREBUILD_SPEC.md` §8 measurement. It would also let a model manufacture a `cold` pass. This lane is
deterministic, provider-free and self-report-labelled by construction.

---

## 4. Frozen behaviour

### 4.1 Lane predicate

A submission takes the confirmation lane **if and only if all of the following hold**:

1. `checks.reference_json.kind == "rubric_only"`;
2. `checks.stimulus_json.format == "verification"`;
3. `checks.stimulus_json.items` is a non-empty list of `{id, label}`;
4. `answer.kind == "selection"`;
5. the enrollment's course `recipe != "parent"` (§6).

Anything else falls through to the existing router unchanged. In particular:

* a `text` answer on a verification checklist stays `needs_retry` (today's behaviour, H-20 test);
* a pack `production`/`transfer` check has `reference.kind == rubric_only` but its projected
  stimulus is `{"prompt": …}` with **no format and no items** (`pack_flow.check_spec_from_pack_check`),
  so it can never enter this lane;
* a closed `exact|numeric|selection` check is untouched;
* a `rubric_only` check with `format: "text"` or no items is untouched.

The predicate is a **shape** rule, not a recipe rule (except the parent exclusion). It does not
require the check to have been generated by the one-off recipe, because any stored verification
checklist with declared items has the same epistemics.

### 4.2 Payload

```json
{
  "kind": "selection",
  "selection": ["item_1", "item_2", "item_3"]
}
```

The entries are the **declared item ids** from the served stimulus, not labels: ids are stable,
≤64 characters and localized labels are not identity. Order is irrelevant. Duplicates are collapsed
for grading; the stored `answer_json` remains the verbatim submission and its hash covers it.

### 4.3 Refusals (before any attempt row, `VALIDATION_FAILED`)

| Condition | `reason` | Writes |
|---|---|---|
| `selection` empty after dedupe | `checklist_no_items_confirmed` | nothing |
| any entry not a declared item id | `unknown_check_item` | nothing |
| selection longer than the contract allows | schema refusal before the handler | nothing |

A refusal is not a failed attempt: no attempt, no evidence, no revision bump. The pane should
disable Submit until at least one item is ticked.

### 4.4 Verdict and criteria

One criterion per **declared item**, in declared order:

```json
{"id": "<item id>", "observed": "<item label>", "met": true}
```

| Ticked | Verdict | Next action | Check | Objective state |
|---|---|---|---|---|
| every declared item | `pass` | `review_objective` (non-cold pass rule) | `closed` | `introduced` if `not_started`, else unchanged |
| ≥1, not all | `partial` | `retry_attempt` | stays `open` | `needs_review` |
| 0 or unknown id | — | refusal above | stays `open` | unchanged |

`pass` **never** produces `complete_objective`, because `domain.attempt_submit` already rewrites a
non-cold pass's next action to `review_objective`. No layer-2 row is written, because layer-2 is
written only for a `cold` pass. The two existing tests that pin those invariants remain the guard;
this lane cannot bypass them.

### 4.5 Evidence class

`evidence_class = self_reported` for every graded confirmation (`pass` and `partial`), regardless
of prior hints. Rationale: the class describes **how this answer was produced** — by the learner's
own confirmation, not by a comparison. A prior `hint_request`/`answer_shown` event is not erased; it
is a separate layer-1 row that `evidence.inspect` still shows, and it never becomes `cold` either
way. Forcing the class also makes the assurance independent of retry history (a second partial
submission would otherwise be classified `hinted`, which is true but less informative).

The grader may return this class; `domain` accepts **only** the module constant
`grading.CONFIRMATION_EVIDENCE_CLASS == "self_reported"` from a grader result and otherwise keeps
`_classify_evidence`. A future aux adapter cannot smuggle `cold` through this channel.

### 4.6 Provenance

```json
{"grader": "provider-free:confirmation",
 "reference_sha256": "<hash of the rubric_only reference>",
 "declared_items": 3,
 "confirmed_items": 2}
```

No provider, model or credential field. The reference itself is never returned.

---

## 5. What must not change

* `checks.reference_json` stays `{"kind": "rubric_only"}`. Rewriting it to `exact`/`selection`
  would assert a comparable answer set that does not exist. This decision explicitly forbids it.
* `checks.stimulus_json.items` remains the single list of steps; no second copy, no labels in the
  answer.
* `cb.rpc` response shape is unchanged; per-item criteria fit the existing `criteria[]` bounds
  (≤40 entries, id ≤80, observed ≤500).
* `answer_kind`, `evidence_class`, `verdict`, `next_action`, check kinds and reference kinds are
  unchanged.
* Open-lane behaviour for genuinely open prose is unchanged and still gated (CB-QA-11).
* Pack-imported checks cannot enter this lane today: `pack_flow.check_spec_from_pack_check`
  projects `stimulus` as `{"prompt": …}` with no `format` and no `items`. If that projection ever
  grows a checklist, the import audit must be amended in the same change; this decision does not
  authorise it.
* `desktop/plugin.js` is not touched by the kernel card.

---

## 6. Boundary with B-2 / H-21 (`observation.record`)

| Case | Path | Evidence class | Attempt row |
|---|---|---|---|
| Learner ticks a verification checklist that is an objective's check | `attempt.submit` (`selection`) — **this decision** | `self_reported` | yes |
| Parent records an observation of a child | `observation.record` (v12, H-21) | `self_reported` / `parent_reported` | no |
| Parent-authored observation check (`kind: observation`) | `observation.record`; the check surface shows no tick-list | `parent_reported` | no |
| Pack `production`/`transfer` open response | open lane, unconfigured → `needs_retry` | — | persisted, nothing advances |

To keep that boundary, the confirmation lane is disabled when the enrollment's course recipe is
`parent`. A parent lesson therefore does not gain a child-operated checklist by accident; B-2's
recording seam is the only write path for a parent's observation. This is a two-line lookup
(`courses.recipe`) in `attempt_submit`, not a new contract concept.

---

## 7. Implementation map (Cinder's card)

**Dependency:** base must contain H-20 (`wt/harness-grading-lanes`, `ce6c8c1`) — it introduces
`validators.seal_reference` and the explicit `rubric_only` lane this rule keys on. If master does
not yet contain it, merge/rebase it first. Do not re-implement H-20.

| File | Change |
|---|---|
| `coursebook/grading.py` | Add `CONFIRMATION_EVIDENCE_CLASS`, `ConfirmationAnswerError(reason)`, `confirmation_items(reference, stimulus)`, `grade_confirmation(items, answer)`. In `grade(..., allow_confirmation=True)`, try the confirmation lane before the open lane. Add `evidence_class: str \| None = None` to `GradingResult`; only the confirmation lane sets it. |
| `coursebook/domain.py` | In `attempt_submit`: resolve `courses.recipe` and pass `allow_confirmation = recipe != "parent"`; translate `ConfirmationAnswerError` into `VALIDATION_FAILED` (field `answer`, the reason from §4.3) **before** the write transaction; after a successful grade, accept `graded.evidence_class` only when it equals `grading.CONFIRMATION_EVIDENCE_CLASS`. No other state-machine change. |
| `tests/test_grading_lanes.py` (or a new `tests/test_checklist_confirmation.py`) | The acceptance tests in §8, through the real `check.open` → `attempt.submit` path on a real migrated DB. |
| `tests/test_contracts.py` | Pin that a selection-of-declared-ids `attempt.submit` payload validates and that an extra `answer` key is refused (the measurement in §2.1, kept as a regression). |
| `docs/CONTRACTS.md` | One clarification under the v10 wire rule: a `verification`-format check's confirmation rides `answer.kind = "selection"` with declared item ids; **no version change**. |
| `docs/GRADING-LANES.md` | Amend §2.3 and §5 when H-20 is on the same base: the explicit `rubric_only` lane is now graded through the confirmation rule instead of staying ungraded. If the file is not on the base, record the amendment in the completion handoff for the integration card. |

No new module, no migration, no provider call. The implementation should be under ~150 lines of
product code.

---

## 8. Acceptance tests (executable evidence required)

Through `check.open` → `attempt.submit`, one-off verification fixture
(`tests/test_check_items_authoring.py:one_off_lesson`), real migrated DB:

1. **Full confirmation passes as self-reported.** Tick every declared item id → `verdict = pass`,
   `evidence_class = self_reported`, `next_action = review_objective`, check `closed`, objective
   state `introduced` (never `independent_evidence`), zero layer-2 rows, and `criteria` has one
   entry per item with `met = true` and the item id as criterion id.
2. **Answer is persisted.** The attempt row's `answer_json` contains exactly the submitted
   selection; `answer_kind = "selection"`; `evidence.inspect` shows `self_reported`.
3. **Partial confirmation advances nothing.** Tick one of three → `partial`, `retry_attempt`,
   check stays `open`, `evidence_class = self_reported`, objective `needs_review` (the existing
   `_objective_state_after` rule for `partial`), no layer-2 row.
4. **Unknown item refused.** `item_9` → `VALIDATION_FAILED`, reason `unknown_check_item`, no
   attempt row, revision unchanged.
5. **Empty confirmation refused.** `selection: []` → `VALIDATION_FAILED`, reason
   `checklist_no_items_confirmed`, no attempt row, revision unchanged.
6. **Text answer is not a confirmation.** `{"kind":"text","text":"all done"}` on the same checklist
   → `needs_retry`, `retry_grading`, no advance (H-20's behaviour preserved).
7. **A hint does not make it cold.** Record a hint event, then tick every item → `pass` with
   `evidence_class = self_reported`, hint row still present in `evidence.inspect`, objective not
   `independent_evidence`.
8. **Pack open response cannot be ticked into a pass.** A `production` pack check
   (`rubric_only`, no items/format) with a selection answer → `needs_retry`, nothing advances.
9. **Closed checks are untouched.** A generated `exact` quiz still grades right/wrong exactly as
   H-20 pins it (run the existing 15 cases).
10. **Parent course is excluded.** A parent-recipe enrollment with a verification-shaped check does
    not take the confirmation lane; `observation.record` remains the recording path.
11. **Wire legality pinned.** A `selection`-of-ids `attempt.submit` payload validates against
    `cb.rpc`; an extra key in `answer` is refused.
12. Full suite `python3 -m unittest discover -s tests -t .` and
    `bash scripts/validate-plugin.sh` on a clean export, with exact counts reported.

---

## 9. UI contract (Vellum's card — frozen strings)

1. When the served stimulus has `format: "verification"` and a non-empty `items[]`, render the
   items as **checkboxes** with the served `id` and `label`; today they are a read-only list.
2. Submit `{"kind":"selection","selection":[<checked ids>]}` — not `text`, not labels. Disable
   Submit while no item is ticked.
3. Render the returned `criteria[]` beside the items (id → label, `met` → ticked/not). A `pass`
   closes the check; a `partial` keeps it open and invites the remaining steps.
4. Copy on a self-reported pass, verbatim:

   > **You confirmed every step. This is your own report, not an independent check.**

   and, wherever evidence class is shown:

   > **Self-reported — you told us. It cannot count as independent evidence.**

   No "mastered", "verified", "passed independently" or "complete" without the self-reported
   qualifier. If an assist event exists, the surface must keep showing it.
5. A parent-observation surface shows **no** tick-list; it uses the `observation.record` control
   from B-2/H-21 and labels the result `parent_reported`.
6. `desktop/plugin.js` only; no kernel edits in that card.

This copy is the same claim `PREBUILD_SPEC.md` §5 makes: instruction completion may rest on a
self-reported checklist, and it never implies independent verification.

---

## 10. Risks and mitigations

| Risk | Why it does not become a false claim |
|---|---|
| Learner ticks everything without doing the work | The evidence class says `self_reported`; the objective cannot reach `independent_evidence`; layer-2 is only written for `cold`; copy states it. This is the epistemics PREBUILD §5 already accepts. |
| A retry after a hint looks cold | The lane forces `self_reported`; hint/answer-shown rows remain inspectable. |
| `selection` is overloaded | The lane is gated on all five conditions in §4.1; closed selection checks and pack open responses are unaffected and tested. |
| Parent mode accidentally gains a child checklist | Recipe gate excludes `parent`; B-2's `observation.record` is the only write path. |
| Reference is silently upgraded to a closed answer | Forbidden in §5 and pinned by a test that the stored reference stays `rubric_only`. |
| Future aux adapter returns `cold` from this lane | `domain` accepts only the constant `self_reported` from a grader; everything else falls back to `_classify_evidence`. |

---

## 11. What would change this decision

* The contract dropping `selection` from `attempt.submit` (it will not; the object is frozen).
* A measured finding that a self-reported checklist pass can reach independent evidence on any path
  (it would be a defect in `_objective_state_after`, not a reason to re-open this decision).
* CB-QA-11 closing and a measured model-assessed lane shipping — that would add a *separate*
  lane; it would not change this one, because a model cannot make a self-report independent.

---

## 12. Scope, non-goals and verification

**Non-goals.** No contract version, no DB migration, no new vocabulary, no provider call, no model
grading, no change to pack import, no change to closed checks, no master merge, no push, no tag,
no release claim, no demo recording, no `desktop/plugin.js` edit in this card.

**This card's verification.**

```
python3 -m unittest discover -s tests -t .     # base suite on the doc-only commit
bash scripts/validate-plugin.sh                # release gate on a clean export
git show --stat HEAD                           # docs/CHECKLIST-CONFIRMATION.md only
```

**Final position.** The confirmation seam is not missing from the contract; it is missing from the
kernel's reading of an existing field. 0.1.0 will collect the checklist, record which steps were
confirmed, label the result `self_reported`, and never let it masquerade as independent evidence.

---

## 13. Verification performed on this card

| Check | Result |
|---|---|
| `python3 -m unittest discover -s tests -t .` | **Ran 1130 tests, OK (280.499s)** on `f17ec54` + this document |
| `bash scripts/validate-plugin.sh` | **Release gate passed: 3/3 checks (1230 files)** on the commit carrying this document |
| Contract probe (§2.1) | **3/3 OK**: selection-of-item-ids valid; extra `answer` key refused; `rubric_only` verification raises `GradingUnavailable` |
| H-20 lane suite (`tests.test_grading_lanes`, `ce6c8c1`) | **15 tests OK (5.056s)**: checklist stays `needs_retry` / `rubric_only` today |
| Changed files | `docs/CHECKLIST-CONFIRMATION.md` only — no product code, contract, DB, UI or test change |

No provider was called, no model was configured, no pack was installed, nothing was pushed or
merged.
