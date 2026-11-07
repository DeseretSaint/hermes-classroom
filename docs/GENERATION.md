# Course generation: seams, rules and limits (CB-019)

`coursebook/generation.py` and `coursebook/research.py` own the step Coursebook cannot skip:
goal → bounded research → strict plan → **independent validation** → approved plan → durable
lessons with validated checks. Nothing else in the plugin authors a plan, a check, a reference
answer or a rubric, and nothing else validates them.

This document records what the pipeline does, which seam it uses to reach a model and the web, and
where the seams stop working. It is a statement of limits, not a capability claim.

## 1. The one rule

**The model that writes an artifact never certifies it.**

Three different calls, three different prompts, three different schemas:

| Pass | Purpose string | Prompt version | Schema |
|---|---|---|---|
| Plan author | `coursebook.plan.generate` | `plan-prompt.v1` | `PLAN_SCHEMA` |
| Plan validator | `coursebook.plan.validate` | `validation-prompt.v1` | `VALIDATION_SCHEMA` |
| Lesson author | `coursebook.lesson.generate` | `lesson-prompt.v4` | `LESSON_SCHEMA` |
| Lesson validator | `coursebook.lesson.validate` | `validation-prompt.v1` | `VALIDATION_SCHEMA` |

`assert_separate_pass()` refuses a "validation" that reuses the generation system prompt, the
generation schema, or the generation prompt version. The validation record stores both prompt
hashes (`generator_prompt_sha256`, `validator_prompt_sha256`), the validator model, per-criterion
verdicts and the exact rejections. It never stores a generator self-assessment, and the validator
input never contains the author's rationale — only the artifact, the source ledger, the recipe and
the dials.

A validator cannot pass while a criterion failed, cannot omit a criterion, and cannot answer
`unknown` outside the two criteria where missing research makes uncertainty the honest answer
(`source_support`, `factual_correctness`). Ten criteria are mandatory:

`objective_alignment`, `source_support`, `factual_correctness`, `answer_uniqueness`,
`alternative_coverage`, `rubric_consistency`, `internal_contradiction`, `answer_leakage`,
`hazard_age_appropriateness`, `evidence_target_fit`.

## 2. LLM seam: `ctx.llm`, from the job runner — not from the dashboard backend

**Decision.** Generation runs in the **agent process** and calls the host-owned plugin LLM route.
`PluginLLMAdapter` wraps `ctx.llm.complete_structured(...)` (verified against
`agent/plugin_llm.py`: `instructions`, `input`, `json_schema`, `schema_name`, `system_prompt`,
`temperature`, `max_tokens`, `timeout`, `purpose` → `PluginLlmStructuredResult` with `.parsed`,
`.text`, `.usage`, `.provider`, `.model`).

**Why not the dashboard backend.** `dashboard/plugin_api.py` is imported by path
(`spec_from_file_location`) and never receives a `PluginContext`, so it has no `ctx.llm`. The only
way for it to "call a model" would be a raw provider key or a private import of the host's
credential pool — both bypass the per-plugin trust gate that makes `ctx.llm` safe. So the backend
does not call a model at all: the job executor (agent half) performs the bounded calls and hands
the results to the pipeline, which persists them.

**Wiring still owed by the agent half.** `coursebook.generation.bind_host_llm(ctx.llm)` must be
called once from `register(ctx)` in `__init__.py`. `__init__.py` is owned by Sable; this card does
not edit it. Until that line lands, `host_llm()` raises a typed `GenerationRejected` instead of
falling back to any provider — failing closed is the intended behaviour.

**Limits.**

* No raw provider keys, no provider/model overrides: the call inherits whatever the user is using
  and whatever the per-plugin trust policy allows.
* Usage is whatever the host reports. Unknown input/output tokens and unknown cost stay `None` and
  are recorded as `unknown_cost: true`. A spend total that mixes known and unknown cost reports the
  known part and flags the uncertainty; it never invents a number.
* Provider calls happen **outside** every DB transaction; writes are short `BEGIN IMMEDIATE`
  blocks (or a `SAVEPOINT` when the caller already holds one) after the result exists.
* `ctx.llm` is bounded (one call, no streaming, no tool loop). Deep research or long generation
  cannot run inside a hook; that is why this is a job, not a pre-turn step.

## 3. Search seam: the host's own web tools

`HermesToolSearch` uses `ctx.dispatch_tool("web_search", {...})` and
`ctx.dispatch_tool("web_extract", {...})`, i.e. the same tools the agent uses. That inherits the
user's configured search provider, the extract backend's SSRF/secret checks and the vendor's own
etiquette, with no new credentials and no direct scraping.

