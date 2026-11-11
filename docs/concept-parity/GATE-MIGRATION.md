# GATE-MIGRATION — the v2 gates, versioned for v3

Card: **CP-003**. Owner `sentinel`, reviewer `cbqa`. Parent: CP-002. Branch `wt/cp-003-gates`.

This document is the migration record for the eight visual test modules that guard the shipped
surfaces. Its one rule:

> **No v2 protection is deleted to make room for v3.** A v2 assertion is re-pointed at the v2
> region, or it is kept whole-file because its claim is universal, or it is marked
> superseded-by-v3 and its v3 replacement is named. There is no fourth option.

The card's acceptance is mechanical: the full suite is green on this branch with
`V3_REQUIRED = False`; flipping that flag locally makes the v3 gates fail for the stated reasons.
The seam those gates depend on is itself gated by `tests/test_desktop_gate_scope.py`, which proves
in both directions that it cuts v3 paint and keeps every v2 protection.

---

## 1. Why a seam is necessary

`desktop/plugin.js` is one material system today (Atlas Lamp v2). Five v2 assertions read it as a
single blob and would be falsified by legitimate v3 paint:

| v2 assertion | what v3 would add | why the claim cannot simply be dropped |
|---|---|---|
| "no raw hex outside the token table" | `CB_TOKENS_V3_JSON` (18 roles × 2 modes) | dropping it lets a raw hex into any v2 surface |
| "no decorative gradient" | the named parchment vignette | dropping it lets a decorative fill anywhere |
| "no box shadow" | `box-shadow: var(--cb3-elev-*)` contact elevation | dropping it lets a glow or drop shadow anywhere |
| "no font size outside the six steps" | CSS `font-size` in `CB_V3_CSS` | dropping it lets an off-scale size into v2 |
| "one motion ladder" | the v3 ladder (120/150/240/300/600) | dropping it lets a second duration drift in anywhere |

So the module is treated as two regions and each gate keeps its claim on the region it governs.

## 2. The classes

| Class | Meaning | Consequence in the suite |
|---|---|---|
| **U — universal** | The claim must hold on every version. It is not renegotiated by v3. | Stays whole-file (or whole-source where the mechanism is version-independent). Never relaxed. |
| **V2 — v2-material** | The assertion binds a v2 surface, component, contract value or document. | Scoped to the v2 region / a named v2 function / the rendered v2 DOM. The v3 counterpart is named in the table. |
| **S — superseded-by-v3** | The exact v2 value is deliberately replaced on v3 surfaces (v2 stays valid for v2). | Scoped to the v2 region; the v3 value is gated by `tests/test_desktop_tokens_v3.py`. Never copied into a v3 gate as-is. |

Counts across the 177 assertions: **155 V2, 17 U, 5 S**. The per-file counts are the anti-deletion
baseline in `tests/test_desktop_gate_scope.py`.

## 3. The seam

`tests/cb_source_scope.py` (not a test module) defines the boundary:

- **v2 region** — everything outside the v3 literals and markers.
- **v3 region** — the `CB_TOKENS_V3_JSON` literal, the `CB_V3_CSS` literal, and anything between
  `// CB-V3-BEGIN` … `// CB-V3-END` if a builder wraps more than the two literals.

`v2_source()` returns the module with the v3 region cut; `v3_source()` returns the v3 region; the
same module supplies the CSS parser (`css_blocks`, `declarations`, `style_rules`,
`split_selectors`) that both the v3 gate and `scripts/v3-audit.py` use, so the gate and the audit
cannot disagree about what the stylesheet says.

Design decisions worth recording, because each is a place a later card could weaken the seam:

1. **The seam cuts literal bodies, not identifiers.** `const CB_V3_CSS =` survives in the v2 text;
   its content does not. No v2 gate asserts on the identifier, and cutting the whole statement
   would make the seam rewrite the module rather than read a region of it.
2. **An unterminated `CB-V3-BEGIN` cuts to end-of-file.** A half-marked region must never leave v3
   paint inside the v2 scan.
3. **The seam does not edit `desktop/plugin.js`.** CP-003 does not own that file; CP-020a adds the
   literals. Until then `v2_source()` is byte-identical to the file, and
   `test_without_v3_material_the_v2_region_is_the_whole_file` asserts that — skipping, not failing,
   once `V3_REQUIRED` is armed (see §6).
4. **No gate is allowed to read a bare region count.** `v3_spans()` merges overlapping spans, so a
   marker nested inside a literal cannot double-cut and hide text.
5. **A marker region is not a paint exemption.** `v3_spans()` (used to cut the v2 region) includes
   marker spans; the v3 shadow and gradient scans exempt only the shipped `CB_V3_CSS` literal via
   `stylesheet_spans()`. Exempting markers too would leave their content in no gate at all: cut from
   v2, unscanned by v3. Markers may carry v3 control-flow scaffolding, never hex, a shadow or a
   gradient.

### 3.1 The edits actually made (eight modules)

| File | Edit | Behaviour today |
|---|---|---|
| `test_desktop_tokens.py` | `no_colour_literal_outside_the_token_table` and `no_decorative_gradients` read `v2_source()` | identical (no v3 region exists) |
| `test_desktop_type_scale.py` | `TypeScaleSourceTest.setUp` reads `v2_source()` | identical |
| `test_desktop_h152_motion.py` | `MotionSourceTest.setUp` reads `v2_source()`; `test_no_decorative_beat_survives` reads `full_source` (universal) | identical |
| `test_desktop_field_desk.py` | `test_the_desk_paints_only_from_the_token_layer` reads `v2_source()` before the M2 split | identical |
| `test_h197_covers.py` | the "no font asset reference" clause reads `v2_source()`; the external-fetch clauses stay whole-file | identical |
| `test_desktop_h150_library_shelf.py` | versioned docstring only; source reads were already scoped to named v2 functions | identical |
| `test_gm_visual_spec.py` | versioned docstring only; reads documents and the v2 contract, not the plugin | identical |
| `test_desktop_home_hub.py` | versioned docstring only; the paint claim reads rendered v2 HTML | identical |

No assertion was removed, renamed to hide it, or marked skip. The count gate
(`NoProtectionDeletedTest`) fails if any module drops below its CP-003 baseline.

### 3.2 The seam's proof (negative controls)

`tests/test_desktop_gate_scope.py` builds synthetic module text and runs the **real** v2 scans:

| Control | Injection | Expected |
|---|---|---|
| positive | token literal hex, `var(--cb3-elev-1)` shadow, named-vignette gradient, CSS `font-size`, v3 durations | no v2 gate fires |
| negative | `color: '#ff00ff'` in the v2 region | hex scan fires |
| negative | `linear-gradient(…)` fill in the v2 region | gradient scan fires |
| negative | `boxShadow` in the v2 region | shadow scan fires |
| negative | `var(--cb-dur-hover)` in the v2 region | ladder scan fires |
| safety | unterminated `CB-V3-BEGIN` | cut to EOF, no leak |

That is the difference between scoping and weakening: the mechanism is proven to still catch a
violation while ignoring a legitimate v3 declaration.

**The v3 gate is proven in both directions too.** A gate that has only ever failed because the
literal was absent has not shown it would catch a bad stylesheet. `V3GateBitesTest` points the
**real** gate (`tests/test_desktop_tokens_v3.py`) at a temporary module — never the product file —
and:

