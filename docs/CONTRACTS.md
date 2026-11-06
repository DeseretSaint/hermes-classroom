# Coursebook contracts — authoritative files and owners

Status: **frozen at v2** (CB-018 additive amendment). Governed by `PREBUILD_SPEC.md`
(architecture) and `UX_SPEC.md` (interface). Owner of every contract: **Atlas**. Implementers are
the specialists named below.

A contract file is the single authority for its vocabulary, payload shapes and error codes.
No module may redeclare an enum or error code that lives in `contracts/`. Python reads them
through `coursebook/contracts.py`; the Desktop half reads them from the backend
(`GET /api/plugins/coursebook/schema`) instead of embedding a copy.

## The contract set

| Contract id | File | Ver | Implementer | Consumers |
|---|---|---|---|---|
| `cb.vocabulary` | `contracts/vocabulary.v1.json` | 1 | Atlas | every other contract (shared enums, hashes, ids) |
| `cb.errors` | `contracts/errors.v2.json` | 2 | Atlas | RPC envelope, job errors, HTTP mapping |
| `cb.rpc` | `contracts/rpc.v2.json` | 2 | Cinder (kernel methods), Sable (transport) | Desktop half, Coursebook tools, `pre_llm_call` |
| `cb.db` | `contracts/db.v2.json` | 2 | Cinder | migrations, every command, evidence views |
| `cb.jobs` | `contracts/jobs.v2.json` | 2 | Cinder | job service, Activity view |
| `cb.pack` | `contracts/pack-manifest.v1.json` | 1 | Lattice | import/export, bundled demo packs |

The v1 files for `cb.rpc`, `cb.errors`, `cb.db` and `cb.jobs` remain on disk, unmodified, as
immutable history. `CONTRACT_FILES` in `coursebook/contracts.py` points each id at its current
version only. `audit_contracts()` rejects any `$ref` that still targets a superseded version.

Each document carries `$id` (versioned URI), `x-contract-id`, `x-contract-version`, `x-owner`
and, where superseded, `x-supersedes`. `tests/test_contracts.py` asserts that the id, the
version in the URI and the declared version agree for every file.

## Wire rule

`cb.rpc` is transport-neutral. The root schema validates a **request envelope**:

```json
{ "contract": "cb.rpc", "contract_version": 2,
  "method": "attempt.submit", "operation_id": "op-...", "idempotency_key": "...",
  "expected_revision": 12, "payload": { } }
```

Success and failure are separate envelopes (`$defs/envelope_response_ok`,
`$defs/envelope_response_error`). Every method has `request` and `response` payload schemas in
`$defs.methods`; `coursebook.api.dispatch` validates the envelope, then the payload, then runs the
handler, then validates the handler's result against the response schema. A handler that returns
something outside the contract becomes `INTERNAL_ERROR` — it is never rendered.

Envelope-level requirements added by v2 (enforced by the schema before any handler runs):

| Method(s) | Required envelope fields |
|---|---|
| `attempt.submit` | `idempotency_key`, `expected_revision` |
| `lesson.begin` | `idempotency_key` (a double click must not mint two chats) |
| `enrollment.delete`, `pack.delete` | `idempotency_key`, `expected_revision` |
| `enrollment.update`, `notebook.update`, `binding.abandon` | `expected_revision` |

`POST /api/plugins/coursebook/rpc` always answers **HTTP 200** with a contract envelope. A refused
command is `ok:false` with an error code; a transport failure is the only reason a client sees an
HTTP error. That keeps the Desktop half to one branch (`response.ok`) instead of two.

### State and identity rules baked into the contract

* Every mutation is fenced by `expected_revision` and refused with `STALE_REVISION` +
  `current_revision` rather than silently winning.
* `attempt.submit` **requires** `idempotency_key` and `expected_revision`. Repeating a key with the
  same payload hash returns the persisted original result; the same key with a different payload is
  `IDEMPOTENCY_CONFLICT`.
* Evidence classes are fixed: `cold`, `hinted`, `answer_shown`, `self_reported`, `parent_reported`,
  `override`. Only `cold` can count as independent evidence; `override` grants access, never mastery.
