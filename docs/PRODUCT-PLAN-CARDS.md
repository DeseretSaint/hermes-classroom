# Product-line card map

Created 2026-11-06 from `docs/VISUAL_MEDIA_PLAN.md`. This is the review index; the Kanban board
(`coursebook`) is the live state and the card body is the acceptance contract.

At creation: **81 done · 1 blocked (operator demo gate) · 2 ready · 14 todo · 0 running**, master
`4a33f2d`. The two ready cards are M1-P1 and M3-S1; every other card has an explicit parent and
will be promoted only when its parent completes. All cards use `worktree`, `max_retries=1`, and a
bounded `max_runtime`; workers commit to their branch and never merge to master. The supervisor
merges gated branches. Publication remains gated by `docs/SUBMISSION.md` §0.

| Phase | Card | Owner | Branch | Parents |
| --- | --- | --- | --- | --- |
| M1 | `t_c165db6f` — P1 capability policy | cinder | `wt/m1-capability-policy` | — |
| M1 | `t_40b55705` — P2 rubric angles | lattice | `wt/m1-rubric-angles` | P1 |
| M1 | `t_5e6523a3` — P3 policy integration | cinder | `wt/m1-policy-integration` | P1, P2 |
| M1 | `t_a2bb0b46` — P4 LessonDocument v8 | lattice | `wt/m1-lesson-document` | P3 |
| M1 | `t_d72c8a4c` — U1 Textbook + Guided | vellum | `wt/m1-textbook-guided` | P4 |
| M1 | `t_ff6ce87a` — QA mode parity | sentinel | `wt/m1-mode-parity` | U1 |
| M2 | `t_45b1acf6` — V1 Ink & Field Notes tokens | sable | `wt/m2-ink-field-notes` | U1 |
| M2 | `t_0c732822` — U1 Field Desk | vellum | `wt/m2-field-desk` | V1 |
| M2 | `t_d6bdfdde` — U2 Field Quest | vellum | `wt/m2-field-quest` | Field Desk |
| M2 | `t_fa9ada47` — U3 Field Notes | vellum | `wt/m2-field-notes` | Field Quest |
| M3 | `t_43ec5abc` — S1 STT seam spike | atlas | `wt/m3-pronunciation-seam` | — |
| M3 | `t_7fc18f4a` — B1 pronunciation backend | cinder | `wt/m3-pronunciation-backend` | P4, S1 |
| M3 | `t_873b4137` — U1 Pronunciation Studio | vellum | `wt/m3-pronunciation-ui` | U3, B1 |
| M4 | `t_e2b13c62` — V2 procedure renderer | vellum | `wt/m4-procedure-renderer` | U1 (M3), V1 |
| M4 | `t_26395337` — QA visual/accessibility | sentinel | `wt/m4-visual-regression` | V2 |
| M4 | `t_5025741e` — D1 product docs | harbor | `wt/m4-product-docs` | QA |

## What “in motion” means

- P1 and S1 run first. P1 defines the policy that decides when an image, narration, procedural
  schematic, verification checklist or rubric angle is appropriate. S1 settles whether a safe
  pronunciation STT path exists; if it does not, B1 blocks rather than inventing a score.
- Each dependent card merges its parent branch into its worktree before editing, then runs the
  full suite and a clean-export validation. A conflict or missing seam is a stop-and-report, not
  a workaround.
- UI cards are serialized through `desktop/plugin.js` so two workers cannot fight over the same
  surface. Backend/contract work is serialized through the policy/document chain.
- The visual plan is not a license to add media everywhere. The policy defaults to no media and
  requires the lesson’s evidence to justify it.

## Not in these cards

- No publication, release tag, catalog PR, or “installable” claim.
- No pronunciation score without a proven seam and a configured provider.
- No new child-facing chat; Parent Studio remains the parent’s authoring surface.
- No claim that an AI illustration is a measurement, procedure, sequence or safety authority.
