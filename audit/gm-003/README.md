# GM-003 evidence

Branch: `wt/gm-003-world` (rebased on `origin/master` `e1f8e6e`, which carries GM-001 `4e3d6c6`,
migration 0013, the published `rpc.v21.json`/`rpc.v22.json`/`rpc.v23.json`, GM-014's print
fixtures and the GM-002/GM-005/GM-011 visual/take-home/tutor merges; no master merge, no
push, no gateway restart, no manifest/contract/migration edit on this branch).

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

**Update (round 11):** the rebased base `e1f8e6e` publishes `rpc.v23.json` (GM-005's
take-home methods), but it still carries no `world.*` entry. The four world methods
therefore remain keyed by the frozen GM manifest and non-dispatchable; the additive `world.*`
entries plus the `coursebook/contracts.py` bump remain the integration card's work. This branch
does not edit `contracts/*.json`.

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

## Review round 7 — sentinel changes requested (J1–J3, S7)

Round 7 confirmed I1a, I2 and S2 fixed and found three remaining ways the orientation-only rule
could be reached through course text that no presentation field guards. All three are fixed
here, tests first.

Red evidence: `audit/gm-003/red-attempt7.txt` (3 tests, 9 failures: six procedure motifs accepted
and spent, a field-atlas section title with digits in the plate prompt, and `lantern district`
in a workshop prompt). Green: `audit/gm-003/green-attempt7.txt` (3 OK), then
`audit/gm-003/test_world-attempt7.txt` (34 OK) and `audit/gm-003/full-attempt7.log`.