* `bindings.status` of anything other than `active` refuses a submit with `BINDING_NOT_ACTIVE`.
* Ids are minted by Coursebook (`identifier` pattern). Titles, paths and chat session ids are never
  primary keys — that is the R1 finding in `AUDIT.md`.

## v2 delta (CB-018)

v1 froze 24 methods. Operator review found screens the UX contract requires but the wire could not
serve: the library could not be listed after restart, a textbook section had no durable page or
resumable run, activity jobs could not be listed, an exported pack artifact could not be fetched,
and a notebook entry could not be edited. v2 adds ten methods and nothing else; every v1 method and
payload is byte-identical (asserted in `tests/test_contracts.py`).

| New method | Purpose | Request (required fields) | Response (required fields) |
|---|---|---|---|
| `library.list` | Courses home after restart: search/filter/sort, next step, provenance, empty states | `query?`, `filter`, `recipe?`, `sort`, `limit`, `cursor?` | `items`, `next_cursor`, `total`, `empty_reason`, `applied_filter` |
| `lesson.page` | Durable Textbook section page; read-only navigation, never changes evidence | `enrollment_id`, `objective_id`, `section_id?` | `course`, `section`, `runtime`, `segments`, `sources`, `artifacts`, `checks`, `notebook_entries`, `attempts`, `state`, `revision` |
| `lesson.begin` | Resume or start a section's durable lesson run | `enrollment_id`, `objective_id`, `mode` (`resume`/`fresh`) | `lesson_run_id`, `run_state`, `binding`, `resume`, `revision` |
| `enrollment.update` | Archive/unarchive/pause/resume an enrollment (reversible) | `enrollment_id`, `action` | `enrollment_id`, `status`, `revision` |
| `enrollment.delete` | Delete one enrollment's learning data, with previewed scope | `enrollment_id`, `dry_run`, `data_scope_hash?` | `deleted`, `data_scope`, `revision` |
| `pack.delete` | Remove one imported pack's content, preserving evidence | `pack_id`, `dry_run`, `data_scope_hash?` | `deleted`, `data_scope`, `revision` |
| `artifact.get` | Metadata + authenticated, expiring download handle | `artifact_id`, `disposition?` | `artifact_id`, `course_id`, `kind`, `mime`, `bytes`, `content_hash`, `provenance`, `download` |
| `jobs.list` | Activity/recovery list, bounded and filterable | `state[]`, `kind[]`, `enrollment_id?`, `since?`, `limit`, `cursor?` | `jobs`, `next_cursor`, `counts` |
| `notebook.update` | Edit note/tags in place without touching provenance | `entry_id`, `note?`/`tags?` | `entry_id`, `revision` |
| `binding.abandon` | Retire a detached/branched/orphaned binding so resume stops offering it | `binding_id`, `reason?` | `binding_id`, `status`, `revision` |

`cb.errors` v2 adds one code: `DELETE_SCOPE_STALE` (conflict, HTTP 409, not retryable) — the
deletion data scope changed between preview and confirmation; nothing was deleted.

`cb.jobs` v2 adds `$defs.job_state`, so `jobs.list` filters reference the single job-state
authority instead of redeclaring it.

### `library.list` semantics

* `filter` is one of `all`, `in_progress`, `review_due`, `archived` (the UX §6 filter row).
* `empty_reason` distinguishes "nothing yet" (`no_courses`), "everything is archived"
  (`all_archived`) and "this filter matched nothing" (`no_matches`). The client must preserve the
  course list and offer **Clear filter** only for `no_matches`.
* `next_step` is a navigation summary (`kind` + human `label`), deliberately separate from the
  post-attempt transition enum `cb.vocabulary#next_action`. A course row can say "Parent pack
  awaiting review" without inventing a transition.
* `evidence_summary` carries counts only (`independent`, `review_due`, `total_objectives`). There is
  no global mastery percentage.
* `provenance.source` is `bundled` / `local` / `community` / `authored` with optional pack id and
  version. Archived rows are returned only when `filter = archived` (or `all` with the archived
  flag excluded by the handler; the client never guesses).

### `lesson.page` semantics

