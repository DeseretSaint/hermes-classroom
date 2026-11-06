# Coursebook contracts — authoritative files and owners

Status: **frozen at v5** (CB-026 additive amendment; v4 = CB-024, v3 = CB-022, v2 = CB-018).
Governed by `PREBUILD_SPEC.md` (architecture) and `UX_SPEC.md` (interface). Owner of every
contract: **Atlas**. Implementers are the specialists named below.

A contract file is the single authority for its vocabulary, payload shapes and error codes.
No module may redeclare an enum or error code that lives in `contracts/`. Python reads them
through `coursebook/contracts.py`; the Desktop half reads them from the backend
(`GET /api/plugins/coursebook/schema`) instead of embedding a copy.

## The contract set

| Contract id | File | Ver | Implementer | Consumers |
|---|---|---|---|---|
| `cb.vocabulary` | `contracts/vocabulary.v1.json` | 1 | Atlas | every other contract (shared enums, hashes, ids) |
| `cb.errors` | `contracts/errors.v2.json` | 2 | Atlas | RPC envelope, job errors, HTTP mapping |
| `cb.rpc` | `contracts/rpc.v5.json` | 5 | Cinder (kernel + learning-loop methods), Sable (transport), Lattice (`pack.*`) | Desktop half, Coursebook tools, `pre_llm_call` |
| `cb.db` | `contracts/db.v2.json` | 2 | Cinder | migrations, every command, evidence views |
| `cb.jobs` | `contracts/jobs.v2.json` | 2 | Cinder | job service, Activity view |
| `cb.pack` | `contracts/pack-manifest.v1.json` | 1 | Lattice | import/export, bundled demo packs |
| `cb.projection` | `contracts/projection.v1.json` | 1 | Atlas (contract), Lattice (importer) | pack import, Parent Studio generation, community upload review |

The v1 **to v4** files for `cb.rpc`, `cb.errors`, `cb.db` and `cb.jobs` remain on disk, unmodified,
as immutable history. `CONTRACT_FILES` in `coursebook/contracts.py` points each id at its current
version only. `audit_contracts()` rejects any `$ref` that still targets a superseded version.
`tests/test_contracts.py` pins the sha256 of every superseded `rpc.v*.json`, so "additive" is a
fact about the bytes rather than a claim about a diff.

Each document carries `$id` (versioned URI), `x-contract-id`, `x-contract-version`, `x-owner`
and, where superseded, `x-supersedes`. `tests/test_contracts.py` asserts that the id, the
version in the URI and the declared version agree for every file.

## Wire rule

`cb.rpc` is transport-neutral. The root schema validates a **request envelope**:

```json
{ "contract": "cb.rpc", "contract_version": 5,
  "method": "attempt.submit", "operation_id": "op-...", "idempotency_key": "...",
  "expected_revision": 12, "payload": { } }
```

Success and failure are separate envelopes (`$defs/envelope_response_ok`,
`$defs/envelope_response_error`). Every method has `request` and `response` payload schemas in
`$defs.methods`; `coursebook.api.dispatch` validates the envelope, then the payload, then runs the
handler, then validates the handler's result against the response schema. A handler that returns
something outside the contract becomes `INTERNAL_ERROR` — it is never rendered.

Envelope-level requirements added by v2, v3 and v5 (enforced by the schema before any handler runs).
v4 adds none: both of its methods are reads, so they carry neither `idempotency_key` nor
`expected_revision`. `course.outline` and `check.get` (v5) are reads for the same reason; only
`lesson.assist` is a command:

| Method(s) | Required envelope fields |
|---|---|
| `attempt.submit` | `idempotency_key`, `expected_revision` |
| `lesson.begin` | `idempotency_key` (a double click must not mint two chats) |
| `enrollment.delete`, `pack.delete` | `idempotency_key`, `expected_revision` |
| `enrollment.update`, `notebook.update`, `binding.abandon` | `expected_revision` |
| `review.action` | `idempotency_key`, `expected_revision` |
| `lesson.assist` | `idempotency_key`, `expected_revision` |

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

## v3 delta (CB-022)

CB-008 proved the learning loop in the backend — `coursebook/review.py` derives the review queue and
records learner review actions, `coursebook/evidence.py` assembles the L1/L2/L3 view and the dispute
history — but none of it had a wire method, so the Desktop review queue and Evidence tab had no
command path. v3 adds four methods and nothing else. Every v1 and v2 method and payload is
byte-identical (asserted in `tests/test_contracts.py`).

| New method | Purpose | Request (required fields) | Response (required fields) |
|---|---|---|---|
| `review.queue` | Derived review queue for one enrollment: due first, then upcoming, capped but never hiding the backlog | `enrollment_id`, `cap?`, `include_upcoming?` | `enrollment_id`, `items`, `total_due`, `total_overdue`, `total_scheduled`, `upcoming_hidden`, `now`, `cap` |
| `review.action` | Learner scheduling command: `snooze` / `stretch` / `drop` / `resume`, recorded as layer-1 self-reported evidence | `enrollment_id`, `objective_id`, `action` + envelope `idempotency_key`, `expected_revision` | `objective_id`, `action`, `recorded_at`, `state`, `due_at` |
| `evidence.inspect` | The Evidence pane in one read: L1 raw record, L2 per-objective claim, L3 revisable recommendation, dispute history | `enrollment_id`, `objective_id?`, `limit?` | `l1`, `l2`, `l3`, `disputes` |
| `evidence.disputes` | Bounded, attempt-filterable dispute view for the Evidence tab's dispute section | `enrollment_id`, `attempt_id?`, `limit?` | `enrollment_id`, `disputes`, `count`, `truncated` |

### `review.queue` semantics

* The queue is **derived**, not stored: a cold layer-2 pass (`independent_evidence` /
  `delayed_retrieval`) starts the clock, `review_snooze` restarts it, `review_stretch` and another
  `delayed_retrieval` advance the ladder step, `review_drop` removes the item and `review_resume`
  puts it back. There is no `review_schedule` table, because a second copy of "what is due" would be
  a competing authority (AUDIT R5).
