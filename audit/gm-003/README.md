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
by the frozen manifest, `world.ensure_registered()` binds nothing under v20, and dispatch would
answer `NOT_IMPLEMENTED` rather than invent a method. The wire bump and the response validation
it enables belong to the integration card, together with the v21 file.

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
