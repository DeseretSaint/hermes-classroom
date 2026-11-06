# CB-019 review packet — governed generation + independent validation

Branch: `wt/cb-019-quill` · Owner: Quill · Base: `0c323be` (CB-001 skeleton)
Code commits: **54b8fbc** (modules, tests, fixtures, `docs/GENERATION.md`), **6c73600** (atomic
persistence of the plan and lesson bundles), **bbf91de** (no stale validator report across
attempts). This packet file is updated by the branch-tip commit; `git log --oneline` on
`wt/cb-019-quill` is authoritative.
Status: **not merged**. Atlas integrates.

## 1. What landed

| File | Purpose |
|---|---|
| `coursebook/research.py` | bounded research: deterministic query derivation, executable ceilings, host-tool search/extract adapter, source ledger with real provenance + content hash, support status that only a validator can move |
| `coursebook/generation.py` | strict plan/lesson/validation schemas, `ctx.llm` adapter, `run_plan_job`, `run_lesson_job`, `learner_page`, generation-owned SQLite schema, idempotent persistence, usage accounting |
| `tests/test_generation.py` | 43 offline cases with a fake LLM and fake search seam |
| `tests/fixtures/generation/*.json` | 9 fixtures: Japanese L0 plan/lesson, one-off plan/lesson, parent plan/unsafe parent lesson, three validation reports |
| `docs/GENERATION.md` | seam decision, rules, limits |

No kernel file was touched: `coursebook/domain.py`, `coursebook/db.py`, `coursebook/jobs.py`,
`desktop/plugin.js`, `contracts/**`, `plugin.yaml`, `__init__.py` and the pack schema are untouched.

## 2. Test output (real)

```
$ python3 -m unittest discover -s tests -t .
........................................................................................
----------------------------------------------------------------------
Ran 89 tests in 0.163s

OK

$ node --check desktop/plugin.js
desktop/plugin.js: syntax OK

$ hermes plugins validate .
Validation passed.
```

`tests.test_generation` alone: **43 tests, OK**. 46 pre-existing contract/RPC/job/desktop tests
still pass unchanged.

## 3. Seam decision (short form; full text in `docs/GENERATION.md` §2)

*Generation runs in the agent process and uses `ctx.llm.complete_structured(...)`.* The dashboard
backend (`dashboard/plugin_api.py`) is imported by path with no `PluginContext`, so it cannot reach
`ctx.llm`; giving it a raw provider key would bypass the per-plugin trust gate. So the backend does
not call a model — the job executor does, and the pipeline persists the result.

Search uses the host's own tools via `ctx.dispatch_tool("web_search" | "web_extract", ...)`, which
inherits the configured provider and the extract-side SSRF/secret checks.

**One-line wiring still owed by Sable:** `coursebook.generation.bind_host_llm(ctx.llm)` inside
`register(ctx)`. `__init__.py` is Sable-owned and not edited here. Until that exists `host_llm()`
raises `GenerationRejected` rather than falling back to any provider.

## 4. Sample generated plan (real run, fake provider)

Fixture goal: *"Order coffee in Japanese"*, recipe `committed`, locale `ja-JP`, dials `{"level": "L0"}`,
one fetched source.

```json
{
  "plan_id": "f20cf4a6ac45af30",
  "plan_hash": "sha256:6805dd805559dc2514833569321d9887a4496bb2f63fd1d39f35555e893d1cf3",
  "plan_version": 1,
  "status": "draft",
  "validation_verdict": "pass",
  "objectives": 4,
  "sections": 3,
  "sources": 1,
  "research": {"status": "ok", "queries": ["Order coffee in Japanese",
                "Order coffee in Japanese syllabus learning objectives"]},
  "usage": {"calls": 2, "input_tokens": 240, "output_tokens": 480, "cost_usd": 0.02}
}
```

Ids and therefore the plan hash are minted per run (the plan cites the ledger source id), so a
fresh run produces a different hash over identical plan text. The document above is one real run of
the pipeline; `tests/fixtures/generation/plan_ja.json` is the stable payload it was generated from.

Plan body (excerpt; full document in `tests/fixtures/generation/plan_ja.json` and in the persisted
`gen_plan_documents.document_json`):

