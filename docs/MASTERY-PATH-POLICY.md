# Mastery path and checkpoint policy

Status: policy record, 2026-11-07. Owner: atlas (H-154 `t_27f1cbb4`). Branch:
`wt/h154-path-policy` at base `c6b658e` (local `master`).

Source research: `docs/MASTERY-PATH-RESEARCH.md` (25 peer-reviewed sources; effect sizes are
population averages and carry explicit caveats). That file landed in commit `1a01f95` on
`wt/h151-action-type` and is **not on this branch's base**, so every finding used below is quoted
from it, not re-derived here (`git show 1a01f95:docs/MASTERY-PATH-RESEARCH.md`). The card itself
comes from the H-154 row of `docs/EXPERIENCE-REVIEW.md` §3.3, which landed in the same commit.
Quality gates: `docs/EXPERIENCE-QUALITY-BAR.md` Q4 (real progress), Q6 (lesson loop), Q11 (copy
and truth).

Executable half: `coursebook/mastery_path.py`. Tests:
`tests/test_mastery_path_policy.py` (22 tests). This card adds **no database migration and no
RPC change**. It makes one existing generation rule stricter and moves the review ladder into one
shared policy module; everything else is stated as policy with an explicit implementation status.

## 1. The one-sentence rule

A path node is one capability stated as an exit performance; a checkpoint is a scheduled cold
retrieval event that writes evidence; and no number, lock or checkpoint may exist that the backend
cannot record.

## 2. The node contract

Research §2 requires five fields per node. Only four have a storage seam today.

| Field | Policy requirement | Where it lives today | Status |
|---|---|---|---|
| **Exit performance** | What the learner can do unaided at the end of the node; not a topic heading | `objectives.title` | **Implemented as a prompt directive + a coarse refusal helper.** The v2 plan prompt now demands an exit performance; `mastery_path.exit_performance_problems()` refuses obvious topic labels (`Introduction to…`, `… vocabulary`, `… basics`). It is intentionally **not** a hard plan-validation rule: no field separates a title from a capability, and a strict English-verb heuristic would reject valid titles in other languages. |
| **Prerequisite edge(s)** | What must already be possible before this node; a graph, not a difficulty rank | `plan_units.prereq_unit_ordinals_json`; reader rules `prerequisite_edge_reasons`; access gate `check.open` | **Implemented.** Edges point backwards only, are unique, acyclic, and every unit after unit 1 may declare an edge or be independent. Unmet edges refuse with `PREREQUISITE_UNMET` and an explicit continue option — see §6. |
| **Check family** | `recall` / `comprehension` / `production` / `discrimination` / `procedure` / `transfer`; the check must measure the node's family | `objectives.evidence_target` + `check_plan[].evidence_target`; checks store `evidence_target` | **Implemented and now enforced at plan time.** New v2 rule 5b refuses a check-plan entry whose `evidence_target` differs from its objective's. The lesson stage already refused it (`enforce_lesson_rules`). |
| **Misconceptions to catch** | The specific error the check must be able to reveal | No column. The check rubric's criteria are observable claims, not misconceptions. | **Spec-only.** `mastery_path.MISCONCEPTION_FOCUS` names the class per family so the check author has a target, but Coursebook does not store an authored misconception. Persisting one needs a plan/check schema amendment and its own contract card. |
| **Review obligation** | The spaced return the node creates | Derived from `evidence_target` through `mastery_path.LADDERS`, read by `coursebook.review` | **Implemented as a read-only derivation.** No new column; the ladder is the existing product heuristic, now owned by the policy module so generation and the scheduler cannot drift. |

The path is rendered as a prerequisite graph on a line. Unit order is dependency order, not
difficulty order; an independent node may branch. Rendering is H-148's surface, not this card.

## 3. What generation must do

The v2 plan author receives `mastery_path.plan_policy_lines()` (wired in
`generation._plan_instructions_v2`):

- write objective titles as exit performances, not chapter headings;
- name the same `evidence_target` in the objective and its check-plan entry;
- order units by prerequisite dependency, never by difficulty;
- name the misconception the check must catch;
- promise no mastery percentage, XP, streak, level or adaptive difficulty;
- do not draw or claim a cumulative checkpoint.

Deterministic enforcement added by this card:

| Rule | Where | Test |
|---|---|---|
| A check-plan entry must name its objective's `evidence_target` | `generation._enforce_plan_v2`, rule 5b | `test_a_v2_plan_whose_check_measures_another_family_is_refused` |
| Every evidence target keeps its own ladder and pass criterion | `mastery_path.LADDERS` / `PASS_CRITERIA` | `test_every_evidence_target_has_its_own_pass_criterion` |
| The v2 prompt carries the policy | `generation._plan_instructions_v2` | `test_the_v2_prompt_carries_the_mastery_policy` |

