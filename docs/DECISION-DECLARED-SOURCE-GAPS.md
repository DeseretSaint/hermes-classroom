# Declared source gaps: `source_support` judges claims, not honesty

| | |
|---|---|
| Card | `CP-015g/D1-F2` / `t_65054c74` (found while completing `CP-015g/D1-F1` `t_285529c8`) |
| Branch | `wt/cp-015g-d1-f2-unverified` |
| Base | `e728fbe9` (`wt/cp-015g-d1-f1-authoring`, which is `wt/cp-015g-d1-validation-repair` + D1-F1) |
| Author | Cinder (backend kernel), 2026-11-11 |
| Status | **Decided.** Answer is: an honestly declared gap is not a `source_support` defect; it is recorded and disclosed, and the plan is parked with a sourcing note instead of re-authored. |
| Contract / DB delta | **None.** No `cb.rpc` bump, no `cb.db` migration, no new job kind, verdict value, evidence class or error code. `validation-prompt.v6 → v7` (instruction text changed; the label is recorded in stored validation bindings). |
| Code delta | `coursebook/generation.py`; `tests/test_cp015g_d1_f2_unverified.py` (19 tests); `tests/test_validation_shape_repair.py` (label assertion); `docs/GENERATION.md` §5c |

This card is a contract decision card. It writes kernel code for the rule it decides, changes no
schema, edits no authoring prompt, no fixture and no rubric, calls no provider and spends no money.

---

## 1. The measured defect

`docs/cp015g-d1-f1/run-f1-live-r2.json`, job `job_c3a5f5ca512a4d518e7b06c924e53eed`, goal *"Set up a
small backyard telescope and find and observe the moons of Jupiter on a clear night"*, Short,
casual, `nous/deepseek-v4.1-flash-1017`.

The authored plan:

* objectives: `comprehension` (sourced, verbatim `source_quote`), `procedure`, `transfer` (sourced,
  verbatim quote), `comprehension` (`support: "unverified"`, no ids);
* checks: `quiz`, `verification`, `observation`, `quiz`.

The validator refused on `source_support`, per item:

```
objective:2: The setup/aim procedure is unsourced and must not be presented to a learner as verified content.
objective:4: The orbital-explanation objective is unsourced and must not be presented to a learner as verified content.
```

Both objectives carried `support: "unverified"` and an empty `source_ids`. They do not present
themselves as verified content, and `docs/GENERATION.md` §5b tells the author to write exactly that
when no supplied excerpt carries the claim. The refusal therefore rested on the plan's honesty, not
on an unsupported assertion.

## 2. The two questions, answered

### 2.1 Does `source_support` refuse an objective marked `unverified`?

**No.** `source_support` judges the claims an artifact *makes*, never the gaps it *declares*. It
refuses three things and only those:

| # | Refused | Why it is a defect |
|---|---|---|
| 1 | a claim marked `sourced` that the excerpt it cites does not carry | the plan asserts a source says something it does not — the over-citation D1-F1 removed on the authoring side |
| 2 | a claim presented to the learner as established fact with no support | the learner is invited to rely on an unbacked assertion |
| 3 | a claim the supplied excerpts contradict | the artifact misstates the evidence; also a `factual_correctness` defect |

A claim the artifact itself marks `support: "unverified"` with no source ids is a **declared gap**.
There is nothing for a source to contradict and nothing presented as verified. It is recorded and
disclosed at approval, never refused.

The other reading — refuse `unverified` outright and say so — is rejected: it makes the
`unverified` support value nearly unusable, and it means no plan for an under-sourced topic can ever
pass, however honestly it is authored. That is the defect this card exists for, restated as policy.

The rule is now stated where the answer is asked for (`_PLAN_SUPPORT_RULE`, in every
plan-validation pass, `validation-prompt.v7`), because a rule the kernel enforces that the model is
not told about is a trap (the H-191 lesson).

### 2.2 If the claim is refused, what should the pipeline do instead?

It is not refused, but the gap still has to go somewhere. The answer is **pause the plan with a
sourcing note**, and the pipeline no longer pays for a repair it cannot make:

| Option | Answer | Ground |
|---|---|---|
| Re-research the missing claim | **Not the plan stage's call.** It is a research-stage decision, and the reason the claim is missing today is page-chrome excerpts (`t_41f23b3e`) and under-covered queries | Research owns its own budget and evidence; the plan stage cannot re-run a fetch without a new research decision |
| Narrow the objective | **The author's job**, already closed by D1-F1 | It changes what the course is for; the plan stage must not silently drop a learning goal |
| Pause with a sourcing note | **Adopted** | The gap is real, it is disclosed, and a human decides whether to re-research, narrow or approve with the lesson labelled unverified |

What the pipeline does now:

* `plan_declared_gaps()` reads the plan's own unverified objectives, and
  `validation_verdict(..., declared_gaps=...)` moves a `source_support` rejection naming one of them
  out of `rejections` and into `sourcing_notes` (`{item, claim, validator_reason}`).
* **No pass is invented.** A declared `reject` stays a `reject`, the plan stays `needs_review`, and
  the approvability gate in `domain._plan_validation_facts` is untouched. What changes is
  attribution and cost: the author is not blamed for a source that was never fetched.
* When the refusal rested *only* on declared gaps (`gap_only_refusal`), the plan stage parks the
  document `needs_review` on the first attempt instead of spending a second authoring and research
  cycle.
* The plan result carries `sourcing_notes`, and the warnings state the gap and the three real
  options. `_refusal_reasons` prints the gap and the next action instead of a bare
  `criteria failed: source_support`; `_feedback` adds "do not invent a citation to satisfy a support
  complaint".

## 3. Limits, stated

* A validator that fails `source_support` with **no itemised rejection at all** keeps its refusal.
  The criterion verdict is the validator's, not the kernel's; the reader sees
  `criteria failed: source_support`. The kernel does not rewrite a criterion verdict into a pass.
* Lesson page-level disclosure for an objective marked unverified is the lesson stage's contract and
  is unchanged by this card.
* No live provider run was made under `validation-prompt.v7`. The defect evidence is the two live
  runs in `docs/cp015g-d1-f1/`; what is proven here is the contract and the kernel rule, not that a
  given model obeys the new paragraph on the wire.

## 4. Verification

`docs/CP015G-D1-F2-EVIDENCE.md` records the commands and their real output: 19 focused tests, 209
tests across every suite this change touches, the three-scenario end-to-end harness PASS, and
`check-docs-truth.py --skip-tests` PASS with the prompt labels read from the module.
