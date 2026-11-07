# M1-U1 — Textbook and Guided renderers on the lesson document

Evidence for the card `t_d72c8a4c` on branch `wt/m1-textbook-guided`. Product-line work; it does
**not** change the 0.1.0 release evidence and does not claim Coursebook is installable.

## What the window shows

The isolated rig runs **this checkout** for both halves:

- backend: `hermes serve --isolated` on `127.0.0.1:44301`, `HERMES_HOME` = the rig home, whose
  `plugins/coursebook` symlink points at the worktree (`plugin_root` in `/runtime` confirms it,
  `wire_version: 8`);
- window: Electron on CDP `127.0.0.1:9351`, launched with `HERMES_DESKTOP_REMOTE_URL` so no
  `connections.json` or renderer LevelDB was edited.

The course is the real `Japanese affection and register — an L0 demonstration classroom` course in
that rig's database, opened through Courses → Textbook → Open section.

## Frames

| file | variant |
|---|---|
| `01-textbook-dark.png` | 1280 px, dark |
| `02-textbook-light.png` | 1280 px, light |
| `03-textbook-dark-200pct.png` | 1280 px, dark, root font-size 200 % |
| `04-textbook-dark-460px.png` | 460 px, dark |
| `05-textbook-light-460px.png` | 460 px, light |
| `06-textbook-dark-460px-200pct.png` | 460 px, dark, 200 % |

`evidence.json` records the measured DOM for each frame (block ids, roles, headlines, check
attachment, horizontal overflow, computed root font size, theme class). Every frame is gated on
`[data-cb-route]` having text, so a click that never landed cannot produce a plausible screenshot.

Measurements: no horizontal overflow in any variant (`scrollWidth === innerWidth`), the practice
block carries the only `[data-cb-block-check]`, and no separate `CURRENT CHECK` panel is rendered
next to the document.

## What is honestly *not* proven here

Every `lesson.page` this backend serves reports `state=textbook_only` and `views.guided=false`.
That is not a Desktop bug: the lesson authoring prompt writes `segments` only — nothing authors
the document's `short` or `blocks` — so the projection has no guided material to serve. The window
therefore renders the honest state the contract asks for ("Textbook only" + the server's
`view_note`), which is what frames 01–06 show.

The Guided renderer and the Textbook/Guided switcher are exercised against contract-v8 documents
in `tests/test_desktop_lesson_views.py`, which renders the shipped plugin module with real React
(`react-dom/server`); it asserts one block per step, `short` rather than `deep`, step progress, a
single check attached to the practice block, unchanged block ids across views, and the
textbook-only refusal. A live Guided screenshot needs the authoring seam; it is filed separately
rather than faked here.

Media: this database holds zero media segments, so the no-media case is the live case. The
degraded media text-equivalent frame is not reachable without generating an artifact, and is not
claimed.