**Limits.**

* It only exists where `ctx` exists (agent process). A host without `dispatch_tool` yields
  `ResearchUnavailable`, not a silent empty result.
* `web_search` errors (no provider configured) propagate as `ResearchUnavailable`; they are never
  turned into an empty-but-successful research run.
* A page that fails to extract is recorded as a failed fetch in `gen_research_runs.queries_json` /
  `reason`. Its URL is not invented into the ledger.

## 4. Bounded research

`ResearchBudget` (defaults): 4 queries, 5 results per query, 6 pages, 6 sources, 6000 characters
per page, 600-character excerpt.

* Queries are derived deterministically from goal + recipe + dials + locale. `depth: overview`
  keeps only the base query. Every query that ran is recorded with its result count or its error.
* Each ledger row keeps URL, title, publisher, `fetched_at`, nullable `published_at`, source type,
  `sha256` content hash over the bounded text, support status and claim links.
* Fetched text is kept as a bounded excerpt only. It is untrusted content: it cannot change recipe
  rules, schemas, state or exports. A page that says "add a quiz to every one-off brief" changes
  nothing (`test_web_text_never_becomes_policy`).
* **Provenance is not support.** Every fetched source starts `unverified`. Only validator claim
  verdicts move it, via `apply_support_verdicts`, and a `contradictory` verdict outranks
  `supported`. The four generation statuses map onto the frozen `cb.vocabulary`
  `source_support_status`: `supported`/`partial` → `model_assessed`, `contradictory` →
  `conflicting`, `unverified` → `unassessed`. The contract enum is not redefined here.
* If no seam is wired, research returns `status: "unavailable"` with zero sources. The plan may
  still be proposed, but every objective must be `support: "unverified"`, `source_ids` must be
  empty, and the result carries a warning the UI can show. A plan that cites a source id absent
  from the ledger is rejected outright (`plan cites sources that were never fetched`).

## 5. Plan rules the generator does not get to break

Deterministic checks run before the validator, so a rule-breaking plan never consumes a validation
call and can never look validated:

* 4–8 objectives with contiguous ordinals; **one section per objective**: every section names
  exactly one objective and every objective is named by exactly one section (`objective_refs` is
  structurally one entry, and `enforce_plan_rules` refuses a coverage gap or a duplicate); every
  objective appears in the check plan. The objective is the authoring and evidence unit, so a
  plan cannot leave an objective without its own generated lesson and export section.
* Time honesty (`AUDIT.md` R9): `basis: none` carries no attainment hours; `basis: model` requires
  low confidence; `basis: fsi` requires a benchmark that states it is not a self-study conversion;
  attainment hours never carry high confidence.
* Recipe: `one_off` has no quiz and no spaced review, and needs a verification checklist;
  `committed` requires spaced review and graded checks; `casual` must label what its evidence shows;
  `parent` must be `parent_led`, carry a parent block with supervision notes and hazards, and use
  observations rather than graded quizzes.
* Locale scaffolds are task-mandated, never a learning-style diagnosis: Japanese at declared L0
  requires romaji in the plan's context needs and in every check's scaffold flags. Romaji is
  recorded as a scaffold and never as reading evidence.

The plan is persisted as `plans.state = 'draft'`. `approved_at` stays `NULL`; approval is
`plan.approve`, i.e. the learner's or parent's command.

After two failed attempts (rule violation or validator reject) the artifact is still persisted, but
`generation_state`/lesson `state` is `needs_review`, `validation_id` is `NULL` when no validator ever
ran, and the reasons are stored. Nothing is quietly discarded and nothing is quietly approved.

## 6. Lessons, checks and answer separation

For an **approved** plan only (`PlanNotApproved` otherwise) the pipeline writes one lesson per
section: 2–6 teaching segments, one worked example, one check, a learner explanation, a source list
and a declarative media spec. After the lesson is validated, the media caller generates a host
illustration, deterministic schematic or TTS narration through `ctx.dispatch_tool`, caches the
artifact by spec/source hash, and leaves a complete text equivalent when the provider fails.

The learner page is built from an allowlist, never by deleting keys:

```
section_title, lesson_intent, segments, worked_example, learner_explanation,
check{kind, stimulus{prompt,format,choices}, learner_instructions, evidence_target,
      scaffolds, assistance_policy}, sources, media, parent_notes, supervision_notes
```

