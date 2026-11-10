# Coursebook architecture (0.1.0 candidate)

Governing design: `PREBUILD_SPEC.md`. Interface contract: `UX_SPEC.md`.
This document records what is **verified against the live Hermes source**, not what the design
hoped for. Where the spec and the SDK disagreed, the SDK won and the correction is listed under
"Spec ↔ SDK reconciliation".

## 1. Authority chain

```
contracts/*.json                (frozen data: enums, payloads, error codes, table inventory)
        │
coursebook/contracts.py         (loader, cross-document resolver, validators)
        │
coursebook/api.py ── dispatch ──> handler ──> coursebook/db.py (SQLite, the source of truth)
        │                                  └──> coursebook/jobs.py (state machine from cb.jobs)
        │
dashboard/plugin_api.py         (FastAPI: /health, /schema, /rpc, /runtime)
        │
desktop/plugin.js               (ctx.rest → the routes above; renders only real state)
```

Chat is a view of a lesson, never its source of truth. SQLite holds courses, plans, objectives,
checks, attempts, evidence, transitions, bindings, sources, artifacts, jobs, usage, notebook
entries, idempotency keys and packs (`cb.db`). Markdown/JSON/PDF/audio are exports or artifacts.

## 2. Package layout (one installable folder)

```
plugin.yaml                      agent half: declared tools/hooks, python_dependencies
__init__.py                      register(ctx): 1 tool + 3 hook adapters
coursebook/                      backend package (contracts, api, db, jobs, packs, hooks, tools)
dashboard/manifest.json          {"name":"coursebook","api":"plugin_api.py","tab":{"hidden":true}}
dashboard/plugin_api.py          router mounted at /api/plugins/coursebook/
desktop/plugin.js                Desktop half: route, sidebar row, pane, palette, settings page
contracts/                       frozen contracts
tests/                           stdlib unittest
scripts/                         test / validate / install-dev / install-local / uninstall-local / probe-backend
```

Verified layout source: `website/docs/developer-guide/desktop-plugin-sdk.md` §"One package, both
SDKs": a `desktop/plugin.js` inside the agent package is copied by the Electron main process into
`$HERMES_HOME/desktop-plugins/<id>/` beside a `.hermes-package.json` marker and loaded through the
same disk-door pipeline as a standalone plugin. The renderer never scans `plugins/` itself.

## 3. Verified SDK seams (each one is a fact from source, not a guess)

| Seam | Evidence |
|---|---|
| Unified package loads from `plugins/<id>/desktop/plugin.js` | `desktop-plugin-sdk.md` §One package, both SDKs; `apps/desktop/electron/desktop-plugins-root.ts` (`PACKAGE_MARKER`) |
| A disk plugin is **one** ESM module; only `@hermes/plugin-sdk`, `react`, `react/jsx-runtime` resolve | `apps/desktop/src/contrib/runtime-loader.ts::unsupportedImports` refuses every other specifier, including relative paths |
| No JSX in a disk plugin | same loader evaluates the file uncompiled (`Blob` + dynamic `import`); SDK doc §"No JSX, no build" |
| Areas: `ROUTES_AREA='routes'`, `SIDEBAR_NAV_AREA='sidebar.nav'`, `PANES_AREA='panes'`, `PALETTE_AREA='palette'`, `TOOL_MEDIA_RENDERER_AREA`, `TRANSCRIPT_DIRECTIVE_AREA` | `apps/desktop/src/sdk/areas.ts`, `app/routes.ts`, `app/command-palette/contrib.ts`, `sdk/index.ts` |
| `ctx.rest(path)` reaches `/api/plugins/<id><path>` only | `apps/desktop/src/api/plugins.ts::pluginRest` (namespace is the boundary; `..` refused) |
| Backend routes are `dashboard/manifest.json` + `dashboard/plugin_api.py` exporting `router` | `hermes_cli/web_server_dashboard.py::_mount_plugin_api_routes` (`spec_from_file_location`, prefix `/api/plugins/<name>`) |
| The API module is imported **by path**, so the plugin dir is not on `sys.path` | same function; `dashboard/plugin_api.py::_load_backend` loads the package explicitly under a private name |
| SQLite handle is `plugins.plugin_storage.plugin_db(name)` (WAL, FK on, not autocommit) | `plugins/plugin_storage.py` |
| Hooks `pre_llm_call`, `post_llm_call`, `post_tool_call` exist; `pre_llm_call` may inject `{"context": …}` or block | `hermes_cli/plugins.py::VALID_HOOKS`; `developer-guide/plugins/index.md` hooks table |
| `post_llm_call` runs on successful turns only — it cannot be the gate | docs hooks table + `AUDIT.md` R2 |
| `register_tool(name, toolset, schema, handler, …)`; schema is `{name, description, parameters}` | `hermes_cli/plugins.py::register_tool`; `plugins/google_meet/tools.py` |
| Admission compares **registered vs declared** tools/hooks; undeclared registration fails | `hermes_cli/plugin_validate.py::_check_capabilities` |
| Catalog installs must stay inside the SDK surface | `hermes_cli/plugin_validate_desktop.py` (rules: eval, dynamic/remote import, script injection, app DOM reach, preview guest reach) |
| No config_schema is rendered as a settings form; the agent half's schema appears as a sub-page of the Desktop entry | `desktop-plugin-sdk.md` §Plugin settings pages |