| Control | Input | Expected |
|---|---|---|
| compliant | contract-canonical token literal + `[data-cb-v3]` stylesheet with `@font-face`, `var(--cb3-elev-1)`, named vignette, `CB ` families, the five-beat table | all 12 gated claims pass |
| glass | `backdrop-filter` added | blur claim fails |
| shadow | `box-shadow: 0 4px 12px rgba(…)` | elevation claim fails |
| gradient | `linear-gradient(#fff,#000)` on a normal property | vignette claim fails |
| scope | a selector with no `[data-cb-v3]` prefix | scope claim fails |
| font | `"Inter"` as the first family | font claim fails |
| motion | a literal `90ms` transition | motion-table claim fails |
| loop | `@keyframes` | no-animation claim fails |
| measure | `4vw` | route-relative claim fails |
| drift | one hex changed in the token literal | byte-equality claim fails |
| raw paint | `#a5763f` in the stylesheet | hex-only-in-literals claim fails |
| marker shadow | `box-shadow: 0 0 24px …` inside `CB-V3-BEGIN`…`END` | elevation claim fails (markers are not an exemption) |
| marker gradient | `linear-gradient(120deg, …)` inside `CB-V3-BEGIN`…`END` | vignette claim fails |

The compliant control also pins the extractor: the token literal is embedded with the backslash
escaping a real JS string literal requires, so a builder cannot satisfy the gate with a literal the
runtime would mis-parse.

---

## 4. The assertion table (every assertion, all eight modules)

Columns: **class** (§2); **where it reads now**; **v3 counterpart / note** — the gate or rubric
dimension that covers the same claim for v3 surfaces. An empty counterpart would mean a claim was
dropped, which the count gate forbids.

The count gate is enforced twice, because a method count alone cannot see a deleted assertion
(cbqa round 2, D4): `NoProtectionDeletedTest` pins the **test-method** count per module *and* the
**`assert*` call** count per module over the AST. Both are floors (`>=`), so additions stay legal.
The assertion-call floors, recomputed at base `7a0841f` (`test_desktop_gate_scope.py` at `d63b65d`):

| module | test methods | `assert*` calls |
|---|---|---|
| `test_desktop_tokens.py` | 17 | 63 |
| `test_desktop_type_scale.py` | 8 | 16 |
| `test_desktop_h152_motion.py` | 22 | 96 |
| `test_desktop_field_desk.py` | 44 | 170 |
| `test_desktop_h150_library_shelf.py` | 21 | 99 |
| `test_h197_covers.py` | 28 | 81 |
| `test_gm_visual_spec.py` | 17 | 56 |
| `test_desktop_home_hub.py` | 20 | 103 |
| `test_desktop_gate_scope.py` (the proof itself) | 24 | 38 |


### `tests/test_desktop_tokens.py`

| # | assertion | class | where it reads now | v3 counterpart / note |
|---|---|---|---|---|
| 1 | `TokenContractTest.test_the_shipped_table_equals_the_contract` | V2 | v2 token table + v2 contract | v3 palette gated by test_desktop_tokens_v3 / v3-audit V-02 |
| 2 | `TokenContractTest.test_every_token_has_a_light_and_a_dark_value` | V2 | v2 token table + v2 contract | v3 palette gated by test_desktop_tokens_v3 / v3-audit V-02 |
| 3 | `TokenContractTest.test_no_colour_literal_outside_the_token_table` | U | v2_source() (v2 half) | hex in CB_TOKENS_V3_JSON allowed; v3 half is test_desktop_tokens_v3 |
| 4 | `TokenContractTest.test_no_decorative_gradients` | S | v2_source() | v3 permits the named vignette; v3 claim is test_desktop_tokens_v3 |
| 5 | `TokenContractTest.test_the_gradient_ban_still_covers_surface_fills` | U | helper self-test | exemption for the v2 mask is one declaration, not a hole |
| 6 | `TokenContractTest.test_contrast_gates_hold_for_the_values_that_ship` | V2 | v2 token table + v2 contract | v3 palette gated by test_desktop_tokens_v3 / v3-audit V-02 |
| 7 | `TokenContractTest.test_the_host_tertiary_floor_is_not_lowered` | U | v2 token table | v3 gates keep ink-soft at >=4.5 on every ground |
| 8 | `TokenContractTest.test_the_route_and_pane_roots_are_the_scope` | U | whole file | v3 paints on the same two roots; a third scope root fails here |
| 9 | `RouteShellRenderTest.test_the_scope_carries_every_token_in_both_modes` | V2 | rendered v2 shell | v3 shell owned by CP-020a/CP-022; v3 rubric dims 2, 8 |
| 10 | `RouteShellRenderTest.test_layout_stacks_below_the_breakpoint_and_never_guesses_wide` | V2 | rendered v2 shell | v3 shell owned by CP-020a/CP-022; v3 rubric dims 2, 8 |
| 11 | `RouteShellRenderTest.test_wide_shell_puts_the_rail_beside_the_reading_column` | V2 | rendered v2 shell | v3 shell owned by CP-020a/CP-022; v3 rubric dims 2, 8 |
| 12 | `RouteShellRenderTest.test_a_460px_shell_stacks_the_rail_and_keeps_the_measure` | V2 | rendered v2 shell | v3 shell owned by CP-020a/CP-022; v3 rubric dims 2, 8 |
| 13 | `RouteShellRenderTest.test_the_reading_typography_scales_with_the_root_font` | V2 | rendered v2 shell | v3 shell owned by CP-020a/CP-022; v3 rubric dims 2, 8 |
| 14 | `RouteShellRenderTest.test_dark_mode_paints_the_dark_table_on_the_same_root` | V2 | rendered v2 shell | v3 shell owned by CP-020a/CP-022; v3 rubric dims 2, 8 |
| 15 | `RouteShellRenderTest.test_media_frame_carries_caption_provenance_and_text_equivalent` | V2 | rendered v2 shell | v3 shell owned by CP-020a/CP-022; v3 rubric dims 2, 8 |
| 16 | `RouteShellRenderTest.test_the_lesson_page_is_a_three_part_workspace` | V2 | rendered v2 shell | v3 shell owned by CP-020a/CP-022; v3 rubric dims 2, 8 |
| 17 | `RouteShellRenderTest.test_a_460px_lesson_page_does_not_render_a_side_rail` | V2 | rendered v2 shell | v3 shell owned by CP-020a/CP-022; v3 rubric dims 2, 8 |

### `tests/test_desktop_type_scale.py`