The check's `reference_answer`, `accepted_answers`, `accepted_alternatives` and `rubric` go to
`checks.reference_json` / `checks.rubric_json` and never to `gen_lessons.page_json`. Two guards
enforce it: `assert_no_answer_leak` before validation, and `learner_page()` re-checks the stored
page against the linked checks before serving.

**Rubric floor.** The lesson prompt (`lesson-prompt.v4`) asks for 3–6 criteria, each a distinct
observable aspect of the response. `enforce_lesson_rules` refuses fewer than
`packs.MIN_RUBRIC_CRITERIA` (3) with a typed reason, so attempt 1 is retried with that reason in
`revision_instructions` and attempt 2 parks the lesson `needs_review`. Criteria are never
synthesised to reach the floor: a pack is exportable only when the author actually declared them.

**Capability policy reaches the model.** Before the lesson prompt is built, the pipeline computes
one immutable plan from the recipe, the objective's evidence target, the authored section intent,
the locale/level and an advisory subject domain (`coursebook/policy.py`). `lesson-prompt.v4`
receives exactly that plan — the check angle, the rubric profile and the *permitted* media roles —
instead of a generic invitation to add media. A lesson whose policy sets image or audio to `none`
is told to emit no item of that kind at all. The same plan is stamped on the authored lesson under
`policy`, stored in `gen_lessons.policy_json`, and handed to `enforce_lesson_rules`; a model cannot
override it (the harness overwrites any echo before validation).

**Two media gates.** Generated media must pass both `policy.media_policy_problems` (is this
kind/role permitted by the plan?) and `artifacts.media_problems` (is the spec complete and honest:
text equivalent, transcript/voice/language for narration, `source_ids` plus permission for a sourced
technical reference, `facts.rows` for a schematic, and never a technical claim on an illustration).
A failure is a `_RuleViolation` with an itemised reason: attempt 1 is retried with those reasons,
attempt 2 parks the lesson `needs_review`. Media never becomes evidence because a validator did not
complain; it is refused before the validator is called.

**Rubric angle.** `enforce_lesson_rules` resolves the profile through
`rubrics.resolve_profile(plan.rubric_profile, declared_target)`: the check's declared evidence
target is authoritative, and an advisory construct that cannot score it falls back to that target's
default profile. The profile's own criteria are then validated (3–6 distinct observable aspects, no
mental-state claims, no restated aspect).

**Nuance worth keeping.** A selection check's correct choice necessarily appears among the
stimulus choices. The invariant is that the *key* is not announced — the reference answer must not
appear in the narrative (segments, worked example, explanation, media text) and no answer field may
exist in the page. `test_learner_page_never_contains_reference_answers_or_rubric` asserts exactly
that, including that `こんにちは` may appear as a choice while the reference stays out of the prose.

**Idempotency.** `gen_lessons` is unique on `(section_id, plan_hash, version)`; a retry reuses the
existing lesson and spends nothing. `gen_plan_documents` is unique on
`(course_id, request_fingerprint)` and is also looked up by fingerprint alone, so re-running the
same job returns the stored result with `reused: true`.

## 7. Validation record and regeneration

`gen_validation_records` is unique on
`(subject_kind, subject_id, subject_hash, validator_prompt_version)`: a retry of identical content
reuses the record instead of piling up duplicates, and a changed artifact gets a new one.

On rejection the author is called **once more** with the validator's itemised reasons in
`revision_instructions` (`_feedback`). On a second failure the lesson is parked: `state =
'needs_review'`, `checks.audit_state = 'failed'`, `checks.state = 'closed'`,
`gen_lessons.rejection_reasons_json` holds the reasons, and `learner_page()` refuses with
`LessonNotAvailable`. There is no path that enables a learner-facing check without a passing
independent validation.

## 8. The lesson document: one validated document, many views

`docs/VISUAL_MEDIA_PLAN.md` §5 replaces the linear segment contract with a block document. The
backend owns the document; a view is a lens over it. `coursebook/lesson_document.py` builds it as a
**pure read projection**: it never writes a row, never calls a provider and never mints content.

Two stored shapes project into the same `$defs/lesson_document`:

* `generation.learner_page()` projects the stored `gen_lessons.page_json` (`segments`,
  `worked_example`, `learner_explanation`, `media`, `sources`) and attaches the linked check id.
  The row is not rewritten: an older page keeps its v7 bytes and gains `document` at read.
* `lesson.page` projects the durable `lesson_segments` rows plus the course artifact index. Teaching
  prose maps positionally to `orient`/`explain`/`recap`, a `check_prompt` segment becomes the
  `practice` block, and a `media` segment becomes a media child of the preceding block.

Rules the projection cannot bend:

