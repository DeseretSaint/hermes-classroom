# GM-003 evidence

Branch: `wt/gm-003-world` (based on `master` at 5673047 plus merged parent `wt/gm-001-contract`
at 4e3d6c6; no master merge, no push, no gateway restart).

## Named tests

Command: `python3 -m unittest tests.test_world -v`

Required names and where they live:

| Required test | Test class |
|---|---|
| `test_world_grammar_deterministic` | `WorldPolicyTest` |
| `test_head_gasket_never_field_atlas` | `WorldPolicyTest` |
| `test_world_style_swap_rejects_generic_art` | `WorldPolicyTest` |
| `test_world_prompts_are_textless` | `WorldPromptTest` |
| `test_world_cache_prevents_duplicate_spend` | `WorldMediaJobTest` |
| `test_partial_world_failure_names_missing_roles` | `WorldFailureAndModeTest` |
| `test_textbook_generates_no_world_job` | `WorldFailureAndModeTest` |
| `test_world_approval_hash_fence` | `WorldFailureAndModeTest` |

Extra proof: `test_world_methods_are_wired_to_the_frozen_manifest` asserts the four handler names
are exactly the frozen `GM_RPC_METHODS` subset and that registration is still fenced by `cb.rpc`
v20 (see below).

## Files

- `coursebook/world.py` — policy, grammar table, textless prompt builder, cache key, media seam,
  concept/kit job stages, `world.*` handlers, registration fence.
- `coursebook/domain.py` — imports the world handlers into the kernel registry.
- `coursebook/executor.py` — registers the `kind=media` world resolver in the job pump.
- `tests/test_world.py`, `tests/world_fixtures.py` — Japanese L0, head gasket, generic swap.
- `docs/GM-003-WORLD-COST.md` — call accounting, labelled latency/price estimate, failure rules.

## Contract decision

The four wire methods are frozen in `docs/GM-CONTRACT.md` §8 / `coursebook/gm_contract.py`, and
`cb.rpc` v20 does not contain them. GM-001 §1 says the first implementation card may bump
`cb.rpc`, while this card's own instructions say **do not edit the migration or the shared
contract manifest**. This build therefore keeps the intended fence: handlers exist and are keyed
by the frozen manifest, `world.ensure_registered()` binds nothing under v20, and dispatch answers
`VALIDATION_FAILED: 'world.read' is not one of [...]` rather than inventing a method. The wire
bump and the response validation it enables belong to the integration card, together with the v21
file.

This is deliberate, not an omission: it avoids rewriting the ten historical contract-immutability
tests and avoids racing GM-002/GM-005/GM-009, which are parallel backend cards that would each
otherwise need the same single manifest bump.

## Review round 2 — sentinel changes requested (D1–D4)

Reviewer verdict on `f1adddc` reproduced two blockers and two should-fix defects; all four are
fixed in this branch with failing tests written first.

| Defect | Fix | Regression test |
|---|---|---|
| **D1** concept-stage provider failure left `course_worlds.state='concepts_generating'` with `error:null` | `_concept_stage` now catches `WorldMediaFailure` per board, keeps the boards that succeeded, writes `state='failed'` with `{'reason':'provider_unavailable','missing_roles':['style_board:<direction>',…]}`, then re-raises | `test_concept_failure_leaves_named_terminal_state` |
| **D2** `brief_patch` could override `subject_domain`/`end_capability`/`safety_class`, turning a head-gasket course into a field atlas | `_merged_brief` always re-derives classification, title and sections from the course row; `brief_patch` is a closed whitelist (`tone`, `motifs`, `forbidden`, `audience`, `level`) and any classification key is refused `VALIDATION_FAILED` before spend | `test_brief_patch_cannot_reclassify_a_technical_course` |
| **D3** (should-fix) kit was accepted at `concepts_ready` with no style approval | kit requires `selected_concept_id == style_id` and state in `style_selected`/`kit_generating`/`failed`; a failed kit retry keeps its selection | `test_kit_requires_an_approved_style` |
| **D4** (should-fix) `trades` selected `workshop_manual` but could be forced to `field_atlas` | the technical fence derives from the *selected grammar*, not the keyword list | `test_head_gasket_never_field_atlas` (trades case) |

The technical fixture now comes from `course.create(subject_domain='technical_procedure',
goal='Replace a head gasket on a four-cylinder engine')` with real objectives, not a patch on a
braising course. The concept failure test proves no fabricated asset is written.

Red-then-green evidence: `audit/gm-003/red-attempt2.txt` (4 failures for the intended reasons)
and `audit/gm-003/green-attempt2.txt` (13 OK).

## TDD trail

Each slice was written as a failing test first and observed red before implementation:
import error (`coursebook.world` absent) → policy green; `AttributeError: build_prompt` → prompt
builder green; `AttributeError: bind_media`/`cache_key` → job green; missing
`world_job_on_create` and an empty-assets failure → partial/mode green; a stale-revision failure
in the approval test was fixed as a test bug (the snapshot predated the style approval), then green.

