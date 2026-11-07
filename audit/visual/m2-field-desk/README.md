# M2-U1 — the Field Desk home

Evidence for the course home that answers “what do I do next?” in one glance. This is a
product-line card, not release evidence: nothing here claims Coursebook is installable.

> **2026-11-07 — recaptured on the learning cockpit.** The desk was rewritten by `0fb9cff` and
> `54c39c5`. The live frames and `live-evidence.json` here were re-read in a fresh isolated window
> against a real backend on this tree, at the shipped plugin sha
> `638e0f5e18ff854f066368d6185826255e5b2df135f62962e27b11d9187d3684`. See
> [Recapture](#recapture--the-learning-cockpit-638e0f5e) below. The `01`–`12` static frames were
> rendered at M2-U1 and still show the pre-cockpit module; they are kept as the state-shape proof,
> not as a picture of the current desk.

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

The cockpit build adds, on the same route: the course name above the continued section, the
`sections / with evidence / due now` stat row, a numbered path with real state dots, a Field Notes
strip, and a two-column layout at wide widths that stacks Continue → Path on a split window. It adds
no RPC method and no new visual language: same tokens, same `Panel`/`Button`/`Loader`/`ErrorState`
components.

## Files

| File | What it proves |
|---|---|
| `01-real-light-wide.png` … `07-real-no-estimate-dark.png` | The M2-U1 desk at 1280 and 460 px, light and dark, 100 % and 200 % text, with the drawer open and with no recorded estimate. Static render of the module as it was at `5928593`; not the cockpit. |
| `08-empty-light.png` | No courses: first run, real create/import actions, no sample course. Static render, M2-U1. |
| `09-loading-dark.png` | The desk’s own loader. Static render, M2-U1. |
| `10-error-light.png` | A failed `library.list`: error code, retry, and no empty-course substitution. Static render, M2-U1. |
| `11-backend-off-light.png` | The route’s real `BackendUnavailable` screen. Static render, M2-U1. |
| `12-keyboard-focus-460.png` | Four `Tab` presses land on the current path row (`aria-current="step"`) with a visible focus ring at 460 px. Static render, M2-U1. |
| `evidence.json` | M2-U1 per-frame DOM measurements: tokens painted, section/estimate/last-touched text, path states, overlap count, overflow, table count, unnamed buttons, active element. |
| `live-01-real.png` | **Live** cockpit, 2026-11-07, sha `638e0f5e…`: course name, Continued section, `4 sections / 1 with evidence / 0 due now`, four-row path with one `aria-current` row, 3 Field Notes, All courses (3 of 20) — every value from stored rows. |
| `live-03-sources-open.png` | **Live** drawer opened on the continued section: six real source rows from `lesson.page` (Marugoto coursebook, teacher FAQ, Wiktionary 好き/愛する, and two model-assessed pages), one marked `stale`. |
| `live-02-backend-off.png` | **Live** backend off: the route’s own “Coursebook needs its agent plugin” screen with `Open Capabilities` / `Check again`, plus the refused call (`503: connect ECONNREFUSED 127.0.0.1:44291`). |
| `live-04-empty.png` | **Live** empty profile (second isolated home with no Coursebook database): first run with the real goal / shared course / syllabus actions. |
| `live-05-loading.png` | **Live** desk loader while `library.list` is held for 6 s; chrome (header, tabs, New course) intact, and the same window reaches `ready` when the read lands. |
| `live-evidence.json` | The live measurements at sha `638e0f5e…`: tokens actually painted, Continue/path/stats/notes counts, drawer state, overflow, table count, unnamed route controls, and the rig commands. |

## Recapture — the learning cockpit (`638e0f5e`)

Run on 2026-11-07 against this worktree (`wt/h61-field-desk-evidence`, base `d0ec20d`).

```
# 1. fresh isolated state: disposable home + userdata copied from an existing test home,
#    with home/plugins/coursebook and home/desktop-plugins/coursebook/plugin.js materialised
#    from this checkout (sha 638e0f5e… verified after the copy).
S=~/.hermes/coursebook-test-h61fd-1789000000

# 2. real backend on the course-data home, and a second one on a course-free home
COURSEBOOK_TEST_HOME=$S/home CB013_PORT=44291 bash scripts/cb013-live-backend.sh
COURSEBOOK_TEST_HOME=~/.hermes/coursebook-test-h61fd-empty-1789000000/home/home \
  CB013_PORT=44292 bash scripts/cb013-live-backend.sh

# 3. transport in front of both (loopback only): forwards 44281 -> 44291/44292,
#    refuses for the backend-off frame, delays only library.list for the loading frame
CB_PROXY_PORT=44281 CB_PROXY_TARGET=http://127.0.0.1:44291 \
  node audit/visual/m2-field-desk/recapture/h61-proxy.mjs

# 4. the isolated Desktop window
COURSEBOOK_TEST_STATE=$S CB013_CDP_PORT=9361 bash scripts/cb013-live-window.sh

# 5. capture driver: navigates #/coursebook, gates each frame on
#    [data-cb-desk], measures computed styles, and writes the PNG + live-evidence.json
CB615_PROXY_STATE=/tmp/h61-proxy-state.json COURSEBOOK_TEST_STATE=$S \
  node audit/visual/m2-field-desk/recapture/h61-capture.mjs
```

The proxy is a capture transport, not a fixture: it never rewrites a Coursebook response, so every
row, count and token in the frames above came from the real backend. The 6 s delay exists only to
hold the desk’s own loader on screen long enough to photograph; the backend-off frame refuses the
call at the transport and leaves the host’s gateway link up, which is why the route paints its own
`BackendUnavailable` screen instead of the host’s “CONNECTING” splash.

Measured in `live-evidence.json`:

- tokens: `--cb-paper #141312`, `--cb-paper-raised #1e1c19`, `--cb-ink #f2ece0`,
  `--cb-ink-soft #b5aa97`, `--cb-rule #3b372f`, `--cb-accent #9db5ee`,
  `--cb-accent-soft #232b3c`, `--cb-field #9cba87`, `--cb-ochre #d7a94e`, `--cb-coral #e38a76`
  (dark scope; the scope attribute is `data-cb-scope="dark"`).
- ready frame: `data-cb-desk="ready"`, `Section 2 of 4`, `≈ 10 min`, `Last touched 14 hr ago`,
  `4 SECTIONS / 1 WITH EVIDENCE / 0 DUE NOW`, 4 path rows, 1 `aria-current`, 3 Field Notes,
  3 courses listed of 20; `scrollWidth == clientWidth == 1280` (no horizontal overflow), 0 tables.
- sources frame: `data-cb-sources-drawer="open"`, 6 source rows.
- empty frame: `data-cb-desk="empty"`, no course rows, first-run actions only.
- loading frame: `data-cb-desk="loading"`; after the delayed read the same window reports `ready`.
- 0 unnamed controls inside the route in every frame.

## Honest limits

- The `01`–`12` frames are a static render of the M2-U1 module in Chromium: no backend, no chat,
  no RPC. They predate the cockpit rewrite and are kept for the state matrix only. The cockpit’s
  live states are the `live-*` frames.
- The live frames used disposable isolated rigs (`~/.hermes/coursebook-test-h61fd-1789000000`,
  backend 44291; `…-empty-…`, backend 44292) copied from an existing test home; no operator profile
  or gateway was touched. The window is the dev app on Electron with CDP on 9361.
- The ready and drawer frames were captured at an emulated 1280×1500 CSS viewport so the whole
  cockpit fits one frame; the window’s own split width is 941 px, where the layout stacks with
  Continue and Path first. Narrow-width and 200 % text for the cockpit are not re-proved here — the
  `460 px` / `200 %` evidence for this module is the M2-U1 static set plus the `field-desk-*-460-*`
  frames in `audit/visual/m4-visual/audit.json`.
- The loading frame is held open by a transport delay, not a slow backend; it proves the loader the
  desk paints while `library.list` is in flight, not backend latency.
- The screenshots are single frames; motion is functional-only and the desk has no transitions.
- Focus ring in `12` is the browser/host ring: the plugin sets no outline of its own.
