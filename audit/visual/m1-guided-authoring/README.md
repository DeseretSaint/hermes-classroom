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

## Desktop frames — t_0a030589 (the screenshot gap closed)

The frames in this directory were taken by vellum on branch `wt/m1-guided-frame` (base `ef0a249`)
against the same isolated backend, so the *renderer* half is now a real capture rather than a claim.

| item | value |
|---|---|
| window | isolated Electron, CDP `127.0.0.1:9361`, `HERMES_DESKTOP_REMOTE_URL=http://127.0.0.1:44331` |
| rig | `~/.hermes/coursebook-m1v-212425` (throwaway copy of the M1-U1 rig) |
| plugin loaded | `desktop/plugin.js` sha256 `6934b8330aecd6b51ed8de8646b664525626ea3302a7a0238bc7623e06522924` |
| course opened | `Order coffee in Japanese`, enrollment `enr_4edc11e37dff47c4aa1e0200e00a3813`, objective `59a186e978db31bf` |
| served document | `doc_cb0c0af423236b90835b` — the first 20 hex of the served `content_hash` `sha256:cb0c0af423236b90835bcfff38aabb238203b4f535d0ced859d8d3cb4013d76f` |
| switcher | `data-cb-view-switcher="available"`, `Textbook`/`Guided` segments, `aria-pressed` flips on click |

| frame | what it shows |
|---|---|
| `01-textbook-dark` | Textbook, dark, 1280 px |
| `02-textbook-light` | Textbook, light, 1280 px |
| `03-textbook-dark-200pct` | Textbook at 200 % root text scale |
| `04-guided-dark` | Guided, dark, 1280 px, step 1 of 5 with the authored short |
| `05-guided-light` | Guided, light, 1280 px |
| `06-guided-dark-200pct` | Guided at 200 % root text scale |
| `07`–`09` | Textbook at 460 px viewport (dark, light, 200 %) |
| `10`–`12` | Guided at 460 px viewport (dark, light, 200 %) |
| `13-guided-practice-check-dark` | Guided step 3 of 5: the practice block carrying the authored `Check v1` |

`evidence.json` holds the measured DOM per frame (lesson view, document id, route/view width,
`horizontalOverflow`, theme class and computed body background, per-frame block roles and text
lengths), the observed switcher transitions (`guided → textbook → guided`, pressed states), the
five-step walk with each step's heading and body, and the keyboard probe (14 focusable controls in
DOM order; focusing the Guided segment lands on `Guided`).

### The pane-registration blocker was a navigation race, not a missing pane

`scripts/m1v-live-window.sh` against `127.0.0.1:44331` produced a window at `#/` with no
`[data-cb-route]` node precisely because the caller assigned `location.hash = '#/coursebook'` before
the plugin's route contribution had mounted; the router dropped it and the hash stayed `#/`. The
reproducible entry is the real UI path: click the sidebar `Coursebook` nav item (which only exists
once the route is registered), then the enrolled course row, then `Open this section`. The capture
script now does exactly that (`ensureRoute`), and it throws if the route still never appears.
Nothing in `desktop/plugin.js` needed a change, and none was made on the strength of the old
observation.

Two smaller rig truths found while doing this:

* the course page's section control reads `Open this section`, not `Open section`; the old capture
  script matched only the latter and would have failed with `no-section` even on a healthy pane;
* the Guided stepper resumes where the last viewer left it, so the step walk rewinds with the real
  `Back` button before recording; otherwise a run starts at `Step 5 of 5` and proves nothing.

### Narrow width, honestly

The 460 px frames emulate the viewport with the host chat zone still open. The host gives the route
its `22vw` floor (101–120 px measured) and the chat zone keeps the rest, so plugin labels truncate
while `horizontalOverflow` stays `false` in every frame. That is host width allocation, identical on
Textbook and Guided, and recorded as `routeWidth`/`viewWidth` rather than hidden. The left host
sidebar is collapsed for those frames so the number is not further diluted by chrome.

### Still open, and why

**The demo course itself still reports `textbook_only`.** Making
`Japanese affection and register — an L0 demonstration classroom` show Guided requires re-running
the real lesson job against a provider, which spends money, and the card owner has not approved that
spend. Nothing was backfilled and no paid call was made; this frame set proves the renderer and the
projection, on a real document over the real RPC, not a paid re-authoring of the demo course.

