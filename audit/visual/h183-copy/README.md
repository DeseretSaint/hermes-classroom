# H-183 — truth sweep evidence

Renderer audit of the shipped Desktop module: the real component tree in jsdom, painted and
screenshotted in headless Chromium. No backend, no chat, no provider, no RPC.

- **before** = `desktop/plugin.js` at `d84cfc5` (the merged H-179 line this card started from)
- **after** = `desktop/plugin.js` in `wt/h183-truth-sweep` (`sha256 ac59766d…`)

Both modules were rendered with the same harness (`scripts/h183-copy-render.mjs`) and the same
fixtures, so a PNG pair differs only by the module under test.

## Frames

| surface | state |
| --- | --- |
| `first-run` | the start plate with create, import and syllabus available |
| `home` | the Field Desk with one active classroom and Continue |
| `lesson-empty` | approved plan, page not written yet (`not_started`) |
| `lesson-failed` | failed authoring, code `JOB_FAILED`, behind Technical detail |
| `settings` | the Home settings sheet, Haptics section included |
| `check-after/` | the Field Quest checkpoint (same check Textbook and Guided mount) |

Every surface is captured at **1049 light**, **460 light**, **1049 dark** and **1049 light at 200%
text**. The check surface is captured at 1280 light/dark, 460 light and 460 light at 200% text.
`check-before/` holds the committed frames from `audit/visual/m2-field-quest` (same harness, module
at `d84cfc5`) for the caption pair.

## What the pair proves

- First run and Home read the same in both modules; the sweep did not buy truth by adding noise.
- Empty lesson: "The lessons job has not run yet" → "This lesson page is not written yet", with the
  plan named as the owner and one action.
- Failed lesson: the learner reads "This lesson page could not be written"; `JOB_FAILED: …` now sits
  inside the `Technical detail` disclosure instead of the sentence.
- Check: "Hint and Show answer are not registered by this build yet" → "No hint and no shown answer
  are offered on this check. Work it out from the section text." The assist buttons stay absent when
  `lesson.assist` is not implemented.
- Settings before showed a disabled **Haptics switch**; after shows an availability note with no
  control (the checkbox is gone). Study companion and Session length keep their readers.

## Copy inventory

`python3 scripts/h183-copy-inventory.py` → `copy-inventory.json`. It strips `<details>` disclosures
and markup, then scans the painted text of every after frame for `lessons job`, `job`, `queue`,
`queued`, `next tick`, `revision`, `reconcile`, `plan-pending`, `JOB_FAILED`, `not registered`, ticket
labels (`H1xx`) and raw ids. Result: **all surfaces CLEAN**, exit 0. The only source-literal hits are
internal thrown messages, the operator-only surface and the create receipt's technical rows.

## Limits

- This is a renderer audit, not a live window. The live route is exercised by the desktop test suite
  (`tests.test_desktop_h183_copy_inventory`, `h147`, `h174`, `h86`, `h28`, `h151`) and by M4.
- The rig's `H103 live reject check` / `H103 live failure check` rows are **data**, not plugin copy:
  `docs/STORY-GAPS.md` G2 assigns demo-data hygiene to H-109. No plugin string can rename a course
  row without lying about what the profile holds.
- `sessionMinutes` is a parent-written plan, not a countdown (H-156); its reader is the Home and
  Parent Studio line, tested in `test_session_length_setting_reaches_the_home_line_it_claims_to_change`.
