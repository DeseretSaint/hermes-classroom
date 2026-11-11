# CP-015g — a lesson retry needs room for a second, different mistake

Status: implemented and tested on branch `wt/cp-015g-lesson-v15`, rebased onto `origin/master`
@ `9695de74` (W2-11). Owner: Cinder (backend kernel).

## The defect, from the two validation records

Live run for an unseen topic ("prune a fig tree"), scratch home `cb-prod-home`, 2026-11-11. One
lesson section produced two records:

| attempt | recorded at | refused under | what the refusal names |
|---|---|---|---|
| 1 | 20:27:48 | `rubric_consistency`, `source_support` | the claim that long branches shade lower growth, fix hint "Drop the shade mechanism or add a source that states it." on `lesson.segments[0].body` |
| 2 | 20:41:27 | `answer_leakage`, `source_support` | `learner_explanation` restated the reference answer in different words |

Attempt 2 **applied the hint** — the shade claim was gone. Its new refusal was a different defect,
and `LESSON_ATTEMPTS = 2` had no attempt left to repair it, so the section parked `needs_review`
and every check stayed closed. The first defect was not a broken retry; the second was a prompt
gap: the author was never told that `learner_explanation` is a coaching surface that must not
state, quote or paraphrase the key.

## Decision

1. **`LESSON_ATTEMPTS` 2 → 3.** A repair can expose a different mistake. Each retry carries the
   immediately preceding refusal (item paths and `fix_hint`s), so attempt 2 repairs attempt 1 and
   attempt 3 repairs attempt 2. A generator that repeats one mistake through all three attempts
   still parks the section: the honest ceiling is unchanged.
2. **The prompt names the explanation rule.** `lesson-prompt.v15` states that
   `learner_explanation` describes how to reach the answer and must not state, quote, paraphrase
   or summarise the reference answer or an accepted answer.
3. **The repair pass is binding.** The instruction text now says `revision_instructions` is the
   validator's refusal, that each item path and hint must be applied literally, and that a
   rejected claim is removed or supported by an exact excerpt of a supplied source.
4. **`_feedback` itemises, not line-counts.** The old eight-line cap silently dropped rejection
   tails whenever the two-line item+hint pair pushed past it. One rejection is now one block, so an
   item path and its hint always travel together. (W2-2 on master had already removed the
   truncation altogether; the block shape is what survives the rebase.)
5. **Budgets count the third attempt.** After the rebase onto W2-2, each attempt may spend two
   truncation re-asks (the lesson's own cut answer and the validator's), so `lesson_calls` is `2n`
   minimum and `12n` worst legal (3 attempts × generate + validate + 2 re-asks);
   `lesson_cost_budget` sizes the dollar floor from the same count (five sections $2.40, eight
   $3.84). The pre-rebase branch's `9n` counted one re-ask and would undercount the master path.
   No call the pipeline legally makes is refused by the default ceiling.

## Tests

`tests/test_cp015g_lesson_retry_hint.py` (fake provider seam, no network):

* `test_a_different_second_mistake_still_earns_a_third_attempt` — draft 1 carries the unsupported
  claim, draft 2 drops it but restates the key in the explanation, draft 3 is compliant. The
  section ends `validated`; the third request carries `answer_leakage` and the explanation item
  path, and not the first hint.
* `test_a_generator_that_repeats_the_same_mistake_twice_still_parks` — three identical refusals
  park the section `needs_review`, checks `closed`/`failed`, page not servable.
* `test_the_prompt_names_the_explanation_as_a_coaching_surface` — v15 states the rule.
* `test_a_prompt_compliant_explanation_does_not_trip_answer_leakage` — a compliant section passes
  the deterministic scan and the independent pass end to end.

Existing suites updated for the arithmetic and the label (`test_generation`,
`test_cp015f_lesson_budget`, `test_cost_ceilings`, `test_adversarial_round2`,
`test_text_completeness`, `test_policy_integration`, `test_procedure_authoring`,
`test_cp015c_answer_leak_surfaces`, `test_w2_2_truncation_and_repair`).

## Verification (real runs on the rebased tree, `origin/master` 9695de74 + this commit)

```
$ python3 -m unittest discover -s tests -t .
Ran 4350 tests in 939.023s

OK (skipped=12)

$ python3 scripts/check-docs-truth.py --skip-tests
docs-truth: PASS   (GENERATION.md labels match: lesson-prompt.v15)

$ bash scripts/validate-plugin.sh
Release gate passed: 4/4 checks on a clean export
```

The recorded H-40 packet was re-derived because the lesson prompt label and the worst-legal call
ceiling are recorded in it:

```
$ PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py
overall: PASS  (3/3 scenarios)
packet: 8 evidence file(s) content-addressed in manifest.json; 3 transcript input(s)
```

The diff to `audit/adversarial/harness-e2e/evidence/*.json` on the rebased tree is exactly
`lesson-prompt.v14` → `.v15` and `maximum_calls 8 → 12` / `maximum_cost_usd 0.32 → 0.48` per
section (16→24, 0.64→0.96 for the two-section course); no scenario verdict changed.
