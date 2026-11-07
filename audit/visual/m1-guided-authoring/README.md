# M1-U2 — the writer authors block `short`, so Guided is reachable end to end

Evidence for the card `t_7890cf1f` on branch `wt/m1-guided-authoring` (base `f3b70fb`, the M1-U1
renderer commit). Product-line work; it does **not** change the 0.1.0 release evidence and does not
claim Coursebook is installable.

## What changed

`lesson-prompt.v5` asks for an authored `short` beside every `deep` field
(`segments[].short`, `worked_example.short`, `learner_explanation_short`), and `lesson.page`
projects the validated authored page with `lesson_document.document_from_page` instead of the
linear segment rows. No wire field, no contract file, no column, no migration, no rewrite.

## Evidence in this directory

| file | what it is |
|---|---|
| `pipeline-evidence.json` | one lesson authored on disk by the real pipeline (`run_plan_job` → approve → `run_lesson_job`) and then read through `api.dispatch("lesson.page")`: `state=complete`, `views.guided=true`, one check on the practice block |
| `http-evidence.json` | the same two reads over the **real** plugin route (`POST /api/plugins/coursebook/rpc`) on `hermes serve --isolated`, whose `/runtime` names this worktree as `plugin_root` and reports `wire_version: 8` |

The rig home is a throwaway copy (`~/.hermes/coursebook-m1-guided-<HHMMSS>/home`) of the M1-U1 rig,
with `plugins/coursebook` re-pointed at this worktree. Commands:

```
M1U_RIG=<rig> python3 scripts/m1u-guided-probe.py     # author + dispatch read
hermes serve --isolated --port 44331 ...               # backend for this worktree
M1U_RIG=<rig> M1U_PORT=44331 python3 scripts/m1u-guided-http.py
```

Measured over HTTP:

* **pre-existing real course** `Japanese affection and register — an L0 demonstration classroom`,
  section `obj_70327ddd55a348858228a15590a664da`: `state=textbook_only`, `views.guided=false`,
  the server's `view_note`, two blocks (`orient`, `practice`) with `short: null`, and both durable
  segments still served. The stored v7 page was not rewritten.
* **newly authored lesson**: `state=complete`, `views.guided=true`, five blocks
  (`example`/`explain`/`practice`/`example`/`recap`) whose `short` values are the authored strings,
  and exactly one block (index 2, the practice block) claiming the check.

## What is honestly *not* proven here

* **No Desktop frame.** The M1-U1 window capture (`scripts/m1v-capture.mjs`) needs a window whose
  Coursebook pane is registered for this backend; the window I launched against the isolated
  backend exposed no `[data-cb-route]` node at all and its hash route would not change, so no frame
  was taken and none is claimed. The Textbook/Guided switcher and the Guided rendering are covered
  by `tests/test_desktop_lesson_views.py` against contract-v8 documents, and the backend half is
  now proven over HTTP; the missing link is only the screenshot, not the behaviour.
* **No provider call, no spend.** The lesson this directory proves was authored by the
  deterministic offline adapter the test suite uses (`tests.test_generation.FakeLLM` /
  `FakeSearch`) so that the proof records no invented provider output and no cost. The pre-existing
  real lesson in the rig predates `lesson-prompt.v5`; making *that* course show Guided needs a real
  re-authoring run, which costs money and was not run.
* Media: the rig database holds no media segments for these sections, so the no-media case is the
  live case. The degraded media text-equivalent block is not exercised here.
