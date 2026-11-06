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

Every method declared by `cb.rpc` v6 has a handler in this build — 51 declared, 51 implemented, no
contract problems from `/runtime`. A method that is not in the contract is refused by contract
validation with `VALIDATION_FAILED` before any handler runs, and the error lists the declared
methods. `NOT_IMPLEMENTED` is the defensive answer for a declared method that has lost its handler
in this process; it is not what an unknown method gets, and no path returns a plausible success for
work the backend cannot do.

## 6. What this build deliberately does not contain

- Image and speech generation. Media policy, the content-addressed artifact store and the
  text-fallback path ship, and lesson generation emits declarative media specs with text
  equivalents, but no image or text-to-speech provider is wired and no production caller reaches
  the media job path.
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