| # | assertion | class | where it reads now | v3 counterpart / note |
|---|---|---|---|---|
| 18 | `TypeScaleSourceTest.test_the_contract_declares_exactly_six_steps` | S | v2 contract | v3 names six roles with different values |
| 19 | `TypeScaleSourceTest.test_the_shipped_scale_equals_the_contract` | V2 | v2_source() | v3 roles in cb.tokens.v3.json, gated by test_desktop_tokens_v3 |
| 20 | `TypeScaleSourceTest.test_no_authored_font_size_escapes_the_scale` | U | v2_source() (v2 half) | v3 sizes live in CSS and are gated by test_desktop_tokens_v3 |
| 21 | `TypeScaleSourceTest.test_body_is_sixteen_pixels_at_the_default_root` | U | v2 contract | v3 body is 1rem per cb.tokens.v3.json type.rules |
| 22 | `TypeScaleRenderTest.test_each_surface_uses_six_authored_sizes_or_fewer` | V2 | rendered v2 surfaces | v3 type scored on rubric dim 3; 16px/12px floors survive (v3 contract) |
| 23 | `TypeScaleRenderTest.test_no_authored_text_is_under_twelve_pixels` | V2 | rendered v2 surfaces | v3 type scored on rubric dim 3; 16px/12px floors survive (v3 contract) |
| 24 | `TypeScaleRenderTest.test_body_copy_is_sixteen_pixels` | V2 | rendered v2 surfaces | v3 type scored on rubric dim 3; 16px/12px floors survive (v3 contract) |
| 25 | `TypeScaleRenderTest.test_every_long_paragraph_sits_inside_a_ch_cap_of_75` | V2 | rendered v2 surfaces | v3 type scored on rubric dim 3; 16px/12px floors survive (v3 contract) |

### `tests/test_desktop_h152_motion.py`

| # | assertion | class | where it reads now | v3 counterpart / note |
|---|---|---|---|---|
| 26 | `FullMotionTest.test_the_ladder_is_one_table_with_four_beats_and_a_ceiling` | V2 | rendered v2 components | v3 ladder gated by test_desktop_tokens_v3; reduced motion re-proved on v3 frames |
| 27 | `FullMotionTest.test_the_scope_root_carries_the_tokens_the_transitions_reference` | V2 | rendered v2 components | v3 ladder gated by test_desktop_tokens_v3; reduced motion re-proved on v3 frames |
| 28 | `FullMotionTest.test_every_computed_transition_is_transform_opacity_or_colour` | V2 | rendered v2 components | v3 ladder gated by test_desktop_tokens_v3; reduced motion re-proved on v3 frames |
| 29 | `FullMotionTest.test_no_shadow_gradient_or_repeating_animation` | V2 | rendered v2 components | v3 ladder gated by test_desktop_tokens_v3; reduced motion re-proved on v3 frames |
| 30 | `FullMotionTest.test_press_is_one_hundred_milliseconds_of_translate_and_returns_to_rest` | V2 | rendered v2 components | v3 ladder gated by test_desktop_tokens_v3; reduced motion re-proved on v3 frames |
| 31 | `FullMotionTest.test_a_disabled_action_never_animates_and_says_so` | V2 | rendered v2 components | v3 ladder gated by test_desktop_tokens_v3; reduced motion re-proved on v3 frames |
| 32 | `FullMotionTest.test_the_row_primitive_carries_data_cb_state` | V2 | rendered v2 components | v3 ladder gated by test_desktop_tokens_v3; reduced motion re-proved on v3 frames |
| 33 | `FullMotionTest.test_route_settle_is_eight_nodes_at_forty_milliseconds_and_no_more` | V2 | rendered v2 components | v3 ladder gated by test_desktop_tokens_v3; reduced motion re-proved on v3 frames |
| 34 | `FullMotionTest.test_every_route_node_is_a_row_action_with_a_state` | V2 | rendered v2 components | v3 ladder gated by test_desktop_tokens_v3; reduced motion re-proved on v3 frames |
| 35 | `FullMotionTest.test_the_verdict_beat_is_caused_by_a_graded_result` | V2 | rendered v2 components | v3 ladder gated by test_desktop_tokens_v3; reduced motion re-proved on v3 frames |
| 36 | `FullMotionTest.test_completion_is_one_six_hundred_millisecond_beat` | V2 | rendered v2 components | v3 ladder gated by test_desktop_tokens_v3; reduced motion re-proved on v3 frames |
| 37 | `FullMotionTest.test_focus_is_never_part_of_a_beat` | V2 | rendered v2 components | v3 ladder gated by test_desktop_tokens_v3; reduced motion re-proved on v3 frames |
| 38 | `ReducedMotionTest.test_the_preference_reaches_the_root` | V2 | rendered v2 components | universal rule; v3 reduced-motion cell is a capture claim |
| 39 | `ReducedMotionTest.test_every_beat_is_static_and_still_shows_its_state` | V2 | rendered v2 components | universal rule; v3 reduced-motion cell is a capture claim |
| 40 | `ReducedMotionTest.test_the_route_has_no_stagger_under_reduced_motion` | V2 | rendered v2 components | universal rule; v3 reduced-motion cell is a capture claim |
| 41 | `MotionSourceTest.test_one_motion_table_and_one_hook_supply_every_duration` | S | v2_source() | v3 has its own table and hook; v2 keeps one |
| 42 | `MotionSourceTest.test_no_keyframes_no_animation_no_shadow_no_gradient` | S | v2_source() | v3 uses elev-* shadows and the vignette; keyframes/loops stay banned (V-06, V-11) |
| 43 | `MotionSourceTest.test_no_surface_named_a_beat_outside_the_ladder` | S | v2_source() | v3 ladder 120/150/240/300/600 differs; gated by test_desktop_tokens_v3 |
| 44 | `MotionSourceTest.test_the_learner_motion_setting_reaches_the_one_hook` | U | whole v2 source | the v3 surfaces must read the same published preference |
| 45 | `MotionSourceTest.test_the_only_utility_transition_is_colour_only` | V2 | v2_source() | v3 motion table gated by test_desktop_tokens_v3 / v3-audit V-11 |
| 46 | `MotionSourceTest.test_no_decorative_beat_survives` | U | whole file | banned on v2 and v3 alike |
| 47 | `MotionEvidenceTest.test_live_capture_recorded_the_beats` | V2 | v2 live capture (docs/h152-shots) | v3 captures come from cp-capture.mjs and are stamped |

### `tests/test_desktop_field_desk.py`