The coarse topic-label refusal is available to any writer that projects a node, but it is not a
hard validation gate. Calling that "enforced generation" would overstate the build.

## 4. Checkpoints

A checkpoint is a scheduled cold retrieval event over prior nodes, taken without scaffolds, that
writes evidence and can reorder the path. It is not a boss fight, a content gate or a second final
exam (research §3).

| Type | Question | When | State written | Status |
|---|---|---|---|---|
| **Gate check** | Can they do this now, unaided? | End of node, new items | `introduced` (or `not_started`) → `independent_evidence` | **Implemented.** Only a cold pass advances; a hinted or self-reported pass writes `introduced`, not independent evidence. |
| **Delayed check** | Does it survive? | At the scheduled cold return | `delayed_evidence` | **Implemented.** A cold pass while the objective is `review_due` writes the L2 kind `delayed_retrieval` and the state `delayed_evidence`. |
| **Cumulative check** | Can they pick the right move among confusable ones? | After several nodes, mixed | unit-scoped evidence | **Refused.** The backend has no unit-scoped check: `checks.objective_id` is required, so every check belongs to exactly one objective. `mastery_path.plan_checkpoints(cumulative=True)` raises `UnsupportedCheckpoint` naming the missing capabilities `unit_scoped_check` and `cumulative_check`. |

**The cumulative contract, if it is ever scoped** (separate card, not this one): a unit-scoped
check row needs a unit reference that does not erase the objective link, an RPC that records a
check against a unit, a state name for the evidence it writes, and a reader projection that shows
which nodes it covered. Until all four exist, no path may draw or claim a cumulative checkpoint.
The policy module is the single place that refuses it.

## 5. The pass rule (per evidence target, a rule and not science)

There is **no universal "three in a row" rule**. `mastery_path.STREAK_LENGTH` is `None`, and the
tests assert no criterion contains "in a row". Kulik's strongest mastery programmes used high
unit-quiz criteria *plus* corrective feedback and more time; their effects were largest on
locally written tests (research §3). That supports mastery plus correction, not a magic streak.

The declared rule for every family: one cold pass on an unseen form at the gate, then one cold pass
after at least the first rung of that target's ladder. Hints, shown answers and open-answer grader
failures do not count; a grader failure is `needs_retry`, never mastery.

| Check family | Gate cold passes | Delayed cold passes | First return (days) | Ladder (days) |
|---|---:|---:|---:|---|
| `recall` | 1 | 1 | 1 | 1, 3, 7, 16, 35 |
| `comprehension` | 1 | 1 | 2 | 2, 5, 12, 28 |
| `production` | 1 | 1 | 3 | 3, 7, 16, 35 |
| `discrimination` | 1 | 1 | 3 | 3, 7, 16, 35 |
| `procedure` | 1 | 1 | 3 | 3, 7, 16, 35 |
| `transfer` | 1 | 1 | 7 | 7, 21, 45 |