```json
{
  "title": "Japanese café basics",
  "learner_outcome": "At a café, greet the staff, order one drink, ask a price and answer a simple follow-up question in Japanese using standard polite forms, with romaji and furigana available as scaffolds.",
  "delivery": "self_study",
  "time_estimate": {
    "sessions_per_week": 3, "minutes_per_session": 25, "weeks": 6,
    "basis": "model", "confidence": "low",
    "rationale": "Derived from the declared 75 minutes per week and three sections; it schedules practice, it does not promise attainment.",
    "benchmark": null, "attainment_hours": null
  },
  "objectives": [
    {"ordinal": 1, "title": "Greet café staff and open the interaction politely",
     "evidence_target": "production", "support": "sourced", "source_ids": ["<ledger id>"]},
    {"ordinal": 2, "title": "Order one drink using a polite request form",
     "evidence_target": "production", "support": "unverified"},
    {"ordinal": 3, "title": "Distinguish これ / それ / あれ when pointing at menu items",
     "evidence_target": "discrimination", "support": "unverified"},
    {"ordinal": 4, "title": "Understand a staff follow-up question about drink size",
     "evidence_target": "comprehension", "support": "unverified"}
  ],
  "sections": [
    {"ordinal": 1, "title": "Greeting and opening", "objective_refs": [1],
     "context_needs": ["romaji", "furigana", "english meaning"]},
    {"ordinal": 2, "title": "Ordering a drink", "objective_refs": [2, 3]},
    {"ordinal": 3, "title": "Price and follow-up", "objective_refs": [4]}
  ],
  "check_plan": [
    {"objective_ref": 1, "kind": "quiz", "evidence_target": "production", "count": 1, "independent_evidence": true},
    {"objective_ref": 2, "kind": "quiz", "evidence_target": "production", "count": 1, "independent_evidence": true},
    {"objective_ref": 3, "kind": "quiz", "evidence_target": "discrimination", "count": 1, "independent_evidence": true},
    {"objective_ref": 4, "kind": "quiz", "evidence_target": "comprehension", "count": 1, "independent_evidence": true}
  ],
  "context_needs": ["romaji", "furigana", "english meaning", "Japanese-capable fonts and line breaking"],
  "source_ids": ["<ledger id>"],
  "exclusions": [
    "No claim of native-speaker naturalness: wording and usage still need fresh sourcing.",
    "No pronunciation assessment from text or generic TTS.",
    "No keigo beyond standard polite forms."
  ],
  "spaced_review": true
}
```

Persisted state: `plans.state = 'draft'`, `approved_at = NULL`, 4 `objectives`, 3
`gen_plan_sections`, 1 `sources` row (`support_status = 'model_assessed'` after the validator's
claim verdict, `claim_count = 2`), 2 `usage_events`, 1 `gen_validation_records`.

## 5. Sample validation report (real row)

```json
{
  "id": "7ca4053dad3cb5d7",
  "subject_kind": "plan",
  "subject_id": "f20cf4a6ac45af30",
  "subject_hash": "sha256:6805dd805559dc2514833569321d9887a4496bb2f63fd1d39f35555e893d1cf3",
  "generator_prompt_version": "plan-prompt.v1",
  "validator_prompt_version": "validation-prompt.v1",
  "validator_model": "fake-validator",
  "verdict": "pass",
  "criteria": [
    {"id": "objective_alignment", "verdict": "pass", "reason": "objective_alignment checked against the artifact and ledger"},
    {"id": "source_support", "verdict": "pass", "reason": "source_support checked against the artifact and ledger"},
    {"id": "factual_correctness", "verdict": "pass", "reason": "…"},
    {"id": "answer_uniqueness", "verdict": "pass", "reason": "…"},
    {"id": "alternative_coverage", "verdict": "pass", "reason": "…"},
    {"id": "rubric_consistency", "verdict": "pass", "reason": "…"},
    {"id": "internal_contradiction", "verdict": "pass", "reason": "…"},
    {"id": "answer_leakage", "verdict": "pass", "reason": "…"},
    {"id": "hazard_age_appropriateness", "verdict": "pass", "reason": "…"},
    {"id": "evidence_target_fit", "verdict": "pass", "reason": "…"}
  ],
  "rejections": {"rejections": [], "failed": [], "unknown": [], "declared": "pass"},
  "generator_prompt_sha256": "sha256:…",
  "validator_prompt_sha256": "sha256:…"
}
```

The two prompt hashes differ by construction and `assert_separate_pass` refuses identical prompts or
schemas. The validator input is the artifact + ledger + recipe/dials only — never an author
rationale to restate.

## 6. Rejected-material trace (real run)

Same approved plan, lesson 1 submitted twice with an ambiguous selection check:

```
lesson 70d55b48cb69945e  state=needs_review  check_enabled=false
  rejection_reasons:
    "check:1: The stimulus asks for a polite opener but both こんにちは and ありがとうございます are
     acceptable openers, so the key is ambiguous."
  checks.4cfc9e99216cb88a  audit_state=failed  state=closed
  learner_page() -> LessonNotAvailable:
    "lesson '70d55b48cb69945e' is 'needs_review': no learner-facing check is enabled"
sections 2 and 3 validated normally (audit_state=passed, state=open).
```

The second generation call carried `revision_instructions` with that exact reason
(`test_rejected_check_regenerates_once_with_reasons_then_passes` asserts the text is present in
`llm.requests[2].input_text`). Two lesson generation attempts, one validation record per artifact
hash, no duplicate lesson/check rows.