Read-only GET-shaped method: it renders the durable page and **never** opens a check, submits an
attempt, or advances an objective. Jumping backward in the textbook cannot erase later evidence
because nothing is written. `runtime` is null when the section has never had a run. Segment text is
the backend-owned teaching record; the Hermes chat transcript is not required and is not a field.

### `lesson.begin` semantics — resume vs fresh, stale sessions, detached chats

* `mode: "fresh"` always mints a new `lesson_run_id` and a new active binding. The previous run is
  paused, not rewritten. A repeated call is idempotent by `idempotency_key`.
* `mode: "resume"` resolves by the **stored binding**, never by recency or chat title. It returns
  the existing run with `run_state: "resumed"` and `resume.available: true`.
* If no run exists for the section, `resume` behaves like `fresh` and returns
  `run_state: "created"`.
* If a binding exists but its runtime session is gone, the backend tries `stored_session_id`. If
  neither resolves, it returns the existing `lesson_run_id` with
  `run_state: "needs_fresh_run"`, `resume.available: false`, `reason: "session_missing"`, and the
  binding's current `status` unchanged. It does **not** silently bind another chat.
* If the binding is `detached`, `branched`, `orphaned` or `completed`, the same
  `needs_fresh_run` response is returned with that status as `reason`. The UI banner offers
  **Start a fresh run** (`lesson.begin` with `mode: "fresh"`) or **Abandon binding**
  (`binding.abandon`). Evidence is preserved in every case.
* `binding.session_state` values: `live` (runtime id resolves), `stored_only` (only the stored id
  resolves; resume is still possible), `missing` (neither resolves).

### Deletion protocol — separate semantics, server-returned data scope

Archive is not delete, and deleting a chat is not deleting an enrollment. Three distinct methods:

1. `enrollment.update` with `action: "archive" | "unarchive" | "pause" | "resume"` — reversible
   status change, no data removed.
2. `enrollment.delete` — removes one enrollment's learning data. Preview first with
   `dry_run: true`; the response carries `data_scope` (counts, preserved material, `scope_hash`,
   human `summary`). The confirm dialog renders that summary; the destructive call must send the
   returned `data_scope_hash`, and is refused with `DELETE_SCOPE_STALE` if the scope changed.
   Preserved by construction: the course, plan and objectives, pack provenance, artifacts shared
   with another enrollment, exported files, and Hermes' own chat transcripts (host-owned).
3. `pack.delete` — removes one imported pack's content and freezes its courses. Preview/confirm the
   same way. Preserved: evidence, attempts, notebook entries, source ledger and already-exported
   files. Deleting locally authored work is `enrollment.delete`, not `pack.delete`.

Typed confirmation text stays client-side; the server owns the scope facts and the fence.

### `artifact.get` semantics

Returns metadata plus a `download` handle: a relative, authenticated URL on the plugin host
(`/api/plugins/coursebook/artifacts/<handle>`), `requires_session: true`, an `expires_at`, and
`single_use`. The contract has **no** filesystem-path field anywhere in the response; a handler that
returns one fails response validation and becomes `INTERNAL_ERROR`. This covers exported packs,
visuals and audio, and is the fetch step after `pack.export` returns an `artifact_id`.

### `jobs.list` semantics

Bounded (`limit` ≤ 100, `jobs` ≤ 100) and filterable by job state, kind, enrollment and `since`.
`counts` feeds the persistent status row without a second query. Full job objects are
`cb.jobs#/job`; the list never fabricates progress percentages.

### `notebook.update` semantics

Edits `note` and/or `tags` only. `excerpt`, `source_ref`, `objective_id`, `enrollment_id`,
`lesson_run_id` and `kind` are not in the request schema, so provenance cannot be rewritten and an
edit cannot create a duplicate entry. Revision-fenced like every other mutation.

## UX screen → method mapping

Every screen in §6, §7, §8, §10 and §11 is implementable against a method or a documented payload.

