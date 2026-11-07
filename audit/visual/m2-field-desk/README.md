# M2-U1 — the Field Desk home

Evidence for the course home that answers “what do I do next?” in one glance. This is a
product-line card, not release evidence: nothing here claims Coursebook is installable.

## What was built

The `/coursebook` route now opens on the Field Desk instead of the course list:

- **Continue** — one raised frame with the section to continue, the backend’s own next action,
  the estimate it already recorded, and the section’s last touch. The section is chosen from the
  contract, never from a title: a `resolve_review_due` next step picks the due objective, otherwise
  the row’s `current_objective_id`, otherwise the first objective without independent evidence.
- **Path** — the `course.outline` objectives as a route (ordinal, title, state word), with one
  `aria-current="step"` row. It is a list of buttons, not a table, and the summary counts states the
  backend reported (`N of M sections have evidence · K due`), not a vanity score.
- **Sources** — a drawer, collapsed by default, that reads `lesson.page` for the continued section
  only when opened. It names whose sources they are and shows the read’s loading, empty and failed
  states.
- **All courses** — a secondary list of three more courses plus the honest remainder count, and a
  button into the existing search/manage list (`CoursesView` is unchanged apart from a back link).
- **States** — loading, read failure (with the error code and a retry), no courses (first run),
  reconnecting/stale, and the route-level backend-off screen. No sample course, no invented
  minutes and no fabricated progress: an estimate the backend did not record is rendered as
  “Session length not recorded”.

The estimate is read, not derived: a pack-backed course uses the manifest objective’s
`estimated_minutes` (`pack.inspect`), a parent-authored course uses the brief’s `duration_minutes`
(`parent.brief.get`). No new RPC method was added.

## Files

| File | What it proves |
|---|---|
| `01-real-light-wide.png` … `07-real-no-estimate-dark.png` | The desk at 1280 and 460 px, light and dark, 100 % and 200 % text, with the drawer open and with no recorded estimate. Static render of the shipped module. |
| `08-empty-light.png` | No courses: first run, real create/import actions, no sample course. |
| `09-loading-dark.png` | The desk’s own loader. |
| `10-error-light.png` | A failed `library.list`: error code, retry, and no empty-course substitution. |
| `11-backend-off-light.png` | The route’s real `BackendUnavailable` screen. |
| `12-keyboard-focus-460.png` | Four `Tab` presses land on the current path row (`aria-current="step"`) with a visible focus ring at 460 px. |
| `evidence.json` | Per-frame DOM measurements: tokens painted, section/estimate/last-touched text, path states, overlap count, overflow, table count, unnamed buttons, active element. |
| `live-01-real.png` | **Live** isolated Desktop capture on a real backend: Continue, path and All courses from stored rows (`≈ 20 min` came from the course’s parent brief). |
| `live-03-sources-open.png` | **Live** drawer opened. |
| `live-02-backend-off.png` | **Live** backend stopped: the route’s backend-off state. |
| `live-04-empty.png` | **Live** empty profile: first run with real actions. |
| `live-evidence.json` | The same measurements, read from the live window, with the plugin sha256 that was loaded. |

## Honest limits

- The `01`–`12` frames are a static render of the shipped module in Chromium: no backend, no chat,
  no RPC. The rows are shaped like the contract’s responses, and the assertions are about what the
  view does with them (including refusing to invent an estimate or a course).
- The live frames used an isolated rig (`~/.hermes/coursebook-test-m2fd`, backend on 44281) copied
  from an existing test home, with the desktop plugin materialised from this commit. The `empty`
  frame used a second, course-free isolated home. Both are disposable test homes; no operator
  profile or gateway was touched.
- The live `real` frame’s drawer showed no recorded sources for that parent-authored section; the
  drawer’s populated state is proved by the static frame with contract-shaped source rows and by
  the render tests.
- The screenshots are single frames; motion is functional-only and the desk has no transitions.
- Focus ring in `12` is the browser/host ring: the plugin sets no outline of its own.
