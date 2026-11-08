# Parent Studio — what the typed brief does

Status: implemented backend behaviour, proven by `tests/test_parent_studio.py` and
`tests/test_capability_policy.py`. This document describes the kernel contract, not the Desktop
screen. Parent Studio means a parent preparing material to teach; there is no child-facing surface
and no child chat anywhere in this flow.

## One brief, one store

`parent.brief.create` validates and stores the typed brief in the `plan` job row
(`jobs.brief_json`). That row is the authority the executor reads. `parent.brief.get` projects the
typed fields back out of the same row, so "duplicate brief" copies real values. There is no second
brief table and no reconstructed form state.

The model-facing projection is `generation.parent_brief_view(brief)`: the typed fields
(`title`, `goal`, `starting_point`, `age_band`, `reading_level`, `duration_minutes`, `setting`,
`materials`, `exclusions`, `supervision`, `desired_pages`, `desired_visuals`, `narration`,
`locale`) copied verbatim. The two consent flags (`egress_acknowledged`, `redaction_requested`)
are not content and are not sent to the planner.

## What reaches the plan

`generation.run_plan_job` reads that projection for a `parent` recipe and passes it, under the
named `parent_brief` object, to:

* `build_plan_request` — the plan-generate payload gains `parent_brief` and, when the brief
  declares a page budget, `rules.page_budget` plus page-bounded `objective_count`/`section_count`;
* `build_plan_validation_requests` — the independent pass(es) judge the plan against the same
  answers;
* `enforce_plan_rules` — the deterministic rules below;
* `gen_plan_documents.document_json` — the brief is stored beside the plan so the lesson stage
  reads the same answers.

The request fingerprint includes the whole brief, so a changed age band, page budget, materials or
supervision can never be served from the reuse cache as the previous plan.

## Deterministic parent rules

A parent plan, when a brief is present, must satisfy all of:

| Rule | Refusal |
|---|---|
| `delivery` is `parent_led` | `parent plans are parent-led, never a child chat` |
| a `parent` block with `supervision_notes` and `hazards` | `parent plans require supervision notes` / `... name hazards` |
| every check is `observation` | `parent plan check for objective N is 'quiz'; parent checks are observations only` |
| no check claims `independent_evidence` | `parent observation is reported evidence` |
| at most `desired_pages` sections and objectives (one objective → one section → one learner page) | `the parent asked for at most N page(s); the plan authors M sections` |
| the plan's `parent.age_band` matches a band named in the brief | `the plan's parent block declares age band ... but the parent's brief declares ...` |
| no explicit grade/year in a reading level above the age band's ceiling (`3-5`→0, `6-8`→3, `9-11`→6, `12-14`→9, `15-18`→13) | `... that reading level is not age-appropriate` |
| `time_estimate.minutes_per_session` no longer than `duration_minutes` | `the plan's N-minute session exceeds the M-minute session the parent declared` |

The age-band ceiling only fires on an explicit school year (`grade 3`, `year 5`); a phrase the
rule does not understand is left alone rather than guessed at.

## Page budget

One objective authors one section authors one learner page, so `desired_pages` caps both. For a
parent plan the request carries a page-bounded copy of `PLAN_SCHEMA` (`parent_plan_schema`) whose
objective/section `maxItems` is the budget, and the rules refuse a plan over it. A brief asking
for fewer pages than the default four-objective course therefore produces a genuinely shorter
plan; schema and rules use the same bound, so the model is never told two different things.

## Visuals and narration

`desired_visuals` (`none` / `diagrams` / `illustrations`) and `narration` (`none` / `script`) are
parent preferences, not orders:

* a `none` answer **withholds** that medium — `policy.plan_lesson_capability` narrows the
  capability decision to `none` even when the authored lesson intent names a construct that would
  otherwise have earned it;
* a positive answer (`diagrams`, `illustrations`, `script`) never **forces** media — the authored
  intent still has to name the visual or oral construct the medium carries.

The lesson stage reads the preference from the stored plan document, so the decision is the same
one the plan was authored under. Media is still decided by the deterministic capability policy
(`docs/CAPABILITY-POLICY.md`); the brief can only narrow it.

## What the model is told

For a parent brief the plan instructions state, in plain terms: this is parent-led material and
never a child-facing chat, there is no child persona and no grading of the child, every check is a
parent observation, the brief's answers are answers rather than suggestions, the reading level must
stay age-appropriate, and materials/exclusions/supervision are restated rather than contradicted.
The plan schema carries no reference-answer or rubric field, so the plan cannot leak an answer key
into learner-facing content.
