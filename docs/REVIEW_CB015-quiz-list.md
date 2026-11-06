# CB-015 quiz loop — attempt list, timestamps and the two key warnings

**Card:** t_74066a11 (split from t_fca01276). **Branch:** `wt/cb-loops-quiz-list` off `22a9180`.
**Owner:** Vellum. **Window:** isolated Electron renderer, CDP `127.0.0.1:9341`, remote backend
`127.0.0.1:44219` (cb.rpc wire v6), Japanese L0 demo course.
**Evidence:** `docs/cb-loops-quiz.json`, `docs/cb-loops-shots/20-…26-…png`.

## 1. The attempt list was never empty

The previous capture recorded `"rows": []` for the `quiz-list` step while the graded step's own
segment listed five attempts. The list extraction was:

```js
[...root.querySelectorAll('button')].filter(b => /\d{1,2}:\d{2}|ago/.test(b.innerText))
```

`whenLabel()` renders the newest attempt as **"just now"**, which matches neither a clock time nor
`ago`. Every row older than a minute matches; only the row this loop had just created never did.
So the selector found zero rows and the step reported "attempt list empty" against a list that was
rendering 23 attempts.

The re-drive counts rows from their own **Open attempt** control and parses each row container, so
the newest row is included by construction. It also records the list **before** grading, so the
assertion is a delta rather than an impression:

| step | result |
|---|---|
| `list-before` | 26 attempt rows before the submission; newest `Passed · Cold attempt · B` |
| `graded` | Check v14 → `Passed`, criteria feedback, objective complete |
| `quiz-list` | 26 → 27 rows; new newest row `Passed · Cold attempt · just now · B`; verdict matches the grade |
| `review-open` | newest row opens read-only, original answer `B` shown, no Submit/answer field |
| `review-persistence` | renderer reload → still 27 rows, newest still `Passed · Cold attempt · B` |

`active` is now the course view picker (`BUTTON:cb-view-picker`, aria-label `Course view: Quizzes`)
rather than host chrome, because the loop drives the view through the real "Course view" menu
(`role=combobox` → `role=option`) instead of calling `.click()` on an off-screen segmented button.

## 2. Route gate on every screenshot

`shot()` in `scripts/cb-loops-lib.mjs` now refuses to write a capture unless
`document.querySelector('[data-cb-route]')` exists **and** has non-empty text. A snapshot that
shows only shell chrome throws instead of producing a misleading file. All eight shots in this pass
passed the gate on `data-cb-route="/coursebook"` with non-empty route text.

## 3. Timestamps

`docs/cb-loops-quiz.json` was re-recorded in one pass. Every step is appended by the same
`makeLog()` instance, and `finished_at` is written after the last step:

```
started_at  19:54:16.122Z
check-open  19:54:27.033Z
list-before 19:54:30.279Z
…           19:54:35 … 19:54:43
reloaded    19:54:57.740Z
console     19:54:57.761Z
finished_at 19:54:57.762Z
```

The file's `run` block names the single run it came from: CDP port, plugin sha256, base commit and
backend wire version. No step in this file is carried over from an earlier run.

## 4. The two React key warnings

Console capture previously subscribed to `Runtime.consoleAPICalled` **type `error` only**, so the
warning class was never in the evidence at all. `attach()` now records both `error` and `warning`,
and the console step independently matches React's key-warning text.

Findings and fixes in `desktop/plugin.js`:

- Both `<li>` lists (AttemptControls criteria, Quizzes review criteria) already passed the key as
  `jsx()`'s third argument at `22a9180`; the run reports 0 key warnings and shows criteria rows
  rendering under the verdict.
- The remaining key-inside-props site in the file was `ContractList`: `jsx(StatusRow, { key:
  entry.id, … })`. A `key` inside the props object is exactly what React reports as "A props object
  containing a key prop is being spread into JSX", and it also leaves the element without a
  reconcilable key. It now passes `entry.id` as the third argument.

Final console step: **0 errors, 0 key warnings, 0 other plugin warnings**; the only two warnings in
the renderer are Electron's own security notice about the unpackaged dev window (counted separately
as `hostWarnings`).

## 5. One focus-restoration mechanism

`8614e88` added `useReturnFocus(open)`; the loops branch added `FocusReturningDialog`. Both were
running on `NotebookSaveDialog`, restoring focus to the same opener. `useReturnFocus` was removed
and `FocusReturningDialog` kept: the wrapper also owns the label fallback for an opener that the
section refresh replaced, and every dialog in this file already uses it. The remaining call sites
are the five dialogs plus `NotebookSaveDialog`, all through one path.

## 6. Gates on this branch

| gate | result |
|---|---|
| `node --check desktop/plugin.js` | OK |
| `python3 -m unittest discover -s tests -t .` | 664 tests, OK |
| `node scripts/cb015-hygiene.mjs` | 13 rules, **0** findings |
| quiz loop console | 0 errors, 0 key warnings |