## 4. Spec ↔ SDK reconciliation (the corrections that matter)

1. **`plugin_api.py` is not at the package root.** The spec's diagram says `plugin_api.py + backend
   modules`. The mount requires `dashboard/manifest.json` + `dashboard/plugin_api.py`. This build
   uses the real path; the spec diagram is a simplification, not the install layout.
2. **The Desktop half cannot be split into files.** `PREBUILD_SPEC.md` §6 says `desktop/plugin.js`;
   `UX_SPEC.md` asks for shared primitives across many views. A runtime plugin is one module with no
   relative imports, so all Desktop code lives in `desktop/plugin.js`. This is the single-writer
   hotspot recorded in `docs/WORK_PACKAGES.md`.
3. **`plugin_db()` is the SQLite seam**, not a private path under the plugin folder. The install dir
   is deleted by `plugins remove`, so state under `plugin_data_dir()` is the only correct location.
4. **`ctx.llm` exists but is host-owned** (`agent.plugin_llm.PluginLlm`); the grader task lane is
   not assumed here. Plan and lesson generation call it through `PluginLLMAdapter`, which refuses a
   context without `ctx.llm` rather than reaching for a raw provider key. Closed-form checks are
   graded deterministically in-process against the stored reference; the auxiliary open-response
   lane stays unconfigured (`configure_aux_grader` is never called), so it sends nothing.
5. **Media renderers are provenance-scoped.** `TOOL_MEDIA_RENDERER_AREA` claims only tools that this
   package's `plugin.yaml` registered; a claim on a core tool or another plugin's tool is refused.
   Coursebook therefore emits `MEDIA:` only from Coursebook-owned tools.
6. **No transcript-selection API is assumed.** Notebook save falls back to the backend-owned lesson
   segment/artifact, exactly as `PREBUILD_SPEC.md` requires.
7. **`cron.manage` has no update and no idempotency key** (`AUDIT.md` H4). Reminder creation must use
   namespaced list → reuse and remove+add for schedule changes.

## 5. Failure and degradation contract

This build reports three states, and the Desktop half renders exactly those:

* **ready** — backend answered and the database is migrated.
* **degraded** — backend answered (`ok:true`) but `db.ready` is false. Either the store has not
  been provisioned yet (`health.get` provisions it on first contact) or a migration did not
  complete; the schema version says which.
* **unavailable** — `ctx.rest` threw or returned `ok:false`. The page names the enable path
  (Capabilities → Plugins) and offers *Check again*; it never shows an empty course list as if the
  user had none.

Every method declared by `cb.rpc` v7 has a handler in this build — 52 declared, 52 implemented, no
contract problems from `/runtime`. A method that is not in the contract is refused by contract
validation with `VALIDATION_FAILED` before any handler runs, and the error lists the declared
methods. `NOT_IMPLEMENTED` is the defensive answer for a declared method that has lost its handler
in this process; it is not what an unknown method gets, and no path returns a plausible success for
work the backend cannot do.

## 6. Stored lesson text: the one-time repair and its marker

`cb.rpc` caps one lesson segment at 8,000 characters (`lesson.page` →
`segments.items.text.maxLength`) and one page at 500 segments, while the pack manifest allows a
section file of up to 32 MB (`max_single_file_bytes: 33554432`). Those numbers were never
reconciled until D1 (`e3d6770`): the writer stored a whole section file as *one* teaching row, so an
objective with a long chapter imported cleanly and then returned `INTERNAL_ERROR` on every
`lesson.page` (`segments/0/text`) — a permanent, unretryable unreadable section.

`coursebook/segments.py` now owns the cap: imports cut over-cap text into ordered pieces, and
`db.ensure_schema()` repairs text that an older build already stored. Two things come with that and
are named here because nothing else in the tree owns them: a per-database marker, and a mutation of
learner content that a chat turn can reach.

### 6.1 `PRAGMA user_version` is a data-repair marker, not a schema version

The schema version authority is unchanged: `schema_migrations`, declared by `cb.db`
(`migration_table`, `schema_version`), written one transaction per migration by `db.migrate()`,
and reported verbatim by `db.health()`. `PRAGMA user_version` carries no schema meaning in this
build. It holds `db.SEGMENT_REPAIR_MARKER = 1` once stored lesson text has been re-cut to the cap,
and `0` for a database that has never been repaired. It is read and written only by
`db._repair_lesson_segments_once()`; no migration and no handler treats it as a version, and the
tests only assert the marker's value (`tests/test_segment_cap.py`). A future schema change must bump
`cb.db`, not this marker, and nothing may reuse `user_version` for a second purpose without
superseding this one.

### 6.2 `ensure_schema()` runs one in-place repair of `lesson_segments`

`db.ensure_schema()` migrates when needed, then calls `segments.repair_stored()`. That function,
for every `lesson_run_id` holding a `kind='teaching'` row longer than the cap:

* splits the text at semantic boundaries — after a blank line, else after a line, else after a word,
  then a hard cut — moving the cut out of an open code fence and off a trailing heading where the
  boundary allows, so that `"".join(pieces) == original` — no character added, dropped or rewritten.
  A single fence longer than the cap is still cut; it is bounded and exact like any other text;
* keeps the original row's `id`, `created_at`, `artifact_id` and `source_id` for the **first**
  piece, and inserts the remaining pieces as new rows with new ids and the same `created_at`;
* renumbers the run's ordinals contiguously in two passes (`ordinal + 1000000`, then back down) so
  the `UNIQUE (lesson_run_id, ordinal)` fence never collides mid-renumber and the page renders in
  reading order;
* leaves every other row's text alone: inside a run it does touch, rows already within the cap and
  non-teaching rows keep their content and only take a new ordinal, and a run with nothing over the
  cap is not written at all.

A course imported before the fix therefore becomes readable on the next command without a
re-import. `segments.stored_overlong(connection)` reports `(lesson_run_id, length)` for stored text
over the cap and is read-only diagnostics.

**Why the fence is `BEGIN IMMEDIATE`.** The repair is read-decide-write across every run: it scans
for over-cap rows, then rewrites and renumbers. `db.transaction()` issues `BEGIN IMMEDIATE`
(`BUSY_TIMEOUT_MS = 5000`), taking the write lock before the scan, so two processes can neither
split the same rows concurrently nor interleave ordinal renumbering; and the marker write commits in
the *same* transaction as the split, so there is no state where the marker says "repaired" while
the rows are not.

**Idempotent.** After the marker is set, the cost of `ensure_schema()` is one `PRAGMA` read per
command. Every piece a run writes is within the cap, so even a re-run with the marker cleared would
find nothing to repair; the test asserts the lesson's row count is unchanged after a second call.

**Lock contention skips, and never fails a command.** `_repair_lesson_segments_once()` catches
`sqlite3.OperationalError` — the write lock still held after the busy timeout, or a read-only
store — and returns `0` with the marker left unset. The caller's command is unaffected, and the
next command retries. The consequence is stated plainly: on a contended or read-only database the
D1 repair stays pending, so over-cap text there stays unreadable until a command gets the lock.

### 6.3 The lifecycle fence, and why this path is a documented exception

`PREBUILD_SPEC.md` ("Lifecycle hooks never provision storage") and CB-014-R1 fence the
chat-lifecycle paths (`pre_llm_call`, `post_llm_call`, `post_tool_call`) and plugin import from
provisioning or mutating the store: a chat turn is not Coursebook use. The repair sits inside that
fence in one respect and outside it in another, and both halves are stated deliberately.

* **It cannot provision.** `pre_llm_call` returns before touching anything when `db.store_exists()`
  is false, so an unprovisioned profile never grows a database from a chat turn. The repair only
  runs against a store that already exists.
* **On an existing store, a chat turn can reach it.** When a chat is bound to a lesson and the turn
  carries a real answer (or an explicit skip/override), `pre_llm_call` grades it by dispatching
  `attempt.submit`/`attempt.override` on the same `api.dispatch` path the UI uses, and those domain
  handlers call `db.ensure_schema()` first. The first such turn after an upgrade therefore performs
  the one-time repair.

That is why this is the first lifecycle-reachable path that mutates stored learner content, and why
it is written down rather than left to be discovered: the boundary CB-014-R1 draws is about
provisioning and about hooks writing state of their own, and this is neither a provisioning path nor
a hook-authored write, but it does rewrite rows while a turn is in flight. The mutation stays
narrow and deterministic: no row is written for text already within the cap, the text is never
rewritten (`"".join(pieces) == original`), and no table other than `lesson_segments` is touched. On
a database that is already repaired, or that holds nothing over the cap, the cost to that turn is
the single `PRAGMA` read.

Evidence: `tests/test_segment_cap.py`, 12 tests passing at `1b623dd`. `StoredTextRepairTest`
reproduces the old writer exactly (one 24,000-character teaching row, marker cleared), then asserts
the page reads, every piece is within the cap, the pieces join back to the original text, the marker
is set, and a second read adds no rows. `RepairScopeTest` asserts a fresh database reads `0`, moves
to `1` after `ensure_schema()`, and stays `1` after a second call.

## 7. What this build deliberately does not contain

- Pronunciation scoring. The host STT adapter and the `model_assessed` evidence path are planned
  in `docs/VISUAL_MEDIA_PLAN.md`; without a configured scorer the lesson offers practice only.
- Reminders. No RPC, no job kind and no storage.
- A standalone research command. Research runs inside plan jobs only, bounded and ledgered through
  the host `web_search`/`web_extract` seam.
- The auxiliary open-response grader lane. It stays unconfigured: with an adapter installed, learner
  text is passed to the grader and a persuaded pass is accepted (CB-QA-11).
- A working Desktop route. Every registration exists, but `#/coursebook` renders the session home
  (CB-QA-09), so no UI acceptance claim in this repository is verified.

