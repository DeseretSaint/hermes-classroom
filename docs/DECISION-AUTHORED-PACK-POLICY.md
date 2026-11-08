# Authored-pack policy: narration MIME and the teaching minima

**Status:** decided (Atlas, 2026-11-06). Governs `master` @ `adedf47` (CB-011 merged).
**Questions:** t_a356c8a8 (Cinder), follow-up card t_9a7ef546.
**Reproduce:** `python3 scripts/probe-authored-pack-policy.py shipped|one_to_one` (offline; a
throwaway `HERMES_HOME`; only the two LLM seams are faked, exactly as `tests/test_generation.py`
does).

Two questions were asked, and verifying them exposed three defects in the same export path. The
rulings below settle the policy; §3 lists the code that must change before `parent.export` is a
working button rather than a refusal.

## 1. `narration` stays an audio role; roles are permitted, not required

The `role` enum in `cb.pack` is a closed list of **permitted role/MIME pairs**, not a set every
pack must carry. `narration` is an audio role (`coursebook/packs.py:427`): a narration *script* is
text, and text is not a narration artifact.

`parent.export` therefore keeps writing three text files — `parent_guide`, `learner_page`,
`answer_guide` — and the script stays where the approval already binds it:

* the `narration` tab of `parent.blueprint.read`;
* inside the exported parent guide (`## Narration script`);
* inside the approved `content_hash` (the script is one of the four per-section file digests).

When audio exists, the audio artifact takes role `narration` and the script becomes that
artifact's `text_equivalent` — which is precisely why the media rule requires a text equivalent.
A future audio export is a data addition, not a contract change.

**No** `narration_script` role, **no** `cb.pack` revision, **no** `cb.rpc` revision.
`docs/CONTRACTS.md` previously said the export "declares exactly the four roles"; that was wrong
and is corrected in the same commit as this document.

## 2. Generated checks carry three assessment criteria; the pack floor is not lowered

Ruling: **option (a)** of the card. Generation must author at least three rubric criteria per
check; `packs.MIN_RUBRIC_CRITERIA = 3` and the import/export minima stay exactly as they are.

Why the floor belongs where it is: the floor is a property of any pack that leaves Coursebook —
imported, exported, converted — and one policy for all of them is what keeps an authored pack
re-importable. The bundled parent pack already satisfies it
(`bundled/packs/parent-measurement-practice/pack.json` ships three-criterion rubrics next to
two-item plan `evidence_criteria`), so the gap is on the authoring side, not in the policy.

Consequences:

* `_lesson_instructions` (`coursebook/generation.py:787`) asks for 3–6 criteria, each a distinct
  observable aspect of the response; never restatements of one another.
* `enforce_lesson_rules` (`:945`) rejects fewer than three with a typed reason, so attempt 1 is
  retried with targeted feedback and attempt 2 parks the lesson (`needs_review`). Criteria are
  never synthesised to reach the floor.
* `LESSON_PROMPT_VERSION` → `lesson-prompt.v3`; the validation row records the prompt version, so
  the provenance of a changed prompt is visible.
* The exported `checks[].rubric` is composed from **assessment** criteria only: the check's own
  criteria plus the plan's `evidence_criteria`. Supervision notes are safety instructions, already
  rendered in the parent guide; they are not grading criteria and must not appear in a rubric
  (see D2).

Rejected — (b) a parent-observation exemption: an exemption would have to be expressed in the
pack schema and in `cb.projection`, and a converted pack would carry the weak rubric into a graded
recipe. Rejected — (c) a v7 composition rule: how a rubric is composed is an authoring rule, not a
wire shape; nothing on the wire changes.

## 3. Defects found while verifying the export path

The probe runs `parent.brief.create` → plan job → `plan.approve` → lessons job
(`jobs.create {kind:"plan", brief:{stage:"lessons"}}` + `executor.pump_once`) →
`parent.final.approve` → `parent.export`, using the shipped fixtures unchanged in `shipped` mode.

### D1 — `accepted_alternatives` copies the reference answer