| UX spec | Screen | Method(s) / documented payload |
|---|---|---|
| §6 | Courses home: rows, search, filter, empty & filtered-empty, overflow | `library.list` (rows, `next_step`, `evidence_summary`, `warning`, `empty_reason`, `provenance`); `enrollment.update` (archive/unarchive); `enrollment.delete` (delete, previewed scope); `pack.delete` (delete imported pack); `artifact.get` (exported learning backup after `pack.export`); `binding.get` + `lesson.begin` (open bound chat) |
| §6 / §7 | Review-due row and review queue | `library.list` `filter=review_due`; `course.get` payload: plan objectives + evidence (below); `quiz.history` |
| §7 | Overview: current objective, next action, resume/start, recent event, status banners | `library.list` row; `course.get` `course` payload (below); `lesson.begin`; `binding.get` |
| §7 | Textbook: section list and durable lesson page, continue/fresh run, history | `lesson.page` (segments, sources, artifacts, checks, notebook saves, related attempts, state); `lesson.begin` (`resume`/`fresh`); `lesson.page.runtime` for bound-run status |
| §7 | Notebook: search, tag/course filter, edit note/tags, remove, open in textbook | `notebook.list`; `notebook.update`; `notebook.delete`; `lesson.page` (jump back to section) |
| §7 | Quizzes: attempts, original feedback, dispute, new version | `quiz.history`; `attempt.dispute`; `check.open` (new version); `lesson.page.attempts` |
| §7 | Plan: objective states, criteria, challenge-out, dials | `course.get` `course` payload (below); `progression.challenge_out`; `plan.replan`; `plan.approve` |
| §7 | Evidence: L1 attempts, L2 objective evidence, L3 recommendation | `course.get` `course` payload (below); `quiz.history`; `attempt.override`; `attempt.dispute` |
| §7 | Sources: provenance, support, staleness, claim count | `course.get` `course` payload (below); `lesson.page.sources` |
| §8 | Lesson workspace: objective/check pane, attempt states, feedback, continue, detached banner | `lesson.page`; `check.open`; `attempt.submit`; `attempt.override`; `binding.get`; `lesson.begin`; `binding.abandon` |
| §9 | Library and pack trust: preview, import, keep/review/refuse update | `pack.preview`; `pack.import`; `pack.export`; `artifact.get`; `library.list` `provenance.source` |
| §10 | Parent Studio: brief, research/review, approval, pack preview/export | `course.create` (`recipe: parent`); `jobs.create` (`kind: research` / `plan`) with the brief; `jobs.get`; `plan.approve`; `pack.preview` (manifest, integrity, trust); `pack.export`; `artifact.get` (tabs: parent guide, learner pages, answers, audio/visuals, sources are manifest file roles) |
| §11 | Activity, jobs, recovery: running/failed/stale/delivery/recovery/usage | `jobs.list` (states, progress, errors, checkpoints); `jobs.get`; `jobs.cancel`; `usage.summary` |

### `course.get` payload (documented, not re-schemaed)

`course.get`'s v1 response wraps `course` in an open object. v2 does not tighten it (that would be a
breaking change to a preserved payload); instead the payload is **required by this document** to
carry:

```
course: {
  course_id, title, recipe, locale, status, revision,
  plan: { plan_id, version, state, objectives: [
    { objective_id, ordinal, title, evidence_target, state, evidence_criteria[],
      attempts[], hints[], next_review_at, challenge_out_available } ] },
  evidence: { layers: [ { layer: 1|2|3, entries: [ { id, objective_id, kind, evidence_class,
      attempt_id, created_at } ] } ] },
  sources: [ { source_id, title, url, publisher, source_type, published_at, fetched_at,
      support_status, claim_count } ]
}
```

Cinder may implement that payload incrementally; the screen mapping above names exactly which
fields each §7 tab renders.

## Migration impact (cb.db v2)

Migration `0002_lesson_runs_segments_and_revisions.sql`:

* creates `lesson_runs` (one section may have many runs; at most one active/paused resumable run per
  enrollment+objective is a kernel invariant, not a title/recency lookup) and `lesson_segments`
  (backend-owned teaching records rendered by `lesson.page`);
* adds `bindings.lesson_run_id` and `bindings.objective_id`; existing bindings stay valid with NULL
  and are treated as detached for section resume until rebound;