* `cap` (default 10, max 50) bounds `items` only. `total_due`, `total_overdue`, `total_scheduled`
  and `upcoming_hidden` are always the full counts, so a hidden backlog cannot look like an empty
  queue.
* `now` is the **backend** clock and is returned, never accepted. A client cannot age its own queue.
* `interval_days`, `step` and `ladder_days` are exposed so the UI can say what the schedule is
  arithmetic over. They are a declared heuristic per `evidence_target`, never an attainment
  prediction (AUDIT R9/R10) — the contract forbids a `mastery` / `retention` / percentage field.
* Due-objective state changes (`independent_evidence` / `delayed_evidence` → `review_due`) are made
  by the scheduler tick that already runs inside `library.list` (`review.refresh_due`). There is no
  `review.refresh` method: staleness of the objective state is the backend's problem, not a
  command the Desktop has to remember to send.

### `review.action` semantics

* The four actions are scheduling preferences, never evidence of knowing or not knowing anything:
  each is stored as a layer-1 event with `evidence_class: self_reported`.
* It is a learner command, so it is fenced exactly like the other mutations: `expected_revision` and
  `idempotency_key` are required **in the envelope**, validated before any handler runs, and the
  new revision comes back in the response envelope. The payload deliberately carries no
  `expected_revision` and the result carries no `revision`: one fence, one authority.
* `state` and `due_at` in the response are the post-action truth the queue must re-render from
  (`drop` and `resume` change `objectives.state`; `due_at` is `null` once the item is dropped).
* An action on an objective that is not part of the enrollment's approved plan is `VALIDATION_FAILED`;
  a stale `expected_revision` is `STALE_REVISION` with `current_revision`.

### `evidence.inspect` / `evidence.disputes` semantics

* Three layers keep three different claims. L1 is what happened (attempts, hints, shown answers,
  overrides, review actions) and includes the learner's own committed answer, `answer_hash`,
  `criteria` and public `provenance`. L2 is the per-objective claim and is only `independent: true`
  when a cold committed pass links to it (`L2_evidence_ids`). L3 is a short, revisable
  recommendation with an explicit `basis`, and `is_persona` is `false` by contract.
* Nothing in the evidence view may return a reference answer, rubric internals, raw grader output or
  a chat transcript. `tests/test_contracts.py` rejects those property names outright.
* Disputes stay inside `attempts.grading_provenance_json` in `cb.db` v2. v3 does **not** add a
  `disputes` table: there is exactly one writer (`attempt.dispute`, inside the attempt transaction),
  the volume is bounded by that enrollment's attempts, and a second table would need a dual-write
  migration for no proven query need. `evidence.disputes` is the storage-independent read view, with
  `count` = all matching disputes and `truncated` telling the pane that the bounded list omitted
  some. If disputes ever need course-wide filtering or indexing, that is a `cb.db` v3 migration with
  a backfill from provenance, not a quiet addition to this view.

### Handlers Cinder must register (after this freeze)

The backend implementations exist on `wt/cb-008-cinder`; wiring is registration plus response-shape
mapping, no new semantics:

| Method | Register in | Backing code | Handler must do |
|---|---|---|---|
| `review.queue` | `coursebook/api.py` (`register_handler`) or the kernel's `_handler` decorator | `review.queue(connection, enrollment_id, cap=..., include_upcoming=...)` | pass the payload through, add `enrollment_id` to the result (the backend already returns it) |
| `review.action` | same | `review.apply_action(connection, enrollment_id=..., objective_id=..., action=...)` | inside one transaction: `expected = _require_revision(envelope)`, `revision = _bump_enrollment(connection, enrollment_id, expected)`, apply, then re-read the objective for `state`; return `(revision, result)`; persist the idempotency key via `_remember` |
| `evidence.inspect` | same | `evidence.bundle(connection, enrollment_id, objective_id=...)` | map the payload's `limit` onto `layer1(limit=...)`; `bundle()` already returns `{l1, l2, l3, disputes}` in contract shape |
| `evidence.disputes` | same | `evidence.disputes(connection, enrollment_id, attempt_id=...)` | slice to `limit`, set `count` to the full length and `truncated` to `count > limit` |

Because `api.register_handler` and `api.dispatch` validate the payload before the handler and the
result after it, a half-wired method fails as `NOT_IMPLEMENTED` or `INTERNAL_ERROR` — never as a
convincing empty queue.

After wiring, run `python3 -m unittest scripts.proof_contract_v3 -v` in a worktree that contains the
CB-008 kernel. Five tests drive the real commands against a real SQLite database built by the real
migrations and validate the real outputs against `rpc.v3.json`; on a branch without the kernel they
skip with a stated reason rather than passing. The proof already established the exact deltas this
section documents: `review.queue` and `evidence.inspect`'s three layers are contract-shaped as
returned, `review.apply_action` needs `state` (and `due_at` from the queue) added by the handler, and
`evidence.disputes` needs `truncated`.

## v4 delta (CB-024)

CB-010 wired the pack lifecycle — `pack.preview`, `pack.import`, `pack.export`, `pack.delete` — and
proved the loop end to end, then found one gap the Desktop could not work around without inventing a
field: **there was no way to read an installed pack.** `library.list` enumerates *enrollments*
(`courses JOIN enrollments`), so a pack that is installed but not enrolled — imported with
`mode: resume` refused, or after `enrollment.delete` — is invisible; and `pack.preview` requires a
`staged_id`, i.e. a freshly granted file. The only way to re-render a manifest was to re-import it.

That made CB-010's export review carry a `previewCache`: the UI exported only a manifest it had
reviewed *in the same session*, and refused to export blind rather than export against a hash it
could not show. Safe, but it turned "export any installed pack" into a two-step re-import. v4 adds
two read-only methods and nothing else; every v1, v2 and v3 method and payload is byte-identical
(asserted in `tests/test_contracts.py`).

