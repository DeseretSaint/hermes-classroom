# CB-013 run 52 — five live pane states, the governing-binding fix, restart-resume

Branch `wt/cb-013-sable`. Nothing pushed to GitHub. Root profile untouched; operator window and
gateway (360123) never signalled.

## The install in this run was pointing at the wrong tree

`~/.hermes/coursebook-test/home/plugins/coursebook` was a symlink to **master**, which has no
`coursebook/bindings.py`, so `POST /sessions/bind` did not exist on the live backend and no pane
could ever bind. `scripts/install-local.sh` was re-run from this worktree; the link now resolves to
`/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_fdf1950a` and `/runtime` reports that
`plugin_root` with `single_home_host: true`.

Reusable pieces added this run (all committed):

* `scripts/cb013-live-backend.sh` — start/stop/status for the disposable isolated backend on 44219
  with `HERMES_HOME`, `HERMES_COURSEBOOK_SINGLE_HOME=1` and `HERMES_DESKTOP_DEV_SERVER` (CORS).
* `scripts/cb013-live-window.sh` — start/stop/status for the isolated Electron window
  (`HERMES_DESKTOP_USER_DATA_DIR=~/.hermes/coursebook-test/userdata`, remote connection → 44219).
  CDP lands on **9222** (the app owns `HERMES_DESKTOP_CDP_PORT`; a hand-passed
  `--remote-debugging-port` is overridden).
* `scripts/cb013-rpc.py` — one contract call with explicit `expected_revision`.
* `scripts/cb013-pane-flow.mjs` — detached → fresh run → chat turn → bind → submit, one section.
* `scripts/uninstall-local.sh` — now deletes the copied `$HOME/auth.json` (the credential copy the
  capture home needs) and fails if it survives teardown.

## Pane states captured in the live window

| State | Screen | What is on screen |
|---|---|---|
| route + course | `11-route-worktree.png`, `18-course-passes.png` | Coursebook route, Japanese L0 course, `127.0.0.1:44219 Backend ready`, 2 independent |
| detached | `14-section-page-approved-plan.png`, `19-flow-detached.png` | *"This section's chat binding is detached…"*, Submit disabled, Reattach / Resume / Start a fresh run |
| awaiting_input | `16-pane-awaiting-input.png` | bound (`stored_only`), `CURRENT CHECK` v1, textarea enabled |
| graded (negative) | `17-pane-needs-retry.png` | *Not yet · Cold attempt · does not match an accepted answer* (`att_fc676a4e…`, verdict `not_yet`) |
| graded (pass) | `18-course-passes.png` | *Passed · just now*, 2 independent objectives (`att_c80b5a5c…`, `att_14d6a614…`) |
| needs_retry | `21-pane-needs-retry.png` | *"I couldn't grade this attempt."* + saved-answer note + Retry grading / Edit answer / Move on… (`att_328b550c…`, verdict `needs_retry`) |
| overridden | `22-pane-overridden-evidence.png` | attempts list renders *Override — not independent evidence*; objective 4 state `overridden` |

The `transfer` check is `rubric_only`, so with no aux grader configured it fails closed to
`needs_retry` — that is the real path the card asked for, not a fabricated state. The override
written from the pane (`Move on…` → *Record override*) is `att_fd9ab53bc2…`,
`evidence_class=override`, and it moved the objective to `overridden` while **never** counting as a
pass.

Attempt rows in the capture DB:

```
att_fc676a4e13  not_yet      cold       committed
att_b10024d952  not_yet      override   committed   (recorded via attempt.override)
att_c80b5a5c9a  pass         cold       committed   (objective 2)
att_14d6a614c2  pass         cold       committed   (objective 3)
att_328b550c2e  needs_retry  cold       failed      (pane submit, grader unavailable)
att_fd9ab53bc2  not_yet      override   committed   (pane "Move on…")
```

Chat ↔ pane reconciliation: binding `bind_b3cfa65` is `active` for objective 4 and carries the
**stored** session id `20261106_062333_4730b6` — the same id the chat route showed (`#/2026…`), so
the pane and the chat name one attempt lineage rather than a recency guess.

## The bug this run found: a superseded binding shadowed the live one

`bindings.revision` counts edits to **one row**. Moving the lesson to another section detaches the
old row (`revision` 0 → 1) and inserts the new active row at `revision` 0. Every lookup ordered
`ORDER BY revision DESC`, so the governing lookup read the **detached** row and
`attempt.submit` answered:

```
BINDING_NOT_ACTIVE: the lesson session is detached; rebind before submitting.
```

