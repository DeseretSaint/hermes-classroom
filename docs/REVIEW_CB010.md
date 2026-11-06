# CB-010 — pack import/export UI and Parent pack lifecycle integration

Owner: Lattice. Branch `wt/cb-010-lattice`. Base: master after CB-002 (kernel), CB-005 (Desktop
shell), CB-004 (packs), CB-018 (cb.rpc v2), CB-019 (generation).

## What this package adds

**Backend — `coursebook/pack_flow.py` (new, mine).** The seam between the pack document
(`coursebook/packs.py`), the bounded archive reader (`coursebook/archive.py`) and the kernel
(`coursebook/domain.py`, `cb.db`). It registers the three pack lifecycle commands and keeps them
out of `coursebook/api.py` (Sable's file):

| Method | Behaviour |
|---|---|
| `pack.preview` | Validates the staged archive, then returns the manifest, an integrity block and the four trust labels. No verdict, no "safe" badge. |
| `pack.import` | One transaction writes pack row → course → plan + objectives → enrollment → lesson runs/segments → source ledger. `resume` re-opens the existing classroom; `fresh` cuts a new course over the same immutable content. Idempotency key replays the first result. |
| `pack.export` | Rebuilds the pack field-by-field from `packs.export_allowlist()`, refuses unless `options.expected_content_hash` equals the rebuilt hash, writes a deterministic archive, re-reads and re-hashes it, records an artifact, and returns the pack content hash. |
| `pack.delete` | Stays with the kernel (data-scope preview + freeze). This module keeps the *library index* honest via `sync_tombstones()`. |

Registration rides the single existing wiring point in `coursebook/hooks.py` (the same one the
kernel uses), so `__init__.py`/`api.py` stay untouched.

**Invariants enforced in code**

1. **A rejected pack leaves no course residue.** Schema, bounds, MIME, hash and teaching audit all
   run in `validate_and_audit()` *before* the first write; the DB work is one transaction; adoption
   is a filesystem rename before it. Tests assert every course/plan/objective/enrollment/pack
   count is zero after each refusal.
2. **Pack identity ≠ enrollment identity.** Content is stored once per `pack_id` + immutable
   `pack_version`; `fresh` adds a course and an enrollment, never a second copy of the files.
3. **A parent pack never becomes an adult graded course.** The recipe is taken from the manifest
   and there is no request field that can change it. `objective_criteria()` refuses to copy a
   check spec for `recipe == "parent"`, so `check.open` answers `objective_not_checkable`; the
   assessment dial is pinned to `none`. Cross-recipe conversion is `build_conversion()`, which
   refuses without `confirm=True` and a *new* `pack_id` and `pack_version`, records
   `derived_from`, and never mutates the installed pack.
4. **Export cannot carry private state.** `contains_private_fields()` is checked on the built
   document, the archive is re-read and re-hashed after writing, and the response hash is proven
   equal to the reviewed hash (tests + trace below).
5. **An interrupted import is visible, not silent.** Each import journals a `jobs` row
   (`kind=import`). `recover_interrupted_imports()` marks leftovers
   `interrupted_requires_retry`, so `jobs.list` counts them; staging trees are reconciled on
   startup; a lost `staged_id` after restart is an explicit refusal.

**Checks are audited, never assumed.** A manifest check becomes gradable only if the importer's
deterministic audit passes (non-empty stimulus/reference/rubric, reference not leaked into the
stimulus, alternatives add a form). The spec records `audit_source: import_automated_audit` and
`declared_audit_state` from the pack, so the difference between "automated" and "human reviewed"
stays visible. `human_review_recorded` is never synthesized.

## UI — `desktop/plugin.js` (on Vellum's CB-005 shell, commit 75d6035)

Vellum's contribution ids are untouched; everything lives inside the route page as internal
components, and `IMPORT_FLOW_WIRED` is now `true` (Vellum's flag for exactly this hand-off).

* **Import** — folder picker (`ctx.files`) → host grant route `POST /packs/grant` → `pack.preview`.
  The intake is capability-probed (`GET /packs/intake`); when the host route is absent the screen
  says so instead of rendering a picker that cannot deliver. The review screen shows author,
  attribution, licence + redistribution, locale/level, content hash, file count and expanded
  size, integrity result, every trust label *separately* with its meaning, content/safety notes,
  all outcomes with check counts, every source with `support_status` and "linked, not bundled",
  and every file with role/mime/bytes. A parent pack shows the Parent Studio notice on the review
  screen and never offers a graded path.
* **Resume vs fresh** — one screen after review. Resume is offered only when `library.list`
  already holds an enrollment for that `pack_id` (and names it); fresh is always available. The
  copy explains that the content is shared and the choice is progress only. The import result
  names the pack, course and enrollment; the pack stays cached for export review.
* **Export** — from a Library row: full file list (path/role/size) + content hash + explicit
  confirmation → `pack.export` with `expected_content_hash` → the UI *re-checks* that the returned
  hash equals the reviewed hash, then `artifact.get` shows artifact id, file hash, expiring
  session-bound handle and byte count. Without a reviewed manifest in this session it refuses to
  export blind (no second-hand hash).
* **Remove pack** — `pack.delete` dry run shows course/enrollment/artifact counts and what is
  preserved (evidence, attempts, notebook notes, source ledger, exports), then freeze with the
  returned `data_scope_hash`. Frozen packs show the kernel's `pack_frozen` warning and lose the
  remove action.
* **Parent routing** — a `recipe: parent` row shows the Parent Studio notice in its detail view;
  parent blueprints are never presented as graded adult courses.

## Evidence

`bash scripts/validate.sh` → **Validation passed** (360 unit tests, `node --check`, catalog
admission, doctor, 9/9 mounted-backend expectations).
New tests: `tests/test_pack_flow.py` — **26 cases** covering preview shape/labels, import
projection (plan hash equals `domain.plan_hash`), lesson page materialization, fresh/resume
semantics, idempotent replay, no-residue refusals (hash tamper, traversal, active markup, newer
minimum version), parent guard + conversion, export hash equality + private-field exclusion +
reimport, export refusals, delete/tombstone with evidence retained, `library.list` frozen warning,
interrupted-import recovery, staging reconciliation, check audit, and registry membership.

`python3 scripts/pack-flow-trace.py` (real run, throwaway `HERMES_HOME`):

```
pack_id              japanese-affection-context-l0   version 1.0.0
pack content_hash    sha256:638ce371db6bf2340a7b6a37a75a9762e0e9e6c3f723e55b0a0a5103a8376d7f
preview              files 5 · expanded 16802 B · labels [integrity_verified,
                     automated_checks_passed, model_assessed_support]  (no human review)
import               course crs_de220e6c… enrollment enr_69332199…
export               hash == pack content_hash · files 5 · archive 14548 B
archive sha256       sha256:503f331675566ae7a8000558c1eeb78a9ffd6a740263ccdf4f40322d3815cd97
artifact             application/zip · 14548 B · handle resolved, hash verified
re-import            same pack_id, distinct course (progress separated)
delete               frozen · scope counts {courses 2, enrollments 2, artifacts 1, sources 12,
                     jobs 2} · preserved evidence/attempts/notebook/source ledger/exports
                     · enrollments still present afterwards
```

## Cross-owner edits (recorded, minimal)

* `coursebook/hooks.py` — one registration import appended next to the kernel's (the shared
  single wiring point; non-overlapping).
* `coursebook/domain.py` — `binding.get` now refuses *both* identifiers and refuses on an
  unmigrated database, matching `coursebook/api.py`'s documented semantics that the mounted-backend
  probe asserts; runtime-id resolution is left as the kernel had it.
* `tests/test_platform_binding.py` — pins the platform `binding.get` handler so the module's
  result no longer depends on import order once the kernel is loaded.
* `tests/test_rpc.py`, `tests/test_contracts.py` — the "unimplemented method" case now removes a
  handler instead of naming `pack.preview`, which is implemented.
* `scripts/probe-backend.py` — the "method not in the mounted contract" probe used
  `library.list`, which the kernel now implements; it uses a method absent from the contract.
* `desktop/plugin.js` — appended inside Vellum's shell (their explicit hand-off), flag flipped.

## Known limits / seams owned elsewhere

1. **Host intake route.** `staged_id` can only come from a host file grant. `GET /packs/intake`
   and `POST /packs/grant` must be added to `dashboard/plugin_api.py` (Sable) — spec below. Until
   then the Import screen states this plainly and the picker is not shown.
2. **Artifact download route.** `artifact.get` returns a session-bound, expiring handle and
   `pack_flow.open_artifact(handle)` resolves it with hash/size verification; the HTTP route
   `/api/plugins/coursebook/artifacts/<handle>` is Sable's (Cinder's handoff too). The Desktop
   export panel shows the handle, hash and byte count and says the host route serves it; it does
   not fake a download.
3. **No `pack.list`.** `library.list` lists enrollments, not installed manifests, so the UI can
   only re-list a pack's files from a preview reviewed in this session. A `pack.list` (or
   `pack.inspect`) in a v3 amendment is the honest fix; flagged to Atlas and noted in the UI copy.
4. **Live Desktop capture** is CB-020/Sable's installed-profile run. This packet ships the code,
   the flag flip, and the RPC-level evidence above; no screenshot is claimed.