| New method | Purpose | Request (required fields) | Response (required fields) |
|---|---|---|---|
| `pack.list` | Every adopted pack identity, enrolled or not, with the revision `pack.delete` fences on | `pack_id?`, `pack_version?`, `filter`, `limit` | `items[]`, `total`, `truncated`, `applied_filter` |
| `pack.inspect` | One installed pack read from the library: manifest, integrity, trust labels — no upload grant | `pack_id`, `pack_version` | `pack`, `manifest`, `integrity`, `trust` |

No table, column, migration or error code is added: both methods read state that adoption and
`pack.delete` already write. `cb.db`, `cb.errors`, `cb.jobs` and `cb.pack` stay at their current
versions. Refusals use the existing `NOT_FOUND` (unknown identity) and `PACK_REJECTED` (unsafe or
unreadable identity) codes.

### `pack.list` semantics — one authority per fact

* **The library index is the installed-pack authority.** Adoption writes it, so an identity present
  there is installed, whether or not any course was ever cut from it. That is exactly the row
  `library.list` cannot show.
* **The kernel `packs` row wins for `state` and `revision`** when one exists; the index's own
  `state` is the fallback (this is the difference `sync_tombstones` reconciles at startup). One item
  per `(pack_id, pack_version)`; there is no second copy of either fact in the response.
* **`revision` is why this method is required for deletion.** `pack.delete` demands
  `expected_revision` and refuses with `STALE_REVISION` otherwise, and nothing else on the wire
  exposed a pack's revision. The list row supplies it (`coursebook.domain.pack_delete` is the
  reader that fences on it); the delete preview still comes from `pack.delete` `dry_run: true` and
  its server-returned `data_scope_hash`.
* **Counts come from the stored manifest** (`file_count`, `expanded_bytes`), which adoption already
  validated and bounded. `pack.list` therefore reads one small manifest per item and deliberately
  does **not** return the manifest itself; `pack.inspect` is the read that returns it.
* **Bounded, not paged.** `limit` ≤ 200 and `items` ≤ 200; `total` is always the full count and
  `truncated` says the list omitted rows. There is no cursor: a pack library that exceeds 200
  identities is narrowed with `pack_id`/`pack_version`/`filter`, not scrolled.
* **Ordering** (documented, not schema-expressible): `installed_at` descending, then `pack_id`, then
  `pack_version` ascending — a stable order so two renders of the same library agree.
* **No filesystem path, no enrollment claim, no manifest.** The library index stores an absolute
  `directory`; it is storage. Enrollment state stays with `library.list` (keyed by
  `provenance.pack_id`/`pack_version`), because a pack row that also claimed "enrolled" would be a
  second authority for the same fact.
* `filter` is `all` / `installed` / `frozen` / `removed` and echoes back as `applied_filter`.
  `removed` is reserved by the `cb.db` v2 migration and is **not produced by this build**; the
  contract names it so a future writer does not need a wire bump.

### `pack.inspect` semantics — preview without a grant

* Reads the adopted directory through `archive.PackLibrary.read()`, re-validates the manifest
  against `cb.pack` and **recomputes** the content hash over the bytes on disk.
* `integrity.hashes_match` is an honest boolean: `true` only when the recomputed hash equals the
  stored `manifest_hash` and every declared file's size and sha256 match. Drifted content is
  reported, not raised — the review screen can then refuse the export instead of the pane dying.
  A `pack.inspect` that cannot read the directory at all is `NOT_FOUND`.
* `trust.labels` is the same four-dimension list `pack.preview` returns
  (`integrity_verified`, `automated_checks_passed`, `human_review_recorded`,
  `model_assessed_support`), computed by `packs.trust_labels()` from the stored manifest. There is
  still no `safe` or `verified` badge.
* `content_hash` in `pack` is the identity `pack.export` is checked against: the export request
  carries `options.expected_content_hash`, so the UI can show the hash it inspected and the backend
  refuses if the archive would not reproduce it. That is what replaces `previewCache`.
* Read-only, GET-shaped: it never stages, adopts, imports, exports or deletes.

## The pack-check → check-spec projection (cb.projection v1)

The second gap CB-010 recorded was that the manifest-check mapping lived in importer code. `cb.pack`
checks are `{stimulus, rubric[], reference_answer, accepted_alternatives, evidence_target, locale,
audit_state}`; the kernel grades `{stimulus: {prompt}, reference: {kind}, rubric: {criteria}}`.
`coursebook.pack_flow.check_spec_from_pack_check` and `::objective_criteria` define the projection,
but import is only the **first** consumer: Parent Studio generation and community upload review need
the same mapping. Two implementations of one mapping is how a pack starts grading differently in two
places, so v4 freezes it in `contracts/projection.v1.json` (`cb.projection`, v1) and the importer
applies that contract instead of restating it.

`cb.projection` is a new contract **id**, not a new `cb.pack` version: the manifest did not change,
only the derivation from it is now frozen. Its `$defs.check_spec` is the machine-checkable shape of
what gets stored in `objectives.evidence_criteria_json`, and `$defs.objective_criterion` is the shape
of each criteria entry.

The gate, in order:

1. **P1 recipe gate.** `recipe == parent` yields no spec (`parent_observation_not_graded`). A parent
   observes; the harness never grades a child.
2. **R1–R6 audit.** `stimulus_present`, `reference_present`, `rubric_present`,
   `reference_not_in_stimulus`, `alternatives_add_a_form`, `declared_audit_not_failed`. Any failure
   yields no spec (`import_audit_failed`) and the problems are reported verbatim.
3. **Projection.** `audit_state: passed`, `audit_source: import_automated_audit`,
   `declared_audit_state` preserved, `stimulus.prompt` trimmed, `reference` = `rubric_only` for
   `production`/`transfer` and `exact` (reference plus declared alternatives) otherwise,
   `rubric` = `{construct, pass_rule: "all", criteria: [{id: c<N>, description}]}` with positional
   ids over the raw rubric array, `locale` verbatim or `null`.
