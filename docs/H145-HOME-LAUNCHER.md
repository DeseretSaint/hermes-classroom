# H-145 — Home launcher evidence

Branch `wt/h145-home-launcher`, base `c6b658e`. Live frames: `docs/h145-shots/` (10 PNG) and
`docs/h145-shots/h145-facts.json`, captured from the isolated Electron rig
(`~/.hermes/coursebook-test-h145`, CDP 9361, remote backend `127.0.0.1:44219`) with
`scripts/h145-capture.mjs`. The window's own Appearance setting chose light/dark; the capture
records the mode the plugin actually painted (`data-cb-scope`), not a forced attribute.

## What changed in `desktop/plugin.js`

- **Wordmark, not seal.** `CoursebookWordmark` is an uppercase serif wordmark (caption size,
  `--cb-ink-soft`) above the page title. The route header no longer renders `SurveyMark`; the seal
  component and every remaining render site (first-run plate, Continue plate, course cover, Course
  Detail hero) are gone. `cbSealStation` stays exported for the visual-identity probes.
- **One display h1.** The page title is `CB_TYPE.display` (clamp 2.25–2.5 rem) in the serif voice;
  it is the only `h1` on the route. An open course reads `Course` (CourseDetail keeps the course
  name at h2), so no page label repeats a card title.
- **Home first.** `DESTINATIONS` is Home, Courses, Library, Parent Studio; the remembered default
  is Home. `destination === 'courses'` now always renders the all-courses catalog
  (`CoursesView`); the launcher (`FieldDesk`) is the Home branch. `coursesMode` is deleted.
  "Back to the Field Desk" and "All courses" still return to Home / Courses respectively.
- **One Continue surface.** The plate keeps course title, section title, position, the recorded
  estimate (or its explicit failure), last-touched, one primary and one secondary. The duplicate
  `Next ·` sentence and the 64 px stamp are removed at every width.
- **Measured gutter.** `routePad` (0.7 rem below a 760 px route) now actually applies to the route
  root; the unused declaration is gone.
- **ENG-D4/D5.** `plural(n, one, many)` is the one count rule. The duplicated plate caption on the
  path is dropped; the tally caption remains and reads "1 of 1 section with evidence".

## Live facts (1049 / 900 / 460)

| frame | h1 count | h1 text | h1 size | seals | Continue cards | `Next ·` | route gutter | horizontal overflow |
|---|---|---|---|---|---|---|---|---|
| light 1049 | 1 | Home | 37.75 px | 0 | 1 | 0 | 11.2 px | 0 |
| light 900 | 1 | Home | 36.70 px | 0 | 1 | 0 | 11.2 px | 0 |
| light 460 | 1 | Home | 36.00 px | 0 | 1 | 0 | 11.2 px | 0 |
| dark 1049 | 1 | Home | 37.75 px | 0 | 1 | 0 | 11.2 px | 0 |
| dark 900 | 1 | Home | 36.70 px | 0 | 1 | 0 | 11.2 px | 0 |
| dark 460 | 1 | Home | 36.00 px | 0 | 1 | 0 | 11.2 px | 0 |
| 200% light 1049 | 1 | Home | 72 px | 0 | 1 | 0 | 22.4 px | 0 |
| 200% light 460 | 1 | Home | 72 px | 0 | 1 | 0 | 22.4 px | 0 |
| 200% dark 1049 | 1 | Home | 72 px | 0 | 1 | 0 | 22.4 px | 0 |
| 200% dark 460 | 1 | Home | 72 px | 0 | 1 | 0 | 22.4 px | 0 |

The route pane is narrower than the window when the chat and explorer are open, so the measured
gutter is the 0.7 rem branch in every frame — which is the point of measuring the route.

Destination nav order in every frame: `home → courses → library → studio`, with `aria-current="page"`
on Home. Keyboard: the skip link is the first stop and reveals itself (`skipRevealed: true`); the
destination nav takes a visible focus ring (`auto 1.1 px` in light, `rgb(238,238,238)` in dark);
SDK buttons take the 3 px focus shadow. Real Tab traversal is recorded in the run log.

## States

Loading, failed-read, stale/offline, empty/first-run and detached states are unchanged by this
card and are covered by `tests/test_desktop_field_desk.py` (`data-cb-desk` loading/error/empty,
`libraryStatus` error never renders the empty welcome). Home's failed read still says the desk
"will not show an empty course in place of a failed read".

## Gates

- Q1 First-screen grasp: wordmark + Home + one Continue; the primary is "Review the plan" on the
  live row (the demo row's own next step) and the secondary "Open the section".
- Q2 One primary: one lamp-filled control on the plate; the estimate retry is a text control.
- Q3 Path legibility: `PathPreview` still lists every node with its state word and current step.
- Q5 Authored visual: no seal anywhere in the route; the wordmark is type; Continue is the only
  raised plate.
- Q7 State completeness: see above.
- Q12 Human proof: frames at three widths and both modes, plus 200% text, exist in `docs/h145-shots/`.

## Limits / residual risk

- The live rig's most recently updated course is `H103 live reject check` (rig data, not this
  card's copy). H-109 owns demo-data hygiene; the surface is honest about that row (it shows the
  real plan-review next step and a failed estimate with Retry).
- `test_m4_visual_audit.test_evidence_is_not_stale_against_the_shipped_module` fails until
  `python3 scripts/m4v-audit.py` re-pins the M4 captures to this `plugin.js`. That evidence pass is
  outside this card's capture and was not run here.
- `test_conversation_practice` / `test_lesson_skills` reported loader errors under one concurrent
  discovery run and pass when run alone; re-run the suite serially before quoting a failure count.
