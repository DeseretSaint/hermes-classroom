# GM-003 evidence

Branch: `wt/gm-003-world` (rebased on `origin/master` `5721389`, which carries GM-001 `4e3d6c6`,
migration 0013 and the published `rpc.v21.json`; no master merge, no push, no gateway restart).

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
| **G2** free-text `tone`/`audience` bypassed the fence | Both fields are scanned against other grammars' vocabulary and refused `POLICY_VIOLATION reason=presentation_names_foreign_grammar` with the offending field and phrase, before spend. **Correction (round 5):** this was phrase-exact and was bypassed by a paraphrase; it is superseded by the token-level + mood-lexicon fence described below | `test_technical_world_rejects_scene_text_in_tone_or_audience` |
| **G3** (should-fix) README overclaimed that rule 2 held at runtime; the anti-generic test only saw fixtures | Claim corrected in this section; `test_world_style_swap_rejects_generic_art`'s generated-brief counterpart now asserts through the handler path that the stored brief keeps the field-atlas cues and yields no `anti_generic_problems` against the head-gasket brief | `test_world_cache_prevents_duplicate_spend` (generated-brief assertions) |
| **G4** (should-fix) derived objective titles were subject to the ownership fence | The ownership and anti-generic fences now inspect the caller's `brief_patch` only; derived course content (objective titles promoted into motifs) is not re-fenced as if it were a presentation patch | `test_derived_objective_titles_are_not_presentation_fenced` |

The anti-generic runtime invariant is a majority/at-least-two rule over normalized grammar
vocabulary, not a second copy of `anti_generic_problems()`: the swap test compares two chosen
briefs, while generation only has one brief and must judge the patched motif mix. `four-cylinder
block` / `engine block cutaway` remains a legitimate workshop patch.

**Correction (round 5):** the paragraph above described the round-4 threshold, which was
`non_native <= native`. That was looser than `anti_generic_problems()` (which fails at **two**
shared motifs), so two paraphrased decorative motifs passed. The shipped rule is now
`non_native < 2` on the caller's patch, for **every** grammar including the default
`field_atlas`.

## Review round 5 — sentinel changes requested (H1–H6)

Round 5 reproduced F2 and the exact G1/G2 repros as fixed, then found four blockers inside the
same card rule (`head gasket is a service bay/workshop manual, never a lantern district`) plus
two should-fix defects. All six are fixed in this branch, tests first.

Red evidence: `audit/gm-003/red-attempt5.txt` (5 tests, 9 subtest failures — every case
"world.generate unexpectedly succeeded", i.e. the fence was absent). Green:
`audit/gm-003/green-attempt5.txt` (27 OK) and the full-suite log named below.