4. **Criteria list.** `pack_objective` first, then `target<N>` per declared `evidence_criteria`,
   then one entry per check in manifest order — graded with `check_spec`, or withheld with
   `check_spec_withheld: true` and a reason. A withheld check stays visible; it is never silently
   dropped and no placeholder spec is invented.

A pack's own `audit_state` can refuse a check (`failed`) and can never grant one: a pack that
declares `passed` on a check whose reference answer is in the stimulus is still withheld, because
the deterministic audit is the only gate.

### Divergence record: both entries closed by CB-025

The freeze found two places where `coursebook/pack_flow.py` did not implement the frozen rules. Both
are recorded in the contract's `x-known-divergences` and both keep their conformance vector in
`examples` (marked `divergence` as provenance). Lattice closed both in CB-025 (commits `577d268`,
`725ffbf`), so the entries are `status: resolved` with a `resolved_by` commit instead of open defects:

| Id | Importer when frozen | Contract requires | Now |
|---|---|---|---|
| `empty-alternatives` | `all(...)` over an empty alternatives list was vacuously true, so **every** check declaring no accepted alternatives was withheld | an empty/whitespace-only list is not a flaw; the reference answer is already an accepted form | R5 has the non-empty guard. The bundled demo pack's `chk-register-transfer-1` (`accepted_alternatives: []`) projects, and `obj-register-transfer` opens through the real dispatcher (`ok: true`, `rubric_only`) |
| `declared-audit-failed` | a check declaring `audit_state: failed` was still projected when the automated audit passed, so the spec said `audit_state: passed` while `declared_audit_state: failed` | the author's `failed` withholds gradability | R6 withholds it; `check_spec_from_pack_check` returns `None`, so `declared_audit_state` in a stored spec is only `unreviewed` or `passed` |

`test_projection_matches_every_frozen_vector` no longer skips `divergence` examples: all 13 vectors
and both `objective_examples` run and match. The pinning tests that held the divergences in place were
deleted in the same commit, so a new divergence now shows up as a red vector rather than a red pin.

One wording fix came with the closure. R6 is listed as an audit rule with its own `problem`, and
`problem_order` says every failing problem is reported, but the `declared_failed_withholds` vector
used to expect `reason: "declared_audit_failed"` with `problems: []` — a reason vocabulary no
implementation emitted. The vector now expects what the shipped importer produces and what the other
five rules produce: `{"kind": "none", "reason": "import_audit_failed", "problems": ["the pack declares
this check failed its own audit"]}`. `declared_audit_state` in `$defs.check_spec` is likewise narrowed
to `passed`/`unreviewed`, which is what the projection note already claimed. Neither change alters a
stored spec, a wire payload or a handler, because the projection returns a spec or `None` and never
emits `reason`/`problems`; they make the frozen text agree with itself.

### Handlers to register (after this freeze)

| Method | Register in | Backing code | Handler must do |
|---|---|---|---|
| `pack.list` | `coursebook/pack_flow.py` `ensure_registered()` (Lattice) | `pack_flow.library().list()`, `db` `packs` rows, `packs.load_manifest()` | join index record to the `packs` row by `(pack_id, version)`; `state`/`revision` from the row, index as fallback; read the stored manifest for `file_count`/`expanded_bytes`; sort, filter, slice to `limit`, set `total` and `truncated`; never emit `directory` |
| `pack.inspect` | same | `pack_flow.library().read()` + `packs.preview(manifest, integrity=...)` | re-validate and re-hash, `hashes_match` = hash and per-file digests match, wrap `packs.preview()` output; `NOT_FOUND` when the identity is not in the library |
| `objective_criteria` / `check_spec_from_pack_check` | `coursebook/pack_flow.py` (Lattice) | `cb.projection` | apply the contract's rules; delegate rather than restate, and satisfy the conformance vectors |

Run `python3 -m unittest scripts.proof_contract_v4 -v` in a worktree that contains the CB-010 pack
lifecycle: it drives `check_spec_from_pack_check`/`objective_criteria` against the conformance
vectors and the two bundled demo packs, and composes `pack.list`/`pack.inspect` responses from a
real adopted pack and a real SQLite database, validating each against `rpc.v4.json`. On a branch
without that backend it skips with a stated reason rather than passing.

### Version numbering