## 7. Acceptance criteria → evidence

| Criterion | Evidence |
|---|---|
| fixture goal → schema-valid plan + validation report, no network | `test_fixture_goal_produces_a_validated_draft_plan_with_no_network` |
| wrong check rejected; enabled-check set excludes it | `test_second_validation_failure_parks_the_lesson_and_disables_the_check`, trace §6 |
| no reference answer in learner-facing output | `test_learner_page_never_contains_reference_answers_or_rubric`, `learner_page()` defence in depth |
| re-running the job duplicates nothing | `test_retrying_the_same_plan_job_does_not_duplicate_rows_or_spend`, `test_lesson_generation_is_idempotent_per_plan_section_version` |
| unsupported sources labelled `unverified` | `test_research_unavailable_marks_claims_unverified_and_says_so`, `no_research.json` |
| suite + admission still pass | §2 |
| review packet | this file |

Additional case coverage: malformed JSON, empty plan, oversized output, fabricated citation,
contradictory source, accepted alternatives, Japanese L0 romaji/furigana scaffolds, one-off quiz
suppression, parent hazard rejection, provider timeout, cost ceiling, unknown cost staying null,
web text not becoming policy, and structural separation of the two passes.

## 8. Decisions a reviewer may want to overturn

1. **Contract tables created with `CREATE TABLE IF NOT EXISTS`.** `cb.db` v1 names
   `courses/plans/objectives/checks/sources/usage_events` but `coursebook/migrations/` is empty
   (Cinder's package), so this module creates the contract-shaped tables it writes when they are
   absent. When Cinder's migration lands the statements become no-ops. Authoring-only rows live in
   `gen_*` tables (`gen_plan_documents`, `gen_plan_sections`, `gen_lessons`, `gen_lesson_checks`,
   `gen_validation_records`, `gen_research_runs`). If cb.db v2 renames or normalises these, they
   need folding in — see open questions.
2. **Idempotency fingerprint is global, not per-course.** `gen_plan_documents` is looked up by
   `request_fingerprint` (goal + recipe + dials + locale + pipeline/prompt versions) before a course
   is minted, so a retried job reuses its plan instead of creating a second draft course. Passing an
   explicit `course_id` is how two genuinely separate courses with the same brief are kept apart.
3. **`unknown` criterion verdicts.** Allowed only for `source_support` and `factual_correctness`, and
   only when research status is not `ok`. Everywhere else `unknown` is treated as a failed
   validation. A validator that "can't tell" is not a pass.
4. **Selection checks and the leak rule.** A correct choice necessarily appears in the stimulus
   choices, so `assert_no_answer_leak` scans the *narrative* (segments, worked example, explanation,
   media text) rather than the whole page. The page still contains no answer field and no reference
   answer in prose.
5. **Rejection records are keyed by artifact hash.** Two identical rejected attempts produce one
   validation record, not two. The second attempt's failure is visible in
   `gen_lessons.rejection_reasons_json`, which is what the UI should show.

## 9. Open questions for Atlas

* **`source_support_status` vocabulary gap.** The card's ledger statuses (`supported`, `partial`,
  `contradictory`, `unverified`) are finer than the frozen `cb.vocabulary` enum. This card maps them
  (`model_assessed`/`conflicting`/`unassessed`) rather than editing a frozen contract. If the ledger
  is meant to surface "partial" vs "supported" to the user, the contract needs a v2 enum or a
  `details` field; that is an Atlas decision, not a silent plugin-side fork.
* **Where do `gen_*` tables belong?** They are additive and plugin-owned, but `cb.db` is the stated
  source of truth. Options: fold them into a cb.db v2, or have Cinder's kernel own them. This
  affects CB-002's migration inventory and should be settled before merge ordering.
* **`bind_host_llm` wiring** in `__init__.py` (Sable) — one line, but the pipeline is inert without
  it. Is that a CB-003 follow-up or a merge-time edit?
* **Job states.** `run_plan_job` returns a result dict; it does not write `jobs.state`. The job
  executor (Cinder, `cb.jobs`) owns transitions, including `interrupted_requires_retry` after a
  `ProviderTimeout`. Confirm the executor treats `GenerationRejected`/`ProviderTimeout` as `failed`
  (retryable) and `CostCeilingExceeded` as a safe stopping point.
* **Media spec handoff to CB-012.** `lesson["media"]` items are `{kind, purpose, spec,
  text_equivalent}`. CB-012 needs to accept exactly that shape; if it expects a different key for the
  generation prompt, decide the mapping rather than duplicating it.
* **Live smoke test.** Deliberately absent. If we want one, it must be behind an explicit env flag
  and must not be required by CI; a "precomputed artifact" demo must be labelled as such
  (`AUDIT.md` R13).