| Defect | Fix | Regression test |
|---|---|---|
| **H1** rule-2 fence skipped for the default grammar (`field_atlas`), so a language course could be patched into a service bay | the presentation-motif fence now runs for **every** grammar, judging the caller's `brief_patch` plus the native top-up (derived titles stay exempt, G4) | `test_default_grammar_patch_cannot_smuggle_foreign_motifs` |
| **H2** two paraphrased decorative motifs (`non_native == native == 2`) were accepted on concepts and kit | the patch threshold is `non_native < 2`: one genuine subject addition is allowed, two non-native motifs is already the generic swap `anti_generic_problems()` rejects. Motif ownership is now token-level, so a paraphrase that borrows another grammar's distinctive token (`paper lanterns`, `izakaya counter`) is refused `motif_not_in_grammar` before spend | `test_technical_world_rejects_two_paraphrased_decorative_motifs` |
| **H3** presentation text was phrase-exact, so `paper lanterns and izakaya counters under night-market neon` / `regulars at a sake bar` reached the prompt | `tone` and `audience` are validated against a closed **mood/role lexicon** and refused when they use another grammar's distinctive token; unknown words are refused `presentation_text_not_mood_vocabulary` rather than interpolated. This replaces the phrase-exact scan | `test_technical_world_rejects_paraphrased_scene_text` |
| **H4** free text could put `90 ft-lb`, a part number or an answer-key instruction into the plate request | a digit/unit/instruction fence refuses `POLICY_VIOLATION reason=presentation_names_number_or_answer_content` for `tone`, `audience` **and** `forbidden` entries before spend. A "motif to avoid" may still name a scene (F2's `forbidden: ['lantern district']` is legal) | `test_presentation_text_cannot_name_numbers_or_answer_content` |
| **H5** (should-fix) `level` was accepted and hashed in the cache key but never rendered | `level` is no longer a `brief_patch` field: a learner-level change is a course mutation, so a level-only patch is refused `VALIDATION_FAILED` before spend instead of buying identical plates under a new key | `test_level_patch_changes_the_plate_or_is_refused` |
| **H6** (should-fix) README overclaimed the round-4 fences | this section and the corrections above; the explicit shipped rules are `non_native < 2` for motifs, a mood/role lexicon for text, and number/unit/instruction refusal | — |

What the shipped fence does and does not claim:

- It runs on the **caller's** presentation patch, for every grammar, before any world row, job
  or provider call, on both `concepts` and `kit`.
- It refuses a motif set with two or more non-native motifs, and any motif/text that borrows
  another grammar's distinctive vocabulary token.
- It refuses digits, units and label/answer instructions in `tone`, `audience`, `forbidden`
  **and caller-supplied `motifs`**, before any world row, job or provider call.
- It never promotes an approved objective title carrying a torque value, unit, part number or
  answer instruction into a motif; the grammar's own cues carry the scene instead.
- For a course whose own title/goal contains such text (a legitimate title may contain digits,
  e.g. `Japanese 101`), the course is **not refused**. The plate prompt substitutes the grammar
  label for the subject and omits the capability clause; the persisted `WorldBrief` keeps the
  verbatim course strings, so this is prompt-local and not a cache-key change.
- It accepts one genuine subject-specific motif (`four-cylinder block`) and mood/role text
  (`practical, calm, cold overhead light`, `apprentice technicians`). It does not claim to be a
  semantic classifier; a word that is neither another grammar's vocabulary nor in the mood
  lexicon is refused rather than silently dropped.

## Review round 6 — sentinel changes requested (I1, I2, S1–S3)

Round 6 confirmed H1–H5 fixed and found the same orientation-only rule still reachable through
two unscanned free-text paths. All three defects and both should-fix items are fixed here,
tests first.

Red evidence: `audit/gm-003/red-attempt6.txt` (4 tests, 10 subtest failures, every case
"world.generate unexpectedly succeeded" or the wrong error code). Green:
`audit/gm-003/green-attempt6.txt` (4 OK), then `audit/gm-003/full-attempt6.log`.

| Defect | Fix | Regression test |
|---|---|---|
| **I1a** caller `brief_patch.motifs` reached the prompt with `answer key 1-2-3-4`, `part number 8AB`, `torque sequence 90 ft-lb` | `presentation_motif_problems()` content-scans every caller motif with `_names_numbers_or_answer_content()` **before** the native/non-native count and refuses `POLICY_VIOLATION reason=presentation_names_number_or_answer_content` (field `motifs`) before spend | `test_presentation_motifs_cannot_name_numbers_or_answer_content` |
| **I1b** a promoted objective title (`Torque sequence 90 ft-lb`) became a positive motif | `_derive_brief()` promotes a title only when it does not name a number/unit/instruction; grammar cues still carry the scene | `test_technical_world_never_carries_torque_or_sequence` (plan §10C name) |
| **I2** derived course `title`/`goal` were interpolated verbatim, so a course created elsewhere could inject `90 ft-lb` / `answer key` without any patch | `build_prompt()` sanitises only the prompt text: the subject falls back to the grammar label and the capability clause is omitted when `_names_numbers_or_answer_content()` matches. The course is accepted and the stored brief stays verbatim | `test_course_subject_text_cannot_name_numbers_or_answer_content` |
| **S2** a bare-string `forbidden` was iterated per character | the handler requires a list/tuple of strings and refuses `VALIDATION_FAILED` (field `forbidden`) before spend | `test_forbidden_patch_must_be_a_list` |
| **S3** README/cost note did not state the residual paths | this section and the bullets above; `docs/GM-003-WORLD-COST.md` records the round-6 fence cost | — |