v3 is frozen at four learning-loop methods. The draft v3 that carried `pack.list` on the unowned
`wt/cb-020-rpc-v3` branch had no backend function, no handler and no consumer, and it was not
adopted; this amendment supersedes it by putting the installed-pack read in v4 with its own owner,
its own storage analysis and its own proof. No shipped version file may be extended in place — v1,
v2 and v3 were not, v4 is not, and the three CB-026 methods therefore land in **v5** rather than
being bolted onto v4 (whose 40-method freeze is already referenced by the pack handlers and by
CB-024's review packet).

## v5 delta (CB-026)

CB-009 (the Desktop learning workspace) could not be built against `cb.rpc` v4 without the Desktop
half reading SQLite directly or inventing a second authority. Three surfaces of the signature
learning screen had no wire path:

* the **Textbook section index** and the **Plan tab** could name at most one objective
  (`library_item.evidence_summary.current_objective_id`) plus scheduled review rows, so "Textbook —
  sections, not one endless thread" and "returning to a past section" had no list to render;
* the **Coursebook pane** could submit an answer but could not show the question: `check.open`
  returns `{check_id, check_version, evidence_target, revision}` and nothing else, while the prompt,
  format and choices already sit in `checks.stimulus_json`;
* the pane's **Hint** and **Show answer** controls had no command path. `turn.py` writes
  `hint_request` / `answer_shown` as layer-1 evidence that the next committed attempt consumes, but
  only the chat hook could write them.

v5 adds three methods and nothing else; every v1, v2, v3 and v4 method and payload is byte-identical
(asserted in `tests/test_contracts.py`, which also pins the sha256 of each superseded `rpc.v*.json`).
`rpc.v3.json` and `rpc.v4.json` are untouched on disk.

| New method | Purpose | Request (required fields) | Response (required fields) |
|---|---|---|---|
| `course.outline` | Plan + flat objective index for one enrollment: the Textbook section list and the Plan tab | `enrollment_id` (`limit?`) | `enrollment_id`, `plan`, `objectives[]`, `total`, `truncated` |
| `check.get` | The structured stimulus of one check, by check id or by objective | `enrollment_id` + exactly one of `check_id`, `objective_id` | `check_id`, `objective_id`, `check_version`, `evidence_target`, `state`, `audit_state`, `stimulus`, `attempt_count` |
| `lesson.assist` | Pane-driven Hint / Show answer, recorded as a layer-1 event the next attempt consumes | `enrollment_id`, `objective_id`, `kind` + envelope `idempotency_key`, `expected_revision` | `event_id`, `kind`, `evidence_class`, `revision` |

No table, no column, no migration and no error code is added: every field is derived from
`plans`/`objectives`/`checks`/`lesson_runs`/`attempts`, or written to the existing `evidence` table
(`cb.db` v2). `cb.errors`, `cb.db`, `cb.jobs`, `cb.pack` and `cb.projection` stay at their versions.

### `binding.get` section identity (additive within v5 — CB-009 pane scope)

CB-009 found that `binding.get` returned neither `bindings.objective_id` nor `bindings.lesson_run_id`
even though `cb.db` v2 stores both, so the Coursebook pane could scope only by enrollment: it had to
render `library_item.evidence_summary.current_objective_id`, the enrollment's *current* section. A
chat bound to section 3 therefore displayed section 1's page and section 1's detached run. Live
evidence at the time: chat `20261106_072357_ad7e67` was bound active to `obj_9b596207…`
(`bind_eacdfd2382ed494582a00539e84b3465`) while the pane rendered `obj_2ec4b8ec…`.

The `binding` member of the `binding.get` response is declared as an **open object**
(`{"type": "object"}`, no `additionalProperties: false`) in `rpc.v5.json`, and `cb.db` v2 already
carries both columns. Emitting two fields the schema already permits is therefore additive within
v5: **no v6, no schema file change, no version bump.** `rpc.v5.json` is untouched on disk, so the
sha256 pins in `tests/test_contracts.py` still hold and every other v5 payload is byte-identical.

Both fields are required on **every** non-null `binding` answer:

| Field | Source | Meaning |
|---|---|---|
| `objective_id` | `bindings.objective_id` | the one section this chat governs; `null` for a legacy/course-level binding |
| `lesson_run_id` | `bindings.lesson_run_id` | the run that section was opened under; `null` when the binding never named a run |

Rules:

* **Status semantics are unchanged.** `status` is still the row's own status (`active`, `paused`,
  `detached`, `branched`, `orphaned`, `completed`) for the chat the request named. The section fields
  do not derive, override or relax it; a detached binding still refuses a submit.
* **`null` means "no section", never "this build did not answer".** A `cb.db` v1 binding table has no
  `lesson_runs`; the platform seam answers both fields as `null` there rather than omitting them,
  because every v1 binding is a course-level chat. A client can then tell a course-level chat from
  an unanswered field.
* **The write half already agrees.** `coursebook.bindings._view` has emitted both fields since
  CB-013; this amendment makes the read half (`binding.get`) match the row `bind_session` wrote, so
  there is one shape for a binding on the wire and not two.
* The value is read from the row, never recomputed from "the current section" or from recency: the
  pane scopes to the bound section, which is the point (AUDIT R1).

### What these three methods may not return

This is the reason the methods are small. Each one is a *view*, and a view that leaks the grading
authority would make the learning surface dishonest no matter how correct the rest is.

| Method | Never returned | Why |
|---|---|---|
| `course.outline` | any `reference_answer`, `reference`, `reference_json`, `rubric`, `rubric_json`, grading `criteria`, `evidence_criteria`, grading provenance, review schedule, learner label or filesystem path | It is an index. Scoring internals belong to the grader and the committed attempt row; the outline must be safe to render in a list with no attempt in flight. |
| `check.get` | `reference_answer`, `reference` / `reference_json`, `accepted_answers` / `accepted_alternatives`, `rubric` / `rubric_json`, `audit_source`, `declared_audit_state`, `grading_provenance`, `check_spec`, and any chat transcript | `grading.py` keeps the answer and the rubric separate from the stimulus on purpose, and `quiz.history` withholds them; the pane renders a question, never a key. |
| `lesson.assist` | any answer text, rubric, verdict, criteria or objective state | It records *that* scaffolding was used, never what the learner knows. Access is not evidence. |

The stimulus is built from a **closed allowlist** (`prompt`, `format`, `choices`,
`learner_instructions`). `checks.stimulus_json` is importer- and generator-written, so it can hold
keys nobody planned for; `check.get` drops what it does not recognise instead of echoing it, and
`additionalProperties: false` in the response schema means a handler that passes the JSON through
fails response validation and becomes `INTERNAL_ERROR` rather than a rendered answer key. The
contract tests exercise exactly that: a stimulus carrying `reference_answer` is refused.

### `course.outline` semantics

* **One plan authority, the same one `library.list` counts against.** `plan` is the course's
  approved plan; when there is no approved plan it is the highest-version plan, which is then a
  `draft` awaiting approval (`_current_plan_sql()` in the kernel). A `draft` state is therefore not
  an error: it is what the Plan tab shows the learner to approve. `plan` is `null` only when the
  course has no plan row at all.
* **Objectives are the sections.** Ordered by `ordinal`, bounded at 400 rows, with `total` always
  the full count and `truncated` saying whether rows were omitted. A short list never hides a long
  course.
