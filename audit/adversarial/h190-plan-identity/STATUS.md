# H-190 — Plan identity: generation writes under the plan id the course holds

Branch `wt/h190-plan-identity`, base `883cdfe` (master) with the H-187 live-generation fixes
integrated from `0957ca6` (request bound scaled by scope, H-89 vocabulary rule gated on a declared
language). Neither of those fixes is modified here.

## Resolution (a), implemented

`course.create` mints one empty `draft` plan and returns its `pln_…` id. The plan job used to
insert a **second** plan row (`MAX(version)+1`) and write the authored document, its units, its
objectives, its sections and its `gen_plan_documents` row under that new id, so the id
`course.create` returned (the one the Desktop's `planJobBrief` and `plan.approve` use) named an
empty plan forever.

Generation now **reuses** that row. Inside the job's single write transaction it resolves the
course's placeholder plan and, when it is still empty — the course's only plan, state `draft`, no
objectives, no `plan_units`, no `gen_plan_sections`, no `gen_plan_documents` row — authors the
document under **that** id, keeping its version. Any authored content means the job authors a new
version exactly as before, so a manual objective or an earlier version is never overwritten. No
fallback in `plan.approve`; the empty-plan refusal is untouched.

The placeholder is not left as dead weight: it *is* the authored plan (same row, version 1).

Files: `coursebook/generation.py` (`_placeholder_plan`, and the plan-id decision moved inside the
write transaction in `run_plan_job`).

## Live acceptance — real product path, fresh isolated home

Command (`audit/adversarial/h190-plan-identity/run_single.sh`):

```
HERMES_HOME=~/.hermes/h190-plan-identity/single-r3/home \
  <host venv python> audit/adversarial/h190-plan-identity/worker.py \
  --tag single-h190 --title "Sharpen a kitchen knife on a whetstone" \
  --goal "Sharpen a kitchen knife on a whetstone without rolling the edge" \
  --recipe one_off --scope single --subject-domain technical_procedure --depth working \
  --max-seconds 900 --result audit/adversarial/h190-plan-identity/evidence/single.json
```

The home was created fresh for this run: no demo pack, no recorded transcripts, its own SQLite
store (only a `config.yaml` naming the host author model and the Coursebook validator route).
`course.create` -> `enrollment.create` -> `jobs.create(stage=plan)` -> the real
`executor.pump_once` (ctx.llm = `agent.plugin_llm.PluginLlm`, research through
`coursebook.research.HermesToolSearch` over the host `web_search`/`web_extract`) ->
`plan.approve`.

| fact | value |
|---|---|
| `course.create` → `plan_id` (before job) | `pln_4b499480…9406f` |
| plan job checkpoint `plan_id` (after job) | `pln_4b499480…9406f` — identical |
| `gen_plan_documents.plan_id` | `pln_4b499480…9406f` |
| plans held by the course | 1 (version 1, `draft` → `approved`); no orphan row |
| objectives on that plan | 1 |
| generation state / verdict | `draft` / `pass`, `outcome = independently_validated` |
| generator / validator | nous `deepseek/deepseek-v4.1-flash-1017` / nous `z-ai/glm-5.3-flash` |
| job | `completed` at 346.2 s, stage `plan` |
| `plan.approve(plan_id=<the id course.create returned>)` | **ok**, `revision = 1`, `plan_hash sha256:a38ac15c…d7c95` |
| read of that id after approval | the authored objective is there; plan `approved` |

Before (measured on `0957ca6`, H-187 evidence `single.json`): `course.create` returned
`pln_f91cb3ef…41a8` while the document landed on `24edbf47…` — an id with no `pln_` prefix and a
second plan row — and `plan.approve(plan_id=pln_f91cb3ef…)` refused with
`VALIDATION_FAILED: an empty plan cannot be approved; it has no objectives`.
`evidence/regression_on_0957ca6.log` in this directory shows the same split in a unit test:
`'f568365b70725ff7' != 'pln_21c8df5c…062f'`.

The research pass on this run was `degraded` (one firecrawl fetch failed); the plan says so, and
the approval warning block is empty because the independent validator passed with grounded facts.
No pass, evidence or token count is claimed beyond what the stored rows say.

## Regression test

`tests/test_learner_plan_flow.py::LearnerPlanFlowTest::test_the_plan_stage_runs_against_the_created_course`
now asserts the identity directly: the plan id returned by `course.create` is the id carrying the
authored document after the plan job (same row, version 1, exactly one plan for the course), the
read on that id carries the authored objectives, and `plan.approve` on it succeeds
(`revision 1`, row `approved`).

- Fails on `0957ca6`: `evidence/regression_on_0957ca6.log` (assertion above).
- Passes here: `python3 -m unittest tests.test_learner_plan_flow` → `Ran 16 tests … OK`.

`tests/test_syllabus_import.py::CompanionCourseTest::test_delete_refuses_while_a_course_is_bound_then_removes_every_row`
was updated from "2 plans" to "1 plan" for the same reason: the companion course no longer carries
an empty placeholder beside the authored plan.

## Full suite

```
python3 -m unittest discover -s tests -t .
Ran 2444 tests in 444.404s
FAILED (failures=4, skipped=1)
```

The only failures are the 4 pre-existing `V3AmendmentTest` failures that also fail on master
(`test_review_action_is_a_revision_fenced_learner_command`, and
`test_v3_payloads_are_validated_before_any_handler` for `review.queue`, `evidence.inspect`,
`evidence.disputes`). Nothing else fails.

Baseline on `master` @ `883cdfe`, same command:
`Ran 2441 tests in 441.830s` / `FAILED (failures=4, skipped=1)` — the same four
`V3AmendmentTest` failures and nothing else. This branch runs 3 more tests (the integrated
`tests/test_h187_vocabulary_gate.py` and the scope-bound case) and fails the same four.

## Packet evidence re-pin

`audit/adversarial/harness-e2e/evidence/*` and `manifest.json` were re-pinned: the packet harness
allocates deterministic ids, and the plan job now mints one id fewer (it no longer invents a plan
row), so every recorded id shifted by one. No semantic field changed — the diff is ids and the
hashes derived from them. `harness_e2e.verify_packet()` returns `[]` and
`tests.test_harness_e2e` is green (`Ran 26 tests … OK`).

## Not done here

- No validator, grading lane, rubric, RPC schema or vocabulary-rule change.
- `plan.approve` was not weakened; the empty-plan refusal is intact.
- Three-scope acceptance is H-192; this record claims only the single scope.
- This branch is not merged.