* adds `notebook_entries.revision` for `notebook.update` fencing (existing rows start at 0);
* adds `packs.state` (`installed`/`frozen`/`removed`) and `packs.revision` for `pack.delete`
  (existing rows backfill to `installed`, 0).

Additive only: no v1 column is dropped or retyped, and no table is renamed. Deletion never cascades
into evidence, attempts or notebook entries, and never claims to erase Hermes' own transcripts,
backups, provider-side data, or artifacts referenced by another course.

## Changing a contract

1. Open an Atlas decision in the task thread. A semantic change is **not** a patch.
2. Add a new file (`rpc.v3.json`) and bump `$id`/`x-contract-version`/`x-supersedes`. Never edit a
   shipped version in a way that changes meaning; clients cache by version.
3. Update `CONTRACT_FILES` in `coursebook/contracts.py` and run
   `python3 -m unittest discover -s tests -t .`. `audit_contracts()` fails on a stale `$ref`
   version, a method-enum/payload mismatch, or a wire-constant/version disagreement.
4. Record the decision, the reason and the migration path below.

| Version | Date | Decision |
|---|---|---|
| v1 | 2026-11-06 | Initial freeze. 24 RPC methods, 17 tables, 16 error codes, 9 job states, 1 pack manifest. |
| v2 | 2026-11-06 | CB-018 additive amendment. 34 RPC methods (+library.list, lesson.page, lesson.begin, enrollment.update, enrollment.delete, pack.delete, artifact.get, jobs.list, notebook.update, binding.abandon), +DELETE_SCOPE_STALE, +lesson_runs/lesson_segments and revision fencing in cb.db v2, +$defs.job_state in cb.jobs v2. |

## Deliberate omissions (do not "helpfully" add these)

* No `mastered` boolean and no global progress percentage. Evidence states are distinct on purpose.
* No free-form `instructions` field in a pack or a check. Untrusted prose is content, never policy.
* No `provider`, `model` or credential field in a pack, and no `settings` passthrough.
* No `safe`/`verified` badge enum. Trust dimensions stay separate (`pack_trust_label`).
* No numeric attainment estimate field. Schedule arithmetic and attainment uncertainty are separate
  (R9); an estimate, if ever shown, is a `model_estimate` with limits, not a contract field.
* No transcript or notebook text in the pack schema, and none is obtainable by export options.
* No filesystem path in `artifact.get` (or any RPC response). Artifacts are fetched through an
  authenticated, expiring handle.
* No mutation in `lesson.page`; navigation cannot change evidence.
* No "delete everything" method. Archive, delete enrollment and delete imported pack are separate
  scopes with separate, server-returned data scope.

## Open questions for Atlas (blocking a *feature*, not this amendment)

1. **Aux grader task lane.** `ctx.llm` exists (`agent.plugin_llm.PluginLlm`), but which auxiliary
   task name Coursebook claims, and whether that needs `llm.task_override` consent, must be settled
   by Sentinel's probe #4 before `attempt.submit` gets a grader body.
2. **Workspace topology.** Is an isolated course workspace creatable outside any git root on the
   supported local topology, and does the Desktop half share it? Probe #3 decides; until then
   `TOPOLOGY_UNSUPPORTED` is the honest answer for remote backends.
3. **`pack.import` staging transport.** `staged_id` assumes a backend upload route. If the gateway
   offers no upload door, import uses an explicit local file grant and `staged_id` refers to a
   backend-registered staging record. Lattice must not invent a `file://` path.
4. **`artifact.get` transport.** The contract fixes a relative authenticated URL on the plugin host.
   Sable must confirm the gateway can stream an arbitrary bounded artifact through that route
   without buffering the whole file, or the response gains a short-lived signed handle instead. The
   contract forbids a filesystem path either way.
5. **`binding.abandon` vs. reattach.** Abandon is defined; "Reattach if valid" (§8) is served by
   `lesson.begin` `mode: resume` when `resumable`/`reattachable` is true. If the host cannot
   re-enter a stored session after a process restart, Session-lifecycle work (Cinder + Sentinel)
   must say so, and the banner degrades to **Start a fresh run** only.
