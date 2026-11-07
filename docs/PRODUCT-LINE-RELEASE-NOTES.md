# Product-line notes after 0.1.0

Status: a mapping document for a product line in progress. **This is not a release.** Nothing here
was tagged, published, pushed to a public remote, opened as a catalog pull request or submitted to
the contest. `docs/SUBMISSION.md` §0 is unchanged and still closed. The 0.1.0 release record in
`docs/CB017-RELEASE-VERIFICATION.md` describes the commit `29bede7`; it was not re-run on this tree
and is not replaced by anything below.

Written on branch `wt/m4-product-docs`, base `master` at `d28e7e3` with `wt/m4-visual-regression`
(`2b37b5b`) merged. The commits named are where the work became reachable on that branch, not
release pins.

Purpose: one place where each phase of `docs/VISUAL_MEDIA_PLAN.md` §10 points at the commit that
carries it, the evidence that was actually produced, and the part that is still gated.

## Phases

| Phase | Commit | What exists on this branch | Evidence | Still gated |
| --- | --- | --- | --- | --- |
| **M0** — media truth | `3cead45` (merge of the host media slice) | `HostMedia` adapter over `ctx.dispatch_tool`, lesson-post generation, content-addressed cache, `/media/{artifact_id}` preview route, inline image/audio renderer with text equivalents and degraded states | `docs/M0-MEDIA-PROBE.md` — one real host image (`sha256 193c10f4…f15036`) and one real host MP3 (`sha256 9772e2d1…f64f3d9e`); `tests/test_media_generation.py` | A live lesson-pane generation on the default gateway waits on the operator gateway restart `t_6a32ffe9`. M0 itself is on `master`. |
| **M1** — capability policy, rubrics, LessonDocument, Textbook/Guided | `fdf9db2` (policy), `85eda4c` (v8 document projection), `cbc5483` (Textbook/Guided renderers), `97a6289` (writer authors `short`), `0a021a3` (M1-QA parity and answer-leak), `eee3b6b` + `5664dbe` (narrow-width decision and host patch basis) | Typed `LessonCapabilityPolicy` and rubric angles drive generation and validation; one validated `LessonDocument` serves Textbook and Guided; a view switch changes no revision, attempt or check; the old duplicate-checklist defect is closed; one checklist print | `docs/CAPABILITY-POLICY.md`; `tests/test_m1_mode_parity.py` (13 tests); `audit/visual/m1-mode-parity/`; `audit/visual/m1-guided-authoring/` (13 live frames, HTTP reads showing `state=complete`, `views.guided=true`); `audit/visual/m1-narrow-width/DECISION.md` | The narrow-width host change (`DeseretSaint/hermes-agent` branch `wt/host-narrow-rail`, `5900b6e7a0`) is **not merged and not installed**. The demo course still reports `textbook_only` until a real re-authoring run, which costs provider spend and was not approved. |
| **M2** — Field Quest, Field Desk, Field Notes | `5033f92` (Ink & Field Notes tokens and route shell), `f616c2e` (Field Desk), `b4e7639` (Field Quest), `05b829d` (Field Notes save/search/return) | `/coursebook` opens on the Field Desk (Continue, path, sources, all courses); Field Quest is a third lens over the same blocks with the same single check; Field Notes saves from a block, searches, and returns to the exact block id | `docs/INK-FIELD-NOTES.md`; `audit/visual/m2-field-desk/` (12 static frames plus 4 live isolated frames); `audit/visual/m2-field-notes/` (16 static frames plus 15 live frames, `live-evidence.json`); `audit/visual/m2-field-quest/` (14 static frames plus one live availability capture) | **No live Field Quest frame.** The stored lessons in every reachable home predate authored `short`, so `views.field_quest` is false there; Quest is proven by the shipped-module render, the parity suite and the live availability rule. The Field Desk sources drawer's populated state is proven statically only. |
| **M3** — Pronunciation Studio | `5314d5f` (M3-B1 bounded backend), `535da69` through `d28e7e3` (M3-U1 studio in the lesson) | Listen to the lesson's own narration artifact, record one bounded take, compare through the local recogniser with `word`-level output and `model_assessed` evidence, delete the take, save the result to the notebook, dispute path, practice-only state when no recogniser is configured | `docs/M3-PRONUNCIATION-UI.md`; `docs/PRONUNCIATION-SEAM.md`; `tests/test_desktop_pronunciation.py` (15 tests); `audit/visual/m3-pronunciation/` (14 frames plus a live route capture) | **No live studio walkthrough.** No existing section has a narration media child, so no block seats the studio and generating one is provider TTS spend this card did not authorise. The isolated backend the frames reached was an older wire and did not serve `/pronunciation/*`. The component states are proven by the frames and jsdom interaction tests, not by a live attempt. |
| **M4** — visual identity, procedure layout, truth gate | `5067b35` (M4-V2 procedure lens, merged at `e115aab`), `2b37b5b` (M4-QA visual/accessibility/media gate) | "Ink & Field Notes" token layer, reading rhythm, field-note media frames, responsive rail; a procedure lens with typed header, numbered steps, hazard callout, deterministic schematic rows and source permission; a 15-claim visual/a11y/media audit over the shipped module | `docs/M4-PROCEDURE-LAYOUT.md`; `tests/test_procedure_document.py` (15), `tests/test_desktop_procedure.py` (13); `audit/visual/m4-procedure/` (7 frames); `docs/M4-VISUAL-MEDIA-AUDIT.md` and `audit/visual/m4-visual/` (62 frames, `audit.json` sha256 `ac3538bd8b97fdf3cfff17f2bb4891a66416bf9c21df79ec30e9483d56e1bf70`) | No lesson prompt authored a `procedure` header at the time of this release note, so the lens was validator-and-renderer proof against a contract-valid fixture; H-06 has since added the authoring path (`lesson-prompt.v7`, `tests/test_procedure_authoring.py`) and the visual frames remain a static render. One low defect is open: a failed audio preview is typed `visual` in `data-cb-media-kind` (`t_acd97416`). The audit is a static render in a stubbed host, not a live Desktop capture. |

## What the 15 M4 claims do and do not cover

The claims record what the shipped module paints in headless Chromium: token-only paint, 0
plugin-authored contrast failures over 2,102 text nodes (worst authored 6.61:1), no clipped text or
horizontal overflow in 62 frames, 0 unnamed of 340 accessibility controls, no autoplay of 22 audio
elements, a text equivalent for every image and a transcript for every audio item, and a generated
illustration that an independent review confirmed carries no torque, sequence or clearance
authority.

They do **not** cover: a live Desktop, a real backend, `lesson.page` or the media route; host-theme
contrast inside host SDK primitives (reported separately and never counted as product evidence);
audible playback (attributes and decode only); a real screen reader (the Chromium AX tree only); or a
user-facing text-only preference, which does not ship. The `reduced motion` claim is trivially
satisfied because the module paints no transition or animation at all.

## Gates run for this documentation change

- `python3 -m unittest discover -s tests -t .` — 1039 tests, `OK`.
- `node --check desktop/plugin.js` — syntax OK (the file is unchanged by this branch).
- `bash scripts/validate-plugin.sh` on a clean export — recorded in the commit message.

## What a reader may conclude

That a documented product line exists, that each phase has a commit and a named evidence file, and
that the parts without live proof are listed as gated rather than implied. A reader may **not**
conclude that Coursebook is released, installable from the catalog, demo-recorded, or that its
product-line surfaces have passed a live end-to-end run.