| # | assertion | class | where it reads now | v3 counterpart / note |
|---|---|---|---|---|
| 48 | `FieldDeskRenderTest.test_the_companion_appears_only_when_a_real_pet_answers` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 49 | `FieldDeskRenderTest.test_continue_names_the_section_the_next_action_and_the_position` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 50 | `FieldDeskRenderTest.test_a_narrow_desk_stacks_and_drops_the_course_stamp` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 51 | `FieldDeskRenderTest.test_the_continue_plate_has_no_seal_at_any_width` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 52 | `FieldDeskRenderTest.test_continue_shows_the_recorded_estimate_and_last_touched` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 53 | `FieldDeskRenderTest.test_a_course_with_no_recorded_estimate_says_so_instead_of_guessing` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 54 | `FieldDeskRenderTest.test_a_failed_estimate_read_is_not_reported_as_not_recorded` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 55 | `FieldDeskRenderTest.test_a_successful_answer_without_an_estimate_still_says_not_recorded` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 56 | `FieldDeskRenderTest.test_estimate_label_never_derives_minutes` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 57 | `FieldDeskRenderTest.test_a_thrown_parent_brief_read_renders_could_not_be_read_with_one_retry` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 58 | `FieldDeskRenderTest.test_a_thrown_pack_manifest_read_renders_the_same_failure_state` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 59 | `FieldDeskRenderTest.test_a_refused_estimate_read_is_a_failure_but_parent_brief_not_found_is_an_answer` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 60 | `FieldDeskRenderTest.test_retry_re_reads_the_estimate_and_paints_the_real_answer` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 61 | `FieldDeskRenderTest.test_a_successful_empty_answer_mounted_in_the_desk_still_says_not_recorded` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 62 | `FieldDeskRenderTest.test_path_lists_every_objective_with_its_state_word` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 63 | `FieldDeskRenderTest.test_path_marks_exactly_one_current_step` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 64 | `FieldDeskRenderTest.test_path_summary_counts_real_states_not_vanity` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 65 | `FieldDeskRenderTest.test_a_single_section_reads_as_one_section` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 66 | `FieldDeskRenderTest.test_path_is_not_a_table` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 67 | `FieldDeskRenderTest.test_sources_are_collapsed_by_default_and_read_nothing` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 68 | `FieldDeskRenderTest.test_open_sources_name_the_section_and_its_real_rows` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 69 | `FieldDeskRenderTest.test_a_failed_source_read_is_shown_with_no_source_rows` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 70 | `FieldDeskRenderTest.test_empty_sources_say_the_backend_recorded_none` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 71 | `FieldDeskRenderTest.test_model_continues_the_due_review_when_the_next_step_says_so` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 72 | `FieldDeskRenderTest.test_model_labels_a_resume_from_the_backends_next_step` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 73 | `FieldDeskRenderTest.test_model_falls_back_to_the_rows_own_current_objective` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 74 | `FieldDeskRenderTest.test_mainline_objective_never_matches_on_title` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 75 | `FieldDeskRenderTest.test_mainline_objective_prefers_the_section_open_over_the_course_write` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 76 | `FieldDeskRenderTest.test_last_touched_falls_back_to_the_course_write_and_says_which` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 77 | `FieldDeskRenderTest.test_no_courses_renders_first_run_not_a_sample_course` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 78 | `FieldDeskRenderTest.test_loading_renders_a_loader_and_no_course` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 79 | `FieldDeskRenderTest.test_a_failed_read_keeps_its_code_and_retry` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 80 | `FieldDeskRenderTest.test_a_stale_read_says_it_is_reconnecting` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 81 | `FieldDeskRenderTest.test_the_home_names_the_other_classroom_without_a_card_grid` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 82 | `FieldDeskRenderTest.test_a_single_classroom_names_itself_without_a_switcher` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 83 | `FieldDeskRenderTest.test_above_four_classrooms_becomes_one_labelled_select` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 84 | `FieldDeskRenderTest.test_the_wide_desk_is_one_trailhead_not_a_card_grid` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 85 | `FieldDeskRenderTest.test_the_trailhead_falls_back_without_a_pet_and_keeps_continue` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 86 | `FieldDeskRenderTest.test_a_course_contour_is_stable_and_distinct_per_course` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 87 | `FieldDeskRenderTest.test_resume_without_a_binding_opens_the_section_instead_of_a_blank_chat` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 88 | `FieldDeskRenderTest.test_path_titles_wrap_without_colliding_with_the_state_label` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 89 | `FieldDeskRenderTest.test_the_field_desk_return_is_on_the_courses_list_not_the_library` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 90 | `FieldDeskRenderTest.test_the_desk_arms_the_exact_run_before_opening_a_chat` | V2 | rendered v2 Field Desk | v3 Home/desk scored on rubric dims 6, 7, 9 |
| 91 | `FieldDeskRenderTest.test_the_desk_paints_only_from_the_token_layer` | U | v2_source() then M2 block | v3 stylesheet is gated by test_desktop_tokens_v3 |

### `tests/test_desktop_h150_library_shelf.py`

| # | assertion | class | where it reads now | v3 counterpart / note |
|---|---|---|---|---|
| 92 | `LibraryShelfRenderTest.test_the_whole_row_is_one_button_and_selection_is_spelled_out` | V2 | rendered v2 shelf row/preview | v3 Discover shelf scored on rubric dims 2, 6 |
| 93 | `LibraryShelfRenderTest.test_a_selected_row_keeps_a_text_cue_not_colour_alone` | V2 | rendered v2 shelf row/preview | v3 Discover shelf scored on rubric dims 2, 6 |
| 94 | `LibraryShelfRenderTest.test_an_empty_pack_says_no_sections_once_and_shows_no_path_or_seal` | V2 | rendered v2 shelf row/preview | v3 Discover shelf scored on rubric dims 2, 6 |
| 95 | `LibraryShelfRenderTest.test_the_row_resolves_the_backend_plural_placeholder` | V2 | rendered v2 shelf row/preview | v3 Discover shelf scored on rubric dims 2, 6 |
| 96 | `LibraryShelfRenderTest.test_a_label_outside_the_review_form_is_still_scrubbed` | V2 | rendered v2 shelf row/preview | v3 Discover shelf scored on rubric dims 2, 6 |
| 97 | `LibraryShelfRenderTest.test_pack_preview_moves_identifiers_under_closed_technical_details` | V2 | rendered v2 shelf row/preview | v3 Discover shelf scored on rubric dims 2, 6 |
| 98 | `LibraryShelfRenderTest.test_pack_preview_has_one_primary_one_secondary_and_no_inline_destructive` | V2 | rendered v2 shelf row/preview | v3 Discover shelf scored on rubric dims 2, 6 |
| 99 | `LibraryShelfRenderTest.test_the_member_disclosure_names_records_without_a_hash` | V2 | rendered v2 shelf row/preview | v3 Discover shelf scored on rubric dims 2, 6 |
| 100 | `LibraryShelfFocusTest.test_enter_and_space_leave_focus_on_a_visible_control` | V2 | rendered v2 shelf focus path | v3 rail/tab focus is an accessibility capture cell |
| 101 | `LibraryShelfFocusTest.test_enter_and_space_are_the_same_path` | V2 | rendered v2 shelf focus path | v3 rail/tab focus is an accessibility capture cell |
| 102 | `LibraryShelfFocusTest.test_the_focused_row_paints_the_identity_ring_and_clears_it` | V2 | rendered v2 shelf focus path | v3 rail/tab focus is an accessibility capture cell |
| 103 | `LibraryShelfFocusTest.test_the_preview_offers_the_back_control_focus_lands_on` | V2 | rendered v2 shelf focus path | v3 rail/tab focus is an accessibility capture cell |
| 104 | `LibraryShelfSourceTest.test_one_page_lead_and_no_repeated_library_label` | V2 | named v2 function blocks | v3 Discover source is new; nothing here scans v3 text |
| 105 | `LibraryShelfSourceTest.test_filters_name_the_rows_they_return` | V2 | named v2 function blocks | v3 Discover source is new; nothing here scans v3 text |
| 106 | `LibraryShelfSourceTest.test_trust_is_read_below_the_shelf` | V2 | named v2 function blocks | v3 Discover source is new; nothing here scans v3 text |
| 107 | `LibraryShelfSourceTest.test_the_shelf_layout_is_decided_from_the_route_column` | V2 | named v2 function blocks | v3 Discover source is new; nothing here scans v3 text |
| 108 | `LibraryShelfSourceTest.test_the_row_is_a_whole_row_button_with_one_preview_affordance` | V2 | named v2 function blocks | v3 Discover source is new; nothing here scans v3 text |
| 109 | `LibraryShelfSourceTest.test_pack_menu_puts_destructive_actions_under_overflow` | V2 | named v2 function blocks | v3 Discover source is new; nothing here scans v3 text |
| 110 | `LibraryShelfSourceTest.test_technical_fields_are_named_and_closed` | V2 | named v2 function blocks | v3 Discover source is new; nothing here scans v3 text |
| 111 | `LibraryShelfSourceTest.test_counts_use_the_shared_plural_helper` | V2 | named v2 function blocks | v3 Discover source is new; nothing here scans v3 text |
| 112 | `LibraryShelfSourceTest.test_backend_plural_placeholder_never_reaches_the_shelf` | V2 | named v2 function blocks | v3 Discover source is new; nothing here scans v3 text |

