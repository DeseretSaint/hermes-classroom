# H-182/D1–D3 — repair path, real retry, fail-closed approval

Branch `wt/h182-plan-repair` from master `7e15963`. Cold-walk evidence here was captured in a
**dedicated, disposable profile** (`~/.hermes/coursebook-test-h182d3`, own backend :44301, own CDP
:9397), installed from this checkout with `scripts/install-local.sh` (Desktop half sha256
`413796c0…28c7`, the module under test). Operator profile, installed plugin and gateway untouched.

## Proven by tests (real kernel + real contract)

| What | Test |
|---|---|
| A new job for the same brief does **not** get the refused draft back; `reuse_declined` names what was declined and the new attempt writes a new `plan_id`/`plan_hash` | `tests.test_h182_plan_repair.RejectedPlanIsNotReplayedTest` |
| The job that wrote a draft, a passing draft and a manual-authoring record still reuse (a reconnect stays free) | same class |
| `course.outline` and `parent.blueprint.read` project one `plan.validation` object; a refused draft is `approvable:false` with its reasons, and `plan.approve` refuses on the same facts | `PlanValidationProjectionTest` |
| An edit is the repair: `parent.plan.edit` → `approvable:true`, `source:"manual"`, `verdict:"not_validated"`, then `plan.approve` succeeds | `test_an_edit_is_the_repair_and_approves_as_manual` |
| A version with no record is **not** approvable (`plan_not_validated`) | `test_a_version_with_no_record_is_not_approvable` |
| Renderer: refusals keep the panel up while a retry job runs, an edited plan steps out of it, a replayed retry is named as a replay, Approve is rendered only when `plan.validation.approvable === true`, and approval re-checks the durable gate before sending | `tests.test_desktop_plan_reject` (model + wiring) |
| A parent brief that states no locale is re-queueable: the stored/projected brief omits `locale` and the exact `jobs.create` payload the renderer sends passes the closed `plan_brief` schema | `ParentStageRetryTest` |

## Live, in the cold profile

1. First run renders one primary (`Start with a goal`) — `10-cold-first-run.png`.
2. Parent Studio → `New lesson plan` → an arbitrary non-Japanese brief (“Why volcanoes erupt”,
   goal + starting point + reading level + materials + exclusions + supervision, egress
   acknowledged) — `11-brief.png`. `parent.brief.create` queued a real `plan` job.
3. **Environmental blocker found, not code:** `coursebook.plan.generate` exceeded its declared
   240 s deadline on the first attempt (`HOST_UNAVAILABLE`), and exceeded an operator-raised
   480 s deadline on the retry. The provider call itself (Nous `deepseek/deepseek-v4.1-flash-1017`)
   was still outstanding; web search returned immediately, so this is model latency, not the
   research fan-out. The parent cold walk saw the same stage take 222 s, so the declared 240 s
   single-call bound is below observed behaviour for the same provider on the same day.
4. **Live defect found and fixed:** `Run this stage again` sent the job's own `brief` back to
   `jobs.create`, and a parent brief that stated no locale was stored as `locale: null` —
   `$defs/plan_brief.locale` is a non-nullable locale string, so the payload was refused with
   `VALIDATION_FAILED: brief/locale: None is not of type 'string'` and **no plan stage could ever
   be retried**. Fixed by storing/projecting absence instead of null (see the diff), with a
   contract-level regression test.

## Not yet captured (blocked on provider latency, not on this change)

The end of the loop — plan review → `Edit the plan` → `Save changes` → `Approve plan` →
lessons → open lesson — was not re-walked live because no plan job completed in the window this
session had available. Re-run the walk when the provider is responsive; the fix it must exercise is
already pinned by the tests above. Also still stale until the module moves: the M4 visual pin and
the harness-e2e packet (`tests.test_m4_visual_audit`, `tests.test_harness_e2e`), which must be
regenerated for this `desktop/plugin.js` before merge.