`build_pack` (`coursebook/parent_authoring.py:582-584`) writes every `accepted_answers` entry into
`checks[].accepted_alternatives`, including the reference answer, and `validate_minima` refuses a
pack whose check lists its own reference answer as an alternative (`coursebook/packs.py:377-379`).
Every shipped lesson fixture has `accepted_answers == [reference_answer]`
(`tests/fixtures/generation/lesson_ja.json:47-54`), so the export refuses the pack it just built.

Evidence (`one_to_one`, 4 validated lessons, approval `active`):

```
"reason": "export_not_exportable",
"message": "the authored pack is not exportable: pack does not meet the teaching minima:
            check '…' lists its reference answer as an accepted alternative" (×4)
```

Fix: exclude the reference answer (normalised) from `accepted_alternatives` and dedupe.

### D2 — supervision notes counted as rubric criteria

`_check_rubric` (`:493`) appends `notes.supervision_notes` to the rubric. The composed rubric is
`3 = 1 check criterion + 1 plan evidence criterion + 1 safety note`, so the pack's rubric literally
contains "An adult stays within arm's reach for the whole activity". Today the floor is met only by
mislabelling a safety instruction as a grading criterion.

Fix: rubric = check criteria + plan evidence criteria, nothing else.

### D3 — a section covering two objectives yields no section for the second objective

`sections()` (`:337`) labels a composed section with `objective_refs[0]`; `build_pack` (`:531`)
refuses any objective that has no composed section. The shipped parent plan
`tests/fixtures/generation/plan_parent.json` has **2 sections covering 4 objectives**, so the real
pipeline produces two validated lessons, `parent.final.approve` succeeds, and then the export
refuses with `no_generated_content`.

Evidence (`shipped`, 2 validated lessons, approval `active`):

```
"reason": "no_generated_content",
"problems": ["objective … has no generated section", "objective … has no generated section"]
```

The existing export tests cannot see this: `seed_generated_content`
(`tests/test_parent_studio.py:287`) seeds exactly one objective per section.

Fix (ruling): **the objective is the authoring and evidence unit.** `enforce_plan_rules`
(`coursebook/generation.py:845`) must refuse a plan whose section covers anything other than
exactly one objective, or that leaves an objective uncovered, with the reason fed back to the plan
author; the plan instructions say one section per objective; `sections[].objective_refs` becomes
exactly one entry. No `gen_lessons` identity change and no schema migration. `plan_parent.json`
gains two sections (4 objectives, 4 sections).

## 4. Acceptance for the implementation card

1. A new test runs `plan_parent` through the **real** pipeline (executor pump for plan and lessons,
   the unmodified lesson author) → `parent.final.approve` → `parent.export` **succeeds**. No seeded
   staging rows, no padded criteria.
2. Exported `files[].role` == `{parent_guide, learner_page, answer_guide}`; the narration text is
   present in the blueprint `narration` tab and in the parent guide; no pack file claims role
   `narration` with a text MIME.
3. Every exported `checks[].rubric` has ≥3 entries, all sourced from that check or the plan's
   `evidence_criteria`; no supervision text appears in any rubric.
4. No exported `check.accepted_alternatives` contains the check's `reference_answer`.
5. A genuinely short rubric (a lesson stored before this change) still refuses with
   `export_not_exportable` and the named problems: the floor is enforced, not bypassed.
6. `rich_lesson_response` padding is removed from `tests/test_parent_studio.py`; the suite,
   `node --check desktop/plugin.js`, `hermes plugins validate .` and the probe script all pass.

## 5. Not changed

`contracts/pack-manifest.v1.json`, `contracts/rpc.v6.json`, `contracts/db.v3.json`,
`contracts/projection.v1.json`, `MIN_RUBRIC_CRITERIA`, the `parent.export` response shape, and the
blueprint's four tabs. The `parent_export_status.blocked_reason` enum stays the four gates it
documents; `export_not_exportable` remains a refusal reason on `parent.export` itself, and after
D1–D3 a course that has real generated content no longer reaches it.
