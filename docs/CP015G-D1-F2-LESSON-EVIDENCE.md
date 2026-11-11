# CP-015g/D1-F2 followup — the lesson stage resolves the plan's domain

**Task:** `t_c23d633c` (child of `t_2c045efc`). **Branch:** `wt/cp015g-lesson-domain`, based on the
parent's `wt/cp015g-domain-default` at `e31f3edb`. Unpushed.

## The defect

`t_2c045efc` replaced the plan-stage domain default with one resolver,
`curriculum.resolve_domain(goal, domain, locale)`. `language` stopped being reachable from the
locale alone at plan time. The lesson stage was deliberately out of that boundary and still held the
pre-v10 rule in `policy._normalise_domain(None, locale)`: a declared locale with no declared domain
resolved to `language`.

The CP-015g live flow (`docs/cp015g-d1-f1/run-f1-live-r2.json`) carries `subject_domain: null` on
the course and plan. Its telescope lesson was therefore gated as a language lesson: a section intent
naming listening could declare narration audio, an illustration was read as a "language visual aid",
and the rubric profile could be `language_production`. The course's own records said "default"; the
per-lesson media/rubric policy said "declared language course".

## The decision

One resolver, recorded once, reused by every later stage:

1. **The plan persists its decision.** The plan document stores `domain_provenance` (the resolver's
   `resolved_domain`, `source`, `declared_subject_domain`, `declared_locale`, `target_language`,
   plus `inferred_from`/`note`) beside the declared `subject_domain`.
2. **The later stages reuse it.** `_stage_domain_provenance` reads the stored record;
   `run_lesson_job` and `run_unit_sections_job` pass it to `lesson_capability_plan`. A plan authored
   before the field existed resolves from the course row's own `goal` with the same
   `curriculum.resolve_domain`, so legacy and new plans cannot disagree. Only a record whose
   `source` is one of `policy.DOMAIN_SOURCES` is reused: an H-44-era record stored
   `source: "declared_locale"` and a locale-derived `language`, and reusing it would both resurrect
   the telescope defect and pass a retired source value to the policy. Such a record is discarded
   and re-resolved from the goal (a legacy telescope plan therefore becomes
   `technical_procedure`/`inferred`, and a legacy Spanish plan `language`/`inferred`).
3. **Precedence stays honest.** A domain declared on the section/plan document/dials is `declared`
   and wins (canonicalised by the one alias table). Otherwise the plan's recorded decision is used
   verbatim, and only then does the goal resolve one.
4. **The policy no longer guesses.** `policy._normalise_domain(None, locale)` returns `general`; the
   locale is the delivery language, not the subject. `LessonCapabilityPlan` records
   `subject_domain` and `domain_source`; `to_dict()` and `LESSON_SCHEMA.policy` carry both, as does
   the stored `gen_lessons.policy_json`.
5. **Media follows the resolved domain.** Audio stays refused outside a language lesson. A new,
   narrow `_LANGUAGE_VISUAL` gate refuses an illustration whose construct names a language artefact
   (word card, phrase scene, script chart, pronunciation, script) outside a language course; generic
   context artwork remains optional, so nothing is invented and nothing legitimate is banned. The
   pattern names only language-artefact spellings: a bare "script" (code), "letter" or "word" is
   ordinary technical artwork, and a test pins that a programming lesson may still declare a script
   illustration.
6. **The records agree.** The lesson job result carries `subject_domain`, `domain_source` and the
   full `domain_provenance`; every lesson summary (authored or reused) carries the same pair, and the
   stored policy carries the same values the plan record named.

The unit-sections stage also receives the resolved domain and its source (payload + one instruction
line), and its prompt advances to `unit-sections-prompt.v2`.

## Tests

`tests/test_cp015g_lesson_domain.py` (16 tests):

* an omitted domain is `general` in the policy whatever the locale; a declared domain still wins;
* a CP-015g telescope lesson resolves `technical_procedure`/`inferred`, cannot declare narration
  audio, cannot declare a language visual aid, and is not scored `language_production`; generic
  context artwork is still an optional illustration;
* an inferred language course (named target language + locale) keeps `pronunciation_reference`
  audio, and a declared language course keeps `domain_source=declared`;
* a declared `technical_procedure` course keeps its required schematic;
* a coding lesson may still declare a script illustration (the language-artefact gate is narrow);
* an H-44-era plan document (`source: "declared_locale"`) is not reused: a legacy telescope plan
  gates as `technical_procedure`/`inferred`, a legacy Spanish plan as `language`/`inferred`, and a
  retired source value never reaches `LessonCapabilityPlan` (no `CapabilityPolicyError`);
* the lesson run record, every lesson summary and the stored `policy_json` name the same domain and
  source the plan record did (plan document round-trip asserted too).

Corrected to the new contract (they encoded the old locale-only rule): the `japanese_greeting`
matrix row in `tests/test_policy_integration.py` now declares `subject_domain: language`, and the
two locale-only assertions in `tests/test_policy_threading.py` expect `general`.
`tests/test_capability_policy.py` asserts the mirrored `DOMAIN_SOURCES` cannot drift.

## Verification

| check | result |
|---|---|
| targeted suites (capability policy, policy threading/integration, media plan, CP-015g domain/authoring/lesson, rubrics, generation, blueprint units, check items, media generation, H-192 bounds, text completeness, scope copy, validation shape repair, course-quality media) | 364 tests OK |
| new module | 11 tests OK |
| full suite | `FULL_SUITE_RESULT` |
| docs truth (`scripts/check-docs-truth.py --skip-tests`) | PASS (prompt labels read from the module) |

No provider was called, no network request was made and no data was deleted.
