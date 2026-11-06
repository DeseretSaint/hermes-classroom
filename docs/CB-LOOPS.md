# CB-015 — the three human loops, as run

**Assembled by:** the build supervisor, from Vellum's live run evidence on `wt/t_fca01276`.
**Why assembled here:** Vellum's two worker runs on t_fca01276 both exhausted the 150-iteration
budget after producing the evidence but before writing this document or committing. The
`desktop/plugin.js` diff, the three evidence JSONs and the screenshots were taken unmodified from
that worktree and committed by the supervisor. Nothing in them was re-run, edited or reinterpreted.

**Candidate:** worktree `.worktrees/t_fca01276`, base `b476738` (merge of CB-049).
**Window:** one isolated Electron renderer over CDP, Japanese L0 demo course, dark theme, 1280×900.
**Evidence:** `docs/cb-loops-notebook.json`, `docs/cb-loops-quiz.json`,
`docs/cb-loops-textbook.json`, screenshots in `docs/cb-loops-shots/`.

## 1. What the loops proved

### Notebook — PASS

One pass, 19:06:37 → 19:07:06 UTC, every step recorded with expected vs actual:

| step | result |
|---|---|
| open a section | section page rendered, two "Save to notebook" controls |
| open the editor | dialog opens with a 2,457-char excerpt, empty personal note, tags field |
| type | note and tag accepted (`loop-proof-ci4cr`) |
| save | `notebook.save` commits, dialog closes, **focus returns to "Save to notebook"** (was `BUTTON||Courses` before) |
| search | exactly 1 entry matches the unique note marker |
| edit | inline editor prefilled from the saved row; save keeps one entry, v2 note shown, v1 gone, focus stays on the editor trigger |
| reload | after a full renderer reload the edited note and both tags survive; the original text stays gone |

### Textbook — PASS

Section open → switch to a second section → follow a reference from the notebook back to a section →
open the chat context → return → the section list and the reopened section's state are unchanged.

### Quiz — PASS

Grading is proven end to end: check v14 opens bound (`submitDisabled: true` until an answer exists),
a typed answer enables Submit, `attempt.submit` returns `Passed` with criteria feedback, the verdict
takes focus, and the attempt history renders under the section. Passing through Quizzes records 26
rows before the submission and 27 after, with the new row first (`Passed · Cold attempt · just now ·
B`); opening it shows the original answer and feedback read-only, and after a renderer reload the
same row is still first with the same verdict. Console: 0 errors and 0 key warnings.

The first capture of this loop was faulty in two ways, both repaired in the re-drive recorded in
`docs/REVIEW_CB015-quiz-list.md`: its attempt-list selector never matched the newest row ("just
now"), and its screenshot helper had no route gate. That file was superseded by a single-pass
re-recording with monotonic timestamps and a `run` block naming the window, plugin sha256 and base
commit.

## 2. Two product defects found and fixed in this diff

Both are in `desktop/plugin.js` and both blocked the loops from completing:

1. **Long written answers could not be graded (P1).** `attempt.submit` was sent
   `answer: { kind: 'text', text, selection: [text] }` for every answer, but `cb.rpc` v6 caps each
   `selection` item at 200 characters. Any answer longer than 200 characters was refused as
   `VALIDATION_FAILED` before grading ran. `attemptAnswer()` now sends `selection` only when the
   answer fits the cap, and always sends `text`.
2. **The verdict was wiped by the refresh (P1).** Committing an attempt refreshes the section and
   opens the next check version; the form's reset effect then cleared the verdict the learner had
   just earned. `resultCheck` now pins the graded check so feedback stays on screen until the
   learner acts, and the verdict panel takes focus so a keyboard user is not dropped on `<body>`.

Also in the diff: the notebook editor and the override dialog now use `FocusReturningDialog`, which
returns focus to the control that opened it (and, if that node was replaced, finds the same control
again by its label inside the plugin's own route root). A second mechanism, `useReturnFocus(open)`,
briefly ran alongside it on `NotebookSaveDialog`; it was removed in t_74066a11, leaving
`FocusReturningDialog` as the only focus-restoration path.

## 3. Known friction, recorded and not fixed

- A notebook entry renders its full excerpt unclamped, so the personal note and its actions sit
  several screens below the excerpt. Two screenshots needed programmatic scrolling.
- The Textbook reopens a section by position after returning from a reference; the section identity
  is not retained in the URL.

The console key warnings this section used to list were resolved in **t_74066a11**
(`docs/REVIEW_CB015-quiz-list.md`): both `<li>` lists pass their key as `jsx()`'s third argument, the
last key-inside-props site (`ContractList`) was fixed, and the re-recorded quiz loop reports 0
console errors and 0 key warnings.

## 4. Gates on the merged tree

`python3 -m unittest discover -s tests -t .` and `node --check desktop/plugin.js` are run by the
supervisor at merge time; their results are recorded in the merge comment on t_fca01276, not in this
file, because this file must not claim a gate result it did not see.
