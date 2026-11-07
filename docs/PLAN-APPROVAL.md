# Plan approval: fail-closed, and what it means

`plan.approve` approves **one exact plan content hash**. It is not a rubber stamp on a plan row and
it is not a second validation pass. H-12 makes it fail closed: a plan that is empty, rejected,
never validated, or edited after validation cannot become the course's approved plan.

## What approval means

* The caller read the plan, and the `plan_hash` it sends still equals the current kernel plan
  content hash (`parent_authoring.plan_hash` over course id, version, schedule and objectives).
* The enrollment revision equals `expected_revision`; otherwise `STALE_REVISION`.
* The plan is approvable by exactly one of two provenances:

| Provenance | Required durable record | Approval claim |
|---|---|---|
| `generated_validated` | The latest `gen_plan_documents` row for the plan has `generation_state = 'draft'`, `result_json.validation_verdict = 'pass'`, and `result_json.plan_content_hash` equal to the current kernel content hash. | The independent validation pass was recorded for *these* bytes. |
| `manual` | No generation document, **or** a generation document explicitly invalidated by an authoring command (`result_json.manual_authoring = true`). The plan has at least one objective with a non-empty title and evidence target. | Parent-authored outline. No validation pass is claimed. |

Approval then writes one transition, bumps the enrollment revision, supersedes the previous
approved plan version and stamps `plans.approved_at`. The exact-hash fence, expected-revision
fence, idempotency replay and single-transition rule are unchanged.

## What approval does not mean

* It does not mean the plan was validated manually. A manual plan is labelled by provenance, never
  described as validated, and its response carries no validation claim.
* It does not re-run validation. The pass (or the manual decision) happened before approval.
* It does not make an edited plan valid. Editing after a pass invalidates that pass.
* It does not approve lessons or exported content; `parent.final.approve` binds that separately.

## Refusals (all typed, all side-effect free)

| Reason | When |
|---|---|
| `plan_empty` | The plan has zero objectives. Always refused, generated or manual. |
| `plan_not_validated` | Latest generation record is not the pass state (`needs_review`, `reject`, carried/replanned), has no validation verdict, or has no durable content binding. A manual outline with no usable objective also refuses here. |
| `plan_validation_stale` | The recorded pass is bound to a different kernel content hash than the current plan. |
| `plan_hash` (field) | The caller's `plan_hash` no longer matches the current content. |

A refusal writes no transition row, does not bump the enrollment revision, does not set
`approved_at` and does not change `plans.state`.

## Invalidation rules

* `parent.plan.edit`, `plan.replan` and direct objective authoring change the plan. The previous
  validation is bound to bytes that no longer exist.
* `plan.replan` carries the authored outline but **not** the approval or the validation: the copied
  `gen_plan_documents` row becomes `needs_review` with `validation_verdict = 'not_validated'`,
  `invalidated_reason = 'plan_replanned'`, no `validation_id`, and no content binding. Approval of
  the new version refuses until revalidation or an explicit manual-authoring decision.
* An explicit authoring command (`parent.plan.edit`, direct objective authoring) records
  `manual_authoring = true` on the generation row. That is the parent's decision to own the plan;
  approval then reports manual provenance and requires a real outline.
* Invalidation is durable rows, not a query-time guess, so it survives a restart.

## Hash note

`gen_plan_documents.plan_hash` is the **generation digest** (`generation.plan_hash(document)`), a
different function from the kernel content hash `plan.approve` binds. They are never compared
directly. The generation row stores the kernel hash it validated as
`result_json.plan_content_hash`; that snapshot is the binding. Rows written before H-12 have no
snapshot and therefore fail closed rather than being interpreted.

## Schema note

H-12 does not add `plans.validation_state`/`validation_id`: cb.db v6 and migration `0006` are owned
by H-01 (plan-brief inputs), so a second v6 was a collision. The durable record lives in the existing
`gen_plan_documents` row for the plan version. No schema change is needed for the rule to survive a
restart.