* **Derived, never stored** — every field is one query over an existing row, with one authority per
  fact:

  | Field | Derivation |
  |---|---|
  | `state` | `objectives.state` verbatim (`cb.vocabulary#objective_state`) |
  | `check_state` | the objective's highest-version `checks` row: its `state`. `none` when the objective has no check row (never opened, or a draft plan's objective) |
  | `attempt_count` | `COUNT(attempts)` for **this enrollment** and this objective's checks with `state = 'committed'`. Failed `needs_retry` rows are not attempts at knowing |
  | `independent` | `true` only when `objectives.state` is `independent_evidence` or `delayed_evidence` — the same rule that makes `library.list.evidence_summary.independent`; it is a view of the state, not a second claim |
  | `last_opened_at` | `MAX(lesson_runs.last_opened_at)` for this enrollment + objective, `null` when the section was never opened |

* **Read-only and unfenced.** No revision bump, no transitions row, no idempotency key; the
  response envelope carries the read revision `0` like `library.list`. Opening the outline cannot
  change evidence.
* **No `section_titles`.** The draft of this card asked for a per-objective `section_titles[]`. The
  database has no heading field: `lesson_segments.text` is a verbatim teaching transcript (written by
  `turn.record_assistant_snapshot`), not a title, and `plans.schedule_json` is always `{}` in this
  build. Rather than freeze a fabricated label list — first lines of chat prose rendered as
  "sections" — the field is omitted: the section index **is** `objectives[]`, and a section's page is
  `lesson.page`. If authored headings ever exist they are a `cb.db` migration plus a v6 field, not a
  quiet string slice.

### `check.get` semantics

* **Two addressing modes, exactly one.** By `check_id` (the exact item the pane is showing) or by
  `objective_id` (the objective's open check, else its highest-version check). Both or neither is
  `VALIDATION_FAILED` before any handler runs.
* **Membership follows `check.open`/`attempt.submit`:** the objective must belong to the
  enrollment's course and to its **approved** plan, not the outline's current (possibly draft) plan.
  A check from another course is `VALIDATION_FAILED` with `reason: check_not_in_enrollment_course`; an
  unknown identity is `NOT_FOUND`.
* **Stimulus normalization is part of the contract**, because the storage is heterogeneous:
  `prompt` comes from the stored stimulus and is bounded at 8000 characters — the same bound
  `cb.pack` allows a pack check's stimulus, which is copied into `checks.stimulus_json` verbatim;
  `format` defaults to `text` when the stored stimulus declares none, which is the honest reading of
  an imported pack check (an open answer, and `cb.projection` v1 emits no format); `choices` is `[]`
  for a text item; `learner_instructions` is passed through when the generator stored it.
* **`audit_state` is exposed, and it is honest.** A check whose audit failed can still be rendered —
  the pane must be able to say why it refuses — but `attempt.submit` keeps refusing it with
  `POLICY_VIOLATION` / `reason: check_not_audited`. Seeing a question is not grading it.
* `attempt_count` counts committed attempts for this enrollment on this check only.
* Read-only: no revision bump, no transitions row. It never opens a check (`check.open` does that,
  and it is fenced) and never supersedes one.

### `lesson.assist` semantics

* **It is the same event the chat hook writes**, so it has the same shape: a layer-1 `evidence` row
  with `attempt_id = NULL`, `kind` in `hint_request` / `answer_shown`, and
  `evidence_class` `hinted` / `answer_shown` respectively. The next **committed** attempt on that
  objective consumes it (`UPDATE evidence SET attempt_id = ?`), which is what keeps a hint from
  contaminating a later, independent answer.
* **It must bump the enrollment revision.** This is not ceremony: `attempt.submit` classifies
  evidence inside its *read* transaction and then grades outside any transaction, so a hint recorded
  while a grade is in flight would be invisible to that classification and the answer would be
  committed as `cold`. Bumping the revision makes the in-flight submit lose the fence
  (`STALE_REVISION`, or `CHECK_STALE`), and the pane's resubmit is classified `hinted`. A hint that
  cannot change the evidence class is not a hint, it is a lie in the record.
* **No transitions row.** `review.action` already bumps a revision for an event that is not a
  transition (CB-022); the kernel's ledger is one row per *learner transition*, and a hint is an
  action, not a movement. `lesson.assist` follows that precedent exactly.
* **Preconditions**, all refused with existing codes:
  * the objective must be in the enrollment's approved plan (`VALIDATION_FAILED`,
    `reason: plan_not_approved` / `objective_not_in_plan`);
  * an **open check must exist** for the objective (`VALIDATION_FAILED`, `reason: no_open_check`).
    Without one the event can never be consumed by an attempt, and `evidence` has no `check_id`
    column — an unconsumed hint would silently contaminate the *next* check on that objective;
  * the chat binding must not be detached (`BINDING_NOT_ACTIVE`) — the same precondition
    `attempt.submit` enforces, because the event exists to change the class of the next answer and
    that answer would be refused.
* `idempotency_key` replays the original result; the same key with a different payload is
  `IDEMPOTENCY_CONFLICT`. `revision` in the response equals the envelope revision.
* It never writes an `attempts` row, never sets a verdict and never changes `objectives.state`.

### Storage read and written (all `cb.db` v2)

| Method | Rows |
|---|---|
| `course.outline` | reads `plans`, `objectives`, `checks`, `lesson_runs`, `attempts` |
| `check.get` | reads `checks`, `objectives`, `plans`, `attempts` |
| `lesson.assist` | reads `enrollments`, `plans`, `objectives`, `checks`, `bindings`; writes one `evidence` row (layer 1) and bumps `enrollments.revision` |

### Known divergence: the chat hook's hint path does not bump

`turn.pre_turn` records the same `hint_request` / `answer_shown` event today **without** bumping the
enrollment revision, so the chat path has the narrow race the pane path closes: a hint typed in chat
while a pane submit is grading can be missed by that grading's classification. The wire contract
cannot fix a host hook, and changing `pre_turn` touches Cinder's session-lifecycle code, so it is
recorded here and handed to Cinder on the handler card rather than changed in this amendment. Until
then, both paths write the same evidence event; they differ only in the fence.

### Handlers Cinder must register (after this freeze)

The backing rows all exist; wiring is derivation plus response mapping, no new semantics.