### `tests/test_h197_covers.py`

| # | assertion | class | where it reads now | v3 counterpart / note |
|---|---|---|---|---|
| 113 | `SpecAmendmentTests.test_the_old_refusal_clause_is_gone` | V2 | v2 identity doc + refusal clause | v3 identity doc is a separate file (COURSEBOOK-VISUAL-IDENTITY-V3.md) |
| 114 | `SpecAmendmentTests.test_the_new_refusal_clause_is_present` | V2 | v2 identity doc + refusal clause | v3 identity doc is a separate file (COURSEBOOK-VISUAL-IDENTITY-V3.md) |
| 115 | `SpecAmendmentTests.test_the_icon_rule_is_unchanged_and_the_ornament_sentence_is_appended` | V2 | v2 identity doc + refusal clause | v3 identity doc is a separate file (COURSEBOOK-VISUAL-IDENTITY-V3.md) |
| 116 | `SpecAmendmentTests.test_the_unchanged_gates_are_still_refused` | V2 | v2 identity doc + refusal clause | v3 identity doc is a separate file (COURSEBOOK-VISUAL-IDENTITY-V3.md) |
| 117 | `LicenceAndProvenanceTests.test_every_cover_is_a_declared_image_of_its_own_pack` | V2 | v2 cover catalogue + provenance | universal licence rule applies to any v3 cover lane |
| 118 | `LicenceAndProvenanceTests.test_every_cover_file_carries_a_permissive_licence_and_an_attribution` | V2 | v2 cover catalogue + provenance | universal licence rule applies to any v3 cover lane |
| 119 | `LicenceAndProvenanceTests.test_a_cc_by_cover_would_need_visible_credits` | V2 | v2 cover catalogue + provenance | universal licence rule applies to any v3 cover lane |
| 120 | `LicenceAndProvenanceTests.test_provenance_records_every_shipped_cover_file_with_its_hash` | V2 | v2 cover catalogue + provenance | universal licence rule applies to any v3 cover lane |
| 121 | `LicenceAndProvenanceTests.test_the_parent_pack_states_its_typographic_fallback` | V2 | v2 cover catalogue + provenance | universal licence rule applies to any v3 cover lane |
| 122 | `LicenceAndProvenanceTests.test_no_cover_borrows_a_restrictive_or_competitor_source` | V2 | v2 cover catalogue + provenance | universal licence rule applies to any v3 cover lane |
| 123 | `AccuracyTests.test_every_cover_text_says_what_it_is` | V2 | v2 cover manifest + alt text | universal truth rule: art is textless, alt describes |
| 124 | `AccuracyTests.test_no_cover_carries_a_safety_critical_value` | V2 | v2 cover manifest + alt text | universal truth rule: art is textless, alt describes |
| 125 | `AccuracyTests.test_the_cover_alt_is_a_description_and_not_the_title` | V2 | v2 cover manifest + alt text | universal truth rule: art is textless, alt describes |
| 126 | `NoHotlinkAndIconFamilyTests.test_the_cover_image_src_is_the_artifact_preview_not_a_url` | U | v2 WorkshopCover block | v3 covers go through the same artifact route |
| 127 | `NoHotlinkAndIconFamilyTests.test_the_plugin_fetches_no_external_image_or_font` | U | whole file + v2_source() for the font-file clause | url(http)/@import universal; local font file is v3-legal |
| 128 | `NoHotlinkAndIconFamilyTests.test_the_icon_family_is_unchanged` | U | whole file | v3 uses sdk.Codicon only (SPEC-V3 §3.7) |
| 129 | `NoHotlinkAndIconFamilyTests.test_no_icon_or_illustration_dependency_was_added` | U | package.json | no icon/illustration dependency may be added for v3 either |
| 130 | `NoHotlinkAndIconFamilyTests.test_the_catalogue_cover_paths_are_relative_and_plain` | V2 | whole file / v2_source() / package.json | no-fetch and one-icon rules are universal; font-file clause is v2-only |
| 131 | `BuilderIsTheOnlySourceTests.test_each_committed_plate_matches_the_generator` | V2 | committed v2 plates + builder | v3 plates come from CP-010/011/012 builders |
| 132 | `BuilderIsTheOnlySourceTests.test_plates_are_16_by_9_and_the_crop_is_3_by_2` | V2 | committed v2 plates + builder | v3 plates come from CP-010/011/012 builders |
| 133 | `BuilderIsTheOnlySourceTests.test_the_acceptance_block_passes_on_the_committed_files` | V2 | committed v2 plates + builder | v3 plates come from CP-010/011/012 builders |
| 134 | `BuilderIsTheOnlySourceTests.test_a_third_unsent_plate_exists_for_the_lane_and_ships_nowhere` | V2 | committed v2 plates + builder | v3 plates come from CP-010/011/012 builders |
| 135 | `CoverFlowTests.test_before_install_every_cover_is_the_composed_typographic_plate` | V2 | v2 catalogue/artifact route | v3 cover flow is CP-014/CP-021 |
| 136 | `CoverFlowTests.test_after_install_the_cover_is_the_plate_the_catalogue_names` | V2 | v2 catalogue/artifact route | v3 cover flow is CP-014/CP-021 |
| 137 | `CoverFlowTests.test_the_same_plate_is_presented_on_store_library_and_detail` | V2 | v2 catalogue/artifact route | v3 cover flow is CP-014/CP-021 |
| 138 | `CoverFlowTests.test_the_parent_pack_keeps_its_typographic_fallback_after_install` | V2 | v2 catalogue/artifact route | v3 cover flow is CP-014/CP-021 |
| 139 | `CoverFlowTests.test_a_catalogue_cover_that_is_not_the_first_visual_is_refused` | V2 | v2 catalogue/artifact route | v3 cover flow is CP-014/CP-021 |
| 140 | `CoverFlowTests.test_a_cover_no_route_can_serve_is_refused` | V2 | v2 catalogue/artifact route | v3 cover flow is CP-014/CP-021 |

### `tests/test_gm_visual_spec.py`