Course creation, plan and lesson generation, grading, transitions, evidence, notebooks, the review
queue, usage accounting, pack import/export and Parent Studio authoring are implemented and tested
against the frozen contracts. They are unreachable from the UI while CB-QA-09 is open, which is a
reachability gap, not missing code.

## 8. Job liveness: deadlines, heartbeat, reconciliation (H-66)

A live `plan` job was observed `running` for over nine minutes with an expired lease, empty
progress, no heartbeat renewal and a `cancel_requested` that never reached a boundary. The cause was
not one bug: the execution path had three foreign calls that could block forever and a heartbeat
that silently renewed the wrong database.

### 8.1 Every foreign call has an executable deadline

A timeout passed to the host (`complete_structured(timeout=...)`, a tool argument) is advisory. The
plugin now enforces its own wall clock in `coursebook/deadline.py`:

| Seam | Bound | Typed failure |
| --- | --- | --- |
| `ctx.llm` provider call | `PROVIDER_TIMEOUT_SECONDS[purpose]` (env-overridable) | `ProviderTimeout` |
| any of the above, inside a job attempt | `min(purpose bound, remaining attempt budget)` (`COURSEBOOK_JOB_DEADLINE_SECONDS`, default 1800 s) | `ProviderTimeout` with `details.job_deadline: true` |
| `ctx.dispatch_tool("web_search"/"web_extract")` | 45 s / 60 s (`COURSEBOOK_WEB_*_TIMEOUT_SECONDS`) | `ResearchTimeout` (a `ResearchUnavailable`) |
| `ctx.dispatch_tool("image_generate"/"text_to_speech")` | 180 s (`COURSEBOOK_MEDIA_TOOL_TIMEOUT_SECONDS`) | `MediaTimeout`, degraded to text |

