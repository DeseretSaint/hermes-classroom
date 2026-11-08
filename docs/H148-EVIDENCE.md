# H-148 — Path and checkpoint truth: evidence

> Superseded for geometry and row content by H-177 (`docs/H177-EVIDENCE.md`): the same honest data
> now renders as a continuous trail (curved route, Start/Course end, gate diamonds, one detail line
> for current/next) instead of a straight spine with a `<details>` disclosure under every row.

Base: `66ac373` (master). Branch: `wt/h148-path-truth`. Live surface: the isolated Hermes Desktop
window (`~/.hermes/coursebook-test-h148-000806`) against the isolated backend on `127.0.0.1:44219`
(cb.rpc v14, plugin `desktop/plugin.js` sha256 `824e02767c7bb376849c9861903752f243c34b6b3e0caf8af95436756912248c`).
Course: "Japanese affection and register — an L0 demonstration classroom", 4 objectives, 0
independent evidence, 3 due, 1 overridden.

## What changed

- `PathPreview` → `CheckpointPath`: every objective is a real node (no slice, no “more sections”
  footer). Current 56 px / next 40 / done 28 / future 28; compact (route < 620 px, including 460)
  44 / 32 / 24 / 24. Current carries `aria-current="step"` and the accent ring; every node is a
  button into its section, with an accessible name `Checkpoint N: <title>, <state>, <check>`.
- `check_state` is shown on the marker (`data-cb-path-marker-check`) and as a learner word
  (`No check yet` / `Check open` / `Check closed` / `Check replaced`). The objective state word is
  always present. `overridden` stays its own word and is never counted as evidence.
- Current + next nodes expand by default; every node has a native `<details>` disclosure with the
  evidence target in learner words, the committed attempt count and the last opened time.
- One evidence caption (`No evidence yet` / `N of M sections with evidence · D due`); the duplicate
  plate caption and the Overview plate caption are removed. The route consumes the measured
  `routePad` instead of the unused value beside a window-derived class.
- `CoursePath` truth: one segment per objective up to 12 (larger courses show the count only); no
  `current` segment; `done` only for evidence held, `due` only when due, `quiet` otherwise. Zero
  evidence paints no accent and the caption says `No evidence yet`.

## Live measurements (rendered DOM, not source)

`scripts/h148-capture.mjs` calibrates `Emulation.setDeviceMetricsOverride` against
`window.innerWidth`, collapses the host sidebars, and refuses to capture unless the Coursebook route
is mounted. Output: `docs/h148-shots/measurements.json`.

| width | route width | current | next | done | future | overflow (page / route) |
|---|---|---|---|---|---|---|
| 1049 | 1022 | 56 | 40 | 28 | 28 | 0 / 0 |
| 900 | 872 | 56 | 40 | 28 | 28 | 0 / 0 |
| 460 | 460 | 44 | 32 | 24 | 24 | 0 / 0 |
| 460 @ 200% text | 460 | 44 | 32 | 24 | 24 | 0 |

Other live facts at every width:

- `pathCaption`: `No evidence yet · 3 due`; the word `Overridden` is present on node 4 and
  `desk.settled` is 0 — overridden is not evidence.
- 4 node buttons, 4 focusable; exactly one `aria-current="step"`; labels carry state and check
  words; details open for nodes 1 and 2 only.
- Keyboard: real `Tab` presses move `Checkpoint 1 → its Details → Checkpoint 2 → its Details →
  Checkpoint 3`; the focused node paints a visible ring.
- Clicking `Checkpoint 3` opens the real section surface (`Section 3 of 4 — Recall the intimate
  declaration in a new context`), so a node is a destination, not a decorative mark.
- Every `CoursePath` row on the desk reports `background: var(--cb-rule)` on every segment, with
  captions `No evidence yet` / `No sections yet`. No accent segment at zero evidence (ENG-D1).

Screenshots: `path-1049.png`, `path-900.png`, `path-460.png` (viewport),
`path-{1049,900,460}-section.png` (the path itself), `path-460-text200.png`,
`path-1049-keyboard-focus.png`, `shelf-zero-evidence-1049.png`.

## Tests

- `python3 -m unittest tests.test_desktop_h148_path_truth -v` — 13 tests: zero-evidence truth,
  one segment per objective, size helper 56/40/28 and 44/32/24, node kinds, every node a
  destination, one current, `check_state` on marker, current+next expanded, one evidence count,
  overridden not evidence, no lock/star/percentage/XP/streak/cumulative, empty course.
- `python3 -m unittest discover -s tests -p 'test_desktop_*.py'` — 472 tests, OK.
- The H-155 audit repro, with its `expectedFailure` decorator removed locally:
  `test_zero_evidence_path_paints_no_reached_segment` — OK.
- `bash scripts/validate-plugin.sh --worktree` — release gate 4/4 on `66ac373`.

## Merge notes for the reviewers

These pinned expectations describe the old behaviour and must be updated when the branches meet;
they are not regressions in this diff:

- `wt/h155-engagement-audit` `test_course_path_clamps_unreadable_and_hostile_summaries` expects
  four `empty` segments for a zero-objective course; this card deliberately draws none. Its
  caption regex also predates the card's `No evidence yet` copy.
- `wt/h146-classroom-rail` `test_path_nodes_read_only_recorded_states_and_invent_no_gate` forbids
  the string `Checkpoint 1`; H-148 now uses `Checkpoint N` as the accessible name by design, and
  H-146a/b own the remaining rail/focus work.

No backend, contract, pack or migration file changed.
