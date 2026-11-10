# GM-008 — Homework and adult take-home UI: live proof packet

Captured from the isolated Desktop window (`~/.hermes/coursebook-test-gm008`) against a real
`cb.rpc` v24 backend on `127.0.0.1:44331`, never the operator's window or profile.

- **plugin**: `desktop/plugin.js`, sha256 `931f719de62e542b4db11331057021eb21bbe4ae0fccce9d34647432467e4f85`
- **implementation commit**: the commit that carries this packet (branch `wt/gm-008-homework-ui`)
- **capture script**: `scripts/gm008-live-capture.mjs` (CDP 9361)
- **frames**: 10, each one `Page.captureScreenshot` of the live window

## What was driven, not mocked

1. The Home shelf card for **Japanese at home** was opened from the rendered `[data-cb-home-card]`.
2. The section page's own footer rendered `Take this with you` (`[data-cb-homework-action]`), which
   was clicked; the inline panel opened (`[data-cb-homework-panel="ready"]`).
3. The one-sentence context was typed into `#cb-homework-context` with the native value setter plus
   a real `input` event, then **Show me the task** was pressed.
4. `homework.create` proposed the task over the wire; the card on screen is that
   `homework.read` answer (`data-cb-homework-state="proposed"`).
5. **I did it** posted `homework.complete` with `actor: "learner"` and
   `expected_revision` = the task's own revision; the card repainted
   `data-cb-homework-completion="reported"` / `self_reported_done`.
6. **Save to notebook** posted `notebook.save` (`kind: personal_note`,
   `source_ref.homework_task_id`); the course Notebook tab then listed the task under
   **Taken with you** (`[data-cb-notebook-homework]`), read back through `homework.read`.
7. Parent Studio → **Homework** listed the same task through `homework.read`
   (`[data-cb-homework-studio]`).

## Frames

| frame | width | root text | task state | route overflow | banned words in panel |
|---|---|---|---|---|---|
| homework-course-home--1049--dark.png | 1049 | 16px | — | no | none |
| homework-lesson--1049--dark.png | 1049 | 16px | — | no | none |
| homework-panel--1049--dark.png | 1049 | 16px | — | no | none |
| homework-sheet--1049--dark.png | 1049 | 16px | proposed | no | none |
| homework-sheet--900--dark.png | 900 | 16px | proposed | no | none |
| homework-sheet--460--dark.png | 460 | 16px | proposed | no | none |
| homework-sheet--460--dark--200.png | 460 | 32px | proposed | no | none |
| homework-reported--1049--dark.png | 1049 | 16px | self_reported_done | no | none |
| homework-notebook--1049--dark.png | 1049 | 16px | self_reported_done | no | none |
| homework-studio--1049--dark.png | 1049 | 16px | self_reported_done | no | none |

md5:

```
a19abe7346333dd95202440b08d12e03  homework-course-home--1049--dark.png
fe0e36a473bdb09a35317ea474ac93a8  homework-lesson--1049--dark.png
dfad9758b458a48416f173682024ba18  homework-notebook--1049--dark.png
922614d330a18d58579329d839be4d87  homework-panel--1049--dark.png
b27b600d4f3d37a63f3c037db55135b5  homework-reported--1049--dark.png
f19d0746ee035605ee5881df31e6e287  homework-sheet--1049--dark.png
a729d5f017a0b4045720346ce6f53ef0  homework-sheet--460--dark--200.png
dfacc7cbe86c0ae1dfbec37b524a83a5  homework-sheet--460--dark.png
c91bb71e4715e0e5aa8ea879df8d9386  homework-sheet--900--dark.png
e9fce0109b4f61259deff28945330d4a  homework-studio--1049--dark.png
```

`live-evidence.json` is the machine-readable form: per-frame width, root font, overflow flag,
task state, and the panel's forbidden-word scan (`xp`, `grade`, `score`, `mastery`, `streak`,
`answer`) — all empty.

## What the window measured

- **Widths**: `window.innerWidth` settled at exactly 1049 / 900 / 460 after iterating
  `Emulation.setDeviceMetricsOverride` (this Electron build zooms the page, so the raw override is
  not the CSS width).
- **200% text**: `document.documentElement.style.setProperty('font-size','32px','important')`;
  the card reflows, the reading column does not scroll sideways (`overflow: false`).
- **Keyboard**: the action is a real `<button>`; focused programmatically plus a dispatched
  `focusin`, it is `document.activeElement` and carries `data-cb-homework-action`.
  The host paints the ring, so this build reports `outline: none 3px` on the button — recorded
  honestly rather than claimed as a plugin-drawn ring.
- **No grade/XP**: the panel's visible copy contains none of the banned words in every frame
  (the copy was corrected once: an earlier draft said "A report, not a grade", which the scan
  caught on the live surface and the frame set was re-captured).

## Known gaps / what this packet does not prove

- **No `homework.list`** in cb.rpc v24. The notebook and Parent Studio enumerate a task only
  because (a) the learner saved it to the notebook (`source_ref.homework_task_id`) or (b) this
  device's plugin storage indexed the id when it was proposed. Every row is then read with
  `homework.read`. A second device can see a backpacked task only through the notebook save, and
  a task that is proposed but neither saved nor indexed on that device is invisible. A backend
  `homework.list` is the honest fix; it is outside this card's file scope.
- **Staging**: `course.create`, `enrollment.create`, `plan.approve` and every `homework.*` call are
  on the real wire. The lesson page, its check row and its `homework` block were written
  directly into `gen_lessons`/`checks` because the rig has no model to author a page; the block
  itself is the reviewed L0 demo proposal (`coursebook.homework.demo_lesson_block`).
- **Print** is a local action: the backend's own `task.sheet.html` is loaded into an off-screen
  same-origin frame and `contentWindow.print()` is called. The frames prove the control is
  present and enabled; the OS print dialog itself was not captured (CDP cannot screenshot a native
  dialog). Download uses a local `Blob` + `<a download>`.
- **Palette**: dark appearance only (the rig's host is dark). The surface uses `--cb-*` tokens
  exclusively.
- The 460/200% frame shows the card from its top; the action row sits below the fold at that
  scale and is reached by scrolling (the route reports no horizontal overflow).