| Method | Register in | Backing code | Handler must do |
|---|---|---|---|
| `course.outline` | `coursebook/domain.py` (`@_handler`) | `_enrollment`, `_approved_plan`/`_current_plan_sql`, `objectives`, `checks`, `lesson_runs`, `attempts` | one `db.read()`; resolve the current plan; select objectives by `ordinal` bound by `limit`; derive `check_state` (highest-version check), `attempt_count` (committed, this enrollment), `independent` (state in independent/delayed), `last_opened_at` (`MAX(lesson_runs.last_opened_at)`); set `total`/`truncated`; return `(0, result)` — never bump a revision |
| `check.get` | same | `checks`, `_objective_in_plan`, `_approved_plan` | one `db.read()`; resolve the check by id, or by objective (open first, else highest version); build the stimulus from the four-key allowlist with `format` defaulting to `text` and `choices` to `[]`; count committed attempts; return `(0, result)` |
| `lesson.assist` | same | `_require_revision`, `_idempotent_lookup`, `_bump_enrollment`, `_remember`, `evidence` | one transaction: replay the key; load enrollment, approved plan, `_objective_in_plan`; require an open check; `_binding_refusal`; `to_revision = _bump_enrollment(...)`; insert the layer-1 `evidence` row (`attempt_id NULL`, mapped `evidence_class`); `_remember(...)`; return `(to_revision, result)` |

One writer: factor the insert currently inlined in `turn._record_assist` into
`evidence.record_assist(connection, ...)` and have **both** `turn.py` and `domain.py` call it, so the
hook and the pane cannot drift in `kind`/`evidence_class` mapping.

Until registration lands, `api.dispatch` answers `NOT_IMPLEMENTED` for all three (the payload is
still validated first), and the Desktop gates its controls on `/runtime.implemented_methods` — which
is why the pane's Hint/Show answer and the Textbook index stay in the honest "not in this build"
state rather than becoming dead buttons.

Run `python3 -m unittest scripts.proof_contract_v5 -v` in a worktree that contains the CB-008/CB-022
kernel: it drives real commands against a real SQLite database built by the real migrations, composes
all three responses from the resulting rows under the rules above, and validates each against
`rpc.v5.json` — including the smuggle case (a check row whose `stimulus_json` carries
`reference_answer` must not put it on the wire) and the assist case (the event is written, the
revision moves, and the next committed attempt is classified `hinted`). On a branch without that
kernel the module skips with a stated reason rather than passing.

## UX screen → method mapping

Every screen in §6, §7, §8, §10 and §11 is implementable against a method or a documented payload.

| UX spec | Screen | Method(s) / documented payload |
|---|---|---|
| §6 | Courses home: rows, search, filter, empty & filtered-empty, overflow | `library.list` (rows, `next_step`, `evidence_summary`, `warning`, `empty_reason`, `provenance`); `enrollment.update` (archive/unarchive); `enrollment.delete` (delete, previewed scope); `pack.delete` (delete imported pack); `artifact.get` (exported learning backup after `pack.export`); `binding.get` + `lesson.begin` (open bound chat) |
| §6 / §7 | Review-due row and review queue | `library.list` `filter=review_due`; `review.queue` (due/overdue/cap/`upcoming_hidden`); `review.action` (`snooze`/`stretch`/`drop`/`resume`); `course.get` payload: plan objectives + evidence (below); `quiz.history` |
| §7 | Overview: current objective, next action, resume/start, recent event, status banners | `library.list` row; `course.get` `course` payload (below); `lesson.begin`; `binding.get` |
| §7 | Textbook: section list and durable lesson page, continue/fresh run, history | `course.outline` (the section list: plan + every objective with state, check state, attempts, independence, last opened); `lesson.page` (segments, sources, artifacts, checks, notebook saves, related attempts, state); `lesson.begin` (`resume`/`fresh`); `lesson.page.runtime` for bound-run status |
| §7 | Notebook: search, tag/course filter, edit note/tags, remove, open in textbook | `notebook.list`; `notebook.update`; `notebook.delete`; `lesson.page` (jump back to section) |
| §7 | Quizzes: attempts, original feedback, dispute, new version | `quiz.history`; `attempt.dispute`; `check.open` (new version); `lesson.page.attempts` |
| §7 | Plan: objective states, criteria, challenge-out, dials | `course.outline` (plan version/state/hash + the flat objective list); `course.get` `course` payload (below); `progression.challenge_out`; `plan.replan`; `plan.approve` |
| §7 | Evidence: L1 attempts, L2 objective evidence, L3 recommendation | `evidence.inspect` (L1/L2/L3 + disputes in one read); `evidence.disputes` (filtered dispute view); `course.get` `course` payload (below); `quiz.history`; `attempt.override`; `attempt.dispute` |
| §7 | Sources: provenance, support, staleness, claim count | `course.get` `course` payload (below); `lesson.page.sources` |
| §8 | Lesson workspace: objective/check pane, attempt states, feedback, continue, detached banner | `course.outline` (which section is current); `lesson.page`; `check.get` (structured prompt, format, choices); `check.open`; `attempt.submit`; `lesson.assist` (Hint / Show answer as layer-1 events); `attempt.override` (Skip); `binding.get`; `lesson.begin`; `binding.abandon` |
| §9 | Library and pack trust: preview, import, keep/review/refuse update | `pack.list` (installed packs, enrolled or not, with state and revision); `pack.inspect` (manifest, integrity, trust of an installed pack without a new upload); `pack.preview`; `pack.import`; `pack.export`; `artifact.get`; `library.list` `provenance.source` |
| §10 | Parent Studio: brief, research/review, approval, pack preview/export | `course.create` (`recipe: parent`); `jobs.create` (`kind: research` / `plan`) with the brief; `jobs.get`; `plan.approve`; `pack.preview` (manifest, integrity, trust); `pack.inspect` (re-open a pack generated in an earlier session); `pack.export`; `artifact.get` (tabs: parent guide, learner pages, answers, audio/visuals, sources are manifest file roles) |
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
2. Add a new file (`rpc.v5.json`, `projection.v1.json`) and bump
   `$id`/`x-contract-version`/`x-supersedes`. Never edit a
   shipped version in a way that changes meaning; clients cache by version.