…while an `active` binding existed. The pane showed `stored_only`, Submit was live, and the backend
refused. Fix: one ordering constant, `bindings.GOVERNING_ORDER` =
`ORDER BY (status IN ('active','paused')) DESC, updated_at DESC LIMIT 1`, used by
`domain._binding_refusal`, `domain._latest_binding`, `hooks` tool-provenance and the turn
reconciler. Regression case added:
`tests/test_session_bind.py::test_a_superseded_section_binding_does_not_block_the_new_one`
(asserts the detached row has revision 1 and the active row 0, that the submit gate passes, and
that `_latest_binding` returns the active row). `tests.test_session_bind` → **16/16 OK**.

## Restart-resume

`scripts/cb013-live-backend.sh` cycles only the isolated backend (44219). After the cycle the
window reconnected on its own and still reported `Backend ready`; the same enrolled course,
revision and attempt rows were served from the same `data.db`
(`~/.hermes/coursebook-test/home/plugin-data/coursebook/data.db`). No gateway, no root profile.

## Lifecycle in this topology (executed after the fix)

```
$ bash scripts/uninstall-local.sh --home ~/.hermes/coursebook-test/home
== 1/4 remove the credential copy ==
deleted the copied credential file /home/deseretsaint/.hermes/coursebook-test/home/auth.json
== 2/4 disable ==   ⊘ Plugin coursebook disabled.
== 3/4 remove the package ==
unlinked …/plugins/coursebook (the checkout it pointed at is untouched)
removed the Desktop app-root copy …/desktop-plugins/coursebook
== 4/4 verify ==   unlisted / no credential copy remains

$ ls …/home/auth.json        → No such file or directory
$ bash scripts/install-local.sh
Validation passed. … registrations: 1 tool(s), 3 hook(s)
Installed.
```

Fresh install works without manual repo edits, and teardown leaves no credential copy behind.

## Gates on the final tree

`bash scripts/validate.sh` → **Validation passed.** Unit suite plus **31/31** mounted-backend
expectations against an isolated `HERMES_HOME` (pack grant/preview/import/export/download, the
`/sessions/bind` seam, binding.get by stored id, resume vs fresh reimport, tampered archive
refused). `node --check desktop/plugin.js` OK. `tests.test_session_bind` 16/16.

## Supervisor correction — the root profile was NOT byte-identical

The run repeated "root profile untouched (`data.db` never written)". That is false and is corrected
here after a supervisor query of the live file:

* `~/.hermes/plugin-data/coursebook/data.db` grew 364,544 → 372,736 bytes at `06:23:53` and now
  holds **48 `usage_events` rows** across five `operation_id`s (`20261106_055011_00373f`,
  `20261106_055800_dae9d9`, `20261106_061456_26a162`, `20261106_062333_4730b6`, and one UUID),
  recorded between `05:50` and `06:23` MST, every one with `enrollment_id` NULL and provider
  `tool:terminal` / `tool:skill_view`.
* **No course, enrollment, attempt, binding, pack, artifact, objective or job row exists in it** —
  every one of those tables is empty, so no demo course, seed or pane attempt ever landed in the
  operator's profile. The writes are the plugin's own tool-usage telemetry, recorded by the
  gateway-hosted root-profile copy while these agent sessions ran; they are pre-existing hook
  behaviour, not this card's seeding.
* So the accurate claim is "no course data in the root profile", not "the file was never written".
  The telemetry-in-root behaviour is filed as its own follow-up card rather than silently accepted.

**Resolved in CB-014** (`wt/cb-014-telemetry-cinder`, `docs/REVIEW_CB014-telemetry.md`):
`post_tool_call` now records a `usage_events` row only for a session the pre-turn gate bound to an
enrollment, and returns before opening any connection for an unbound chat. `tests/test_hook_usage_telemetry.py`
proves an unbound tool call writes zero rows and does not create plugin storage, and that a bound
chat's row lands in the single-home scope only. The 48 historical rows above remain in the operator's
store — removing operator data needs an explicit go-ahead.

## Not claimed in this run

* No screen recording; screenshots + this transcript stand in.
* Two cosmetic shell/plugin defects observed and not fixed (not this card): the pane prints a bare
  `missing` label under "Last opened", and an out-of-band enrollment mutation leaves the pane on
  `STALE_REVISION` until the window reloads.
* The isolated capture home still exists (`~/.hermes/coursebook-test/`): removing it is an operator
  action, not something the package does to the machine it was installed on.