Round 2 followed the same cycle: the four new assertions were run against `f1adddc` and failed
(concepts stuck `concepts_generating`; reclassification patch "unexpectedly succeeded"; kit queued
at `concepts_ready`; trades forced into `field_atlas` with no violation) before any production
edit. Only then were `_concept_stage`, `_merged_brief`, the patch whitelist and the kit gate
changed.

## Review round 3 — sentinel changes requested (F1–F5)

Round 3 verified D1–D4 fixed and found two blockers plus three should-fix defects. All five are
fixed in this branch, tests first. Red evidence: `audit/gm-003/red-attempt3.txt` (6 failures for
the intended reasons); green: `audit/gm-003/green-attempt3.txt` (19 OK).

| Defect | Fix | Regression test |
|---|---|---|
| **F1** a head-gasket course could be turned into the lantern district through `brief_patch.motifs` | `foreign_grammar_motifs()` maps each motif to the grammar(s) that author it; a motif owned by another art direction is refused `POLICY_VIOLATION reason=motif_not_in_grammar` before any row, job or spend. `_merged_brief` also tops a patched motif set back up to at least two grammar-native cues (plan §4.4 rule 2) while keeping subject-specific additions | `test_technical_world_rejects_decorative_motif_patch` |
| **F2** `forbidden` changed the prompt but not the cache key or style hash | `cache_key()` intent now includes `forbidden`, `tone` and `audience`; a style board's `prompt_hash` is computed over its full identity (base prompt hash incl. negative, direction id, rendered prompt, negative prompt) | `test_world_forbidden_changes_cache_identity` |
| **F3** (should-fix) `tone`/`audience` were accepted but never reached the prompt | both are rendered into the prompt body and the prompt payload, so they change the plate and the cache identity | `test_presentation_fields_reach_the_prompt` |
| **F4** (should-fix) workshop section prompts embedded procedure titles | `build_prompt` renders a workshop section as "place and mood only, no procedure, sequence or tool action depicted"; field-atlas sections keep their human titles | `test_workshop_section_prompts_have_no_procedure_title` |
| **F5** (should-fix) a `trades` course derived `safety_class='none'` and lost the workshop hard negatives | `_derive_brief` derives safety from the selected grammar, and `build_prompt` enables service negatives from the grammar as well as the brief | `test_trades_world_keeps_workshop_negatives`, `test_trades_course_derives_service_safety_from_grammar` |

The F1 fence is symmetric for *exact* vocabulary: a language course patched with `service bay` /
`torque wrench` is refused by the same ownership check. Exact vocabulary alone is not the whole
of rule 2, which is why review round 4 added the runtime invariant described below.

## Review round 4 — sentinel changes requested (G1–G4)

Round 4 reproduced F2–F5 fixed, but showed that F1 only matched exact authored vocabulary: a
head-gasket course patched with paraphrases (`paper lanterns`, `izakaya counter`, `night market`)
was accepted and spent 3 provider calls, and free-text `tone`/`audience` carried the same scene
into every prompt. Both are fixed with tests first. Red evidence:
`audit/gm-003/red-attempt4.txt` (6 failures + 1 error, all for the intended reasons); green:
`audit/gm-003/green-attempt4.txt` (22 OK).

| Defect | Fix | Regression test |
|---|---|---|
| **G1** paraphrased decorative motifs still turned a head gasket into a lantern district | The runtime form of plan §4.4 rule 2 now runs on the merged brief before any row, job or spend: a patched motif set must keep at least two grammar-native subject cues, and other-subject motifs may never outnumber them (`POLICY_VIOLATION reason=presentation_motifs_not_subject_specific`). Native cues are also sorted ahead of caller additions, so a decorative cluster cannot lead the scene. Applies to both `concepts` and `kit` | `test_technical_world_rejects_paraphrased_decorative_motifs` |
| **G2** free-text `tone`/`audience` bypassed the fence | Both fields are scanned with the case/plural-normalised foreign-vocabulary check and refused `POLICY_VIOLATION reason=presentation_names_foreign_grammar` with the offending field and phrase, before spend | `test_technical_world_rejects_scene_text_in_tone_or_audience` |
| **G3** (should-fix) README overclaimed that rule 2 held at runtime; the anti-generic test only saw fixtures | Claim corrected in this section; `test_world_style_swap_rejects_generic_art`'s generated-brief counterpart now asserts through the handler path that the stored brief keeps the field-atlas cues and yields no `anti_generic_problems` against the head-gasket brief | `test_world_cache_prevents_duplicate_spend` (generated-brief assertions) |
| **G4** (should-fix) derived objective titles were subject to the ownership fence | The ownership and anti-generic fences now inspect the caller's `brief_patch` only; derived course content (objective titles promoted into motifs) is not re-fenced as if it were a presentation patch | `test_derived_objective_titles_are_not_presentation_fenced` |

The anti-generic runtime invariant is a majority/at-least-two rule over normalized grammar
vocabulary, not a second copy of `anti_generic_problems()`: the swap test compares two chosen
briefs, while generation only has one brief and must judge the patched motif mix. `four-cylinder
block` / `engine block cutaway` remains a legitimate workshop patch.