Two mechanisms, chosen so the normal path leaks nothing:

* **Coroutines are cancelled.** When the host exposes `acomplete_structured`, the adapter runs it on
  a supervised daemon thread with its own event loop, and the *calling* thread waits on an event
  bounded by the deadline. At the deadline the coroutine's task is cancelled — the in-flight
  request is closed, not abandoned — and the caller returns; no thread is parked in the caller.
* **Synchronous calls use a capped pool.** `ctx.dispatch_tool` is synchronous and cannot be
  interrupted from Python. Calls run on a small set of reused daemon workers
  (`BoundedCallPool`, 4 by default). A timed-out call abandons its worker until it returns, and that
  slot counts against the cap; when every slot is stuck the next call fails fast with a typed
  unavailable error instead of opening more threads. Normal calls reuse one worker. This is the one
  shape where the socket is abandoned rather than closed: Python offers no way to interrupt it, and
  the host's own `timeout=` remains the only cancel for it.

The **job attempt** has a bound of its own (CP-044). Per-call deadlines are not a job deadline: a
plan attempt runs two author/validate rounds, so calls that each finished "in time" could still keep
the row `running` for over half an hour (CP-015 checkpoint 4 measured a 648 s attempt). The job
runner now declares one wall-clock budget per attempt (`COURSEBOOK_JOB_DEADLINE_SECONDS`) and every
bounded call inside a stage is clamped to what is left of it, so the in-flight request is cancelled
at whichever bound arrives first. On expiry the row is failed with the contract's existing
`HOST_UNAVAILABLE` shape — `details` carry the stage, the elapsed time, `deadline_s` (the remaining
budget) and `job_deadline: true` — and the lease is released by the same `fail` path a stage failure
uses. Plan jobs now also record the per-call liveness rows (`gen_call_waits`) the lesson stage
already had, so a job waiting on a slow provider is visible as *waiting* rather than as a dead row.