| # | assertion | class | where it reads now | v3 counterpart / note |
|---|---|---|---|---|
| 141 | `TestTokenBinding.test_spec_names_every_shipped_token` | V2 | GM-VISUAL-SPEC.md + v2 contract | v3 token binding is the contract test + v3 gate |
| 142 | `TestTokenBinding.test_spec_adds_no_colour_literal` | V2 | GM-VISUAL-SPEC.md + v2 contract | v3 token binding is the contract test + v3 gate |
| 143 | `TestTokenBinding.test_plates_use_shipped_tokens_only` | V2 | GM-VISUAL-SPEC.md + v2 contract | v3 token binding is the contract test + v3 gate |
| 144 | `TestTokenBinding.test_plates_never_use_state_hues` | V2 | GM-VISUAL-SPEC.md + v2 contract | v3 token binding is the contract test + v3 gate |
| 145 | `TestTokenBinding.test_type_scale_is_the_shipped_six` | V2 | GM-VISUAL-SPEC.md + v2 contract | v3 token binding is the contract test + v3 gate |
| 146 | `TestPlatesAreTextless.test_every_plate_has_no_text_or_image_reference` | V2 | v2 SVG boards | v3 art must be textless too (rubric dim 5) |
| 147 | `TestPlatesAreTextless.test_manifest_matches_the_bytes` | V2 | v2 SVG boards | v3 art must be textless too (rubric dim 5) |
| 148 | `TestSubjectWorlds.test_four_worlds_specify_two_motifs_and_a_swap_check` | V2 | v2 world spec + boards | v3 subject worlds are CP-016 |
| 149 | `TestSubjectWorlds.test_every_board_reference_resolves_to_a_file` | V2 | v2 world spec + boards | v3 subject worlds are CP-016 |
| 150 | `TestSubjectWorlds.test_no_world_borrows_a_state_hue` | V2 | v2 world spec + boards | v3 subject worlds are CP-016 |
| 151 | `TestRubric.test_nine_dimensions_and_the_threshold` | V2 | rubric §1 nine v2 dimensions | rubric §7 ten v3 dimensions are additive; frame rule is universal |
| 152 | `TestRubric.test_every_matrix_screen_has_a_comparison_frame` | U | matrix.json + rubric | applies to the five .v3 screens too |
| 153 | `TestMatrix.test_screens_have_frames_and_states` | V2 | visual-review matrix (v2 baseline + 5 v3 ids) | v3 cells are added to the same matrix by CP-001 |
| 154 | `TestMatrix.test_matrix_markdown_lists_every_screen` | V2 | visual-review matrix (v2 baseline + 5 v3 ids) | v3 cells are added to the same matrix by CP-001 |
| 155 | `TestMatrix.test_visual_review_template_is_complete` | V2 | visual-review matrix (v2 baseline + 5 v3 ids) | v3 cells are added to the same matrix by CP-001 |
| 156 | `TestPrintAndArtDocs.test_print_spec_has_five_roles_and_the_answer_key_rule` | U | print spec + art doc (unchanged by v3) | same documents govern v3 print |
| 157 | `TestPrintAndArtDocs.test_art_plate_doc_lists_every_plate_and_provenance_field` | U | print spec + art doc (unchanged by v3) | same documents govern v3 print |

### `tests/test_desktop_home_hub.py`

| # | assertion | class | where it reads now | v3 counterpart / note |
|---|---|---|---|---|
| 158 | `HubProjectionTest.test_one_slot_per_course_and_duplicate_enrollments_are_disclosed_not_split` | V2 | v2 hub projection | v3 Home projection is CP-022 |
| 159 | `HubProjectionTest.test_slot_name_uses_learner_label_then_course_title_and_never_invents_one` | V2 | v2 hub projection | v3 Home projection is CP-022 |
| 160 | `HubProjectionTest.test_parent_recipe_rows_never_appear_as_learner_slots` | V2 | v2 hub projection | v3 Home projection is CP-022 |
| 161 | `HubProjectionTest.test_continue_reads_the_selected_slots_next_step` | V2 | v2 hub projection | v3 Home projection is CP-022 |
| 162 | `HubProjectionTest.test_slot_count_uses_deduped_rows_and_total_only_as_truncation` | V2 | v2 hub projection | v3 Home projection is CP-022 |
| 163 | `HubProjectionTest.test_selected_row_still_works_when_the_outline_read_failed` | V2 | v2 hub projection | v3 Home projection is CP-022 |
| 164 | `HubProjectionTest.test_path_nodes_read_only_recorded_states_and_invent_no_gate` | V2 | v2 hub projection | v3 Home projection is CP-022 |
| 165 | `HubProjectionTest.test_hub_paints_only_token_layer_values` | U | rendered v2 hub HTML | v3 Home must still paint tokens only |
| 166 | `HubRouteTest.test_library_failure_is_not_an_empty_hub` | V2 | rendered v2 hub route | v3 Home route is CP-022; states scored on rubric dim 7 |
| 167 | `HubRouteTest.test_all_archived_is_its_own_state_not_first_run` | V2 | rendered v2 hub route | v3 Home route is CP-022; states scored on rubric dim 7 |
| 168 | `HubRouteTest.test_a_parent_only_profile_names_parent_studio` | V2 | rendered v2 hub route | v3 Home route is CP-022; states scored on rubric dim 7 |
| 169 | `HubRouteTest.test_a_genuinely_empty_profile_renders_the_start_plate` | V2 | rendered v2 hub route | v3 Home route is CP-022; states scored on rubric dim 7 |
| 170 | `HubRouteTest.test_switching_a_slot_rekeys_continue_and_the_outline_read` | V2 | rendered v2 hub route | v3 Home route is CP-022; states scored on rubric dim 7 |
| 171 | `HubRouteTest.test_selection_survives_course_detail_and_back` | V2 | rendered v2 hub route | v3 Home route is CP-022; states scored on rubric dim 7 |
| 172 | `HubRouteTest.test_slot_switch_never_changes_the_profile_scope` | V2 | rendered v2 hub route | v3 Home route is CP-022; states scored on rubric dim 7 |
| 173 | `HubRouteTest.test_selected_slot_missing_falls_back_and_says_so` | V2 | rendered v2 hub route | v3 Home route is CP-022; states scored on rubric dim 7 |
| 174 | `HubRouteTest.test_above_four_slots_is_one_labelled_select` | V2 | rendered v2 hub route | v3 Home route is CP-022; states scored on rubric dim 7 |
| 175 | `HubRouteTest.test_narrow_hub_has_no_fixed_overflow_and_44px_targets` | V2 | rendered v2 hub route | v3 Home route is CP-022; states scored on rubric dim 7 |
| 176 | `HubRouteTest.test_focused_classroom_tab_paints_the_identity_focus_ring` | V2 | rendered v2 hub route | v3 Home route is CP-022; states scored on rubric dim 7 |
| 177 | `HubRouteTest.test_offline_and_stale_keep_the_classroom_and_say_it_is_paused` | V2 | rendered v2 hub route | v3 Home route is CP-022; states scored on rubric dim 7 |


---

## 5. The v3 gate inventory

### 5.1 `tests/test_desktop_tokens_v3.py`

`V3_REQUIRED = False` at the top. Ungated: the contract fixture is well formed (18 roles, both
modes, six-digit hex, five distinct motion beats within the ceiling); the armed-only test is the
first RED on the flip. Gated (each reads the plugin and fails on the flip for the named reason):