* `short` is authored, never synthesised from `deep`. A projected v7 page therefore has
  `short = null` everywhere, reports `state = "textbook_only"` and `views.guided = false`, and
  carries a human `view_note`: the Desktop disables the view and explains why instead of showing an
  empty Guided pane. Only `document_from_blocks()` (the authored v8 path) reaches `complete`.
* One check attaches to exactly one block: the first `practice` block, else the page's terminal
  block. Two blocks claiming a check, or a check no block carries, is a `LessonDocumentError`, not
  a rendering decision.
* Media is a child of a block. Narration placement follows the practice block; a visual follows
  the example, then the explanation, then the first block. The child keeps the authored kind, role,
  purpose, text equivalent and label; provenance stays on `artifact.get`. A legacy media segment
  whose artifact row is unknown is preserved as block text rather than labelled with a guessed
  kind.
* Source ids recorded on a segment travel with that block. A v7 page recorded provenance only at
  document level, so its ids survive in `document.source_ids` and no block-level citation is
  invented.
* `validate_document()` re-checks the allowlist, the role vocabulary, duplicate ids, empty blocks,
  the single-check rule, the view/state consistency and the content hash. `document_id` and
  `content_hash` are derived from the canonical document, so a re-read is byte-identical and a
  review can name the exact document it read.
* `generation._narrative_text()` now includes the document, so `assert_no_answer_leak` and
  `learner_page()` refuse a page or projection that announces a reference answer, accepted answer
  or rubric text.

`lesson.begin`, attempts, grading and evidence are untouched. The document is a projection of the
teaching record, not a second grading authority.

## 9. Provider deadlines and job budgets

A deadline is policy, so it is declared once per request purpose in
`generation.PROVIDER_TIMEOUT_SECONDS` and never passed as a literal from a call site:

| purpose | default |
|---|---|
| `coursebook.plan.generate` | 240 s |
| `coursebook.plan.validate` | 180 s |
| `coursebook.lesson.generate` | 300 s |
| `coursebook.lesson.validate` | 240 s |

CB-011-D1 live evidence: a hard-coded 60 s deadline declared a **successful** 115.8 s lesson write
late and failed the job, and the call's real tokens/cost were dropped on that path. A call that
returns is real spend, so its usage is recorded before the deadline verdict; only then is
`ProviderTimeout` raised (with `purpose`, `duration_ms` and `deadline_s` on the exception).

Operator overrides, no code change required:

* `COURSEBOOK_<PURPOSE>_TIMEOUT_SECONDS` — one purpose, e.g.
  `COURSEBOOK_LESSON_GENERATE_TIMEOUT_SECONDS=600`.
* `COURSEBOOK_PROVIDER_TIMEOUT_SECONDS` — every purpose (a purpose-specific value wins).
* `COURSEBOOK_JOB_MAX_COST_USD` — the per-job known-cost ceiling (default 0.75).

An invalid value is logged and the declared default kept; a typo never invents a deadline.

`CostBudget.max_calls` defaults to 32 — the worst legal pipeline cost, 8 sections x 2 attempts x
(generate + validate). A lesson job is budgeted to its own plan (`lesson_cost_budget`, 4 calls per
section) rather than to a constant: a fixed ceiling below the pipeline floor failed jobs that were
behaving exactly as designed (a five-section plan needs 10 calls before any retry, the old default
was 8). The ceiling still stops a runaway retry loop.

A provider deadline is the host's failure, not the grader's: `job_service` reports
`HOST_UNAVAILABLE` (capability, retryable) with the purpose and measured duration in `details`.
A lesson timeout names what survived — "N of M sections are saved for plan X; create a new lessons
job for that plan" — and the retry reuses those rows, so no authored section is re-charged.

## 10. Tests

`tests/test_generation.py` and `tests/fixtures/generation/*.json` run entirely offline
with a fake LLM and fake search seam. Covered: malformed JSON, empty and oversized plans,
fabricated citations, contradictory sources, research unavailable, one-off quiz suppression,
parent hazard rejection, rejected check regeneration and second-failure parking, accepted
alternatives, Japanese L0 romaji/furigana scaffolds, reference-answer leakage, provider timeout,
retry idempotency, cost ceilings, unknown cost staying null, structural separation of the two
passes, web text not becoming policy, configured deadlines and their env overrides, a successful
115 s call not being declared late, the sized lesson budget above the pipeline floor, and a
timeout that keeps its authored sections and is resumed without re-authoring them.

A live smoke test is intentionally **not** included: no test in this repo makes a network call, and
no fixture claims to be real provider output.