A first research timeout ends that research pass (`run_research` breaks instead of spending the
rest of the query budget on a stuck tool); the ledger records the failure and no source is invented.

### 8.2 The heartbeat runs under the caller's context

`job_service._run_with_heartbeat` renews the lease during a stage. The renewal thread is a bare
`threading.Thread`, which starts with an empty `contextvars.Context`. A gateway carries the active
profile as a *context-local* home override, so every `renew` there opened a different database,
raised `NOT_FOUND` for the job, and was swallowed by the generic `except`: the lease lapsed while the
stage was still running. The beat now runs inside `contextvars.copy_context()` and a run of failures
is logged. The tick and reaper threads are started the same way.

### 8.3 Cancellation stops at a boundary

Cancellation is intent, not an interrupt: a non-idempotent provider call already in flight is never
killed, it is reconciled by operation/artifact key. The cancel probe (`job_service.is_cancel_requested`)
is therefore checked at every provider call (`_Usage.before_call`) and every research call, and the
stage loop now checks again after a stage returns. A stage that ends after cancellation — including
one that ends by hitting its deadline — is recorded `cancelled` with its usage and checkpoint, never
`failed` (which would invite a retry that spends again) and never a long-lived `cancel_requested`.
`completed_late` remains the contract outcome only for a cancel that races the final `finish` write.