3. Update `CONTRACT_FILES` in `coursebook/contracts.py` and run
   `python3 -m unittest discover -s tests -t .`. `audit_contracts()` fails on a stale `$ref`
   version, a method-enum/payload mismatch, or a wire-constant/version disagreement.
4. Record the decision, the reason and the migration path below.

| Version | Date | Decision |
|---|---|---|
| v1 | 2026-11-06 | Initial freeze. 24 RPC methods, 17 tables, 16 error codes, 9 job states, 1 pack manifest. |
| v2 | 2026-11-06 | CB-018 additive amendment. 34 RPC methods (+library.list, lesson.page, lesson.begin, enrollment.update, enrollment.delete, pack.delete, artifact.get, jobs.list, notebook.update, binding.abandon), +DELETE_SCOPE_STALE, +lesson_runs/lesson_segments and revision fencing in cb.db v2, +$defs.job_state in cb.jobs v2. |
| v3 | 2026-11-06 | CB-022 additive amendment. 38 RPC methods (+review.queue, review.action, evidence.inspect, evidence.disputes) with `review.action` fenced in the envelope; no new table, column, migration or error code — the queue stays derived and disputes stay in `attempts.grading_provenance_json`. `pack.list` deferred to a future v4. |
| v4 | 2026-11-06 | CB-024 additive amendment. 40 RPC methods (+pack.list, pack.inspect) reading the existing library index and `packs` row; no new table, column, migration or error code. New contract `cb.projection` v1 freezes the pack-check → check-spec mapping (six audit rules, deterministic projection, conformance vectors) with two importer divergences recorded for Lattice. |
| v4 (projection closure) | 2026-11-06 | CB-025 (importer commits `577d268`, `725ffbf`) closed both `cb.projection` v1 divergences: R5 gained the non-empty guard and R6 withholds a check its manifest declares failed, so the bundled Japanese pack's `obj-register-transfer` opens through the dispatcher. `x-known-divergences` now records both as `resolved` with the implementing commit, the `declared_failed_withholds` vector reports the ordinary `import_audit_failed` problem, and `$defs.check_spec.declared_audit_state` is narrowed to `passed`/`unreviewed`. No RPC method, table, migration, wire constant or handler changed; `cb.projection` stays v1. |
| v5 | 2026-11-06 | CB-026 additive amendment. 43 RPC methods (+course.outline, check.get, lesson.assist) so CB-009 can render the Textbook section list, the Plan tab, the structured check prompt and the pane's Hint/Show answer; `lesson.assist` is fenced in the envelope. No new table, column, migration or error code — every field is derived from `plans`/`objectives`/`checks`/`lesson_runs`/`attempts`, and the assist event is the layer-1 `evidence` row the chat hook already writes. `section_titles` deliberately omitted (no heading storage). Superseded files pinned by sha256. |
| v5 (binding scope) | 2026-11-06 | CB-009 finding: `binding.get` now answers `objective_id` and `lesson_run_id` from the `bindings` row so the pane scopes to the bound section instead of the enrollment's current one. Additive inside v5 because `binding` is an open object in `rpc.v5.json` and `cb.db` v2 already stores both columns: **no v6, no schema edit, no version bump, no status-semantics change**. `null` = legacy/course-level binding; the platform seam answers `null` on a v1 binding table rather than omitting the fields. |

## Deliberate omissions (do not "helpfully" add these)

* No `mastered` boolean and no global progress percentage. Evidence states are distinct on purpose.
* No free-form `instructions` field in a pack or a check. Untrusted prose is content, never policy.
* No `provider`, `model` or credential field in a pack, and no `settings` passthrough.
* No `safe`/`verified` badge enum. Trust dimensions stay separate (`pack_trust_label`).
* No numeric attainment estimate field. Schedule arithmetic and attainment uncertainty are separate
  (R9); an estimate, if ever shown, is a `model_estimate` with limits, not a contract field.
* No transcript or notebook text in the pack schema, and none is obtainable by export options.
* No reference answer, rubric internals or raw grader output in any evidence view
  (`evidence.inspect`, `evidence.disputes`, `lesson.page`, `course.get`).
* No `review_schedule` table and no stored "what is due" copy: the queue is derived from committed
  evidence plus learner action events, and `cap` bounds rows, never the counts.
* No completeness/retention percentage and no persona field: L3 recommendations carry a `basis`,
  and `is_persona` is `false` by contract.
* No filesystem path in `artifact.get`, `pack.list` or `pack.inspect` (or any RPC response). The
  pack library's absolute `directory` is storage; artifacts are fetched through an authenticated,
  expiring handle.
* No enrollment state, course id or course count in a `pack.list` row. Whether a pack has a course
  is `library.list`'s answer; a pack row that also claimed it would be a second authority.
* No manifest inside `pack.list`. The list is a bounded index read; `pack.inspect` is the read that
  returns the manifest, and it re-hashes the bytes on disk before doing so.
* No `safe`/`verified` verdict on an installed pack: `pack.inspect` returns the same four
  independent trust labels as `pack.preview`.
* No `check_spec` (or reference answer, or rubric internals) in any RPC response. The frozen
  projection is storage, not a wire payload.
* No `reference_answer`, `accepted_answers`/`accepted_alternatives`, `rubric` or `rubric_json` in
  `check.get`: the pane renders a question. A stimulus that smuggles an answer is dropped by the
  allowlist and refused by the response schema, not rendered.
* No `section_titles` (or any other derived "heading") in `course.outline`. Storage has no heading
  field — `lesson_segments.text` is verbatim teaching prose — so the section index is the objective
  list itself. A fabricated label list would be worse than an absent one; authored headings would be
  a `cb.db` migration and a v6 field.
* No mastery, retention or "score" field in `course.outline` or `check.get`: `attempt_count` and
  `independent` are facts about committed evidence, not an attainment estimate.
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