| Defect | Fix | Regression test |
|---|---|---|
| **J1** caller motifs accepted imperative procedure phrasing and spelled-out values (`remove the intake manifold`, `drain the coolant`, `lift the cylinder head straight up`, `tighten to seventy five`, `turn another quarter`, `hand tight plus a quarter turn`) | `presentation_motif_problems()` now runs `_names_procedure_or_spelled_value()` after the digit/unit/instruction scan and refuses `POLICY_VIOLATION reason=presentation_names_procedure_or_value` (field `motifs`) before spend. The check is verb-initial, so the native place cue `car on a lift` stays legal, and a hyphenated compound (`four-cylinder block`) is a descriptive, not a value | `test_presentation_motifs_cannot_name_a_procedure_or_spelled_out_value` |
| **J2** field-atlas section titles were interpolated unscanned into section plate prompts (`Section scene … about Answer key 1-2-3-4`) | `build_prompt()` drops an unsafe section title (number/answer instruction, procedure phrasing, or another art direction's scene); the scene falls back to the grammar's place cues and the UI supplies the real typed title | `test_section_titles_cannot_name_numbers_or_answer_content` |
| **J3** a workshop course title alone reached every prompt as `Course subject: A lantern district at night` | the prompt subject (and capability clause) falls back to the grammar label when the course text uses another grammar's distinctive vocabulary, exactly as I2 already does for numbers. Prompt-local: the persisted brief stays verbatim and the cache key is unchanged | `test_workshop_subject_title_cannot_name_a_foreign_scene` |
| **S7** (should-fix) README header named an old base and did not state the round-6 residual paths | header corrected to `d70ceb9`; this section records the shipped fences and the known gaps below | — |

What this round does and does not claim:

- The fenced paths are: caller `brief_patch.motifs`, promoted objective titles, derived
  `title`/`goal` used as prompt subject/capability, and section titles on a non-workshop grammar.
- The text scans are token-level heuristics, not a semantic classifier. A procedure phrased
  without a verb-initial imperative and without a digit/unit/spelled value (for example a bare
  noun phrase such as `valve clearance table`) is not detected; the workshop grammar's hard
  negatives still forbid a depicted procedure, torque value, sequence or measurement.
- A section title is only dropped from the *prompt*; the section card still carries the real
  typed title from the UI, which the image never supplies.
- Known gaps unchanged: `cb.rpc` v20 does not dispatch `world.*` (additive v22 belongs to the
  integration card), the media seam is a deterministic fake (no live provider call), the
  `world_assets` role vocabulary follows the frozen 0013 CHECK, and create-time auto-queue is
  owned by GM-002.

## Review round 8 — supervisor directive: close the class, not the strings

Rounds 3–7 each closed the interpolation sentinel named and the next round found a neighbouring
one (I2 → J1 motifs → J2 section titles → J3 course title), and the round-7 forbidden item still
carried a foreign scene into the prompt's hard negatives. Round 8 replaces the per-field
`if` checks with one predicate applied at every site.

**Shape**

- `_plate_text_problems(value, grammar)` is the single predicate: digits/units/answer/instruction
  vocabulary (`answer`, `key`, `solution`, `ignore`, `instead`, `textless`, …), spelled-out
  quantities (`one`…`ninety`, `half`, `quarter`, `dozen`), verb-initial procedure phrasing, and
  another grammar's distinctive vocabulary. It returns stable reason ids, not prose.
  **Correction (round 9):** round 8 exempted *every* hyphenated spelled token, not just
  `four-cylinder`; that is fixed below, and only a number+noun descriptive compound is exempt.
- `_plate_safe(value, grammar, fallback=…)` is the only way `build_prompt()` interpolates text.
  It is called for **subject** (fallback `record.label`), **capability** (omitted),
  **each motif** (unsafe motif dropped, grammar cues carry the scene), **tone**/**audience**
  (neutral mood/role fallback) and **section title** (dropped; the UI supplies the real type).
  Forbidden items go through the same predicate into the negative prompt.
- `presentation_motif_problems()`, `presentation_text_problems()` and
  `forbidden_presentation_problems()` all call `_plate_text_problems()`, so the patch refusal and
  the prompt cannot disagree by construction. A "motif to avoid" may name *this* world's own
  scene (F2's `forbidden: ['lantern district']` on a field atlas is still legal) but not another
  art direction's scene, a value, a procedure or an answer instruction.
- Stored brief, cache key and `prompt_hash` semantics are unchanged: the fence is prompt-local.

**Class-closing test** `test_every_free_text_field_is_fenced_at_the_prompt` walks every
free-text field of `WorldBrief` (title, goal, section titles ×3, motifs, tone, audience,
forbidden) with one hostile value per category (digit, spelled-out number, procedure verb,
"answer key", foreign grammar word, "ignore the textless rule"), for **every grammar** and every
prompt role (style board/hero/cover/section), and asserts no prompt or negative carries the
hostile text while the persisted brief stays verbatim.

Red evidence `audit/gm-003/red-attempt8.txt` was captured by running the new test against
`HEAD:coursebook/world.py` (pre-round-8): hostile text reaches the plate for all six categories on
every grammar. Green: `audit/gm-003/green-attempt8.txt` (1 OK), regression set 294 OK
(`regression-attempt8.txt`), full suite in `full-attempt8.log`.

Residual paths (out of scope for this card per the supervisor's freeze): token-level heuristics
are not a semantic classifier, so a procedure phrased as a bare noun phrase with no digit, unit,
spelled quantity or verb-initial imperative is not detected; the workshop grammar's hard negatives
still forbid depicted procedures, torque values, sequences and measurements. A genuinely new
surface (new field, role or grammar) is a follow-up card.

## Review round 9 — sentinel K1: hyphenation must not shelter a value

Round 8's class-closing fence was correct in shape but the `four-cylinder` carve-out was matched
on the *raw string* (`token-` / `-token`), so any hyphenated spelled token was exempt. K1 showed
the J1 sequence step and a spelled value passing with one character changed
(`spec is seventy-five`, `hand tight plus a quarter-turn`), and the same root let a course titled
`Seventy-five` reach every plate.

**Fix (tests first)**

- `_descriptive_number_compound()` is the narrow carve-out: exactly two parts, a spelled number
  followed by a plain noun (`four-cylinder`, `two-stroke`). A number followed by another number
  (`seventy-five`) or a quantity word (`quarter-turn`, `half-inch`, `dozen-count`) is not
  exempt. `_QUANTITY_COMPOUND_TOKENS` names the quantity heads.
- `_names_procedure_or_spelled_value()` re-scans hyphen-aware units (`_HYPHEN_COMPOUND_UNIT`), so a
  spelled token is refused when any occurrence is exposed outside a legal descriptive compound.
  The predicate is unchanged in place, so `_plate_text_problems()`, the prompt gate and every
  patch refusal inherit the fix.
- The mood/role lexicon now treats function words (`and`, `at`, `with`, …) as neutral: round 8
  refused `calm and precise` with `presentation_text_not_mood_vocabulary` because `and` was
  unknown. Adjectives still have to be in the lexicon and another grammar's scene words are
  still refused.

**Tests** — `test_presentation_motifs_cannot_hyphenate_a_value_or_sequence` covers concepts and the
approved-style kit path (0 spend), keeps `four-cylinder block` legal, and asserts a course titled
`Seventy-five` with goal `Learn the value seventy-five` falls back to the grammar label at the
prompt while the stored brief stays verbatim. The class-closing table gains a `hyphen` category
(`hand tight plus a quarter-turn`) and `test_presentation_text_allows_function_words` covers S9.

Red evidence: `audit/gm-003/red-attempt9.txt` (12 failures + 1 error against pre-round-9
`coursebook/world.py`, every case hostile text present or the tone conjunction refused). Green:
`audit/gm-003/green-attempt9.txt` (3 OK), `audit/gm-003/test_world-attempt9.txt` (37 OK),
regression set 301 OK (`regression-attempt9.txt`), full suite 2898 OK (skipped=1), exit 0, on the
rebased base `7553925` (`full-attempt9.log`).

Residual paths are unchanged from round 8: token-level heuristics are not a semantic classifier,
and a procedure phrased as a bare noun phrase with no digit, unit, spelled quantity, hyphenated
value or procedure verb is not detected. The workshop hard negatives remain the second line of
defence. **Correction (round 10):** this paragraph previously implied only bare-noun procedures
escaped; in fact round 9 still accepted verb-initial imperatives with a frozen verb when a
leading discourse word preceded it (`First, remove the intake manifold`). That is fixed in
round 10 below.



## Review round 10 — sentinel L1/L2: leading word and fraction

Round 9 fixed the hyphen carve-out but two paths still reached the plate through the same
predicate, both reachable **with no `brief_patch` at all**.

**L1 — one leading word restored a frozen imperative.** `_names_procedure_or_spelled_value()`
ended with `tokens[0] in _PROCEDURE_VERB_TOKENS`, so `First, remove the intake manifold`,
`Then drain the coolant`, `Open the hood`, `Release the fuel pressure`, `Raise the vehicle on the
hoist` and `Seat the gasket on the block` were accepted on concepts (3 calls) and the
approved-style kit path (4 calls); a course titled `First, remove the intake manifold` leaked into
3/3 prompts.

Fix, inside the shared predicate so every call site inherits it:

- leading discourse words (`first`, `then`, `next`, `now`, `finally`, `also`, `carefully`,
  `before`, `after`, …) are skipped before the verb-initial test;
- the procedure verb set gains the missing imperatives (`open`, `close`, `release`, `raise`,
  `lower`, `seat`, `place`, `position`, `route`, `mark`, `tag`, `hold`, `support`, `clamp`, `pry`,
  `jack`, `spray`, `soak`, `check`, `verify`, `ensure`);
- a procedure verb followed by a determiner (`remove **the** manifold`) is refused wherever it
  sits, and gerund forms (`removing`, `installing`) resolve to the same verb set. The native
  place cue `car on a lift` stays legal because its noun is not followed by a determiner, and
  `four-cylinder block` / `two-stroke engine` remain legal.

**L2 — `two-thirds` survived the carve-out.** `_descriptive_number_compound()` compared the raw
tail, and `thirds` is not the singular `third`, so a fraction read as a number+noun compound.
`_singular_compound_tail()` now singularises the tail (with `halves`→`half`) and
`_QUANTITY_COMPOUND_TOKENS` lists the ordinals (`third`, `fifth`, …, `twelfth`, `percent`), so
`two-thirds`, `two-fifths`, `three-quarters` and `two-percent` are refused.

**Tests** — `test_presentation_motifs_with_a_leading_word_still_name_a_procedure` (concepts and
approved-style kit, 0 spend), `test_presentation_motifs_cannot_hyphenate_a_fraction` (concepts and
kit, 0 spend, `four-cylinder block` still legal), and
`test_course_title_with_a_leading_word_cannot_carry_a_procedure` (title-only repro: 3 calls, no
`intake manifold` in any prompt, `Workshop manual` fallback, stored brief verbatim). The
class-closing table gains `leading` and `fraction` categories.

Red evidence: `audit/gm-003/red-attempt10.txt` (4 tests, 28 subtest failures — every bypass
accepted or hostile text present, the intended reasons). Green:
`audit/gm-003/green-attempt10.txt` (4 OK), `test_world-attempt10.txt` (40 OK), regression set
304 OK (`regression-attempt10.txt`), predicate probe `predicate-attempt10.txt` (every L1/L2 string
refused, the native carve-outs allowed), full suite in `full-attempt10.log`.

**Residual paths (unchanged):** token-level heuristics, not a semantic classifier. A procedure
phrased as a bare noun phrase with no digit, unit, spelled quantity, fraction or procedure verb
(`valve clearance table`) is not detected; the workshop hard negatives remain the second line of
defence. `world.*` is still absent from the published `rpc.v22.json`, so registration stays fenced
and non-dispatchable (additive integration bump); the media seam is a deterministic fake; the
`world_assets` role vocabulary follows the frozen 0013 CHECK; create-time auto-queue is owned by
GM-002.

## Review round 11 — sentinel M1: a frozen verb that is also a scene word

Round 10 closed L1/L2, but sentinel found that `clean` — one of the eleven verbs in the
supervisor's own round-7 frozen §4.4 rule-5 list — was absent from `_PROCEDURE_VERB_TOKENS`, so
`_plate_text_problems('Clean the head', 'workshop_manual')` returned `()` and a real head-gasket
course patched with `motifs=['Clean the head']` was accepted (3 provider calls, stored, in 3/3
prompts; the approved-style kit path accepted it too, 4 calls). A course titled `Clean the head`
and a goal `Clean the head and refill the coolant` leaked the same way with no patch. Auditing the
frozen list also found `disconnect` missing, and the ambiguous verbs `refill`/`break`/`polish`
unfenced.

**Fix (tests first)**

- `disconnect` joins `_PROCEDURE_VERB_TOKENS` (unambiguous imperative).
- `_DETERMINER_ONLY_PROCEDURE_VERBS = {break, clean, polish, refill}` is the second half of the
  vocabulary: these are ordinary scene words (`clean service bay`, `break room`, `polish rag`,
  `refill station`), so they are not refused by the unambiguous verb-initial test. They are
  refused when they take an object: verb-initial with a bare object (`Clean head`, `Refill
  coolant`, `Polish lens`, `Break seal`) or anywhere with a determiner (`clean the head`). A
  verb-initial use stays legal only when the phrase names a selected-grammar scene cue
  (`clean service bay`). (Round 12 corrected this: the round-11 implementation required a
  determiner, so bare-object imperatives passed — see the round-12 section below.)
- `_procedure_verb_base(token, verbs=...)` now accepts the vocabulary to resolve against; the
  verb-initial test passes `_PROCEDURE_VERB_TOKENS` and the anywhere-in-phrase determiner test
  uses the default (both sets). Gerund resolution (`cleaning`, `disconnecting`) inherits the same
  sets. Because this lives inside `_names_procedure_or_spelled_value()`, every `_plate_safe()`
  site and every patch refusal inherit it with no other change.

**Tests** — `test_presentation_motifs_cannot_name_a_frozen_procedure_verb` iterates the whole
`FROZEN_PROCEDURE_VERBS` list (the eleven frozen verbs plus the three audited omissions) on
concepts and on the approved-style kit path (0 spend), and keeps `clean service bay` legal
(3 calls). `test_title_or_goal_cannot_name_a_frozen_procedure_verb` covers the title-only repro
(`Clean the head` → `Workshop manual` fallback, no `clean the` in 3/3 prompts, stored brief
verbatim) and the goal-only repro (`Disconnect the battery` → capability clause omitted, stored
`end_capability` verbatim). The class-closing table now walks the **whole** frozen verb list
(`procedure:<verb>` categories × every grammar × every prompt role) instead of one representative
string.

Red evidence: `audit/gm-003/red-attempt11.txt` (3 tests, 12 intended failures — five frozen verbs
accepted by the handler, the title leak, and five `procedure:<verb>` class-table categories).
Green: `audit/gm-003/green-attempt11.txt` (3 OK), `test_world-attempt11.txt` (42 OK), regression
set 317 OK (`regression-attempt11.txt`), predicate probe `predicate-attempt11.txt` (all fourteen
verbs refused with an object; the native scenes allowed), full suite 2942 OK (skipped=1), exit 0
(`full-attempt11.log`, 664.710s).

**Residual paths (unchanged):** token-level heuristics, not a semantic classifier; a procedure
phrased as a bare noun phrase with no digit, unit, spelled quantity, fraction or procedure verb
(`valve clearance table`) is not detected, and the workshop hard negatives remain the second line
of defence. `world.*` is still absent from the published `rpc.v23.json`, so registration stays
fenced and non-dispatchable (additive integration bump); the media seam is a deterministic fake;
the `world_assets` role vocabulary follows the frozen 0013 CHECK; create-time auto-queue is owned
by GM-002.

## Review round 12 — sentinel N1: a bare object sheltered the ambiguous verbs

Round 11 fenced `clean`/`break`/`polish`/`refill` only when a determiner followed the verb, so the
imperative shape without an article — `Clean head`, `Refill coolant`, `Polish lens`, `Break seal`,
`Then clean head` — was accepted on concepts (3 provider calls, stored, in 3/3 prompts) and on the
approved-style kit path (2 new calls, 2/2 kit prompts). A course titled `Clean head` with no patch
leaked verbatim into 3/3 prompts.

**Fix (tests first), closing the shape rather than the string**

- `_verb_initial_bare_object(value)` — the phrase opens (after leading discourse words) with a
  verb from `_DETERMINER_ONLY_PROCEDURE_VERBS`.
- `_names_grammar_owned_scene(value, grammar)` — the phrase contains a selected grammar's authored
  motif as a contiguous token run.
- `_plate_text_problems(value, grammar)` refuses `presentation_names_procedure_or_value` for a
  verb-initial bare object **unless** the grammar owns a scene phrase in it, so `clean service bay`
  stays legal while `Clean head` is refused. Both the patch refusal
  (`presentation_motif_problems`) and every `_plate_safe()` prompt site share this predicate.
- The class-closing table now walks the **whole** frozen verb list × {determiner form
  (`<verb> the component`), bare-object form (`<verb> component`), leading-adverb form (`Then
  <verb> component`)} for every grammar, field and prompt role, so a future omission cannot pass.

**Tests** — `test_presentation_motifs_cannot_name_a_bare_object_procedure` (five bare-object
motifs refused on concepts and the approved-style kit, 0 rows / 0 jobs / 0 calls, `clean service
bay` still spends 3) and `test_title_or_goal_cannot_name_a_bare_object_procedure` (title-only
`Clean head` and goal-only `Refill coolant` fall back / omit in 3/3 prompts, stored brief
verbatim). Red: `audit/gm-003/red-attempt12.txt` (3 tests, 15 intended failures). Green:
`audit/gm-003/green-attempt12.txt` (3 OK), `test_world-attempt12.txt` (44 OK), regression set
319 OK (`regression-attempt12.txt`), predicate probe `predicate-attempt12.txt`, full suite in
`full-attempt12.log`.

**Residual paths (unchanged, token-level heuristics, not a semantic classifier):** a procedure
phrased as a bare noun phrase with no digit, unit, spelled quantity, fraction or procedure verb
(`valve clearance table`) is not detected; a bare-object imperative whose object happens to
contain a selected-grammar motif (e.g. `Clean service bay` used as an instruction rather than a
place cue) is accepted by design, since the carve-out cannot distinguish place from instruction
at token level; the workshop hard negatives remain the second line of defence. `world.*` is still
absent from the published `rpc.v23.json` (additive integration bump); the media seam is a
deterministic fake; the `world_assets` role vocabulary follows the frozen 0013 CHECK; create-time
auto-queue is owned by GM-002.

## Known gap closed by GM-019 — non-frozen imperative verbs and passive voice

The frozen verb list was a lexical tail, recorded here as the accepted GM-003 residual and owned
by follow-up GM-019 (`t_cc8e02ba`). Two shapes escaped: an imperative verb outside the list
(`Scrub the head`, `Swap the gasket`, `Scrape the block`, `Degrease the block`, `Rebuild the
head`) and passive voice (`The head is removed`, `The intake manifold was drained`). Sentinel
reproduced `Scrub the head` through the real handler at 3 calls in 3/3 prompts.

GM-019 closes both by shape, not by extending the verb list: `_object_taking_clause()`
(content word + determiner/possessive + noun) and `_passive_construction()` (be-auxiliary +
`-ed`/closed irregular participle). Frozen verbs and gerunds remain refused; the grammar-owned
scene carve-outs (`clean service bay`, `car on a lift`, `four-cylinder block`) remain legal. The
residuals that remain after GM-019 — a non-frozen bare-object imperative (`Scrub head`), a
non-frozen gerund on a non-procedure grammar, and passive over-refusal of stative scene text —
are named explicitly in `audit/gm-019/README.md`.