The ladder is a declared product heuristic, not a forgetting curve and not an attainment
prediction (`AUDIT.md` R9/R10). Show the rule as a rule ("one cold pass now, one after the
interval"), never as an effect size Coursebook measured.

## 6. The failure rule

| Event | Behaviour | Status |
|---|---|---|
| One miss | Sets `needs_review` on that node. Not a course reset, not a lock. | **Implemented** (`domain._objective_state_after`). |
| Two misses on the **same** check form | Still `needs_review`; repeats of one form are not two different views of the error. | **Policy decision encoded** in `mastery_path.review_outcome`; no consumer yet. |
| Two misses on **different** check forms | Re-teach with a different representation, not the same explanation louder. | **Policy decision encoded; the re-teach lesson is not implemented.** It belongs to the lesson player/authoring card. |
| Unmet prerequisite | Refuse with the unmet list and `PREREQUISITE_UNMET` unless the learner acknowledges; the acknowledgment proceeds and is recorded, never counts as evidence. | **Implemented** (`domain.check_open`, `acknowledge_prerequisites`). This is the concrete "continue with this unresolved" affordance. |
| Path-level lock | None. `FAILURE_RULE["locks_path"]` is `False`; `needs_review` stays in the review queue. | **Implemented** (the queue includes `needs_review`; no command writes a path lock). |

A single wrong answer is a provisional misconception, never a diagnosis. The policy never returns
`reset` or `locked`: there is no such state to write.

## 7. Spacing and interleaving

**Spacing — two structural rules, both implemented.** `mastery_path.review_step()` is the one
advance function; `coursebook.review._item` folds review events through it.

- A **failed** review keeps its rung. A failure writes no layer-2 pass event, so the queue's index
  does not move; it does not restart at the first rung ("day 1") and it does not reset the course.
- A **pass** advances exactly one rung, capped at the last one. It does not jump to the end of the
  ladder. A learner action (`stretch`) advances one rung; `snooze` restarts the interval from now
  but does not move the rung.

Proof: `test_a_failed_review_keeps_its_rung_and_sets_needs_review`,
`test_a_delayed_pass_advances_exactly_one_rung`,
`test_a_gate_pass_starts_at_the_first_rung_not_the_last`.

**Interleaving — policy API, no runtime caller yet.** Block first acquisition; interleave only
confusable sets; never random-mix vocabulary (research §5; words are the one category where
interleaving reverses). `mastery_path.review_sequence()` refuses unacquired items and items with
no confusable set, and groups members of one set adjacently in first-appearance order. It performs
no shuffle. `test_interleaving_blocks_acquisition_and_groups_confusable_sets` proves both
refusals. Generation currently authors owner and review sections per unit; it does not yet compose
an interleaved review set, so this remains policy plus test, not a shipped scheduler feature.

## 8. What is spec-only, and what is implemented

**Implemented (code + executable test):**

- one shared ladder and one advance function, used by the real review queue;
- no day-1 reset on a failed review, no jump to the ladder's end on a pass;
- one miss → `needs_review`, path not locked; `needs_review` stays in the review queue;
- gate writes `independent_evidence`; delayed cold pass writes `delayed_evidence`;
- unmet prerequisite offers an acknowledged continue instead of locking;
- v2 plan rule: the check family must equal the node's family;
- v2 plan prompt carries the node policy;
- checkpoint policy refuses `cumulative` and names the missing backend capabilities;
- node projection exposes the five fields, their storage seam and the misconception gap.

**Spec-only (no code path, no schema):**

- storing an authored misconception per node (needs a plan/check schema amendment);
- a cumulative checkpoint drawn or recorded (needs the unit-scoped check contract);
- re-teaching a node with a different representation after two different-form misses (the
  decision is encoded; the lesson authoring flow is a separate card);
- composing an interleaved review set at generation time (the policy function exists; no caller);
- any path renderer change (H-148 owns the line; this policy does not draw it).

**Not claimed:** XP, streaks, levels, mastery percentages, adaptive difficulty, a course reset, a
locked path, or a cumulative checkpoint. Each of those would require a durable backend fact this
build does not have.

## 9. Gate evidence

| Gate | What this card provides |
|---|---|
| **Q4 Real progress** | Every state this policy names maps to a real field: `objectives.state` (`introduced`, `independent_evidence`, `delayed_evidence`, `review_due`, `needs_review`), L2 `evidence.kind` (`independent_evidence`, `delayed_retrieval`), and `plan_units.prereq_unit_ordinals_json`. There is no percentage, score or streak. The pass criterion is a declared rule, labelled a heuristic. |
| **Q6 Lesson loop** | A node is one capability with one check family; the check measures that family (plan rule 5b + existing lesson rule); the gate and delayed writes are the loop's evidence; a failure is information (`needs_review`) with a continue option, not a reset. |
| **Q11 Copy and truth** | The policy names the state word, not a score. It refuses "three in a row" and any mastery claim. The cumulative checkpoint is refused in the API, so no surface can copy a claim the backend cannot record. |

## 10. Reproduction

```
cd /home/deseretsaint/Projects/hermes-classroom/.worktrees/t_27f1cbb4
python3 -m unittest tests.test_mastery_path_policy -v
python3 -m unittest tests.test_review_evidence tests.test_generation \
  tests.test_blueprint_units tests.test_plan_units tests.test_prerequisite_gating \
  tests.test_capability_policy tests.test_contracts -v
```

The card's own suite is 22 tests. The related-suite run is recorded in the task handoff with its
exact count and result.

## 11. Out of scope

No migration, no RPC version, no `desktop/plugin.js` change. No cumulative checkpoint, no course
reset, no path lock, no mastery percentage, no streak/XP/level, no adaptive-difficulty claim, no
second progress currency. If a later card wants a cumulative checkpoint, it starts by scoping the
unit-scoped check contract named in §4 and comes back to `mastery_path.plan_checkpoints`.