### 8.4 Reconciliation runs live

`reconcile_startup` still runs once per process, but it was the only pass. `job_service.reconcile_expired`
runs every 5 s on a separate `coursebook-job-reaper` thread (separate so a pump stuck inside one job
cannot stop it):

* a live lease is honoured, whoever owns it;
* `running` + expired/absent lease → `interrupted_requires_retry`, lease cleared, brief and
  checkpoint preserved;
* `cancel_requested`/`cancelling` + expired/absent lease → `cancelled`.

The reaper thread also has **no request scope of its own** (H-182/D6). Copying the context is not
enough: the copied context may carry no profile override at all, so the thread resolved
`get_hermes_home()` from whatever the plugin loader left behind. In the isolated
`hermes serve --isolated` topology that home had no `jobs` table — and `db.connect()` *created* the
empty file — so the reaper raised `no such table: jobs` every five seconds and H-66 reconciliation
never ran. `executor.start_tick` now snapshots the store root with `db.store_scope()` **in the
registering context** (the same resolution a request gets, including
`HERMES_COURSEBOOK_SINGLE_HOME`) and pins every background thread it starts with
`db.use_store_scope()`; `db.connect()` opens that exact file. A store with **no schema yet** — the
normal state before the first Coursebook action — is now a skip that is logged once, not an
exception every pass, and the reaper never provisions a store no command has created. The pump
thread takes the same pin, because it reads the same database.

### 8.5 What is still true, and stated plainly

* A synchronous host call that ignores its deadline is not killed; it holds one pool slot until it
  returns. The bound is the pool cap, not the call.
* The provider deadline bounds one call, so a multi-call stage (two attempts × generate + validate)
  can take several deadlines. The job cap is `PROVIDER_TIMEOUT_SECONDS` × calls, not one number.
* The reaper's evidence is the lease. A process that is alive but whose heartbeat fails is detected
  only when the lease expires; the fix above makes that path log instead of vanish.
* Media is optional: a media timeout degrades the item to text and does not fail the lesson.

Evidence: `tests/test_h66_liveness.py` (17 tests: stalled host tool, stalled provider, async
cancellation, pool reuse and capacity, heartbeat under a context-local home, cancel at a deadline,
live reconciliation, reaper thread, end-to-end pump) and `probes/h66-liveness.py`, which reproduces
the three stalls offline and reported `host_seam_stall=False provider_stall=False
heartbeat_not_renewed=False` after the fix. The before/after transcript and the live incident row
are in `docs/H66-EVIDENCE.md`.

## 9. Host seam debt: `hermes_cli.sqlite_util.open_db` (H-115-D4)

One line of this package depends on a host **internal**, and it is accepted debt with a guard
rather than a hidden import. Recorded here with its exact host range because a reader asked to
audit the coupling should not have to grep for it.

**What is coupled.** `plugins.plugin_storage.plugin_db(name, filename="data.db")` is the documented
SQLite seam (§3) and the handle for every ordinary open. It accepts a *filename* only: the directory
comes from `plugin_data_dir(name)` → `hermes_constants.get_hermes_home()` on every call. Under
`HERMES_COURSEBOOK_SINGLE_HOME=1` (§`db.single_home_pin`) the request's `?profile=` scope points
*outside* the launch home, so `plugin_db` would reopen the escaped home — the exact bug the pin
exists to prevent. The host publishes no way to open a database at an explicit path, so the pinned
file is opened through `hermes_cli.sqlite_util.open_db`, the host's own connect+PRAGMA stack (WAL
with the network-FS fallback and the WAL-reset-bug gate, `foreign_keys`, busy timeout). That module
is not on the plugin allowlist (`hermes_cli/plugin_validate_private_imports.py`), so `hermes plugins
validate` reports it under catalog rule 9 — deliberately still reported, see below.

