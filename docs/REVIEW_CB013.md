# CB-013 review packet — local install and the missing binding seam

Owner: Sable. Branch `wt/cb-013-sable` @ `d3888fe`. Status: **install + seams verified; the live
Desktop capture is not claimed in this pass** — §5 states exactly what is still missing and why.

## 1. The defect this card found (and fixed)

`binding.get` and `binding.abandon` existed in `cb.rpc` v5, and every unit test below the pane
inserted `bindings` rows by hand (`tests/test_kernel_commands.py:377`,
`tests/test_kernel_v2.py:113`, `tests/test_turn.py:32`). **No production code ever inserted one.**
Consequence on a real Desktop:

- the pane always answered "Not a Coursebook lesson", so the objective, check, Submit, Retry,
  Override and Detached banner were dead code;
- `pre_llm_call` resolved an unbound chat on every turn, so the grading gate never ran;
- "chat and pane reconciling to one attempt id" was unobservable, because no attempt could start.

Why it could not be fixed inside `cb.rpc`: `lesson.begin`'s payload is frozen at v5 and has no
session field, and a *fresh* chat has no stored id until its first turn — which is exactly what the
shipped UI copy already promises ("Its chat binds after your first message"). The durable id
arrives from the host after the run exists, so the write belongs in a host seam, beside
`/packs/grant`:

| Piece | What it does |
|---|---|
| `coursebook/bindings.py` (new) | `bind_session()` creates the one active binding for a stored id, against the exact enrollment/objective/run; idempotent on repeat; refuses a chat bound elsewhere, a second active chat for one enrollment, a non-active run, and a mismatched run/objective |
| `dashboard/plugin_api.py` | `POST /sessions/bind` — thin adapter; refusals are HTTP 200 `{ok:false, code, message}` |
| `desktop/plugin.js` | arms the *exact* run a fresh lesson starts (`armPendingBind`), binds the focused chat once it has a durable id (`bindPendingChat`), one attempt per stored id, 15-minute arming TTL, renders the seam's own refusal; also fixes `LessonPaneBody` receiving `state.storedId` (undefined) instead of the real stored id |

## 2. Gate result (real output)

```
bash scripts/validate.sh
Ran 557 tests in 45.237s
OK
desktop/plugin.js: syntax OK
Validation passed.                      # hermes plugins validate: 16/16, security scan safe
Validation passed.                      # hermes plugins doctor: 1 tool(s), 3 hook(s)
All 31 backend expectations passed against an isolated HERMES_HOME.
scripts/probe-backend.py
  V POST /sessions/bind writes the active binding the pane and the pre-turn gate read
  V binding.get answers by the stored id the seam wrote, not by recency
  V repeating the same bind is idempotent — one row, never a second chat
  V a runtime id is never accepted as the stored id
```

Two gate defects on master were also fixed, because the admission gate was red on a correct tree:

- `GET /schema` counted "six frozen contracts"; `cb.vocabulary` was frozen in the CB-027 closure
  and made it seven. The probe now names the id set and requires a hash + the wire version, so a
  missing or renamed contract cannot pass by coincidence.
- `hermes plugins validate` refused the teardown script for `destructive_home_rm`. Teardown now
  goes through `hermes plugins remove` (and unlinks a linked symlink rather than following it).

## 3. Install (dedicated home, not the root profile)

```
bash scripts/install-local.sh
source : /home/deseretsaint/Projects/hermes-classroom/.worktrees/t_fdf1950a (d3888fe)
home   : /home/deseretsaint/.hermes/coursebook-test/home
== 1/5 agent half: link the package ==
/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_fdf1950a
== 2/5 desktop half: materialize the app root copy ==
marker: .../desktop-plugins/coursebook/.hermes-package.json
== 3/5 enable the agent half in this home ==
✓ Plugin coursebook enabled.
== 4/5 discover it in this home ==
discovered: coursebook
== 5/5 admission gates ==
Validation passed.
  manifest: coursebook 0.1.0 (standalone)
  OK: runtime discovery, manifest parsing, import, and registration passed
  registrations: 1 tool(s), 3 hook(s)
```

Notes that matter for a fresh install:

- the script deliberately does **not** inherit `HERMES_HOME`: an agent worker runs with it pointing
  at its own profile, and inheriting it installs into a real bot profile (observed and reverted).
- `hermes plugins remove` refuses a *symlinked* package ("resolves outside the plugins
  directory"), so `scripts/uninstall-local.sh` unlinks a linked install and reserves
  `plugins remove` for a copied one.
- the backend half needs a gateway cycle to mount its routes; enabling alone reports "restart the
  gateway".

## 4. Live backend on the dedicated home (verified over HTTP)

`hermes serve --isolated --port 44219 --skip-build` with
`HERMES_HOME=~/.hermes/coursebook-test/home`:

```
GET /api/plugins/coursebook/runtime
plugin_root = .../t_fdf1950a   wire_version = 5   contract_methods = 43
implemented: artifact.get, attempt.*, binding.*, check.get, check.open, course.outline,
             lesson.assist, lesson.begin, lesson.page, pack.*, review.*, … (all 43)
```

`python3 scripts/seed-demo-course.py --base-url http://127.0.0.1:44219 --token …` imported the
bundled Japanese pack through the real door (grant → preview → import):

```
archive: /home/deseretsaint/.hermes/coursebook-test/demo-pack.zip (14548 bytes)
preview: japanese-affection-context-l0 1.0.0
         content_hash=sha256:638ce371db6bf2340a7b6a37a75a9762e0e9e6c3f723e55b0a0a5103a8376d7f
course_id crs_6ca4b609e412456c96fbf2168c782b16
enrollment_id enr_d3e84830f3f14b9eb25ec92a87574ff4   revision 0
```

## 5. What is NOT verified in this pass (honest limit)

The isolated Electron window refused to attach to the test backend: it starts in
`launchMode: "primary"` with `connections.json → {"primary":"local"}`, and this build ignores
`HERMES_DESKTOP_REMOTE_URL`/`_TOKEN` unless the window has no saved connection route
(`electron/main.ts:8807` — `envOverride = key ? false : Boolean(...)`; `desktop-remote-route.ts:117`
— the env route is only reached when no primary connection is selected). Removing
`connections.json` + `active-profile.json` from a fresh user-data dir did not change it; the status
strip stayed "Backend offline / CONNECTING".

Consequently **not claimed**: the five pane states (awaiting_input, graded, needs_retry,
overridden, detached) with screenshots, a section page from an approved plan, chat↔pane one-attempt
reconciliation, and restart-resume in the live window. The code paths that produce them are now
reachable (the seam exists and the probe drives it), but reachable-by-test is not photographed.

Next attempt should either (a) write a `connections.json` v2 entry of `kind: "remote"` with the
server URL and let the app encrypt the token through its own settings IPC, or (b) capture on the
machine-level gateway after its cycle, using the operator's already-connected window.

## 6. Command transcript

See `docs/REVIEW_CB013-transcript.txt` for the verbatim gate, install, lifecycle and backend
transcript produced by this run.