| # | Claim | Mechanism |
|---|---|---|
| 1 | `CB_TOKENS_V3_JSON` equals the contract byte for byte | parses the literal, requires `modes`/`elevation`/`radii`/`type`/`motion`, every carried key equal, and the literal equal to the canonical serialization of the contract projection |
| 2 | hex appears only in the two token literals | masks both literal spans, then scans the rest for `#hex` |
| 3 | every mode carries every role | set equality against `roles` |
| 4 | no `backdrop-filter`, no `blur(` | whole-file scan, normalised: `backdrop-filter` / `backdropFilter` / `blur(` at any casing (shared `GLASS` pattern) |
| 5 | `box-shadow` only inside `CB_V3_CSS`, only as `var(--cb3-elev-*)` | declaration parse, normalised: any vendor-prefixed (`-webkit-`/`-moz-`/`-ms-`/`-o-`), case-varied or camel `boxShadow` property is a shadow declaration; value must be exactly `var(--cb3-elev-*)`. Outside-span scan uses the same normalisation |
| 6 | the only gradient is the named vignette | every gradient declaration must be a `--cb3-vignette*` custom property; none outside the stylesheet |
| 7 | every selector starts with `[data-cb-v3]` | selector list parse; at-rules excepted |
| 8 | every `@font-face` family and every literal `font-family` leads with `CB ` | `@font-face` bodies and first-family rule (contract fallbacks stay legal) |
| 9 | motion durations only from the motion table | every duration must be a `--cb3-dur-*` entry equal to the contract beat (units case-insensitive, so `900MS` is seen); no `@keyframes`/`animation:`/`animation-name`/`infinite` at any casing |
| 10 | the stylesheet is not a stub | ≥3 style rules and ≥400 characters, so "must not contain" rules cannot pass vacuously |
| 11 | no `vw` on a v3 surface | SPEC-V3 §3.1: route-relative measurement |

### 5.2 `scripts/v3-audit.py` + `tests/test_v3_visual_audit.py`

The v2 M4 audit keeps its C-01…C-15 claims against v2. The v3 audit is a separate tool with twelve
v3 claims:

| Id | Claim |
|---|---|
| V-01 | contract declares 18 roles, both modes, every mode complete |
| V-02 | all 30 gates clear their floor in both modes (recomputed; 60 checks) |
| V-03 | every text role paints only on a ground gated for it |
| V-04 | `CB_TOKENS_V3_JSON` equals the contract byte for byte |
| V-05 | raw hex only in the two token literals |
| V-06 | no backdrop-filter, blur or glass (any casing; `GLASS`) |
| V-07 | `box-shadow` — any vendor prefix, any casing — only in `CB_V3_CSS`, only `var(--cb3-elev-*)` |
| V-08 | the only gradient is the named vignette |
| V-09 | every selector scoped to `[data-cb-v3]` |
| V-10 | `CB ` font families only |
| V-11 | motion durations only from the v3 table (units case-insensitive); no keyframe/loop/animation token at any casing |
| V-12 | no `vw` on a v3 surface |

Three properties make it evidence rather than a document:

1. **Module sha pin.** Every run records `plugin_sha256` and `contract_sha256`;
   `tests/test_v3_visual_audit.py` re-derives both from disk and fails on a mismatch, so an audit
   cannot be inherited from a different build. The commit is recorded too.
2. **No fabricated PASS.** While the v3 material is absent, V-04…V-12 are `NOT-BUILT`, never
   `PASS`. `--full` refuses (exit 3) **in both material states** and names the unimplemented paint
   phase: literals + a browser + `cp-capture.mjs` existing is not a measurement, and the phase reads
   no frame and verifies no stamp, so it may never exit 0 until it does.
3. **Black-box test.** The test runs the script through its command line and reads only the JSON it
   writes; it does not import the claims.

The painted phase stays with the screen cards: they capture stamped frames through
`scripts/cp-capture.mjs` (CP-000) from their own commit, and GM-016 re-captures the integrated
build. CP-003 does not produce a screenshot and does not claim one.

---

## 6. The TDD hand-off to CP-020a

1. CP-020a's **first commit** sets `V3_REQUIRED = True` in `tests/test_desktop_tokens_v3.py` and
   `tests/test_v3_visual_audit.py`, and nothing else.
2. The gate goes red: `test_the_gate_is_armed_only_when_the_v3_material_exists` names the missing
   `CB_TOKENS_V3_JSON`; the eleven gated claims report the missing literal or stylesheet; the audit
   still reports V-04…V-12 `NOT-BUILT`.
3. CP-020a adds the token literal (generated from the contract, not hand-typed), the `[data-cb-v3]`
   style scope, the `CB ` faces, the material tiles and the ready marker until the gate is green.
4. CP-020a does not edit the assertions and does not edit this table. If a claim cannot be met, the
   contract or the spec is defective and the card comes back — the gate is not lowered.

**The hand-off is executable on this branch (reviewer round 1, D1).**
`test_desktop_gate_scope.py::SeamHandoffControlTest` points the seam and the v3 gate at the
contract-canonical compliant module in a temp dir and flips `V3_REQUIRED` in memory:

| Control | State | Expected |
|---|---|---|
| armed + compliant build | `V3_REQUIRED=True`, literals present | `test_without_v3_material_the_v2_region_is_the_whole_file` **skips**; no failure |
| disarmed + material present | `V3_REQUIRED=False`, literals present | `test_v3_material_may_not_exist_while_the_gate_is_disarmed` **fails**, naming the disarmed gate |
| disarmed + material absent | today's branch | both pass |

So CP-020a can reach a green suite with `True` without touching a CP-003 assertion, and material
that lands ahead of the flip is caught instead of being silently skipped. `SEAM_BASELINE = 24` pins
this module's own claim count, since the eight-module `BASELINE` does not cover it.

The expected RED output is pasted in the CP-003 review summary; it is not committed as a snapshot
because the exact trace is a property of CP-020a's first commit, not of this branch.

## 6.1 Round 1 review corrections (cbqa, D1–D3)

| Defect | Correction | Test that closes it |
|---|---|---|
| **D1** the seam red a legitimate v3 build; the disarmed flag hid material | the "v2 region is the whole file" claim skips under `V3_REQUIRED`; the converse forbids v3 material while the gate is disarmed; hand-off controls arm the flag in memory | `SeamHandoffControlTest.test_a_compliant_build_passes_the_seam_once_the_gate_is_armed`, `test_material_that_lands_before_the_flip_fails_loudly`, `SeamDirectionTest.test_v3_material_may_not_exist_while_the_gate_is_disarmed` |
| **D2** `--full` exited 0 having read no frame or stamp | `full_phase()` refuses unconditionally with the unimplemented-paint message while no painted claim exists (exit 3, both material states) | `test_v3_visual_audit.py::V3AuditStaticTest.test_full_phase_refuses_instead_of_inventing_frames` (no longer skips) |
| **D3** a `CB-V3-BEGIN…END` region was exempt from the shadow and gradient claims | `stylesheet_spans()` exempts only the shipped `CB_V3_CSS` literal; gate and audit share it | `V3GateBitesTest.test_a_marker_region_cannot_smuggle_a_shadow_or_a_gradient` |

## 6.2 Round 2 review correction (cbqa, D4)