**Host range.** Last verified against `hermes-agent v0.23.0..c02e6e0180` (2026-11-07), where
`hermes_cli/sqlite_util.py::open_db(path, *, db_label, foreign_keys=, check_same_thread=, …)`
exists with the three keywords this package passes. No lower bound is claimed and none is
enforced: the guard inspects the live module, not a version string, so a build that still ships
the surface works whatever its number.

**Why not (a) — a public seam — yet.** The host would have to expose a path-taking open (or a
`plugin_db(..., path=)`). That is a host release with its own review and tests; until it ships, the
plugin cannot use it and would keep the private import as a fallback anyway. The debt is retired
the day the host publishes the seam: this package then calls it and `HOST_SEAM_*` disappears.

**Why not a local re-implementation.** A raw `sqlite3.connect` at the pinned path would drop the
host's WAL policy — the network-FS silent-refusal fallback and the never-live-downgrade invariant
are exactly the rules a plugin must not re-carry by hand (a `PRAGMA journal_mode=WAL` on a WAL-reset-
bug build is a known corruption path). Opening the *right* file with the *wrong* policy trades one
failure for a worse one.

**Why not fall back to a local open when the seam is gone.** The pin's whole promise is that a
single-home backend never reads or writes the ambient profile. A fallback would restore service on
the wrong store the moment the host moves a module — the failure mode H-69 fixed. It fails loud
instead: `DatabaseUnavailable` (subclass `HostSeamUnavailable`).

**The guard, and what it turns a host refactor into.** `coursebook/db.py` names the surface once
(`HOST_SEAM_MODULE`, `HOST_SEAM_ATTR`, `HOST_SEAM_KWARGS`, `HOST_SEAM_VERIFIED`), imports it at one
site (`_host_module`), and checks the module identity, the attribute and the three keyword names
before calling it. A move becomes one sentence naming the surface, the host build it was verified
against, and the two fixes (re-point, or unset the flag):

> the single-home pin (HERMES_COURSEBOOK_SINGLE_HOME=1) opens the launch home's database through the
> host's private hermes_cli.sqlite_util.open_db, which this Hermes build no longer offers as this
> package calls it (…). … Refusing to fall back to the ambient profile's store.

`db.host_seam_status()` reports the same fact without opening anything, and
`install_check --home` (the doctor) already answers it as `SCOPE_PINNED` or an `HOST_SEAM_UNAVAILABLE`
error finding with the fix, so a broken dedicated backend is diagnosable before a request is made.
An error raised *by* the opener (permissions, disk, lock) stays a plain `DatabaseUnavailable`: a
coupling break and an I/O error are different facts.

The import is spelled as a literal inside `_host_module` on purpose. Hermes's admission lint reads
`importlib.import_module("<literal>")`, so keeping the literal means the coupling stays *reported*
under catalog rule 9 instead of being hidden behind the constant; `_seam_identity_problem` fails if
the literal and the constant ever diverge.

**Upgrade procedure.** After bumping the host: `python3 -m unittest tests.test_host_seam_guard`
— the first two tests are the canary and fail with the message above (plus the new surface to
point at) if the host moved it. Then update `HOST_SEAM_VERIFIED` and this section.

**What is still true, stated plainly.** On a host that moved the module without a replacement, a
dedicated single-home backend cannot open its store at all until this package is updated — that is
the price of the pin, and it is loud, not silent. A multi-profile gateway must not set the flag;
nothing here protects an operator who sets it on one.

Evidence: `tests/test_host_seam_guard.py` (12 tests: the live canary, missing module, moved
attribute, renamed keyword, module-identity drift, `**kwargs` acceptance, an opener I/O error not
reported as coupling, the pinned `connect()` opening the launch home through the guard, the
drifted-seam `connect()`, and both doctor findings). Mutation check: with the declared module path
pointed at a name the host does not ship, the canary fails with exactly the message quoted above.
`hermes plugins validate .` still lists `coursebook/db.py:121 hermes_cli.sqlite_util` under
catalog rule 9 (checked in-process with `private_import_findings()` on this tree).
