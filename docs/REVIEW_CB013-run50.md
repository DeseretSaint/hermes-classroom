# CB-013 run 50 — live pane evidence, and the bind rule that was blocking every section after the first

Branch `wt/cb-013-sable` @ `2d3847d`. Nothing pushed. Root profile untouched.

## What is now proven in the live Desktop window

Window: Electron 1685431 (CDP 9337), user-data `~/.hermes/coursebook-test/userdata`,
`HERMES_HOME=~/.hermes/coursebook-test/home`, connection `kind:"remote"` → `127.0.0.1:44219`.
Backend: `hermes serve --isolated --port 44219` on that home with `HERMES_COURSEBOOK_SINGLE_HOME=1`
and `HERMES_DESKTOP_DEV_SERVER=http://127.0.0.1:5174` (CORS).

| Step | Evidence |
|---|---|
| Route mounts | `#/coursebook` renders *Coursebook / A governed learning workspace…* with Courses, Library, New course (**screens 01, 02**) |
| Course reads the launch home | Japanese L0 course card, `enr_d3e84830f3f14b9eb25ec92a87574ff4`, 4 objectives — the single-home pin + `profile=` spelling (run 49) |
| Course detail | objective, review queue ("Nothing due"), recent event, provenance, export note |
| Textbook + teaching segments | Lesson 1/2 segments render with romaji, tables, **Save to notebook** |
| Pane, detached | *"This section's chat binding is detached. Submit stays disabled until it is reconciled."* + Reattach / Start a fresh run — `#cb-attempt-answer` `disabled=true` (**05a/10-pane-detached.png**) |
| Pane, active + awaiting_input | after the fresh run's chat turn, binding row `bind_064fe0d6…` `status=active`, textarea enabled (**05a-pane-awaiting-input.png**) |
| Graded attempt | `attempt.submit` from the pane → `att_1b67410e2fbc49c48d21afbdaff2a6ce` verdict `pass`, evidence_class `cold`; pane shows *Passed · Cold attempt* and objective state `independent_evidence` |

Provider: the test home was given a **copy** of `~/.hermes/auth.json` (mode 600) plus a `model:`
block, because a fresh chat has no durable stored id until a real turn runs and the bind seam
refuses a runtime id. That copy must be removed by `scripts/uninstall-local.sh` (it is not yet
added there — follow-up work).

## The blocker this run found and fixed

`POST /sessions/bind` refused a second section's chat with `enrollment_already_bound` (one active
binding per **enrollment**). Because a passing attempt leaves the objective at `independent_evidence`
with `next_action: continue` and its lesson run still `active`, no later section could ever be
bound: Submit stayed disabled on sections 2–4, so `graded`/`needs_retry`/`overridden` were
unreachable from a live Desktop.

`coursebook/bindings.py` now:
* refuses a second chat only for the **same section** (`enrollment_already_bound`);
* when the learner moves to a **different section of the same course**, detaches the previous
  binding (`status='detached'`, revision+1, row kept) and binds the new chat;
* when the **same chat** is re-attached to another section (Reattach), moves the existing row to
  the new run/objective instead of demanding a second row;
* cross-course migration is still refused (`session_already_bound`).

Tests: `tests/test_session_bind.py` +2 cases (supersede, move) — 15/15; together with
`tests/test_single_home_scope.py`, 23/23 pass. `node --check desktop/plugin.js` OK.

## Not claimed

* `needs_retry` and `overridden` pane screenshots — the fix is committed but the backend still
  needs a restart to load it, then section 2 → chat turn → submit, section 4 → chat turn →
  submit → *Move on…*.
* Approved-plan section page, chat↔pane one attempt id, restart-resume, revoke/disable/
  re-enable/uninstall in this exact topology.
* Screen recording.

## Reproduce

```
bash scripts/install-local.sh
HERMES_HOME=~/.hermes/coursebook-test/home HERMES_COURSEBOOK_SINGLE_HOME=1 \
HERMES_DESKTOP_DEV_SERVER=http://127.0.0.1:5174 HERMES_DASHBOARD_SESSION_TOKEN=cb013-test-token \
hermes serve --isolated --port 44219 --skip-build
node scripts/cb013-nav.mjs     "<section title>"      # walk the pane to a section
node scripts/cb013-shot.mjs    docs/cb013-shots/x.png
node scripts/cb013-run-section.mjs "<section>" "<chat>" "<answer>" <shot>
node scripts/cb013-inspect.py                        # bindings / attempts / enrollments rows
```