| Defect | Correction | Test that closes it |
|---|---|---|
| **D4** `NoProtectionDeletedTest` counted test methods, so "delete the assertion, keep the method" left both the pin and the migrated module green | per-file `assert*` call floors recomputed from the AST (`ASSERT_BASELINE`, `SEAM_ASSERT_BASELINE`), asserted `>=`; method counts kept as a second, coarser floor | `NoProtectionDeletedTest.test_the_assertion_calls_never_drop_below_the_cp_003_baseline`, `test_the_seam_proof_itself_never_loses_an_assertion` |

## 6.3 Round 3 review correction (cbqa, D5)

| Defect | Correction | Test that closes it |
|---|---|---|
| **D5** the banned-token scans were case-sensitive and matched `box-shadow` exactly, so `-webkit-box-shadow`, `Backdrop-Filter: Blur(8px)` and `900MS` all reported PASS in the gate **and** the audit; an `ANIMATION: spin INFINITE` with no duration also passed | one set of normalised patterns in `tests/cb_source_scope.py` (`GLASS`, `SHADOW`, `SHADOW_PROPERTY`, `ANIMATION`, `DURATION` with `re.I`) imported by both gates, so a fix cannot land in one and leave the other green; shadow declarations are matched by property regex (vendor prefix + casing) and still require the `var(--cb3-elev-*)` value | gate: `V3GateBitesTest.test_each_defect_class_trips_the_named_claim` (4 new case/vendor variants); audit: `tests/test_v3_visual_audit.py::V3AuditNormalisationTest.test_the_banned_token_scans_are_case_and_vendor_normalised` replays `static_claims` on the same mutated stylesheets |

RED proven against the pre-D5 scans (temporarily reverting `GLASS`/`SHADOW`/`ANIMATION`/`DURATION` to
their case-sensitive forms): **2 tests, FAILED (failures=8)** — the four gate controls report
`AssertionError not raised` and the four audit controls report `'PASS' != 'FAIL'`; restored, 50
focused tests OK (skipped=14). The font rule is unchanged: the contract's `type.families.cjk` stack
(`"Noto Serif JP", …`) legitimately does not start with `CB `, so requiring every declaration to
lead with a `CB ` family would ban the contract.

## 6.4 Round 4 review correction (cbqa, D6)

| Defect | Correction | Test that closes it |
|---|---|---|
| **D6** the motion-table and `vw` scans used `\d+(\.\d+)?`, which is not the whole CSS `<number>` grammar, so `transition: opacity .9s`, `transition: opacity 1e3ms`, `transition-duration: .4s` and `padding: .5vw` were never seen — the declaration entered neither the motion table nor the escaped list, and the gate and the audit both reported PASS | one `CSS_NUMBER` grammar in `tests/cb_source_scope.py` (`\d+`, `\d+\.\d+`, `\.\d+`, optional `[eE][+-]?\d+`), shared by `DURATION` (the unit is still required) and `VW`; the gate and `scripts/v3-audit.py` import both, so the fix cannot land in one and leave the other green | gate: `V3GateBitesTest.test_css_number_spellings_trip_the_motion_and_vw_claims`; audit: `tests/test_v3_visual_audit.py::V3AuditNormalisationTest.test_css_number_spellings_fail_their_claim` replays `static_claims` on the same mutated stylesheets |

RED proven against the pre-D6 grammar (`CSS_NUMBER` temporarily reverted to `(?:\d+(?:\.\d+)?)`):
**2 tests, FAILED (failures=8)** — the four gate controls report `AssertionError not raised` and the
four audit controls report `'PASS' != 'FAIL'`; restored, the same 2 tests OK and the compliant
baseline still passes V-04…V-12.

## 7. Known gaps and rulings needed

- **V3 surfaces do not exist yet**, by design. Every v3 paint claim is armed and unproven; only the
  contract claims (V-01…V-03) are proven on this branch.
- **The v3 font rule is "first family"**, not "every family in the list": the contract's own stacks
  carry system fallbacks after `CB Display` / `CB UI`, so banning fallbacks would ban the contract.
  `@font-face` names are still required to start with `CB `.
- **The vignette may be a texture tile instead of a CSS gradient.** The gate restricts gradients
  rather than requiring one; the material tile path is legal and is checked by the screen capture,
  not here.
- **CP-002's review noted `round(ratio, 2)` as the comparison method for CP-003.** The v3 audit
  compares `round(ratio, 2)` to the floor exactly as the contract's own tests do; the contract's
  floors are already expressed with that precision tolerance.
- **Rubric §7 vs SPEC-V3 conflicts** (type names/sizes, measure, card radius) are routed in
  `t_3788bb37`; this card gates the contract values, which the owner amendment makes authoritative.
- **"Byte for byte" is enforced as canonical equality with the projection the literal carries.**
  The claim requires `modes`/`elevation`/`radii`/`type`/`motion`, requires every carried key to be
  equal to the contract, and requires the literal to equal the canonical serialization of that
  projection. `roles`/`version` may be omitted from the literal (the audit's V-01 covers the roles
  contract); §5.1 documents this reading so CP-020a is not misled. It is a deliberate interpretation
  of the card's "equals the contract byte for byte" wording, not an accidental weakening.


## CP-053 — the six `test_desktop_gm002_home` gates after the wide scene

Card: **CP-053**, branch `wt/cp-053-home-scene`. Master reverted `471e7c96` because these six gates
answered a compact-Home question with the wide scene's markup: the static harness never pinned a
viewport, so the route saw the SDK stub's default 1280 px and mounted the scene above the 1200 px
breakpoint. The fix is a re-point, not a deletion: the static harness now chooses the compact band
before `plugin.js` is evaluated (`globalThis.__CB_TEST_WIDTH__`, dynamic import), and the wide scene
gets its own home in `tests/test_desktop_home_scene_geometry.py`.

| v2 gate (kept, re-pointed) | v2 region it now reads | v3 counterpart |
|---|---|---|
| `test_shelf_shows_four_to_six_authored_cards_and_see_all` | compact shelf at 1049 px | `HomeSceneTest.test_narrow_home_keeps_its_shelf_and_see_all` |
| `test_shelf_row_declares_its_mask_state` | compact shelf mask | `HomeSceneTest.test_the_scene_is_used_only_at_the_wide_breakpoint` |
| `test_card_shows_real_next_step_and_mode_badge` | compact card | `HomeSceneTest.test_the_four_visible_titles_are_the_reference_strings` |
| `test_card_does_not_repeat_its_title_as_the_goal` | compact card | `HomeSceneTest.test_a_card_bar_reads_sections_not_a_rating` |
| `test_card_does_not_repeat_the_next_step_as_a_goal` | compact card | `HomeSceneTest.test_a_card_bar_reads_sections_not_a_rating` |
| `test_offline_says_so_without_inventing_courses` | compact empty/offline shelf | `HomeSceneTest.test_a_card_without_progress_says_so_and_invents_nothing` |

Nothing was dropped: each v2 assertion still runs on the compact band, and each wide-scene claim is
carried by a named v3 test. The scene's own paint claims are not tested here — they are the
`test_desktop_tokens`, `test_desktop_tokens_v3`, `test_desktop_type_scale`, `test_desktop_h152_motion`
and `test_desktop_gate_scope` gates, which pass unchanged on the same branch.
