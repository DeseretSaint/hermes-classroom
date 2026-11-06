# CB-001 review packet — frozen contracts and unified plugin skeleton

Code commit: `45aa2324d83e0fb989a02ff79e68ccc205c6b0ea` (branch `wt/cb-001-atlas`).
This packet commit follows it and changes documentation only.

## Gate output (verbatim)

```
$ hermes plugins validate .
✓ manifest — plugin.yaml parses
✓ manifest fields — name, version, description present
✓ requires_hermes — spec '>=0.23.0' parses
✓ config schema — not declared
✓ requires_env — all entries UPPER_SNAKE
✓ oauth — not declared
✓ loadable — entry: __init__.py, desktop/plugin.js
✓ python dependencies — 1 requirements from manifest
✓ capability probe — register() ran in isolation
✓ declared tools — matches registrations
✓ declared hooks — matches registrations
✓ declared middleware — matches registrations
✓ built-in tool collisions — no collisions
✓ security scan — safe
✓ no core override — no runtime rebinds of Hermes core
✓ desktop surface — stays inside the plugin SDK surface
◆ Isolation — runs in the plugin host (plugins.isolation: host)
Validation passed.

$ hermes plugins doctor .
manifest: coursebook 0.1.0 (standalone)
OK: runtime discovery, manifest parsing, import, and registration passed
registrations: 1 tool(s), 3 hook(s)

$ python3 -m unittest discover -s tests -t .      → Ran 46 tests … OK
$ node --check desktop/plugin.js                  → syntax OK
```

## Live backend smoke (isolated `HERMES_HOME`, no operator data)

```
routes: ['/health', '/rpc', '/runtime', '/schema']
health: ok:true revision:0  db:{ready:false, schema_version:null}  contract_version:1
schema ids: cb.db, cb.errors, cb.jobs, cb.pack, cb.rpc, cb.vocabulary
runtime: contract_problems: []
rpc ok: True   bad payload -> VALIDATION_FAILED
plugin-data path stayed inside the temporary HERMES_HOME
```

`db.ready:false` is correct and intentional: no migration has landed yet (CB-002 owns it), and the
backend reports that instead of pretending.

## File tree

```
plugin.yaml                     agent half manifest (1 tool, 3 hooks, jsonschema pin)
__init__.py                     register(ctx)
coursebook/
  __init__.py  contracts.py  api.py  db.py  jobs.py  packs.py  hooks.py  tools.py
dashboard/
  manifest.json  plugin_api.py  (routes: /health /schema /rpc /runtime)
desktop/
  plugin.js                     single ESM module: route, nav, pane, palette, settings page
contracts/
  vocabulary.v1.json  errors.v1.json  rpc.v1.json  db.v1.json  jobs.v1.json  pack-manifest.v1.json
tests/                          6 files, 46 cases (unittest, no test-only dependency)
scripts/                        test.sh  validate.sh  install-dev.sh
docs/                           CONTRACTS.md  ARCHITECTURE.md  WORK_PACKAGES.md
.gitignore
```

## Contract summary

| Contract | Ver | Contents |
|---|---|---|
| `cb.vocabulary` | 1 | recipe, evidence_class, evidence_target, verdict, next_action, answer_kind, objective_state, binding_status, job_kind, pack_trust_label, source_support_status, identifiers/hashes/timestamps |
| `cb.errors` | 1 | 16 codes with category, retryable, HTTP mapping and summary |
| `cb.rpc` | 1 | request/success/error envelopes + 24 methods, each with request and response payload schemas |
| `cb.db` | 1 | 17 tables with columns/refs/uniques/indexes, pragmas, execution policy, deletion policy |
| `cb.jobs` | 1 | 9 states, transition table, terminal vs resting states, job record schema |
| `cb.pack` | 1 | pack manifest allowlist, bounds, per-file hashes/MIME, license and trust dimensions, exclusions |

Every contract carries `$id` (versioned URI), `x-contract-id` and `x-contract-version`; a test
asserts the three agree.

## Decisions recorded during the build

1. `dashboard/plugin_api.py`, not a root `plugin_api.py` — that is the only path the gateway mounts.
2. The Desktop half is one file; no relative imports, no JSX. Recorded as a single-writer hotspot.
3. `plugins.plugin_storage.plugin_db("coursebook")` is the SQLite seam.
4. No `config_schema` yet: a settings field nothing reads would be a partially wired control.
5. `failed` is a retryable resting job state, not terminal — corrected after a test caught the
   contradiction in `cb.jobs`.
6. `cancellable()` returns false for `cancelling` — the action would do nothing.

## Open questions

See `docs/CONTRACTS.md` §"Open questions". All three are gated by Sentinel's probes, not by this
skeleton: auxiliary grader task lane, course-workspace topology, and pack staging transport.
