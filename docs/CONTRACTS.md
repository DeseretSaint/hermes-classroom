# Coursebook contracts — authoritative files and owners

Status: **frozen at v23** (GM-005: `cb.rpc` v23 appends the six take-home pack methods — `takehome.sources`, `takehome.preview`, `takehome.create`, `takehome.approve`, `takehome.export`, `takehome.read` — a rendered print artifact bound to the source course/objective/lesson version and content hash, with the learner page and the parent-only answer guide as separate artifacts; `cb.db` v14 scopes a pack's revision to the pack instead of its source slot. GM-011: `cb.rpc` v22 appends the two lesson-bound tutor commands — `tutor.ask`, a bounded, cited, tool-free answer scoped to one lesson run whose context excludes answer keys, checks, rubric and attempts and which never writes an attempt, transition or evidence row, and `tutor.history`, the persisted thread read. A turn is not a grade; while a check is open the final answer is withheld (`answer_withheld`) and a hint rides the existing `lesson.assist` policy; a provider failure is the named `provider_failure` state, never an empty or fabricated answer. GM-009: `cb.rpc` v21 appends the two game-only engagement methods `engagement.read` and `engagement.award`; XP is a play layer derived from real recorded actions, idempotent per `(enrollment_id, action_kind, action_id)`, refused outside a `game` course and never joined by evidence, parent, pack or export reads. H-182/D3: `cb.rpc` v20 carries a second additive amendment — `course.outline`'s `outline_plan` and `parent.blueprint.read`'s `plan` gain one optional `validation` object (`approvable`, `source`, `verdict`, `outcome`, `independence`, `facts_unverified`, `reasons`, `reason`, `detail`, `manual_authoring`), the durable approval provenance computed by the same gate `plan.approve` fences on, so a review surface cannot render an approval control for a rejected or unvalidated version. No method, request shape, error code, job kind or vocabulary value moves. H-194b: `cb.rpc` v20 is one additive amendment over v19 — `parent.blueprint.read` gains one required response array, `sections[]`, one entry per composed section carrying `section_id`, `objective_id`, `ordinal`, `title`, `lesson_state`, `lesson_version` and `page_hash`, the exact digest `lesson.revise` fences on, so the desktop can fine-tune a section that has never been revised.
v19 = H-194 fine-tuning a generated course: `cb.rpc` v19 appends five
commands — `plan.edit`, `plan.undo`, `lesson.revise`, `lesson.regenerate`, `parent.review.read` —
and `cb.db` v12 adds the two durable fine-tune ledgers `plan_revisions` and `lesson_revisions`;
v18 = H-185 model-assessed lesson provenance; v17 = H-106 source provenance: `cb.rpc` v17 additively gives the source item of
`lesson.page` and `parent.blueprint.read` six optional fields — `excerpt`, `excerpt_state`,
`content_hash`, `modality`, `licence`, `support_assessment` — and moves no method, required key or
other payload; v16 = H-120 bounded conversation practice, which appends the four
`practice.*` commands and one optional `check_stimulus.practice` declaration, and `cb.db` v11 adds
the two practice tables; v15 = H-139 job `activity` read model, a reference refresh over
v14 and `cb.jobs` v5 additively adds `job.activity`; v14 = H-53 `observation.record`, additive over H-08 authored-course export at v13,
the H-18 `lesson_document` `lang`/`direction`
addition, and the H-26b syllabus read projection inside v13; v12 = H-26 student syllabus intake,
v11 = H-21 slice A, v10 = H-01, v9 = M3-B1,
v8 = M1-P4, v7 = CB-015 residual, v6 = CB-011, v5 = CB-026, v4 = CB-024, v3 = CB-022, v2 = CB-018).
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
| `cb.errors` | `contracts/errors.v4.json` | 4 | Atlas | RPC envelope, job errors, HTTP mapping |
| `cb.rpc` | `contracts/rpc.v23.json` | 23 | Cinder (kernel + learning-loop + `parent.*` + `source.revalidate` + `pronunciation.*` + `syllabus.*` + `course.export*` + `observation.record` + `practice.*` + source provenance + fine-tune + engagement + tutor), Sable (transport), Lattice (`pack.*` + `lesson_document` + `takehome.*`) | Desktop half, Coursebook tools, `pre_llm_call` |
| `cb.db` | `contracts/db.v14.json` | 14 | Cinder (GM-001 storage), Lattice (GM-005 migration 0014) | migrations, every command, evidence views |
| `cb.jobs` | `contracts/jobs.v5.json` | 5 | Cinder | job service, Activity view |
| `cb.pack` | `contracts/pack-manifest.v1.json` (v2 also accepted: `pack-manifest.v2.json`) | 1 (v2 accepted) | Cinder (v2 media link, H-137) | import/export, bundled demo packs |
| `cb.projection` | `contracts/projection.v1.json` | 1 | Atlas (contract), Lattice (importer) | pack import, Parent Studio generation, community upload review |
| `cb.frequency_inventory` | `contracts/frequency-inventory.v1.json` | 1 | Atlas | plan author + validator, imported/pack-supplied frequency inventories (H-89; no third-party list is bundled — see `docs/FREQUENCY-INVENTORY.md`) |

The v1 **to v21** files for `cb.rpc` (including `rpc.v6.json`, `rpc.v9.json`, `rpc.v10.json`,
`rpc.v12.json`, `rpc.v13.json`, `rpc.v14.json`, `rpc.v15.json`, `rpc.v16.json`, `rpc.v17.json`,
`rpc.v18.json`, `rpc.v19.json`, `rpc.v20.json` and `rpc.v21.json`), the
v1 **to v22** files for `cb.rpc` (including `rpc.v6.json`, `rpc.v9.json`, `rpc.v10.json`,
`rpc.v12.json`, `rpc.v13.json`, `rpc.v14.json`, `rpc.v15.json`, `rpc.v16.json`, `rpc.v17.json`,
`rpc.v18.json`, `rpc.v19.json`, `rpc.v20.json`, `rpc.v21.json` and `rpc.v22.json`), the
v1 **to v13** files for `cb.db` (including `db.v3.json`, `db.v5.json`, `db.v7.json`,
`db.v8.json`, `db.v9.json`, `db.v10.json`, `db.v11.json`, `db.v12.json` and `db.v13.json`), and the v1
**to v3** files for `cb.errors` and the v1 to v4 files for `cb.jobs` remain on disk, unmodified,
as immutable history: the superseded current files are `rpc.v22.json`, `db.v13.json`,
`errors.v3.json` and `jobs.v4.json`.

`cb.pack` is the one contract with a version map: v1 (`pack-manifest.v1.json`) and v2
(`pack-manifest.v2.json`) both live on disk, and a pack is validated, exported and allowlisted
against the `contract_version` it declares. v2 adds one optional root `media[]` array that links a
declared `narration`/`visual` file to the section that may play it, with a short caption; a file
not named there stays stored evidence only, exactly as every v1 pack behaves. No `cb.rpc` method,
`cb.db` column or migration changes (H-137 implements `docs/PACK-MEDIA-PLAYBACK.md` §4, §8).

The inventory current stays **v1** because every frozen `cb.rpc` file (v4…v19) and
`cb.projection` v1 resolve `$ref` targets to `pack-manifest/v1`; naming v2 current would either
break those references or require editing a frozen wire contract. v2 is therefore an accepted
*document* version, selected per pack by `contract_version`, not a change to the cross-document
inventory. Only v2 documents may carry `media[]` (v1's `additionalProperties: false` refuses it).
A pack author who wants playback writes `contract_version: 2`; `packs.build_manifest` accepts that
explicitly, while its default stays v1 so the bundled demo packs keep shipping v1
(`docs/PACK-MEDIA-PLAYBACK.md` §13 ordering).
`CONTRACT_FILES` in `coursebook/contracts.py` points each id at its current
version only. `audit_contracts()` rejects any `$ref` that still targets a superseded version.
`tests/test_contracts.py` pins the sha256 of every superseded `rpc.v*.json` **and** `db.v*.json`, so
"additive" is a fact about the bytes rather than a claim about a diff.

Each document carries `$id` (versioned URI), `x-contract-id`, `x-contract-version`, `x-owner`
and, where superseded, `x-supersedes`. `tests/test_contracts.py` asserts that the id, the
version in the URI and the declared version agree for every file.

## Wire rule

`cb.rpc` is transport-neutral. The root schema validates a **request envelope**:

```json
{ "contract": "cb.rpc", "contract_version": 10,
  "method": "attempt.submit", "operation_id": "op-...", "idempotency_key": "...",
  "expected_revision": 12, "payload": { } }
```

Success and failure are separate envelopes (`$defs/envelope_response_ok`,
`$defs/envelope_response_error`). Every method has `request` and `response` payload schemas in
`$defs.methods`; `coursebook.api.dispatch` validates the envelope, then the payload, then runs the
handler, then validates the handler's result against the response schema. A handler that returns
something outside the contract becomes `INTERNAL_ERROR` — it is never rendered.

Envelope-level requirements added by v2, v3, v5 and v7 (enforced by the schema before any handler runs).
v4 adds none: both of its methods are reads, so they carry neither `idempotency_key` nor
`expected_revision`. `course.outline` and `check.get` (v5) are reads for the same reason; only
`lesson.assist` is a command. v6 adds the Parent Studio family; its three reads stay unfenced and
its five commands are fenced as the table below says. v7 adds one command, fenced by
`idempotency_key` only:

| Method(s) | Required envelope fields |
|---|---|
| `attempt.submit` | `idempotency_key`, `expected_revision` |
| `lesson.begin` | `idempotency_key` (a double click must not mint two chats) |
| `enrollment.delete`, `pack.delete` | `idempotency_key`, `expected_revision` |
| `enrollment.update`, `notebook.update`, `binding.abandon` | `expected_revision` |
| `review.action` | `idempotency_key`, `expected_revision` |
| `lesson.assist` | `idempotency_key`, `expected_revision` |
| `parent.brief.create`, `parent.export`, `parent.reflection.record` | `idempotency_key` (a double click must not mint two courses, two exports or two reflections) |
| `parent.plan.edit`, `parent.final.approve` | `idempotency_key`, `expected_revision` |
| `parent.brief.get`, `parent.blueprint.read`, `parent.reflection.list` | none — reads |
| `source.revalidate` | `idempotency_key` (a double-submitted re-fetch must not record twice; the content-hash comparison is the fence, not a revision) |
| `observation.record` (v14) | `idempotency_key` (a double click must not mint two evidence rows; the write cannot move the aggregate, so there is no `expected_revision`) |

Two v6 commands deliberately carry **no** `expected_revision`: `parent.export` is fenced by the
approved content hash instead (bumping the enrollment revision would refuse an answer that is being
graded), and `parent.reflection.record` appends a parent-reported note that no evidence
classification depends on.

`POST /api/plugins/coursebook/rpc` always answers **HTTP 200** with a contract envelope. A refused
command is `ok:false` with an error code; a transport failure is the only reason a client sees an
HTTP error. That keeps the Desktop half to one branch (`response.ok`) instead of two.

### State and identity rules baked into the contract

* Every learner-facing mutation is fenced by `expected_revision` and refused with `STALE_REVISION` +
  `current_revision` rather than silently winning. `source.revalidate` is the one documented
  exception: a source row is course-scoped with no aggregate revision, so its content-hash
  comparison is the fence (see the v7 delta).
* `attempt.submit` **requires** `idempotency_key` and `expected_revision`. Repeating a key with the
  same payload hash returns the persisted original result; the same key with a different payload is
  `IDEMPOTENCY_CONFLICT`.
* Evidence classes are fixed: `cold`, `hinted`, `answer_shown`, `self_reported`, `parent_reported`,
  `override`. Only `cold` can count as independent evidence; `override` grants access, never mastery.
* `bindings.status` of anything other than `active` refuses a submit with `BINDING_NOT_ACTIVE`.
* Ids are minted by Coursebook (`identifier` pattern). Titles, paths and chat session ids are never
  primary keys — that is the R1 finding in `AUDIT.md`.

### Verification checklist confirmation rides `selection` (no version change)

A `verification`-format check with declared `items[{id, label}]` is confirmed by an ordinary
`attempt.submit` answer:

```json
{ "kind": "selection", "selection": ["item_1", "item_2"] }
```

The entries are the check's **declared item ids** (`check.get` serves them; localized labels are not
identity). Ticking every declared item is `pass` with `evidence_class: self_reported`; a subset is
`partial`; an empty selection (`checklist_no_items_confirmed`) or an id the check did not declare
(`unknown_check_item`) is `VALIDATION_FAILED` before any attempt row is written. The `answer` object
stays closed — no confirmation field is added — and `checks.reference_json` stays `rubric_only`.
This is the kernel reading an existing field, not a v11 amendment: `cb.rpc` remains at 10 and
`cb.db` does not move. A parent-recipe course is excluded; its recording path is
`observation.record` (`docs/CHECKLIST-CONFIRMATION.md` §6).

## v2 delta (CB-018)

v1 froze 24 methods. Operator review found screens the UX contract requires but the wire could not
serve: the library could not be listed after restart, a textbook section had no durable page or
resumable run, activity jobs could not be listed, an exported pack artifact could not be fetched,
and a notebook entry could not be edited. v2 adds ten methods and nothing else; every v1 method and
payload is byte-identical (asserted in `tests/test_contracts.py`).

| New method | Purpose | Request (required fields) | Response (required fields) |
|---|---|---|---|
| `library.list` | Courses home after restart: search/filter/sort, next step, provenance, empty states | `query?`, `filter`, `recipe?`, `sort`, `limit`, `cursor?` | `items`, `next_cursor`, `total`, `empty_reason`, `applied_filter` |
| `lesson.page` | Durable Textbook section page; read-only navigation, never changes evidence | `enrollment_id`, `objective_id`, `section_id?` | `course`, `section`, `runtime`, `segments`, `document`, `sources`, `artifacts`, `checks`, `notebook_entries`, `attempts`, `state`, `revision` |
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

v8 adds `document` to the same response: the validated block document of
`docs/VISUAL_MEDIA_PLAN.md` §5, projected at read time from the rows this response already
returned. It is not a second authority and adds no storage or write. `blocks[]` carry a structural
`role` (`orient`/`explain`/`example`/`practice`/`recap`), a `headline`, `short` and `deep`
renderings of the same authored text, at most one `check_id`, `media[]` children and
`source_ids[]`. One check attaches to exactly one block; media is never free-floating.

`state` says how much of the document exists. `complete` means every block has authored short and
deep text, so Guided, Field Quest and Field Notes are available. `textbook_only` means the page was
authored before v8 (or carries a linear chat transcript), so every `short` is `null`, those views
are `false`, and `view_note` says why in human words: a client disables the toggle and shows the
note instead of rendering an empty Guided view. `empty` means the section has no teaching content
yet. The projection is deterministic: the same rows and check id produce the same `document_id`
and `content_hash`, so a client can cache it and a review can name it. Source ids recorded on a
segment travel with that block; a v7 page recorded provenance only at document level, so its
`source_ids` survive at document level and no block-level citation is invented. The document
contains no reference answer, accepted answer or rubric text, and `generation.assert_no_answer_leak`
reads the document as well as the page.

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

### `cb.projection` v1 carries no checklist, and this card did not change that

A `cb.pack` manifest check's `stimulus` is a prose string; there is no `items` key in the manifest.
The frozen projection emits `stimulus: {prompt: trim(stimulus)}` and states that every listed field
is always present, with no optional field. So an imported pack check reaches the kernel as a
prompt-only stimulus and `pack_flow.check_spec_from_pack_check` keeps writing `{"prompt": ...}`.
Carrying a checklist through import would need two coordinated changes that are deliberately **not**
made here: a `cb.pack` v2 that can declare `items[]` in a manifest check, and a `cb.projection` v2
whose `stimulus` field is no longer a single key. A structured checklist therefore arrives only
through authored generation (`generation.LESSON_SCHEMA` → `checks.stimulus_json`), which is the path
`check.get` already projects. Nothing in `cb.projection` v1 changed and no imported check's stored
spec changed.

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
`learner_instructions`, `items`). `checks.stimulus_json` is importer- and generator-written, so it
can hold keys nobody planned for; `check.get` drops what it does not recognise instead of echoing
it, and `additionalProperties: false` in the response schema means a handler that passes the JSON
through fails response validation and becomes `INTERNAL_ERROR` rather than a rendered answer key.
The contract tests exercise exactly that: a stimulus carrying `reference_answer` is refused.
`items` is structured check data, not prose: an array of `{id, label}` rendered once on the check
surface. `check.get` validates it on the way out (bounds, id shape, duplicate or near-duplicate
labels after case/spacing/punctuation are ignored, and `learner_instructions` that only repeat the
prompt) with `VALIDATION_FAILED` rather than serving a checklist the learner would read twice.

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
  for a text item; `learner_instructions` is passed through when the generator stored it; `items`
  is `[]` when the check carries no checklist, and otherwise the stored `{id, label}` list bounded
  at 24 items and 200 characters per label, with duplicate or near-duplicate labels refused.
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

**Registration status: landed in CB-014.** All three methods are mounted in `coursebook/domain.py`
and appear in `/runtime.implemented_methods`; the CB-014 candidate implements 51 of 51 contract
methods. The paragraph recording the pre-registration behaviour is kept below as history — it is
not a statement about this build.

The backing rows all exist; wiring is derivation plus response mapping, no new semantics.

| Method | Register in | Backing code | Handler must do |
|---|---|---|---|
| `course.outline` | `coursebook/domain.py` (`@_handler`) | `_enrollment`, `_approved_plan`/`_current_plan_sql`, `objectives`, `checks`, `lesson_runs`, `attempts` | one `db.read()`; resolve the current plan; select objectives by `ordinal` bound by `limit`; derive `check_state` (highest-version check), `attempt_count` (committed, this enrollment), `independent` (state in independent/delayed), `last_opened_at` (`MAX(lesson_runs.last_opened_at)`); set `total`/`truncated`; return `(0, result)` — never bump a revision |
| `check.get` | same | `checks`, `_objective_in_plan`, `_approved_plan` | one `db.read()`; resolve the check by id, or by objective (open first, else highest version); build the stimulus from the four-key allowlist with `format` defaulting to `text` and `choices` to `[]`; count committed attempts; return `(0, result)` |
| `lesson.assist` | same | `_require_revision`, `_idempotent_lookup`, `_bump_enrollment`, `_remember`, `evidence` | one transaction: replay the key; load enrollment, approved plan, `_objective_in_plan`; require an open check; `_binding_refusal`; `to_revision = _bump_enrollment(...)`; insert the layer-1 `evidence` row (`attempt_id NULL`, mapped `evidence_class`); `_remember(...)`; return `(to_revision, result)` |

One writer: factor the insert currently inlined in `turn._record_assist` into
`evidence.record_assist(connection, ...)` and have **both** `turn.py` and `domain.py` call it, so the
hook and the pane cannot drift in `kind`/`evidence_class` mapping.

Before CB-014 registered them, `api.dispatch` answered `NOT_IMPLEMENTED` for all three (the payload
was still validated first); that remains the seam's behaviour for any method with no handler. The
Desktop gates its controls on `/runtime.implemented_methods`, so a control whose method is not
mounted renders in the honest "not in this build" state rather than becoming a dead button — and
since CB-014 the three methods behind the pane's Hint/Show answer and the Textbook index are
mounted.

Run `python3 -m unittest scripts.proof_contract_v5 -v` in a worktree that contains the CB-008/CB-022
kernel: it drives real commands against a real SQLite database built by the real migrations, composes
all three responses from the resulting rows under the rules above, and validates each against
`rpc.v5.json` — including the smuggle case (a check row whose `stimulus_json` carries
`reference_answer` must not put it on the wire) and the assist case (the event is written, the
revision moves, and the next committed attempt is classified `hinted`). On a branch without that
kernel the module skips with a stated reason rather than passing.

## v6 delta (CB-011) — Parent Studio authoring surface

`UX_SPEC.md` §10 describes a parent authoring workflow: brief → research/review → plan approval →
generation → **final approval** of the generated learner pages, answer guide, narration transcript
and activity instructions → pack/PDF export → reflection. The v5 wire could not serve it, and
`docs/REVIEW_CB011-GAP.md` (Vellum, `wt/cb-011-vellum` @ `cbed40b`) recorded why with commands and
line numbers: a queued `plan`/`lesson` job had **no typed brief** reachable from the wire, a draft
plan had **no edit command**, a lesson-set approval had **no state**, an authored course could not
be **exported** (`pack.export` refuses `course_not_pack_backed`, `make_pdf` had no caller) and the
five blueprint tabs had **no read**.

v6 adds eight methods, two additive `cb.db` v3 tables, and no error code; every v1–v5 method and
payload is preserved byte-identically (asserted in `tests/test_contracts.py`, which also pins the
sha256 of every superseded `rpc.v*.json` and `db.v*.json`).

| New method | Purpose | Request (required fields) | Response (required fields) |
|---|---|---|---|
| `parent.brief.create` | Create the course (`recipe: parent`), its enrollment and the queued `plan` job in one fenced call, carrying the full §10 brief | `brief` (`parent_brief`), envelope `idempotency_key` | `course_id`, `enrollment_id`, `job_id`, `state`, `revision` |
| `parent.brief.get` | Read the brief back so **Duplicate brief** copies real values, plus the plan job's state | `course_id` | `course_id`, `enrollment_id`, `brief`, `plan_job`, `created_at` |
| `parent.plan.edit` | Draft-only plan field edits (title/target/criteria per objective, add, remove, reorder, course title/goal) fenced on the plan hash the parent saw | `enrollment_id`, `plan_id`, `expected_plan_hash`, optional `course_title`/`goal`/`objective_edits`/`add_objectives`/`remove_objective_ids`/`order` | `plan_id`, `plan_version`, `plan_hash`, `objective_ids`, `changes_need_review` (const `true`), `revision` |
| `parent.final.approve` | Approve the exact generated content set by hash — **distinct from `plan.approve`** | `enrollment_id`, `plan_id`, `plan_hash`, `content_hash`, optional `note` | `approval_id`, `state` (const `active`), `plan_hash`, `content_hash`, `approved_at`, `revision` |
| `parent.blueprint.read` | The five tabs as declared file **text**, plus the approval/export state the studio banners render | `course_id`, optional `limit` | `course_id`, `recipe`, `plan`, `approval`, `content_hash`, `export`, `tabs`, `sources` |
| `parent.export` | Authored parent pack + selectable-text PDF from the export allowlist, with the exact file list | `enrollment_id`, optional `formats` | `export_id`, `pack`, `files`, `artifacts`, `content_hash`, `exported_at` |
| `parent.reflection.record` | Parent-reported easy/about-right/too-hard + revisit note, outside every exported pack | `course_id`, `difficulty`, optional `enrollment_id`/`plan_id`/`revisit_note`/`apply_to_next_draft` | `reflection_id`, `difficulty`, `plan_hash`, `content_hash`, `created_at` |
| `parent.reflection.list` | Bounded read of the reflections that seed the next brief | `course_id`, optional `limit` | `reflections`, `total` |

### The one answer-text exception, stated exactly

Previous amendments say "no reference answer in any RPC response". That rule protects the **learner**
surfaces, and it still does: `lesson.page`, `check.get`, `course.outline`, `evidence.inspect` and
`course.get` are unchanged and still carry no answer text. UX §10 requires an **Answers** tab and an
approval that covers the answer guide, so v6 carves one narrow exception:

* `parent.blueprint.read` serves `answer_guide` content, and it is addressed by `course_id` only —
  there is no `enrollment_id`, no binding and no session in the request, so it cannot be reached
  from a learner's lesson surface.
* The answer text rides in the declared `text` field of a `blueprint_file`, never as a typed
  `reference_answer` field. `additionalProperties: false` means a handler that passes stored JSON
  through fails response validation instead of rendering an answer key.
* `parent.export` writes the answer guide into a file with role `answer_guide`, which is **not** one
  of `packs.LEARNER_FACING_ROLES` (`section`, `learner_page`, `visual`, `narration`), so an exported
  pack keeps the answer key out of the learner page by construction.

### `parent.brief.create` / `parent.brief.get`

* The brief is stored as `jobs.brief_json` — the same row the plan executor reads. There is no
  `parent_briefs` table: a second copy of the brief would be a second authority.
* `egress_acknowledged` is `const: true` in the contract. A parent who has not seen the
  provider/egress disclosure cannot produce a valid request, so no course is created under a paste
  nobody disclosed. `redaction_requested` records the optional redaction answer.
* The call creates `courses` (recipe `parent`, status `draft`), `enrollments` (active, revision 0)
  and a `jobs` row of kind **`plan`** in state `queued`, then returns all three ids. It is fenced by
  `idempotency_key` because a double click must not mint two courses; `expected_revision` is
  meaningless for a course that does not exist yet.
* `parent.brief.get` returns the brief, the enrollment it was created with (stored in the brief) and
  the plan job's `{job_id, kind, state, submitted_at}`. The typed brief is what makes "duplicate
  brief" a copy rather than a re-render of a form.
* `jobs.get` already returns the raw `brief` object (`_job_view`), but its v1 response schema is an
  open object; v6 does **not** tighten that preserved payload. `parent.brief.get` is the typed read.

### Validation provenance at approval (H-15, no wire change)

`plan.approve` still fences on the plan hash and the enrollment revision. What changed is what a
caller is obliged to disclose before it sends that command, and the fact that a pass is no longer
sufficient to call a plan validated:

* The generation job records, per artifact, the `independence` state of the validation pass
  (`independent`, `same_model`, `unidentified`) and an `outcome`
  (`independently_validated`, `model_assessed`, `rejected`). Only `independently_validated` sets
  `gen_plan_documents.generation_state = 'draft'`; the other outcomes record `needs_review`.
* `plan_document()` returns `validation` (both model identities, prompt hashes, waived unknown
  criteria, `facts_unverified`, cost) and `approval` (`needs_review`, `warning`). The job result
  carries the same as `validation` / `approval_provenance`, and `warnings` includes the sentence
  `facts unverified, no sources: ...` whenever research was not `ok`.
* A `model_assessed` plan may still be approved by a human: that is the review the word
  `needs_review` names. Approval is not factual verification, and the warning says so. The kernel
  gate in `domain._plan_validation_source` therefore refuses only an unvalidated or `rejected`
  artifact; a durable passing record whose validator was not independent approves as a
  `model_assessed_pass`, never as `generated_validated`. A `rejected` outcome is a different case.
* `plans.state` keeps its frozen enum (`draft`/`approved`/`superseded`). The distinction lives in
  the authored document and the validation record, not in a new kernel state.

This is documented rather than schemaed: no `cb.rpc` request/response field was added. The line is
`cb.rpc` v11 (`cb.db` v7) and every H-15 addition lives in the plugin's own generation result and
`plan_document()` projection, which the open job result already returns. A Desktop build that wants
to render the provenance from a typed RPC field needs the next contract card: the exact additions
would be `plan_read.plan.validation {outcome, independence, independent, generator, validator,
facts_unverified, warning}` and `plan_read.plan.approval {needs_review, warning}`, both inside the
strict `additionalProperties: false` plan object of `course.outline`/`parent.blueprint.read`. The
plugin does not invent a surfaced field ahead of that contract.

### `parent.plan.edit`

* **Draft only.** An edit against an `approved` plan is refused with `POLICY_VIOLATION` /
  `reason: plan_not_draft`; editing an approved plan is `plan.replan`'s job (which creates a new
  draft version and supersedes the old approval). Editing a `superseded` plan is refused the same
  way. This keeps "approval binds exact bytes" true for plans as well as content.
* **Fenced on the hash, then on the revision.** `expected_plan_hash` is compared with
  `_plan_hash(plan)` and a mismatch is `VALIDATION_FAILED` with `current_plan_hash`; the enrollment
  revision fence follows. Two fences because there are two ways to be stale: the parent saw a
  different plan, or another command moved the aggregate.
* Edits are applied to the draft row: objective `title` / `evidence_target` / `criteria`, additions,
  removals, and a full `order` permutation of the surviving objective ids. `plans.version` and
  `objectives.version` bump, `plans.plan_hash` is recomputed inside the same transaction, the
  enrollment revision bumps, and the response carries the new hash plus
  `objective_ids` in ordinal order so the studio can address what it just created.
* `changes_need_review` is `const: true` in the response: an edited draft is by definition not
  approved. It is not a hint — a handler that returns `false` fails response validation.
* The write reuses `domain.record_objective` for additions so ordinals and hashes stay consistent;
  it must not insert objective rows itself.
* **Not in v6:** editing generated page prose or activity instructions per lesson. Those live in the
  generation staging rows (`gen_lessons.page_json`) and change by regenerating after a plan change.
  Freezing a per-page edit command without a storage decision for it would be a promise the kernel
  cannot keep; it is listed under deliberate omissions.

### `parent.final.approve` and the invalidation rule

Approving a plan is not approving a course. `plans.state` stays exactly `draft | approved |
superseded` (`plan.approve` is unchanged), and the lesson-set approval is a separate row in
`final_approvals` (`cb.db` v3):

| Column | Meaning |
|---|---|
| `plan_id`, `plan_hash` | the plan version whose generated content was approved |
| `content_hash` | the exact generated content set (definition below) |
| `state` | `active` while it binds; `superseded` once anything it covered changed |
| `invalidation_reason` | `plan_edited` / `content_changed` / `course_edited` / `replaced` |
| `approved_at`, `superseded_at` | when it started and stopped binding |

`content_hash` is defined, not chosen by the handler:

```
content_hash = packs.canonical_json_bytes({
    "course_id": <id>, "plan_id": <id>, "plan_hash": "sha256:...",
    "sections": [
        {"objective_id": <id>, "ordinal": <n>,
         "files": {"parent_guide": {"sha256": ..., "bytes": ...},
                   "learner_page": {...}, "answer_guide": {...}, "narration": {...}}},
        ... in ordinal order ...
    ]})
```

Each `sha256` is over the exact text `parent.blueprint.read` serves for that tab entry, so the parent
approves the bytes they read. `parent.blueprint.read` returns the current `content_hash`, the studio
sends it back to `parent.final.approve`, and the handler refuses a mismatch with
`VALIDATION_FAILED` + `current_content_hash`. `parent.export` recomputes it and refuses any row that
is not `active` with that hash — `reason: changes_need_review`.

**Invalidation is a kernel invariant, not a UI rule.** In one transaction with the edit that causes
it:

* a draft edit or a `plan.replan`/new plan version supersedes the course's **active** final approval
  with reason `plan_edited` (a replan also supersedes the approved plan, as it already does);
* regenerating content (a `lesson` stage job producing a different `content_hash`) supersedes it with
  reason `content_changed`;
* a course-level edit the approval covered (`courses.title` / `goal` through `parent.plan.edit`)
  supersedes it with reason `course_edited`;
* recording a new final approval supersedes the previous active row with reason `replaced`.

There is at most one `active` row per course — a kernel invariant, because SQLite cannot express a
partial unique index in the contract's `unique` vocabulary. An approval row is never deleted by an
edit, so the studio can always say what was approved and when it stopped applying. `plans.approved_at`
remains the plan's own timestamp; the two approvals never share a row.

### `parent.blueprint.read`

* **Five tabs, declared text only.** `tabs.parent_guide`, `tabs.learner_pages`, `tabs.answers`,
  `tabs.narration` are arrays of `blueprint_file`; `sources` is answered by the same read because
  the Sources tab must render before any lesson page exists. Each file carries `role`, `title`,
  optional `objective_id`, `text`, `sha256`, `bytes`, `source` (`authored` / `pack`) and `truncated`.
* **There is no path property anywhere in the response.** A pack-backed blueprint resolves its
  declared file *inside* the already-validated manifest and returns its text; an authored course
  composes text from the generation staging rows and `sources`. A generic
  `pack.file.read({pack_id, pack_version, path})` was considered and rejected: a path-addressed read
  is a filesystem-adjacent primitive that widens the surface for one consumer, while the tabs are a
  closed enum that the contract can bound. This is decision (c) of the CB-011 card.
* Bounds: `limit` (default 100, max 100) files per tab, `text` max 20000 characters with an explicit
  `truncated` flag, `sources` max 200. A long course says it was clipped; it never silently shortens.
* Read-only and unfenced: no revision bump, no idempotency key, activity revision `0`.
* It derives and returns `approval` (`parent_approval_status`: state, the approved hashes, timestamp,
  `invalidated_reason`) and `export` (`parent_export_status`: `ready` plus exactly one
  `blocked_reason` from `no_final_approval` / `changes_need_review` / `plan_not_approved` /
  `no_generated_content`) so the studio renders "Changes need review" from storage.

### `parent.export`

* **One pack builder, no new manifest vocabulary.** The export assembles a `cb.pack` v1 document from
  `packs.export_allowlist()` and declares the roles it actually carries: `parent_guide`,
  `learner_page` and `answer_guide` as `text/markdown`, and `narration` only when a real audio
  artifact exists (the role is audio-only in `packs._role_mime_mismatch`). A role enum is a list of
  **permitted** role/MIME pairs, not a set every pack must carry. An authored course has a
  narration *script*, which is text: it is served in the `narration` tab, written into the parent
  guide, and covered by the approved `content_hash`; when audio is produced the script becomes
  that artifact's `text_equivalent`. `docs/DECISION-AUTHORED-PACK-POLICY.md` §1 is the ruling. No
  stored manifest is copied, so `packs.PRIVATE_FIELDS` (attempts, notebook text, reflections,
  transcripts, provider settings, paths) cannot ride along even if a handler tries.
* **The exported rubric is assessment criteria only.** `checks[].rubric` is composed from the
  check's own criteria plus the plan objective's `evidence_criteria`, deduped. Supervision and
  safety notes are instructions to the adult, not grading criteria: they appear in the parent guide
  and never in a rubric. `reference_answer` is excluded from `checks[].accepted_alternatives`
  (alternatives are alternatives to the reference answer); `packs.validate_minima` refuses a pack
  where the two collide. Generated lessons carry at least three criteria per check
  (`MIN_RUBRIC_CRITERIA`), because one-line rubrics are refused on import and export alike.
* **Refusal is the feature.** `parent.export` runs only when the active final approval's
  `content_hash` equals the recomputed one; otherwise `POLICY_VIOLATION` with
  `reason: changes_need_review` (or `no_final_approval`, `plan_not_approved`). A stale studio cannot
  export bytes nobody approved.
* **Artifacts.** Exactly one `kind: pack` artifact and (when `formats` includes `pdf`, the default)
  one `kind: pdf` artifact with `mime: application/pdf`, produced through `artifacts.make_pdf`. The
  PDF is a document artifact — selectable text, low-ink layout, no image-of-a-page and no
  colour-only answer — and the handler records the export as an `artifacts` row of kind `export`
  like `pack.export` already does. `artifact_ref.kind` already names `pack` and `pdf`, so no artifact
  enum changes.
* The response's `files` is the exact file list the UX §10 preview renders: `role`, pack-internal
  `name` (relative, no leading slash, no `..` — enforced by the schema's `not` pattern), `sha256`,
  `bytes`, `mime`. It is the manifest's file list, not a second authority.
* `export_id` is minted per accepted call, and a repeated call with the same `idempotency_key`
  replays the stored result instead of re-writing artifacts.

### Reflections

`parent_reflections` (`cb.db` v3) stores `difficulty` (`easy` / `about_right` / `too_hard`), an
optional `revisit_note`, `apply_to_next_draft`, and the `plan_hash`/`content_hash` that were current
when it was written. It has **no** `evidence_class`, verdict or objective-state column, so a
reflection cannot become evidence of learning; `reflection` is already in `packs.PRIVATE_FIELDS`, so
neither the table nor a rendered reflection can enter an exported pack. `parent.reflection.list` is
the read that seeds the next brief.

### Storage read and written

| Method | Rows |
|---|---|
| `parent.brief.create` | writes `courses`, `enrollments`, `jobs` (kind `plan`, state `queued`, `brief_json`) |
| `parent.brief.get` | reads `courses`, `jobs` |
| `parent.plan.edit` | reads `enrollments`, `plans`, `objectives`; writes `plans` + `objectives`, supersedes an active `final_approvals` row; bumps `enrollments.revision` |
| `parent.final.approve` | reads `enrollments`, `plans`, `objectives`; writes one `final_approvals` row, supersedes the previous active one; bumps `enrollments.revision` |
| `parent.blueprint.read` | reads `courses`, `plans`, `objectives`, `sources`, generation staging (`gen_lessons`, `gen_lesson_checks`, `gen_plan_sections`), `packs` + stored manifest for a pack-backed course, `final_approvals` |
| `parent.export` | reads the same set + `packs`; writes `artifacts` (kind `pack`, `pdf`, `export`) and the pack directory through `packs`/`pack_flow` builders |
| `parent.reflection.record` / `parent.reflection.list` | writes / reads `parent_reflections` |

### Who executes `plan` and `lesson` generation (decision (e))

`generation.run_plan_job` / `run_lesson_job` and `job_service.run_pending(resolvers)` exist; nothing
in a production path registers a resolver or pumps the queue, so a queued job never moves. That is
not a wire gap and is **not** fixed by v6: the executor is the agent-side job tick and belongs to
Cinder (sibling card, `t_a356c8a8`). The contract fixes the seam it needs:

* A `plan` kind job's `brief.stage` selects the work: absent or `plan` means "author the plan",
  `brief.stage = lessons` with `plan_id` means "materialise lessons for this approved plan". This is
  deliberately **not** a new job kind: `cb.vocabulary#job_kind` is referenced by every pack manifest,
  so adding `lesson` would force a `cb.pack` v2 that rejects already-installed `$schema` v1 packs.
  `jobs.list`'s `kind` filter therefore shows authoring jobs as `plan`; the progress `stage` on the
  row says which stage is running. When a coordinated pack-manifest revision is affordable, `lesson`
  becomes its own family and this paragraph is deleted.
* The executor registers one resolver per kind it serves, drives `run_pending` from a bounded tick,
  and keeps the existing lease/checkpoint/cancel semantics. `parent.brief.create` only *queues*.

### `plan.replan` carries the authored outline (behaviour note, no wire change)

`plan.replan` creates a new plan version and copies its objectives, but the generation staging rows
(`gen_plan_documents` + `gen_plan_sections`) are written only by the `plan` job. A replanned version
therefore had no authored document: `jobs.create` with `brief.stage = lessons` for it failed
`plan ... has no authored document`, and `parent.export` stayed `no_generated_content` forever.
`parent.plan.edit` cannot rescue it (approved plans are not editable) and re-running the `plan` job
with the stored brief returns the reuse-cache document instead of writing anything.

The kernel now carries the outline inside the `plan.replan` transaction when — and only when — it
still maps one section per objective:

* every target objective has a source section, and every copied section names exactly one objective;
  `keep`, `retitle` and `defer` land 1:1, and a `remove` drops that objective's section and renumbers
  the survivors;
* an `add` introduces an objective the source outline never covered, so no carry happens. That
  version needs the plan job to author a new outline; the lessons job refuses it explicitly instead
  of authoring a partial set that would export with an objective missing.

The document bytes, research, validation id and generation digest are copied verbatim; copied
sections get new ids, so `gen_lessons` re-authors under its `(section_id, plan_hash, version)` key.
Lesson prompts and exports read objective titles from `objectives`, so retitles take effect without
rewriting the document snapshot. Request/response shapes, error codes and file formats are unchanged
— this is a behaviour note for a frozen v6 method, not a version bump. `require_revision`,
idempotency replay and `plan.approve`'s hash fence are untouched.

### A lessons brief without `unit_ordinal` authors the next unit (behaviour note, no wire change)

H-184. `generateLessons` in the Desktop posts the closed brief `{stage: 'lessons', plan_id,
enrollment_id}` and never a `unit_ordinal`. For a PLAN_SCHEMA v2 plan the lesson stage used to
refuse that brief ("a lessons job needs a unit_ordinal"), so the user reached an approved plan and
could not open a single page. The executor now resolves the unit from the stored plan: the stage
list for that brief is `unit_sections` then `lessons`, under the one leased job with one checkpoint
and one cancellation boundary per stage. Both stages read the same rule, so a retry resumes the unit
it was authoring rather than advancing past it:

* a unit is complete when it has exactly its `target_lessons` section rows at the stored plan digest
  and every one of those sections has a stored lesson at that digest; `unit_authoring_state()`
  returns the lowest-ordinal incomplete unit, or `None` when every unit is complete;
* a plan with no unit dimension (a pre-blueprint v1 plan) keeps the original one-stage path and
  authors every bundled section; `unit_sections` is an honest no-op for it;
* a brief that *does* name `unit_ordinal` keeps the original single-stage `lessons` shape.

The approval gate is unchanged: both stages still require `plans.state = 'approved'`, and
`plan.approve` still fences on the kernel plan hash. Nothing is auto-approved and no second plan is
written. The job checkpoint carries the honest unit facts — `unit_ordinal`, `next_unit_ordinal`,
`next_unit_to_author`, `units_total`, `units_complete` (ordinals whose lessons are stored) and
`units_complete_all` — read from the rows, never from a percentage. A brief for a plan whose every
unit is already authored completes as a no-op that spends nothing and says so.

The jobs preflight counts the unit the brief would author (the named `unit_ordinal`, else the
resolved next unit) rather than the whole plan, so a unit-sized `brief.budget_usd` is not refused
as insufficient for a multi-unit course. No method, job kind, state, error code or brief field
moves. To author a later unit the client posts the same brief with a **fresh** idempotency key and
reads `next_unit_ordinal` from the completed job; the existing `cb-lessons-<plan_id>` key replays
the first unit's job, which is the spend guarantee, not a bug.

### Cost ceilings and the `CostCeilingExceeded` recovery checkpoint (behaviour note + one additive brief field)

The dollar ceiling is now sized from the plan, not flat, and a mid-course abort is a recoverable
state rather than a dead end. No contract *version* moves: the checkpoint and `cb.errors#details`
facts fit inside the existing `jobs.checkpoint` (`type: object`, `maxProperties: 40`),
`cb.errors#details` (`maxProperties: 32`) and the already-frozen `POLICY_VIOLATION` code. One
additive byte change lands inside v10: the closed `$defs/plan_brief` now names the optional
`budget_usd` (positive number, ≤1000) that the `raise_budget` action passes. Without that property
the brief's `additionalProperties: false` refused the field, so the documented override was
unreachable on the wire. Every earlier v10 payload still validates; no method, table, error code,
job kind or vocabulary value moves.

* **`jobs.create` preflight.** When `kind = plan` and `brief.stage = lessons`, the handler counts
  `gen_plan_sections` for `brief.plan_id` and resolves the ceiling
  (`brief.budget_usd` > `COURSEBOOK_JOB_MAX_COST_USD` > the plan-sized default). If the ceiling
  cannot pay the plan's *minimum* (one generation + one validation per section), the request is
  refused with `POLICY_VIOLATION`, `details.reason = "cost_preflight_insufficient"` and the
  preflight arithmetic (`section_count`, `minimum_calls`, `maximum_calls`, `minimum_cost_usd`,
  `maximum_cost_usd`, `max_calls`, `max_cost_usd`, `budget_source`, `fits_minimum`,
  `fits_maximum`). **No job row is created and nothing is spent.** `brief.budget_usd` must be a
  positive number; anything else is `VALIDATION_FAILED` / `field: brief.budget_usd`.
* **The ceiling actually used is recorded.** A successful lessons stage stores
  `checkpoint.budget = {max_calls, max_cost_usd, source}` and `checkpoint.preflight = {...}`.
  `source` is `declared`, `operator_env`, `operator_brief` or `caller`, so an operator can tell a
  raised ceiling from a sized one. `usage.summary` response shape is unchanged (it is frozen to
  aggregate calls/tokens/artifacts); the per-job configured value lives on the job's checkpoint.
* **Mid-course abort checkpoint.** When a lessons stage hits the ceiling the job fails with
  `POLICY_VIOLATION` and `details` carrying `reason: cost_ceiling_exceeded`,
  `sections_total`, `sections_completed_count`, `calls`, `estimated_cost_usd`, `unknown_calls`,
  `max_cost_usd`, `max_calls` and `actions`. The same facts — plus the completed section ids — are
  merged into `jobs.checkpoint` (it survives the failure; `finish` writes it on the failed path):

  | key | meaning |
  |---|---|
  | `kind` | `cost_ceiling_exceeded` or `cost_preflight_refused` |
  | `plan_id`, `sections_total`, `sections_completed`, `sections_completed_count` | what already has durable lesson rows |
  | `calls`, `known_cost_usd`, `estimated_cost_usd`, `unknown_calls` | what was actually spent |
  | `max_cost_usd`, `max_calls` | the ceiling that stopped it |
  | `actions` | `["continue_remaining", "raise_budget", "stop"]` |
  | `resume` | `{method: jobs.create, brief: {stage: lessons, plan_id}}` |
  | `raise_budget` | `{env: COURSEBOOK_JOB_MAX_COST_USD, brief_field: brief.budget_usd}` |

  `continue_remaining` is a plain `jobs.create` for the same plan: `run_lesson_job` reuses the
  existing `(section_id, plan_hash, version)` rows, so completed sections are neither re-authored
  nor re-charged. The action labels authorize nothing on their own — each is a separate command.
  `stop` is the default because the job is already `failed`, not running.

### Handlers Cinder must register (after this freeze)

**Registration status: landed in CB-014.** All eight `parent.*` methods are registered — seven in
`coursebook/domain.py`, with `parent.export` split between `coursebook/pack_flow.py` (builder) and
`domain.py` (handler) — and all eight appear in `/runtime.implemented_methods`. The
pre-registration sentence below is kept as the record of the seam's behaviour without a handler,
not as a claim about this build.

| Method | Register in | Backing code | Handler must do |
|---|---|---|---|
| `parent.brief.create` | `coursebook/domain.py` (`@_handler`) | `course.create`/`enrollment.create`/`jobs.create` bodies, `_idempotent_lookup`, `_remember` | one transaction: replay the key; insert course (`recipe: parent`), enrollment, queued `plan` job with the brief (including `enrollment_id` and `stage: plan`); return the three ids |
| `parent.brief.get` | same | `jobs` row, `_job_view` | read the newest `plan` job for the course; return the typed brief + job summary |
| `parent.plan.edit` | same | `_plan_hash`, `record_objective`, `_bump_enrollment`, `_require_revision` | fence on `expected_plan_hash` then revision; refuse non-draft; apply edits; bump `plans.version`/objective versions; recompute hash; supersede active approval; return new hash + ordered ids |
| `parent.final.approve` | same | `final_approvals`, content-hash builder (shared with `parent.blueprint.read`) | fence on revision; verify `plan_hash` and `content_hash`; supersede previous active row (`replaced`); insert active row; bump revision |
| `parent.blueprint.read` | `coursebook/domain.py` or `pack_flow.py` for the pack-backed branch | `final_approvals`, generation staging, `packs` manifest | one read; build the five tabs from the closed allowlist; compute `content_hash`; derive `approval`/`export`; never emit a path |
| `parent.export` | `coursebook/pack_flow.py` (builder) + `domain.py` (handler) | `packs.export_allowlist`, `packs.FILE_ROLES`, `packs.PRIVATE_FIELDS`, `artifacts.make_pdf`, `pack_flow` pack writer | refuse unless the active approval's `content_hash` matches; build pack + PDF; return the manifest's exact file list and both artifact refs |
| `parent.reflection.record` / `parent.reflection.list` | `coursebook/domain.py` | `parent_reflections` | insert with the current hashes / bounded read ordered by `created_at` |

Before CB-014 registered them, `api.dispatch` answered `NOT_IMPLEMENTED` for all eight (the payload
was still validated first); an unregistered method still fails exactly that way. The Desktop gates
on `/runtime.implemented_methods`. Vellum's CB-011 UI consumes this contract; it does not need a
second amendment.

### Migration impact (cb.db v3)

Migration `0003_parent_studio_approvals_and_reflections.sql` creates `final_approvals` and
`parent_reflections` with their indexes. Additive only: no v2 table, column, index or unique key is
dropped or retyped. No backfill — a plan approved before this migration is not a content approval and
the migration does not invent one; a course with no row reports approval state `none` and export
blocked by `no_final_approval`.

## v7 delta (CB-015 residual) — source revalidation

v6 left a documented hole: `sources.refresh` could mark a source `stale`, but no cb.rpc method
called it, so the state guarded by `CHECK_STALE` was reachable only by hand-writing a database row.
v7 adds exactly one command, `source.revalidate`, and cb.db v4 adds exactly one nullable column,
`sources.content_hash`. Every v1–v6 method name and every v1–v6 method request/response payload is
preserved unchanged; the only bytes that move inside a carried method are `health.get`'s
`contract_version` echo (6 → 7), plus both response envelopes' `contract_version` consts. The
method enum is 52 = the 51 v6 methods + `source.revalidate`.

| `source.revalidate` | Contract |
|---|---|
| Request | `source_id`, `fetched` (`{content, title?}` or `null` for unreachable). No `reason`: a wire field the kernel discards is a seam that reads as working. |
| Response | `source_id`, `changed`, `support_status`, `review_required`, `fetched_at`, `previous_hash`, `content_hash`, `impact` (`objective_ids`, `check_ids`, `artifact_ids`, `lesson_ids`, `course_id`, `support_status`) |
| Envelope | `idempotency_key` required; **no `expected_revision`** (see below) |
| Effect | writes the fetch's content hash as the row's baseline and, on a change, `support_status='stale'`; never writes learner evidence |
| Revision | the response envelope's `revision` is always `0`; it is **not** an enrollment revision |

**Why no `expected_revision`.** Sources are course-scoped and several enrollments may legally share
one course; there is no single aggregate revision to compare-and-swap. The fence is the content-hash
comparison itself: a caller cannot make an unchanged fetch look changed, and the persisted baseline is
read in the same transaction that writes it. This is a deliberate carve-out from the general
"every mutation is fenced by `expected_revision`" line, and it is why the response carries no
revision field: a client must not adopt the envelope's `0` as an enrollment revision.

**The baseline rule (cb.db v4).** `sources.content_hash` is the hash of the last adopted fetch of
that row. It exists because pack-imported sources (`pack_flow._write_sources`) never have a
`gen_research_runs` snapshot, so before v4 they had no baseline and every revalidation would have
reported the convincing lie `changed=false`. `NULL` means "no baseline yet", never "unchanged": the
first successful `source.revalidate` of such a row records the baseline and returns `changed=false`;
only a later fetch whose hash differs marks the row stale. `sources.apply_run` writes the same
column when a research run sees the source, so the row and the immutable run snapshot cannot drift.
The fallback to the latest run snapshot remains for rows written before the column existed. An
unreachable fetch (`fetched: null`) marks the row `unreachable` for review without erasing the last
known baseline.

**Detection only; No recovery.** A changed fetch sets `stale`, and an identical re-fetch deliberately
leaves it `stale`. Nothing in this build writes `support_status` back to a reviewed value, so a
revalidated course's dependent checks stop grading and stay stopped until the plan is regenerated and
re-approved. Restoring a status honestly needs a stored prior status plus a review decision; neither
is in cb.db v4 nor in this card, so it is recorded as a deliberate omission instead of a half-built
recovery path.

**The race is closed in the kernel.** `attempt.submit` re-checks
`sources.assert_check_current` inside the same write transaction that commits the attempt, not only
in its pre-grade read. A revalidation that lands while an answer is being graded therefore returns
`CHECK_STALE` and writes no attempt, attempt row or evidence row. Nothing about the v7 wire changes
for this; it is the kernel keeping the existing gate true. `library.list` already reports the
course-level `warning: "stale_source"` once any source row is stale, so a client does not need to
scan the ledger to show the banner.

**Surface discipline.** This method is for the parent/research path, the Desktop's course-level
banner data and the proof harness. Vellum must **not** ship a Sources-tab "Check for changes" button
in this build: grading is paused with no review step beside it, so that control would be a one-way
switch rather than a wired feature. Harbor must run the demo's stale-source proof last, or on a
disposable course, for the same reason.

### Migration impact (cb.db v4)

Migration `0004_sources_content_hash.sql` is `ALTER TABLE sources ADD COLUMN content_hash TEXT`.
Additive only: no v3 table, column, index or unique key is dropped or retyped, and there is no
backfill. Existing sources have `content_hash` NULL until a research run or a first
`source.revalidate` records a fetch; learner evidence, attempts and notebook entries are never
rewritten by the migration or by revalidation.

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
| §10 | Parent Studio: brief, research/review, plan editing, plan **and** final approval, blueprint tabs, pack/PDF export, reflection | `parent.brief.create` (course + enrollment + queued `plan` job with the typed brief); `parent.brief.get` (duplicate brief, job state); `jobs.get` (progress); `parent.plan.edit` (draft edits + `changes_need_review`); `plan.approve` (the plan-level gate); `parent.final.approve` (the lesson-set gate, hash-fenced); `parent.blueprint.read` (the five tabs: parent guide, learner pages, answers, narration, sources — declared text only, no path); `parent.export` (authored pack + PDF, exact file list); `artifact.get` (fetch both artifacts); `parent.reflection.record` / `parent.reflection.list`; `pack.preview` / `pack.inspect` for an imported blueprint |
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

## Migration impact (cb.db v3)

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

Migration `0003_parent_studio_approvals_and_reflections.sql` (cb.db v3, CB-011) creates
`final_approvals` (one row per approved content set: plan hash, content hash, `state`
`active`/`superseded`, `invalidation_reason`, timestamps) and `parent_reflections` (parent-reported
difficulty + revisit note, no evidence columns), with their indexes. No v2 table, column, index or
unique key changes, and there is no backfill.

## v8 delta (M1-P4) — one lesson document, many views

v7 rendered a lesson as one linear segment list. v8 adds exactly one response field to one read
method: `lesson.page.document`, the validated `LessonDocument` of `docs/VISUAL_MEDIA_PLAN.md` §5.
Every v1–v7 method name and every v1–v7 method request/response payload is preserved unchanged;
no v7 field is removed or retyped, and the only bytes that move inside a carried method are
`health.get`'s `contract_version` echo (7 → 8) and both response envelopes' `contract_version`
consts. The method enum stays at 52 because v8 adds no command.

| Aspect | v8 decision |
|---|---|
| Wire | `lesson.page.response.document` (`$defs/lesson_document`, `$defs/lesson_block`, `$defs/lesson_document_media`), required alongside every v7 field |
| Block | `id`, `role` (`orient`/`explain`/`example`/`practice`/`recap`), `headline`, `short`, `deep`, `check_id`, `media[]`, `source_ids[]` |
| Check | at most one check per document; exactly one block carries it. No block, and no view, duplicates it |
| Media | a child of a block (`kind`, `role`, `artifact_id`, `purpose`, `text_equivalent`, `label`, `degraded`, `reason`), never a free-floating gallery item |
| State | `complete` (short and deep authored for every block), `textbook_only` (projected from the older linear shape; `views.guided=false` plus a human `view_note`), `empty` |
| Storage | none. `document` is projected from rows `lesson.page` already reads (`lesson_segments` and course `artifacts`); `gen_lessons.page_json` is projected by `generation.learner_page`. No cb.db migration, no new column, and old rows are never rewritten |
| Determinism | block ids are derived from position, role and text; `content_hash` is sha256 over the canonical document core and `document_id` is `doc_` + its first 20 hex characters. Re-reading the same rows returns the same document |
| Answers | no `reference_answer`, `accepted_answers`, `accepted_alternatives` or `rubric` anywhere in the document. The projection is built from an allowlist and `validate_document` re-checks it; `generation.assert_no_answer_leak` covers the document |
| Rights | a media child keeps only the authored purpose, text equivalent and label; provenance stays on `artifact.get`. A legacy media segment whose artifact row is unknown is preserved as block text rather than labelled with a guessed kind |
| Views | Textbook renders `deep` in authored order, Guided renders `short` one block at a time, Field Quest maps the same `role` sequence to missions and uses the existing check, Field Notes captures. None of them authors a fact; a view is a lens over the one document |

**Migration.** There is no backfill and no rewrite. A section whose durable rows predate v8 reads
as `textbook_only` with `views.guided = false` and a note that says so. A page projected from
`gen_lessons.page_json` maps the authored segment kinds (`model` → `example`, `explain` →
`explain`, `guided` → `practice`, `retrieval` → `recap`), the worked example to `example` and the
learner explanation to `recap`. A page projected from `lesson_segments` maps teaching prose
positionally (first `orient`, last `recap`, middle `explain`), a `check_prompt` segment to the
`practice` block and a `media` segment to a media child of the preceding block. `short` is never
synthesised from `deep`: only an authored document can reach `complete`. The lesson writer authors
`segments[].short`, `worked_example.short` and `learner_explanation_short` in
`gen_lessons.page_json`, and `lesson.page` projects that validated page with `document_from_page`
when it exists, so a generated section is `complete` with no wire change and no backfill.

**Not in v8.** No authored-block columns and no prompt change to the lesson schema; the projection
is ready for authored blocks (`document_from_blocks`) but this release does not ask the model for
them. No UI change: the Desktop ignores a field it does not know, and older clients keep reading
`segments`. No change to grading, attempts, evidence or mastery semantics.

**After v8: the guided writer (M1-U2).** The lesson writer now authors a `short` beside every
`deep` field — `segments[].short`, `worked_example.short`, `learner_explanation_short` — inside
`gen_lessons.page_json`, and `lesson.page` projects that validated page with
`document_from_page` instead of the linear segment rows. This is a change to stored page content
and to one handler's choice of projection, **not** a contract change: the v8 method, payload and
`$defs/lesson_document` shape are unchanged, `document_from_segments` remains the fallback for
pack/composed sections and older rows, and no row is rewritten or backfilled. A page written before
this change still reads `textbook_only`.

## v9 delta (M3-B1) — bounded pronunciation practice, not a grade

M3-S1 proved there is no documented plugin seam to the host's configured STT. The operator
approved Coursebook's own local recogniser on 2026-11-06. v9 adds exactly two commands and one
`cb.db` table; every v1-v8 method payload stays unchanged apart from the `contract_version` echo
(8 → 9), and the method enum grows from 52 to 54.

| Method | Input | Output | What it may never do |
|---|---|---|---|
| `pronunciation.attempt` | `enrollment_id`, `objective_id`, `attempt_nonce`, `target` (≤200 chars), `locale`, `audio_data_url` (≤5,000,000 chars; ≤3 MiB decoded), optional `prompt` | `status` (`assessed`/`empty`/`unavailable`), `recorded`, `attempt_id` or null, `revision`, typed `assessment`, bounded `reason` | close a check, advance an objective, bump an enrollment revision, write a transition, retain audio, or return a score when no real transcript exists |
| `pronunciation.dispute` | `enrollment_id`, `attempt_id`, `note` (≤1,000 chars) | `dispute_id`, `state: open`, `revision` | rewrite the verdict, the transcript or `evidence_class`; move course state |

`assessment` is `{transcript, target, locale, provider, model, language, unit, word_accuracy,
phoneme_accuracy, confidence, words[], verdict, evidence_class}`. `provider` is always
`coursebook_local_whisper`; `model` is the cached model name. `unit` is `word` for spaced languages
and `character` for Japanese/Chinese/Thai, so the comparison does not pretend every script has word
boundaries. `words[]` carries `expected`, `heard`, `match` and an optional per-word `confidence`.
`verdict` is `meets_target | close | needs_practice | unavailable`; `phoneme_accuracy` is null in
this slice. `evidence_class` is the const `model_assessed` for every assessment, including an
unavailable one — `recorded: false` and a null `attempt_id` are what say no evidence was written.
It is never "verified pronunciation" and never mastery.

**Fail closed.** A missing `faster-whisper`/model/`ffmpeg`, a decode or inference failure, a
silence/empty transcript, or an oversized/mismatched MIME produces `recorded: false`. MIME/size
violations are `VALIDATION_FAILED` with a reason code before the recogniser is called; provider and
empty-audio outcomes are a successful envelope with `verdict: unavailable` and no row. Same-key
replay returns the stored result; a repeated `attempt_nonce` returns the original attempt id.

**Storage.** `cb.db` v5 adds one table, `pronunciation_attempts` (`id`, `enrollment_id`,
`objective_id`, `attempt_nonce`, `target`, `locale`, `transcript`, `provider`, `model`, `language`,
`unit`, `word_accuracy`, `phoneme_accuracy`, `confidence`, `verdict`, `evidence_class`,
`assessment_json`, `disputes_json`, `created_at`), unique on `(enrollment_id, attempt_nonce)`. It is
separate from `attempts`; no v4 table changes and there is no backfill. It has no audio, path,
provider-key or model-cache column.

## v10 delta (H-01) — learner capability inputs and the plan-job brief

The adversarial harness review (P0-3) found the capability policy's inputs unreachable from the
product path: `plan_lesson_capability` needs `subject_domain`, `level` and `lesson_intent`, but
`course.create` froze the dials to `pace`/`depth`/`assessment`/`autonomy` with
`additionalProperties: false`, and `locale` alone was the policy's fallback — so a Spanish technical
procedure was classified as a language lesson and lost its schematic, while the Japanese L0
scaffold (`_scaffold_policy`) could only be reached by an internal test fixture. P0-4's plan-scope
gap had the same shape: there was no `scope` field anywhere.

v10 makes those inputs first-class, additively. No method is added or removed (54 stay), no error
code, job kind or vocabulary value changes, and every v1-v9 payload still validates because every
new field is optional.

| Surface | Added | Notes |
|---|---|---|
| `course.create.request` | `level` (string ≤35 or null), `subject_domain` (string ≤60 or null), `scope` (`single`/`short`/`full` or null) | Optional; `locale` stays optional as before. The four dials are unchanged and stay closed — a level or domain is **not** smuggled into `dials`. |
| `jobs.create.request` | one typed `plan` brief (`$defs/plan_brief`) applied when `kind = "plan"` | Carries `goal`, `brief`, `title`, `recipe`, `dials`, `locale`, `level`, `subject_domain`, `scope`, `course_id`, `enrollment_id`, `plan_id`, `stage`, plus the Parent Studio authoring fields (a `parent.brief.create` job is re-queued through `jobs.create` from the brief its own `jobs.get` returned). `additionalProperties: false`, so an unknown field is `VALIDATION_FAILED` rather than a silent no-op. Other job families keep the bounded open `brief` object. H-17 adds the optional `budget_usd` (positive number ≤1000): it is named inside the closed brief because the `CostCeilingExceeded` recovery action tells an operator to pass `brief.budget_usd`, and a closed brief would otherwise refuse it. |
| `cb.db` v6 | nullable `courses.level`, `courses.subject_domain`, `courses.scope` via migration `0006_courses_plan_brief_inputs.sql` | Stored once on the course so `course.get` and the plan job read the same values. `scope` is CHECK-constrained to `single`/`short`/`full` or NULL. No backfill: an existing row keeps NULL, which means "the brief did not name it". |

**What reads them.** `coursebook.domain.course_create` stores the three values (blank collapses to
NULL) and `course.get` returns them. `coursebook.generation.run_plan_job` reads the same fields from
the job brief, keys its reuse cache on them (a changed level or domain never reuses a plan authored
under a different policy), persists them beside `dials` in the plan document, and hands the policy a
view of the dials that includes `level`/`subject_domain` — the dials stored on the course remain the
four contract dials. `run_lesson_job` reads the same stored values, so a lesson's capability policy
and language scaffold agree with the plan it belongs to. Nothing here invents a value: with all
three absent, every code path behaves exactly as it did at v9.

**Deliberately not in this delta.** No UI control, no plan-shape change from `scope` (the planner
still authors one section per objective), no research-budget change, and no new dial. The contract
only guarantees the inputs arrive and are persisted honestly. Threading them through the plan
runtime is a follow-up with no contract change of its own — see *v10 follow-up (H-13)* below.

## v10 follow-up (H-13) — the plan runtime reads the declared inputs

**No contract change.** Still `cb.rpc` v10 and `cb.db` v6; no method, field, enum or error code is
added or altered. H-13 is the generator side of the same delta, and it is documented here because
it changes what v10's fields *mean* at runtime:

| Input | Research | Plan prompt | Plan-time capability decision | Fingerprint / reuse cache | `plan_document` / `course.get` |
|---|---|---|---|---|---|
| `level` | language-course query qualifier | `Learner level: …`; never inferred from `locale` | `level` on the decision | included | returned |
| `subject_domain` | one subject qualifier; suppresses the locale language query unless the domain is `language` | `Subject domain: …` stated as *what the course is about* | domain-normalised; drives the media reasons | included | returned |
| `scope` | not used (no budget change) | `Scope: …` plus the objective range and week cap | not used | included | returned |

`dials` stays the closed four-dial object wherever the contract carries it — the course row,
`course.get` and the plan document: the declared inputs are siblings there, never members. `scope`
gains exactly one deterministic consequence — a cap on `time_estimate.weeks` (`single` 1, `short`
8, `full` 104) — and no second scope engine is claimed.

## v11 delta (H-21)

`cb.rpc` v11 and `cb.db` v7 freeze the unit contract of `docs/COURSE-BLUEPRINT.md` §4 and §14
(R1-R9 normative). This slice lands the **contract and the migration only**; PLAN_SCHEMA v2, the
unit-scoped stages, prerequisite gating handlers and any UI are later slices and are not claimed
here.

* `plan_brief` gains `unit_ordinal` (integer 1-12) and `stage` accepts `unit_sections` beside
  `plan` and `lessons`. The brief stays closed: `additionalProperties: false`, no
  `prerequisite_policy` under any name (R8 reserves that for a later card).
* `outline_plan` gains an optional `units` array; `$defs/outline_unit` has exactly R9's key set:
  `ordinal`, `title`, `goal`, `prereq_unit_ordinals`, `prerequisite_state`, `unmet`,
  `objectives` (each an existing `outline_objective`). `outline_objective` gains optional `unit`.
  A legacy plan projects one unit titled with the plan title; `independent` remains the
  objective's own state and no derived readiness/mastery field exists (R7, R9).
* `lesson.begin` and `check.open` accept `acknowledge_prerequisites` (boolean, default false) and
  may return `$defs/prerequisite_state` (`no_edges | satisfied | unmet | unmet_acknowledged`)
  with the unmet objective list. `no_edges` leaves the legacy response unchanged (R5).
* `cb.errors` v3 adds one typed refusal, `PREREQUISITE_UNMET` (state, HTTP 409, not retryable):
  the command wrote no `lesson_runs` or `checks` row and repeating with the acknowledgment flag
  is the learner's decision, never evidence (R6).
* `cb.jobs` v3 is a reference-only refresh: every state, transition and note is unchanged from v2;
  it exists so `cb.rpc` v11 and the job error envelope resolve against the current `cb.errors` v3.
* `cb.db` v7 adds `plan_units` (id, plan_id, ordinal, title, goal,
  prereq_unit_ordinals_json, target_lessons, created_at; unique `(plan_id, ordinal)`),
  `objectives.unit_id`, `gen_plan_sections.unit_id` and `gen_plan_sections.section_role`
  (`owner`/`review`, default `owner`) through `0007_plan_units.sql`. Additive only, no backfill.
* **R4 legacy hash invariance:** `parent_authoring.plan_hash` adds `units` only when a
  `plan_units` row exists and an objective's `unit` only when `unit_id` is non-NULL. Every stored
  pre-0007 plan therefore hashes byte-identically and every H-12 `plan_content_hash` keeps
  binding. `tests/test_plan_units.py::LegacyPlanHashInvarianceTest` pins the fixture hash.

## v12 delta (H-26) — the student syllabus import path

`docs/STUDENT-MODE.md` freezes a second import path: a learner uploads the syllabus of a class they
already take, and Coursebook builds a **companion course** aligned to it. It is never a `cb.pack`,
never a catalog artifact, and never an enrollment claim. v12 is additive over v11; every v11 method,
payload and enum value is preserved, the version echo moves to 12, and `cb.vocabulary` stays v1.

| Surface | Added | Notes |
|---|---|---|
| `cb.rpc` v12 | `syllabus.intake.create`, `syllabus.get`, `syllabus.parse`, `syllabus.align`, `syllabus.alignment.get`, `syllabus.alignment.review`, `syllabus.delete` | Intake takes `content_base64` or `pasted_text` — **no path field and no URL field**. A parse/align job is `kind=import` (an existing vocabulary family) with a closed `$defs/import_brief` and `stage` `syllabus_parse`/`syllabus_align`. |
| `course.create.request` | optional `syllabus_id` + `syllabus_revision` (together or not at all) | Writes one `course_syllabi` row, leaves `courses.pack_id` NULL, and refuses `recipe != companion`. |
| `$defs/plan_brief` | optional `syllabus_id`, `syllabus_revision`, `alignment_revision` | The plan job reads validated syllabus items as bounded untrusted scope text; the planner still authors every objective. The brief stays closed. |
| `cb.db` v8 | eight tables via migration `0008_syllabus_intake.sql`: `syllabus_series`, `syllabi`, `syllabus_files`, `syllabus_blocks`, `syllabus_parse_runs`, `syllabus_items`, `course_syllabi`, `syllabus_alignments` | Additive only, no backfill: a pre-v8 course has no `course_syllabi` row and behaves exactly as before. H-21's `plan_units` storage is untouched. |
| `cb.errors` v4 | `SYLLABUS_REJECTED`, `SYLLABUS_NO_TEXT_LAYER`, `SYLLABUS_STALE`, `SYLLABUS_UNREVIEWED`, `SYLLABUS_IN_USE`, `PARSER_UNAVAILABLE`, `BLUEPRINT_UNAVAILABLE` | Every one is a typed refusal with no partial write. H-21's `PREREQUISITE_UNMET` is carried unchanged. |
| `cb.jobs` | unchanged (v3) | The syllabus stages run under the existing `import` job family; no state, transition or kind is added. |

**What the shipped stages do.** Intake sniffs magic bytes (`%PDF-`, `PK\x03\x04`) rather than trusting
a filename or MIME, refuses encrypted/active-content PDFs, macro/external-relationship DOCX, non-UTF-8
or NUL-bearing text, and enforces the 4 MiB / 8 MiB / 200,000-character caps before storing a byte.
Extraction is deterministic and local: stdlib for text/Markdown/DOCX, optional `pypdf` for PDF, whose
absence is `PARSER_UNAVAILABLE`. Every parsed scalar is an item with `extracted` / `unknown` /
`ambiguous` state and a page/section/line anchor; an item's quote is verified verbatim against its
block and a mismatch downgrades it to `unknown`. No model call is made by either stage in this build,
so no syllabus text leaves the machine. Alignment is deterministic too: title-token overlap gives
`aligned`/`partial`/`unmatched`, and an assessment whose syllabus week is earlier than the matching
objective's plan section is a `conflict`. The model-assist lane in `docs/STUDENT-MODE.md` §4.3 is
**not** implemented, and no row claims it was.

**Full scope plans through v11, it is not refused.** A companion course is an ordinary course with
`recipe='companion'`; `scope='full'` runs through the v11 unit-scoped CourseBlueprint exactly like any
other full-scope course (units, unit stages, R1-R9 edge validation, `coursebook.plan.v2`). The
external class in the syllabus is the scope authority for the objective count and ordering, and H-12
`plan.approve` still gates authoring. `BLUEPRINT_UNAVAILABLE` survives in the catalog only for a host
build that cannot run `coursebook.plan.v2`; it is not returned by the companion path on this build.

**Not in this delta.** No UI, no pack change, no second course/plan/lesson engine, no second
enrollment authority, no export of syllabus text, no LMS client, no calendar, no gradebook.

## v13 delta (H-08) — a learner-authored course packages itself

The adversarial harness review (P0-5) found that "package the result for reuse" was true only for a
pack-backed course or a Parent Studio blueprint. `pack.export` refused a course with no `pack_id`
(`course_not_pack_backed`), and the only authored export, `parent.export`, requires a Parent Studio
`final_approvals` row that a `course.create` course never has. The main learner path — a course
created from a goal — had no export command and therefore no export action.

v13 adds exactly two commands. Every earlier method name and payload is preserved unchanged, the
method enum grows from 61 to 63, and no error code, job kind or vocabulary value changes. (The H-08
work was authored as a v11 of its own against an older base; on this line v11 is H-21's unit
contract and v12 is H-26a's syllabus-intake contract, so the delta lands at v13.)

| Method | Input | Output | What it may never do |
|---|---|---|---|
| `course.export.read` | `enrollment_id` | `ready`, `blocked_reason`, `blocked_message`, `problems[]`, `pack_backed`, `content_hash`, `files[]`, `license`, `rights`, `no_upload`, `plan`, `sections` | write an artifact, change a revision, or show a file list it would not export |
| `course.export` | `enrollment_id`, `expected_content_hash` + envelope `idempotency_key` | `export_id`, `pack` (`pack_id`/`pack_version`/`manifest_hash`), `files[]`, `artifacts[]`, `content_hash`, `exported_at`, `license`, `rights`, `no_upload` | copy a stored manifest, an attempt, a notebook entry, a transcript, a provider setting, a path or telemetry; export a page a validator did not clear; export text the caller did not review |

**The gate, in order.** (1) The course must be learner-authored, not pack-backed; an imported
course is refused with `course_pack_backed` and keeps using `pack.export`. (2) The current plan must
be approved (`plan_not_approved`). (3) **Every** lesson section must carry a generated page whose
`gen_lessons.state` is `validated` (`lessons_not_validated`, with one `problems[]` line per
section). (4) If the course has an active `final_approvals` row — a course a parent approved in
Parent Studio — its `content_hash` must still equal the recomputed one (`changes_need_review`).

**Final approval is not required for `course.export`.** Its approval authority is the approved plan
plus explicitly validated pages; requiring a Parent Studio signature would make the learner path
depend on a surface the learner never sees. A stored active approval is still honoured as a hash
fence, so text an adult signed off cannot change and then ship under that signature.

**Two hash fences.** The caller must send back the `content_hash` that `course.export.read`
returned; a mismatch is `DELETE_SCOPE_STALE` and nothing is written. The write then re-reads the
course inside its adopt transaction and refuses with `changes_need_review` if the text changed
between the read and the archive — the exported bytes can never be a page the caller did not see.

**What is rebuilt.** `coursebook.parent_authoring.build_pack` composes a *fresh* `cb.pack` v1
manifest from the validated `gen_lessons.page_json` rows, the plan objectives and the check rows:
`parent-guide/*.md`, `lessons/*.md`, `answer-guide/*.md`, for every objective. Identity is
`authored-<course>`, version `1.0.0`, licence `all-rights-reserved` with `redistribution:
local_only`. `pack.export` is unchanged for pack-backed content, and an imported pack is still never
writable: importing this archive cuts a new course bound to the pack, exactly like any other pack.

**Response, not a path.** `artifacts[]` carries the `artifact.get`-fetchable record; `pack` carries
the manifest identity and `content_hash` the reviewed course-text digest. `rights` and `no_upload`
are sentences the surface prints verbatim: the archive is a local copy, not a publication, and the
no-upload statement (`no_upload`) says the export made no network call and recorded no telemetry.

**Not in this delta.** No PDF handout from the learner surface (that stays `parent.export`; the
archive already carries the lesson text as Markdown), no upload or catalog submission, no change to
`pack.export`'s allowlist, no new `cb.db` table, column or migration, and no `course.export` on a
pack-backed course.

## v13 follow-up (H-18) — text language, direction and locale-aware scaffolds

**Additive inside `cb.rpc` v13; no new version.** H-18b was authored against v11, but on this line
v11 is H-21's unit contract, v12 is H-26a's syllabus intake and v13 is H-08b's authored export, so
the union lands the two optional properties inside v13 — exactly as H-17 landed `budget_usd` inside
v10. Every earlier payload still validates; nothing becomes required.

* `$defs/lesson_document` gains optional `lang` (text language tag, ≤ 35 characters, BCP-47-ish
  pattern `^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$`) and optional `direction` (`ltr` | `rtl`).
  Both are **absent** unless the page the document is projected from recorded them, so a document
  authored before H-18 keeps its bytes, `content_hash` and `document_id`
  (`tests/test_locale_scaffolds.py::LegacyDocumentHashTest` pins the pre-H-18 hash).
* **`contracts/rpc.v11.json` is unchanged.** A shipped version file is a frozen snapshot: the H-18b
  branch edited it in place, and the union reverts it to `origin/master`'s bytes and puts both
  properties in `rpc.v13.json` instead. Clients that cache v11 see exactly the v11 they had.
* `direction` is derived from the *script* of the text's language (`ar`, `fa`, `he`, `ur`, … are
  `rtl`; every other known locale is `ltr`). It is never derived from a claim about the learner
  and it changes no block, check, media, grading or evidence semantics — a direction is a
  rendering fact, never evidence.
* Both are projected through every view root of the Desktop half
  (`data-cb-lesson-view` = `textbook` | `guided` | `field_quest` | `procedure`), so one document
  renders in one direction in every view. A view that receives neither field adds no attribute.
* **Not on the wire:** the generation-side `check.scaffolds` shape. It moves from the fixed
  Japanese triple `{romaji, furigana, english_meaning}` to the bounded open list
  `[{kind, script?, gloss?, direction?}]` over the vocabulary in `coursebook/localization.py`
  (`romaji`, `furigana`, `gloss`, `transliteration`, `diacritics`, `pinyin`, `script_guide`), with
  the legacy object still read so every stored page and lesson hash is unchanged. A scaffold
  remains a task-mandated accessibility aid — never a learning-style diagnosis and never
  unaided-skill evidence. Japanese at L0/L1 still mandates romaji, furigana and a gloss; Arabic
  beginners get harakat diacritics; French is never asked for a Japanese scaffold.
* No method, request/response field, table, column, migration, error code, job kind or vocabulary
  value changes.

## Error codes and subsystem sub-reasons (`details.reason`)

Decision t_d43c0dc1 (H-130). `cb.errors` v4 stands; there is no `errors.v5` for this. The
catalogue is the authority for the three facts a client must branch on without parsing prose:
`category`, `retryable` and the HTTP mapping. It is deliberately *not* the authority for every
subsystem-specific refusal.

The rule:

* A failure whose category, retryability and HTTP status already fit a catalogue code carries its
  subsystem-specific label in `error.details.reason`. `details` is an open object
  (`additionalProperties: true`, `maxProperties: 32`), so this is a zero-version-bump seam.
* `details.reason` values are snake_case labels matching `^[a-z][a-z0-9_]{2,63}$`. They name the
  cause, not the surface: `brief_unreadable`, not `BRIEF_UNREADABLE` or `job_brief_dialog_error`.
* `details` may carry the matching structured context alongside `reason` (a `stage`, a `kind`, the
  preflight arithmetic). Values stay non-sensitive: no answer text, key, raw grader output or path.
* A **new catalogue code** is warranted only when at least one of `category`, `retryable` or HTTP
  status differs from every existing code, or the contract intends the client to branch on `code`
  alone as an exhaustively-switchable enum. "Same category, same retryability, same status, only
  the label differs" is a `details.reason`, not a version.

Documented sub-reasons at v4 (not exhaustive of every emitter, but the ones a client may key on):

| `details.reason` | catalogue `code` | emitted by |
|---|---|---|
| `brief_unreadable` | `VALIDATION_FAILED` | `job_service.run_pending` when a persisted brief cannot be parsed or resolved (H-130). Non-retryable; the row is claimed under the lease fence and failed durably. |
| `cancel_state_unreadable` | whatever `_stage_error` maps the stage's exception to (`HOST_UNAVAILABLE`, `POLICY_VIOLATION` or `INTERNAL_ERROR`) | `job_service` when the cancel flag cannot be read (H-129); the job rests `interrupted_requires_retry`. |
| `cost_ceiling_exceeded` | `POLICY_VIOLATION` | a lessons stage that hit the dollar ceiling; the recovery facts also land in `jobs.checkpoint`. |
| `cost_preflight_insufficient` | `POLICY_VIOLATION` | `jobs.create` preflight refuses a ceiling that cannot pay the plan minimum; no job row is created. |
| `plan_empty`, `plan_not_validated` | `VALIDATION_FAILED` | plan approval and edit fences in `domain.py`. |
| `course_not_pack_backed`, `export_not_exportable` | `POLICY_VIOLATION` | `pack_flow` export gates; `problems` carries the per-question detail. |

The same naming rule applies to `jobs.checkpoint` labels, which are also an open object
(`maxProperties: 40`): `cost_ceiling_exceeded`, `checkpoint_serializer_failed`.

Consequences for clients (H-117 and the retry surface):

* branch on `code` for behaviour (retry button, status copy class, whether a second attempt is
  offered at all);
* read `details.reason` for the specific message and for the narrow discriminations listed above;
* a reason value is part of the observable contract even though the schema does not enumerate it.
  Renaming one is a visible change: record it in this section, and do not rename one that shipped.

## Changing a contract

1. Open an Atlas decision in the task thread. A semantic change is **not** a patch.
2. Add a new file (`rpc.v8.json`, `db.v4.json`, `projection.v1.json`) and bump
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
| v6 | 2026-11-06 | CB-011 additive amendment. 51 RPC methods (+parent.brief.create, parent.brief.get, parent.plan.edit, parent.final.approve, parent.blueprint.read, parent.export, parent.reflection.record, parent.reflection.list) so the Parent Studio can be built without reading SQLite. cb.db **v3** adds `final_approvals` (lesson-set approval bound to plan hash + content hash, with the vocabulary value that invalidates it) and `parent_reflections` via migration 0003; no column changes, no new error code, `cb.vocabulary`/`cb.jobs`/`cb.pack`/`cb.projection` unchanged. Rejected: a generic path-addressed `pack.file.read` (role-scoped tabs instead), a `lesson` job kind (would force a `cb.pack` v2 and reject installed packs), and per-lesson prose editing (no storage decision yet). The Parent Studio answers tab is the one scoped exception to "no answer text on the wire". |
| v7 | 2026-11-06 | CB-015 residual additive amendment. 52 RPC methods (+`source.revalidate`) so the stale-source state is reachable through cb.rpc instead of only by hand-writing a row; the existing `sources.assert_check_current` gate then refuses dependent grading with `CHECK_STALE`. cb.db **v4** adds the nullable `sources.content_hash` baseline column via migration 0004 (additive, no backfill), because pack-imported sources have no research-run snapshot and would otherwise report `changed=false` forever. No new error code, job kind or vocabulary value. `source.revalidate` carries `idempotency_key` and deliberately no `expected_revision`; the envelope revision is 0 and is not an enrollment revision. Detection only: there is no status-restoring recovery command, and a client must not expose a one-way "check for changes" control. |
| v8 | 2026-11-06 | M1-P4 additive amendment. One new response field, `lesson.page.document` (the §5 block document), with `$defs/lesson_document`, `$defs/lesson_block` and `$defs/lesson_document_media`. 52 RPC methods unchanged; no cb.db table, column, migration, error code, job kind or vocabulary value; every v7 `lesson.page` field stays required and unchanged. The document is projected at read time from the same durable rows, so old rows are never rewritten; a page authored before v8 reports `state = "textbook_only"` with `views.guided = false` and a human note rather than a broken toggle. One check attaches to exactly one block, media is a child of a block, and the document can contain no reference answer or rubric text. `rpc.v7.json` is pinned by sha256. |
| v9 | 2026-11-06 | M3-B1 additive amendment. 54 RPC methods (+`pronunciation.attempt`, `pronunciation.dispute`) and cb.db **v5** `pronunciation_attempts` via migration 0005. A pronunciation result is `model_assessed`, never a grade: it cannot close a check, advance an objective or write a transition, and no audio is stored. No new error code, job kind or vocabulary value. `rpc.v8.json` is pinned by sha256. |
| v10 | 2026-11-07 | H-01 additive amendment. `course.create` gains optional `level`, `subject_domain` and `scope`; `jobs.create` gains one closed `$defs/plan_brief` for `kind = "plan"` so unknown fields are refused instead of silently ignored. cb.db **v6** adds nullable `courses.level`/`subject_domain`/`scope` via migration 0006, with no backfill. 54 RPC methods unchanged; no error code, job kind, vocabulary value or dial changes. `rpc.v9.json` and `db.v5.json` are pinned by sha256. |
| v10 (H-17) | 2026-11-07 | Additive inside v10: `$defs/plan_brief` names the optional `budget_usd` (positive number ≤1000), the per-job cost-ceiling override the `CostCeilingExceeded` recovery checkpoint's `raise_budget` action passes. The H-17 behaviour note was written as "no wire change", but a closed brief refuses an unnamed property, so the field had to be declared for the documented override to be reachable. Every earlier v10 payload still validates; no method, table, migration, error code, job kind or vocabulary value changes, and `additionalProperties: false` stays. |
| v11 | 2026-11-07 | H-21 slice A additive amendment (contract and migration only). `plan_brief.unit_ordinal` (1-12) and `stage = unit_sections`; optional `units` projection on `outline_plan` with `$defs/outline_unit` (R9 key set) and optional `unit` on `outline_objective`; `acknowledge_prerequisites` and `$defs/prerequisite_state` on `lesson.begin`/`check.open`; `PREREQUISITE_UNMET` in cb.errors **v3**. cb.db **v7** adds `plan_units`, `objectives.unit_id`, `gen_plan_sections.unit_id` and `section_role` via migration 0007, additive with no backfill. 54 RPC methods unchanged. R4: `parent_authoring.plan_hash` is byte-identical for every stored pre-0007 plan (pinned by `test_legacy_plan_hash_unchanged_after_0007`). `rpc.v10.json`, `db.v6.json` and `errors.v2.json` are pinned by sha256. Handlers for gating, unit stages and PLAN_SCHEMA v2 are explicitly out of this slice. |
| v12 | 2026-11-07 | H-26 additive amendment: the student syllabus import path. Seven `syllabus.*` methods; optional `syllabus_id`/`syllabus_revision` on `course.create` (companion recipes only); optional `syllabus_id`/`syllabus_revision`/`alignment_revision` on the closed `plan_brief`; a closed `import_brief` for `kind=import` with `stage=syllabus_parse`/`syllabus_align`. cb.db **v8** adds the eight syllabus tables via migration 0008, additive with no backfill and no change to `plan_units`. cb.errors **v4** adds the seven syllabus refusals and carries `PREREQUISITE_UNMET`. 61 RPC methods; no job kind, vocabulary value, transition or dial changes. Full scope plans through the v11 blueprint; `BLUEPRINT_UNAVAILABLE` remains only for a host without `coursebook.plan.v2`. `rpc.v11.json`, `db.v7.json` and `errors.v3.json` are pinned by sha256. |
| v13 | 2026-11-07 | H-08 additive amendment: a learner-authored course packages itself. Two methods appended (`course.export.read`, `course.export`) to the 61 v12 methods, so a course created from a goal can export instead of only a pack-backed course or a Parent Studio blueprint; `pack.export` keeps the pack-backed bytes with its own allowlist and unchanged behaviour. The gate is an approved plan plus every lesson page in `validated` state; a stored active final approval is honoured as a hash fence, and the caller's reviewed `expected_content_hash` is the second. No new cb.db table, column, migration, error code, job kind or vocabulary value. Numbered v13 because v11 is H-21's unit contract and v12 is H-26's syllabus intake; `rpc.v12.json` is pinned by sha256. |
| v13 (H-18) | 2026-11-07 | Additive inside v13: `$defs/lesson_document` gains optional `lang` (BCP-47-ish text tag, ≤ 35) and `direction` (`ltr`/`rtl`), both absent on documents projected from pages that never recorded a locale, so old documents keep their content hash and id (pinned by `test_legacy_document_hash_unchanged_by_locale`). `direction` is derived from the text's script, never from a claim about the learner, and it changes no block, check, media or evidence semantics. H-18b was authored against v11 and landed there on its own branch; in the union it lands inside v13 rather than opening a version, because v11 is the frozen H-21 unit contract, v12 is H-26a's syllabus intake and v13 is H-08b's authored export, and the change adds two optional properties to one existing definition — the same shape as the v10 (H-17) amendment. `contracts/rpc.v11.json` is byte-identical to its shipped snapshot. The generation-side `check.scaffolds` contract moves from the fixed Japanese triple to the bounded open list `[{kind, script?, gloss?, direction?}]` with the legacy object still read; that schema is not on the cb.rpc wire. No method, request/response field, table, column, migration, error code or job kind changes. |
| v14 | 2026-11-07 | H-53 additive amendment (contract and migration only). One method appended, `observation.record`, so the layer-1 observation `domain.record_observation` has written since CB-002 is reachable from a client — `docs/ASSESSMENT-BREADTH.md` §11 **B-2**: `self_reported`/`parent_reported` are frozen classes that no learner could produce. Request: `enrollment_id`, `objective_id`, `evidence_class` (the full six-label vocabulary; the **kernel** refuses `cold`/`hinted`/`answer_shown`/`override` with `POLICY_VIOLATION`) and optional `note` (≤ 1000 characters). Response: `evidence_id`, `evidence_class`, `revision`. Envelope: `idempotency_key`, no `expected_revision`. cb.db **v9** adds nullable `evidence.note` via migration 0009, additive with no backfill and no row rewrite. 64 RPC methods; no new error code, job kind, vocabulary value, check kind, answer kind, upload path or learner-media retention. `rpc.v13.json` and `db.v8.json` are pinned by sha256. The handler, the API registration and the UI are follow-up cards; this card ships the contract, the migration and the tests that pin them. |
| v16 | 2026-11-07 | H-120 additive amendment (contract, migration and the grading lane's router). Four methods appended to the 64 v15 methods — `practice.start`, `practice.state`, `practice.end`, `practice.cancel` — plus one optional `check_stimulus.practice` declaration, so a bounded conversation practice is a `quiz` check the learner actually talks through. 68 RPC methods. Grading is provider-free: `practice.end` hands the stored learner turns to `conversation.grade_transcript` through the same `_commit_attempt` path `attempt.submit` uses, and `attempt.submit` on a practice check is refused `POLICY_VIOLATION` / `practice_requires_practice_end`, so one chat line can never produce a verdict. cb.db **v11** adds `practice_sessions` and `practice_turns` via migration 0011, additive with no backfill; practice turns are learner-owned and never reach `pack.export` or `course.export`. No new error code, job kind, vocabulary value, answer kind, evidence class or evidence target; the new refusals ride `error.details.reason`. Authored as a v15 on `wt/h120-practice`, but v15 was already frozen by H-139 when that branch reached master, so the amendment took the next free number instead of editing a frozen document. `rpc.v15.json` and `db.v10.json` are pinned by sha256. |
| v17 | 2026-11-08 | H-106 additive amendment (contract only). The source item in `lesson.page` and `parent.blueprint.read` responses gains six optional properties: `excerpt` (≤ 20000 characters or null), `excerpt_state` (`recorded`/`missing`/`unreadable`), `content_hash` (sha256 or null), `modality` (≤ 60 or null), `licence` (≤ 200 or null) and `support_assessment` (`supported`/`partial`/`unverified`/`contradictory` or null). 68 RPC methods — no method added. Both `required` lists and `additionalProperties: false` are untouched, so every v16 payload still validates. `excerpt_state` is the typed absence: an excerpt that was never recorded or could not be read is reported as `missing`/`unreadable` with `excerpt: null`, never a fabricated excerpt. No `cb.db`, `cb.errors`, `cb.jobs` or vocabulary change. Authored as a v15 on `wt/h106-provenance`, but v15 and v16 were already frozen, so the amendment takes the next free number. `rpc.v15.json` and `rpc.v16.json` are pinned by sha256. |
| v18 | 2026-11-08 | H-185 additive amendment: a model-assessed lesson page is served with its provenance. The `lesson.page` response gains one optional property, `provenance` — an object `{outcome, independent, facts_unverified, check_enabled, warning}` or null. `outcome` is `independently_validated` or `model_assessed`; `independent` is false for a page the author model assessed itself; `check_enabled` is true for a usable check even when the pass was not independent; `warning` states the reason (same model / unidentified identity / facts unverified) and is never a validation claim. The property is optional and null for a page not authored by the generation pipeline, so every v17 payload still validates. 68 methods unchanged; no `required` list, error code, job kind, vocabulary value or `additionalProperties` move. `rpc.v17.json` is pinned by sha256. | 
| v20 | 2026-11-08 | H-194b additive amendment (contract and the one `parent.blueprint.read` handler). The `parent.blueprint.read` response gains one required array, `sections[]`, one entry per composed section: `section_id`, `objective_id`, `ordinal`, `title`, `lesson_state`, `lesson_version` and `page_hash`. `page_hash` is computed by the same function `lesson.revise` fences on (`domain._lesson_page_hash`), so the desktop can call `lesson.revise`/`lesson.regenerate` for a section that has never been revised — previously the first fine-tune of any section was unreachable, because `parent.review.read` only carries a section's identity after a revision and `tabs.*.sha256` is the rendered-text digest. `[]` for a pack-backed course. No method, request shape, error code, job kind, vocabulary value or existing required key moves, and `additionalProperties: false` stays. Found while building the H-194 UI half; numbered v20 because v19 was already frozen. `rpc.v19.json` is byte-identical and `x-supersedes` names it. |
| v21 | 2026-11-09 | GM-009 additive amendment: the game-only engagement layer reaches the wire. Two methods appended — `engagement.read` (Game header read model: `xp_total`, cosmetic `level`, `Game progress`, bounded `recent_events`; refused outside a `game` course) and `engagement.award` (one XP event for a named real action, idempotent per `(enrollment_id, action_kind, action_id)`). No existing method, request shape, response key, error code, job kind, vocabulary value or `additionalProperties` moves; `cb.db` stays v13. `rpc.v20.json` is byte-identical and `x-supersedes` names it. The remaining Game Mode method names stay frozen in `coursebook/gm_contract.py`. |
| v22 | 2026-11-09 | GM-011 additive amendment: the lesson-bound tutor reaches the wire. Two methods appended — `tutor.ask` (one bounded, cited answer for one lesson run; no tools; context excludes answer keys/checks/rubric/attempts; `state` is `answered`, `answer_withheld` or `provider_failure`; never writes an attempt, transition or evidence row) and `tutor.history` (the persisted thread read). `practice` mode reuses the existing `practice_sessions`/`practice_turns` engine and grader, so only learner turns can produce a verdict. No existing method, request shape, response key, error code, job kind, vocabulary value or `additionalProperties` moves; `cb.db` stays v13. `rpc.v21.json` is byte-identical (pinned by sha256) and `x-supersedes` names it. |
| v23 | 2026-11-09 | GM-005 additive amendment: the Parent Studio take-home pack backend reaches the wire on top of GM-011's v22. Six methods appended — `takehome.sources`, `takehome.preview`, `takehome.create`, `takehome.approve`, `takehome.export` and `takehome.read`, exactly the names and field tuples frozen in `coursebook/gm_contract.py::GM_RPC_METHODS`. A take-home pack is a rendered print artifact bound to `source_course_id` / `source_objective_id` / `source_lesson_version` / `content_hash`; it is not a course, not a `cb.pack` and not a `course.export`, and it carries no attempts, tutor turns, notes or private observations. The learner page and the parent-only answer guide are separate artifacts and approval is fenced on the exact previewed pages. No v1-v22 method, request shape, required key, error code, job kind, answer kind, verdict, evidence class or vocabulary value moves; `cb.db` moves to v14 only in storage (one unique key removed from `takehome_packs`, see the cb.db v14 delta). `rpc.v22.json` is byte-identical (sha256 `c187728add6c508d5643e42225a64766d4b887cfce58250fb45d04707b6eb956`) and `x-supersedes` names it; v22 remains GM-011's tutor delta unchanged. |
| no bump (t_d43c0dc1) | 2026-11-07 | H-130 decision: a subsystem-specific reason does not become a catalogue code when `category`/`retryable`/HTTP already fit one. `BRIEF_UNREADABLE` lands as `error.details.reason = "brief_unreadable"` under `VALIDATION_FAILED` (non-retryable, 422), and `checkpoint.reason` uses `checkpoint_serializer_failed`. `cb.errors` stays v4; no enum, catalog, `$defs` or `CONTRACT_FILES` change. The convention and the reason labels a client may key on are frozen in the section above. |

## Deliberate omissions (do not "helpfully" add these)

* No `mastered` boolean and no global progress percentage. Evidence states are distinct on purpose.
* No free-form `instructions` field in a pack or a check. Untrusted prose is content, never policy.
* No `provider`, `model` or credential field in a pack, and no `settings` passthrough.
* No `safe`/`verified` badge enum. Trust dimensions stay separate (`pack_trust_label`).
* No numeric attainment estimate field. Schedule arithmetic and attainment uncertainty are separate
  (R9); an estimate, if ever shown, is a `model_estimate` with limits, not a contract field.
* No transcript or notebook text in the pack schema, and none is obtainable by export options.
* No reference answer, rubric internals or raw grader output in any **learner** view
  (`evidence.inspect`, `evidence.disputes`, `lesson.page`, `course.get`, `check.get`,
  `course.outline`). The one scoped exception is `parent.blueprint.read`, the parent's own authoring
  view: it is addressed by `course_id`, has no binding or enrollment, and carries answer text only
  as the declared `text` of an `answer_guide` file. A pack's `answer_guide` role is never
  learner-facing (`packs.LEARNER_FACING_ROLES`).
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
* No path-addressed pack read (`pack.file.read({pack_id, pack_version, path})`). The Parent Studio
  tabs are a closed enum (`parent_guide` / `learner_pages` / `answers` / `narration` + `sources`),
  resolved server-side inside the validated manifest; a path parameter would be the one wire field
  whose value is a filesystem-shaped string, for one consumer.
* No `lesson` job kind while `cb.vocabulary` is v1. Every pack manifest references the vocabulary
  document, so an added `job_kind` value forces a `cb.pack` v2 that would reject already-installed
  `$schema` .../pack-manifest/v1 packs. Lesson generation runs as a `plan` job with
  `brief.stage = lessons` until a coordinated pack revision exists.
* No per-lesson prose edit command. Generated page text lives in the generation staging rows and
  changes by regenerating from an edited, re-approved plan; there is no approved storage decision
  for editing one page's bytes in place.
* No status-restoring recovery command for a stale source. `source.revalidate` is detection only:
  an identical re-fetch stays stale, and restoring a reviewed status honestly needs a stored prior
  status plus a review decision that `cb.db` v4 does not have.
* No second brief store. The brief is `jobs.brief_json`, read by the executor and by
  `parent.brief.get`; a `parent_briefs` table would be a competing authority.
* No `mastered`/`verified` claim on a final approval. It says which bytes the parent signed off,
  not that the course teaches well; that is what the reflection and the evidence views are for.

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

## v13 delta (H-26b) — a stated due date and weight reach the learner, and an all-aligned mapping is reviewable

This delta was authored as a v14 on `wt/harness-syllabus-read-projection` and folded into the
already-frozen v13 during the H-37 union: it is a response-only addition plus one relaxed request
constraint, so it did not justify moving the wire version. Version echo stays 13.

H-27 wired the learner syllabus review against the merged H-26a handlers and found two read/contract
gaps. Both are additive; no state machine, table, column or migration moves, and `cb.db` stays v8.

**1. `syllabus.get` serves stated assessment fields.** `parse_document` built `due`, `weight` and
`weight_unit` per assessment, but `_store_parse` persisted only the title item, and a
`"<title> (due)"` row was appended only when the due date was *unknown*. A file that stated
`Due: 2026-09-01` and `5%` therefore served neither. The fix is at parse time, not read time: the
single `assessment` item now carries an optional `fields` object in `syllabus_items.value_json`.

```json
"fields": {
  "due":    {"value": "2026-09-01", "state": "extracted", "anchors": [{"block_id": "blk…", "quote": "Due: 2026-09-01"}], "derivation": "explicit"},
  "weight": {"value": 5, "state": "extracted", "anchors": [{"block_id": "blk…", "quote": "5%"}], "derivation": "explicit"},
  "weight_unit": "percent"
}
```

`due` and `weight` reuse the item shape (`value`/`state`/`anchors`/`derivation`, optional
`candidates`); `weight_unit` is `percent`, `points` or `unknown`. An unknown field keeps
`state: "unknown"` with no value and no anchors, and the `"<title> (due)"` placeholder row is still
emitted exactly as before, so consumers of the pre-amendment shape are unaffected. The item `kind`
stays `assessment`; the
cb.db v8 enum is closed and unchanged. Revisions parsed before this amendment carry no `fields`;
consumers key off its presence and nothing is backfilled.

**2. An all-aligned mapping can be reviewed.** `syllabus.alignment.review` required
`decisions` `minItems: 1`, and every action targeted a non-aligned state. A mapping the
deterministic aligner resolved entirely to `aligned` had no legal decision, so `reviewed_revision`
could never be set and `plan.approve` refused `SYLLABUS_UNREVIEWED` forever. This amendment relaxes
`decisions` to `minItems: 0`, where an empty array means *the learner reviewed the mapping and
accepted every row as aligned*. The claim is verified by the backend, not trusted: after the
`alignment_revision` fence, an empty array is refused with `VALIDATION_FAILED` (detail:
`alignment_revision`, `conflict`, `partial`, `unmatched`, `stale` counts) unless this course and
syllabus revision have no non-stale `partial`/`unmatched`/`conflict`/`stale` row and no stale row at
all. `unmatched` and `partial` do not block `reviewed_revision` on their own, so without the guard a
caller could mark a mapping reviewed without acknowledging a single row. No new action value and no
new error code: the guard is one branch, and it is the only relaxed request constraint in v13.

**Not in this delta.** No new method, error code, job kind, vocabulary value, table, column or
migration; no removal or renumbering of the `(due)` placeholder row; no second parser in
`syllabus.get`; no UI change (Vellum re-points H-27's adapter to `fields`).

## v14 delta (H-53) — an observation is reachable from a client

The kernel has recorded observations since CB-002 (`cde58c6`):
`coursebook.domain.record_observation(enrollment_id, objective_id, *, evidence_class,
kind="observation", note=None)` writes exactly one layer-1 `evidence` row and refuses anything but
`self_reported`/`parent_reported`. No client could reach it. `observation.record` appeared in no
`cb.rpc` snapshot, `coursebook/api.py` registered no handler, `desktop/plugin.js` had zero hits, and
`evidence` had no `note` column — so the accepted `note=` was silently dropped. That is **B-2** in
`docs/ASSESSMENT-BREADTH.md` §11: two declared, frozen evidence classes that no learner could
produce.

v14 appends exactly one method. Every v1-v13 method name and payload is preserved unchanged, the
method enum grows from 63 to 64, and no error code, job kind, vocabulary value, check kind, answer
kind, upload path or learner-media retention is added. `contracts/rpc.v13.json` is byte-identical to
its shipped snapshot (pinned by sha256).

| Method | Request | Envelope | Response | What it may never do |
|---|---|---|---|---|
| `observation.record` | `enrollment_id`, `objective_id`, `evidence_class`, `note?` (≤ 1000 chars) | `idempotency_key` | `evidence_id`, `evidence_class`, `revision` | write an attempt, a check state, a transition or a verdict; bump a revision; store an upload; make an observation independent evidence |

**`evidence_class` is the full six-label vocabulary on the wire.** The schema accepts `cold`,
`hinted`, `answer_shown`, `self_reported`, `parent_reported` and `override`; the *kernel* refuses
four of them with `POLICY_VIOLATION`. Closure is a policy judgement that a client must not have to
reverse-engineer from a schema, and a narrower enum would put the kernel's rule in the wrong
authority. No value is added to `cb.vocabulary`.

**The note is stored, not swallowed.** `cb.db` **v9** adds nullable `evidence.note` (TEXT) via
`coursebook/migrations/0009_evidence_note.sql`: additive, forward-only, no backfill and no row
rewrite. Every pre-v9 row keeps `note` NULL, which means "no prose was stored", not "the writer sent
an empty string". The migration *documented* the alternative — refusing `note` on the wire — and
rejected it: a parameter that the wire accepts and the kernel discards is the defect being repaired,
and a bounded prose field on an evidence row is ordinary storage, not a new construct.

**Idempotency lives in the envelope, and there is no revision fence.** The card that authorised this
delta wrote the request as `{enrollment_id, objective_id, evidence_class, note?, idempotency_key?}`.
`idempotency_key` is not a payload field in any `cb.rpc` method: it is an envelope property that
`coursebook.domain` handlers read off the request, and a payload copy would be unenforced. v14
therefore **requires** it at the envelope root, exactly like `parent.reflection.record`: a double
click must not mint two evidence rows. It deliberately requires no `expected_revision` — recording an
observation cannot move the enrollment aggregate, so a stale-revision refusal would invent a fence
that protects nothing. The response echoes the enrollment revision it read.

**Reconciliation with `docs/ASSESSMENT-BREADTH.md` §9.** That section lists `observation.record`
among the methods 0.1.0 may not add. The supervisor's decision, recorded there as a dated paragraph
on 2026-11-07, is that §11 B-2 wins: the §9 bullet was a drafting over-reach that grouped the B-2
repair with three construct widenings (`artifact.submit`, `code.run`, `performance.submit`). This
method adds no check kind, no answer kind, no evidence-class value, no learner upload and no
learner-media retention; it exposes an existing kernel call under existing vocabulary. The other
three stay frozen and unauthorised.

**Regression guard.**
`tests/test_contracts.py::V14AmendmentTest` fails if the method, its request/response shapes, the
bounded `note`, the envelope fence, the `evidence.note` column, the migration or the version links
disappear. The handler and its behavioural tests are Cinder's follow-up card, and the control that
calls it is Vellum's; neither is in this delta.

**Not in this delta.** No handler, no `coursebook/api.py` registration, no `desktop/plugin.js`
change, no check kind or answer kind, no upload path, no `artifact.submit`/`code.run`/
`performance.submit`. An observation is never independent evidence, and
`docs/CHECKLIST-CONFIRMATION.md` §3.2/§6 is unchanged in substance: a checklist that *is* an
objective's check still closes through `attempt.submit` `selection`.

## cb.db v10 delta (H-124) — a lost teaching snapshot is recorded, not swallowed

`hooks.post_llm_call` is the only writer of a `lesson_segments` row with `kind='teaching'` — the
durable record the Textbook and Guided views render. It wrapped
`turn.record_assistant_snapshot` in `except Exception: return None`, so a failed write removed a
teaching turn from the lesson page while the chat transcript still showed it, with no marker
anywhere (H-114 F3, `docs/SILENT-FAILURES.md`).

The hook is still **never the gate**: the turn is not failed, and a snapshot write is still an
observer. What changes is that the loss is now durable and readable.

| Change | Where | What it may never do |
|---|---|---|
| `hook_errors` table | `coursebook/migrations/0010_hook_errors.sql` | become a general error log, lesson text, evidence or a grade |
| one retry, then a row | `coursebook/hooks.py` `post_llm_call` | raise into the host turn, or retry more than once |
| `snapshot_failures` on the binding | `coursebook/domain.py` `binding.get` | claim `0` losses when the count could not be read (`null` means unknown) |

**Storage.** `cb.db` **v10** is v9 plus exactly one table, `hook_errors`
(`id`, `kind`, `session_id`, `lesson_run_id`, `nonce`, `detail`, `attempts`, `created_at`), with
indexes on `lesson_run_id` and `created_at`. `kind` is checked against exactly one value,
`snapshot_write_failed`. `lesson_run_id` is nullable and references `lesson_runs.id`: a failure
whose binding could not be read is still recorded rather than dropped. The migration is additive,
forward-only, with no backfill — a pre-v10 database recorded no hook failures, which is true
because the code that could have written them swallowed the error.

**No `cb.rpc` version.** The `binding` object in `binding.get`'s response is an open object (the
same deliberate choice that let `lesson_run_id`/`objective_id` land without a bump in v5), so the
additive `snapshot_failures: {recorded, last_at}` field needs no rpc version. `recorded` is `null`,
never `0`, when the count could not be read: "unknown" and "no loss" must not look alike.

**Recovery.** One immediate retry runs before a loss is declared, so a transient lock recovers in
place and leaves no row. A row therefore means two attempts failed, and `attempts` records that
count. When even the failure row cannot be written (a read-only or full store) the hook logs at
ERROR with `coursebook_event="snapshot_write_failed"` and `recorded=False` — the one case where the
evidence genuinely could not be persisted, and it is stated rather than implied.

**Regression guard.** `tests/test_hook_snapshot_loss.py` forces the snapshot write to raise and
asserts the turn still returns `None`, the loss is attributed to the run, `binding.get` reports it,
a transient failure recovers without a row, and a normal turn still writes exactly one segment.
`tests/test_contracts.py::DbV10AmendmentTest` pins the additive schema and the open binding object.

## v15 delta (H-139) — a waiting pane can read the durable job stage

The Pane says "may take several minutes" and then shows nothing, so a long generation is
indistinguishable from breakage (H-117, `docs/SILENT-FAILURES.md` F9/F18). Every fact the pane
needs was already durable — `jobs.state`, `jobs.progress_json`, `jobs.created_at`/`updated_at`
and the `usage_events` rows whose `operation_id` is the job id — but no single read exposed it.
**The wire does not gain a method.** `jobs.get` already returns the job; `cb.jobs` v5 adds one
required object to it:

| Field | Source (all durable) |
|---|---|
| `activity.stage` | the last checkpointed stage (`progress_json.stage`), else the queued brief's `stage`, else `null` |
| `activity.stage_source` | `checkpoint` / `brief` / `queued` / `none` — which of those answered |
| `activity.steps_done`, `steps_total` | `progress_json`; `steps_total` stays `null` until the backend knows it |
| `activity.elapsed_seconds` + `elapsed_basis` | `created_at` to now while live; `created_at` to `updated_at` once the row rests |
| `activity.can_cancel`, `can_retry`, `terminal` | the frozen `cb.jobs` transition table, not a UI guess |
| `activity.message`, `last_progress_at` | the checkpoint message and the instant it was written |
| `activity.usage` | `usage_events` for this `operation_id`: calls, the four token counts, `cost_usd`, `unknown_cost_calls`, artifacts, providers, models |

**No percentage.** There is no `percent` field and no computed rate: `steps_done`/`steps_total`
are the real counts, and the total is `null` when the plan is not known. A client that wants a
bar must handle `steps_total: null` honestly.

**`readable` and the named failure.** `activity.readable` is `false` only when a durable JSON
column for the row cannot be parsed; `stage` and both step counts are then `null` (never `0`,
which would read as "not started"). `jobs.get` is stricter than `jobs.list`: an unreadable
`progress_json`/`brief_json` raises `INTERNAL_ERROR` with `details.reason =
"job_progress_unreadable"` and `details.column` naming the column, and an unreadable store raises
`details.reason = "job_store_unreadable"`. `jobs.list` keeps its shape and marks the single row
`readable: false`, because one corrupt job must not blank the whole list.

**No storage change.** `cb.db` stays **v10**: activity is a read of existing columns and rows.

**Wire refresh.** `jobs.list`'s item `$ref` moves from `cb.jobs/v4#/job` to `cb.jobs/v5#/job`,
which is why `cb.rpc` is **v15**. v15 is v14 byte-for-byte apart from `$id`, `x-contract-version`,
`x-supersedes`, the description and that one `$ref`; the method enum, every request and every
other response field are unchanged. `cb.errors` stays **v4**. The method count does not move.

**Tests.** `tests/test_job_progress.py` covers every stage (`plan`, `unit_sections`, `lessons`,
`syllabus_parse`, a checkpointed stage), a finished job, a provider failure, an interrupted job,
a cancelled job, idempotent cancellation, backend-sourced usage (including unknown token/cost
fields) and both named read failures. `tests/test_contracts.py::V15AmendmentTest` pins the
superseded v14 bytes and the additive v5 job shape.

## v16 delta (H-120) — a bounded conversation practice, graded from its transcript

A conversation practice is a **check property**, not a lesson kind (`docs/CONVERSATION-PRACTICE.md`
§2): a `quiz` check whose stimulus carries a stored `stimulus.practice` declaration and whose
`checks.reference_json` declares `kind = "conversation"`. v16 appends four commands to the 64 v15
methods — 68 RPC methods — plus one optional property on `check_stimulus`. Every v1-v15 method name
and every v1-v15 request/response payload is preserved unchanged, including v15's `cb.jobs` v5
reference refresh.

| Method | Request (closed) | Envelope | Response | What it may never do |
|---|---|---|---|---|
| `practice.start` | `enrollment_id`, `objective_id` | `expected_revision` | `session_id`, `check_id`, `check_version`, `state`, `revision`, `session_revision`, `turns{min,max}`, `transcript[]` | start a second session for the same run and check, or start on a check that is not an open, audited practice |
| `practice.state` | `enrollment_id`, `objective_id` | none — a read | `session_id`, `check_id`, `check_version`, `state`, `learner_turns`, `remaining`, `awaiting_tutor`, `transcript[]`, `attempt_id`, `verdict`, `criteria[]` | report `state: none` as an error, or invent a verdict for an ungraded session |
| `practice.end` | `enrollment_id`, `check_id`, `check_version`, `attempt_nonce` | `expected_revision` | `attempt_id`, `verdict`, `evidence_class`, `criteria[]`, `next_action`, `revision`, `transcript_sha256`, `learner_turns`, `session_revision` | grade a cancelled or detached session; mint a second attempt for the same `attempt_nonce` |
| `practice.cancel` | `enrollment_id`, `check_id` | `expected_revision` | `session_id`, `state`, `revision`, `session_revision` | delete a turn, or cancel a session that is already graded |

**Grading is provider-free.** `practice.end` reads the stored *learner* turns and the declared
targets/turn range, and hands them to `coursebook.conversation.grade_transcript` through the same
`domain._commit_attempt` path `attempt.submit` uses. The reference kind is `conversation`, which is
routed in `grading.grade` **before** the open lane and never consults `configure_aux_grader`
(`docs/GRADING-LANES.md` §2.1). Tutor text is never inspected, so nothing the model says can produce
a pass. A reference the grader cannot read raises, and the caller persists `needs_retry` and
advances nothing.

**One chat line is not a verdict.** `attempt.submit` on a practice check is refused
`POLICY_VIOLATION` / `error.details.reason = "practice_requires_practice_end"`, so a verdict can only
come from a bounded session that was actually held. The other practice refusals ride the same
channel (`practice_not_a_practice_check`, `practice_not_bound`, `practice_not_open`,
`practice_already_graded`, `practice_not_available_for_recipe`, `practice_malformed_declaration`);
no error code is added to `cb.errors`, which stays **v4**.

**No new vocabulary.** No answer kind, verdict, evidence class, evidence target, next action or job
kind is added, and `cb.jobs` stays **v5**: the four methods write no job and open no lifecycle —
turns arrive through the existing chat hook. No percentage, score or mastery claim exists on the
wire.

**Why v16 and not v15.** The amendment was authored as a v15 on `wt/h120-practice`. By the time that
branch reached current master, **v15 was already frozen by H-139** (the job `activity` read model),
so `contracts/rpc.v15.json` is immutable history and the amendment took the next free number.
`rpc.v15.json` is byte-identical to its shipped bytes (pinned by sha256); `x-supersedes` names
`.../rpc/v15`. If a reader of this document is looking for "the v15 practice delta", this is it.

**Regression guard.** `tests/test_contracts.py::V16AmendmentTest` fails if a v15 method or payload
moves, if a fifth method appears, if `check_stimulus` gains anything but `practice`, if the echo
drifts from 16, if the envelope fence is dropped, or if the two practice tables or migration 0011
disappear. `tests/test_conversation_practice.py` drives the whole session through the real dispatcher
against a migrated database.

## cb.db v11 delta (H-120) — a practice session and its transcript

`cb.db` **v11** is v10 plus exactly two tables, created by
`coursebook/migrations/0011_conversation_practice.sql`. Additive, forward-only, no backfill: a
pre-v11 database had no practice session, which is true because nothing could create one.

| Table | Shape | What it may never do |
|---|---|---|
| `practice_sessions` | `id`, `enrollment_id`, `objective_id`, `check_id`, `check_version`, `lesson_run_id`, `state` (`active`/`graded`/`cancelled`/`abandoned`), nullable `attempt_id`, `revision`, `started_at`, nullable `ended_at`, nullable `end_reason` | store a "turn limit reached" flag (it is derived from the learner turns), or hold an `attempt_id` that `practice.end` did not set |
| `practice_turns` | `id`, `session_id`, `ordinal`, `speaker` (`learner`/`tutor`), `text`, nullable `nonce`, `created_at` | be edited or deleted; a unique `(session_id, ordinal)` and a unique `(session_id, nonce)` keep a retried hook from double-appending a learner turn |

**Learner-owned data.** Practice turns are the learner's own words. `pack.export` and
`course.export` never include them, and `lesson_segments` is not a writer of them — a practice is
not teaching prose and must not appear on the Textbook page as a second copy of the conversation.
A detached binding or a fresh lesson run marks an active session `abandoned` in the same
transaction, so a detached chat can never grade a practice.

**No `cb.rpc` consequence beyond the four methods above.** `cb.errors` stays v4 and `cb.jobs` stays
v5. No v10 table, column, index or unique key is dropped, retyped or rewritten.

**Regression guard.** `tests/test_contracts.py::V16AmendmentTest` pins the two added tables, every
v10 column and index, the migration's forward-only statements, and the byte-identity of
`db.v10.json`. `tests/test_conversation_practice.py` runs the migration against a real database.

## v17 delta (H-106) — six optional source-provenance fields on the two source reads

A source item already carried `source_id`, `title`, `url`, `publisher`, `source_type`,
`support_status`, `published_at` and `fetched_at`. That was enough to name a source and not enough
to show what was actually read from it: the provenance pane has to display the exact excerpt behind
a claim, its hash, its medium and its licence, and it has to say honestly when there is no excerpt.
v17 adds six **optional** properties to the source item inside exactly two responses —
`lesson.page` and `parent.blueprint.read`. No method is appended or removed (68 before, 68 after),
no required list changes, `additionalProperties: false` stays, and no request payload moves.

| Field | Type | Meaning |
|---|---|---|
| `excerpt` | string ≤ 20000 or null | The exact passage the plan or lesson relies on, as recorded when the source was read. Absent or null when no excerpt was recorded. |
| `excerpt_state` | `recorded` / `missing` / `unreadable` | The typed absence: whether an excerpt was stored, was never captured, or existed but could not be read. |
| `content_hash` | sha256 or null | Hash of the excerpted bytes, so a later re-read can prove the text the verdict was built on has not changed. |
| `modality` | string ≤ 60 or null | How the source is carried — `text`, `audio`, `video`, `image`, `dataset`, and the like. Free-form and bounded; the vocabulary is not closed by this contract. |
| `licence` | string ≤ 200 or null | The licence or terms statement recorded for the source. Null means the licence was not recorded, never that the source is unlicensed. |
| `support_assessment` | `supported` / `partial` / `unverified` / `contradictory` or null | The model's own assessment of how far this source supports the claim it is attached to. Null means no assessment was made. |

**The typed absence rule.** `excerpt_state` is what a missing or unreadable excerpt reports. An
excerpt that was never recorded is `missing`; one that existed but could not be read is
`unreadable`; either is paired with `excerpt: null`. A client must never render an empty string, a
placeholder sentence or a reconstructed passage as though it were the source's own words — the
contract has no default that would let it, and **never a fabricated excerpt** is the rule the pane
is tested against. `excerpt_state` itself is optional only so a v16 payload still validates; a
producer that knows the state should always send it.

**Additivity.** Every one of the six is optional, so any v16 payload validates unchanged against
v17 and the only wire-visible bump is the version echo (17 in both response envelopes, the request
envelope and `health.get`). `support_assessment` is distinct from `support_status`: the latter is
the stored classification the kernel already gates on, the former is the model's own word about
this source and this claim, and neither is derived from the other. No `cb.db` table or column, no
`cb.errors` code, no `cb.jobs` kind, no vocabulary value and no answer/evidence enum moves.

**Why v17 and not v16.** The pane was authored as a v15 contract edit on `wt/h106-provenance`. By
the time it reached integration both v15 (H-139) and v16 (H-120) were frozen on master, so the
amendment takes the next free number: `rpc.v15.json` and `rpc.v16.json` are byte-identical to their
shipped bytes (pinned by sha256) and `x-supersedes` names `.../rpc/v16`. The H-106 branch's own
`contracts/rpc.v15.json` hunk is dropped, not merged.

**One writer.** The contract is Atlas's lane. `desktop/plugin.js`, `coursebook/domain.py` and
`coursebook/sources.py` fill these fields on the H-106 branch; a branch that edits a frozen
contract file must not merge.

**Regression guard.** `tests/test_contracts.py::V17AmendmentTest` fails if a v16 method or payload
moves, if either source item gains anything but the six fields, if a field's bounds or enum drift,
if any `required` list changes, if the echo drifts from 17, or if `rpc.v15.json` / `rpc.v16.json`
stop being byte-identical history. `V15AmendmentTest`, `V16AmendmentTest` and the carried-over
v1-v14 tests compare through `_without_v17_source_fields`, so the additive fields are removed
before the older snapshot comparison rather than the older assertion being weakened.

## v19 delta (H-194) — fine-tune a generated course without regenerating it

`cb.rpc` v19 appends five methods and widens one existing response enum. No existing method,
required key, `additionalProperties`, error code, job kind, answer kind, verdict, evidence class or
vocabulary value moves; v18 stays byte-identical on disk and `x-supersedes` names it.

| Method | Kind | Request (required) | What it does |
|---|---|---|---|
| `plan.edit` | mutation | `enrollment_id`, `plan_id`, `expected_plan_hash` | Reorder objectives (`reorder`, a permutation of objective ids) and/or edit `title`/`evidence_target`/`criteria` on an **approved** plan. Writes ordinals only, re-points every `gen_plan_sections.objective_refs_json` so a section keeps its own objective, and records one `plan_revisions` row. A reorder across units that goes backwards is refused with `reason: prerequisite_order_conflict` and nothing is written. |
| `plan.undo` | mutation | `enrollment_id`, `plan_id`, `expected_plan_hash` | Reverts the last un-reverted `plan_revisions` row (or the named `revision_id`) if the plan still matches that revision's `after` snapshot; otherwise `reason: revision_conflict`. The undo is itself a `plan_revisions` row. |
| `lesson.revise` | mutation | `enrollment_id`, `plan_id`, `section_id`, `expected_page_hash` | Writes a new immutable `gen_lessons` row at the next version with state `needs_review`; the previous row is kept and attempts are untouched. Only that section's validation is stale. If attempts exist, `confirm_evidence_consequence: true` is required or the call is refused with `reason: evidence_consequence_confirmation_required`. |
| `lesson.regenerate` | mutation | `enrollment_id`, `plan_id`, `section_id` | Queues a normal `plan`-kind job whose brief is `{stage:'lessons', section_id, regenerate:true, unit_ordinal}` and returns a one-section cost preflight. The executor authors only that section at its next version. It never queues a plan-wide replan. |
| `parent.review.read` | read | `course_id` | The pending review diff: `plan_revisions`, `lesson_revisions`, current `content_hash`, active approval and the export gate. `parent.final.approve` remains the only approval writer. |

**Approval and export.** A fine-tune supersedes the active `final_approvals` row
(`plan_edited` / `content_changed`). `parent.final.approve` still binds `plan_hash` + `content_hash`;
on success it marks the covered revision rows `approved`, promotes the edited `gen_lessons` row to
`parent_approved` (never `validated`), and the export gates (`parent.export`, `course.export*`)
remain fail-closed until the active approval hash equals the recomputed content hash. A
`needs_review` section is served by `lesson.page` as text with `check_enabled: false`.

**`lesson.page` provenance outcome** gains two enum values: `needs_review` (authored edit awaiting
review, check disabled) and `parent_approved` (human-approved authored edit, still not independent
validation). This is the only change to an existing payload shape, and it is an enum widening inside
a new contract version.

**Mutation fences.** `plan.edit`, `plan.undo` and `lesson.revise` require `idempotency_key` and
`expected_revision`; `lesson.regenerate` requires `idempotency_key`. Idempotent replay, key/payload
conflict and stale-revision conflict are the existing `idempotency_keys` and enrollment-revision
mechanisms, not a second authority.

## cb.db v12 delta (H-194) — two fine-tune ledgers

`cb.db` v12 adds exactly two tables, created by `0012_fine_tune_revisions.sql`. Additive only: no
v11 table, column, index or unique key is dropped or retyped; there is no backfill.

* `plan_revisions` — one structural change to an approved plan. `before_json` / `after_json` are
  full objective snapshots (id, ordinal, title, evidence target, criteria, version);
  `state` is `needs_review` -> `approved` (when `parent.final.approve` covers the new bytes) or
  `reverted`; `reverts_revision_id` names the revision an undo reversed; `approval_id` names the
  approval that covered it.
* `lesson_revisions` — one authored edit to a single generated section. `from_lesson_id` and
  `lesson_id` are both `gen_lessons` rows (the previous version stays), `diff_json` is the review
  diff, `evidence_attempts` is the count the author was shown and
  `confirmed_evidence_consequence` records their confirmation; `unique(lesson_id)`.

Neither table is read by grading. An attempt keeps pointing at the check id it answered; an edit
never rewrites an attempt, transition or evidence row. Regression guard:
`tests/test_h194_fine_tune.py` (reorder, unit-edge refusal, undo, single-section revision,
evidence-consequence confirmation, stale-approval export refusal, re-approve and one-section
regeneration), `tests/test_kernel_schema.py` for the table/unique/index inventory, and
`tests/test_contracts.py` for the v19/v12 delta.

## v20 delta (H-194b) — a section's identity and page digest are readable before any revision exists

`cb.rpc` v20 is v19 with **one** additive change: the `parent.blueprint.read` response gains one
required array, `sections`. No method is added, moved or retyped; no request shape, error code, job
kind, answer kind, verdict, evidence class or vocabulary value moves; `cb.db`, `cb.errors`,
`cb.jobs`, `cb.pack` and `cb.projection` are untouched. `rpc.v19.json` stays byte-identical on disk
(sha256 `0ebc9efb2f1c3bc2dd6b3a756bc7ceab3a0502c6d0eef34031a1edd9a2b6d5f5`) and `x-supersedes`
names `.../rpc/v19`.

**The defect this closes.** `lesson.revise` requires `section_id` **and** `expected_page_hash`, and
`lesson.regenerate` requires `section_id`, but v19 served neither for a section that had never been
revised: `parent.blueprint.read` had no `sections` array, `tabs.*.blueprint_file.sha256` is the
digest of the *rendered text* rather than of the stored `gen_lessons.page_json`, `parent.review.read`
carries `section_id`/`page_hash_after` only for a section that was already revised, and `lesson.page`
serves a projected document whose digest the client must not recompute. The first fine-tune of any
section was therefore unreachable from the desktop.

| Field | Type | Meaning |
|---|---|---|
| `sections` | array, ≤ 100 | One entry per composed section, in `gen_plan_sections.ordinal` order. `[]` for a pack-backed course, which is composed from the pack and has no authored sections. |
| `sections[].section_id` | identifier | The `gen_plan_sections.id`, exactly the value `lesson.revise`/`lesson.regenerate` take. |
| `sections[].objective_id` | identifier | The objective the section is bound to (`objective_refs_json` first ordinal), falling back to the plan id as the composed section already does. |
| `sections[].ordinal` | integer 1–10000 | `gen_plan_sections.ordinal`. |
| `sections[].title` | string 1–300 | The title the blueprint serves, which after an authored edit is the page's `section_title`. |
| `sections[].lesson_state` | string ≤ 40 or null | `gen_lessons.state`; null when no lesson row exists yet. |
| `sections[].lesson_version` | integer 1–10000 or null | `gen_lessons.version`; null when no lesson row exists yet. |
| `sections[].page_hash` | sha256 or null | **The fence value.** The digest `lesson.revise` compares `expected_page_hash` against, computed by the same function (`domain._lesson_page_hash`, sha256 over the canonical page JSON). Null exactly when the section has no usable authored page, which is also the case `lesson.revise` refuses; `lesson.regenerate` is the way to author it. |

**Why the digest cannot drift.** `parent_authoring.sections()` already computed the digest with
`packs.canonical_json_bytes`, and `domain._lesson_page_hash` uses `domain._json_dump`; both emit
`json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False)`, i.e. identical UTF-8
bytes. The handler does not trust that coincidence: `_blueprint_section_identity` calls
`_lesson_page_hash` itself, so the served value is the fence value by construction.

**Required, not optional.** `sections` is appended to the response `required` list. A read whose
stated purpose is to carry the section fence must not be able to omit it; `sections: []` is the
honest answer for a course with no authored sections. No existing required key, property type or
`additionalProperties: false` moves, so every valid v19 response stays valid after the one key is
added.

Regression guard: `tests/test_h194_fine_tune.py` (`BlueprintSectionIdentityTest` — one row per
composed section with the digest, and `lesson.revise` accepting that digest unchanged with no test
helper recomputing it) and `tests/test_contracts.py` for the v20 delta.

## v21 delta (GM-009) — the game-only engagement layer reaches the wire

`cb.rpc` v21 is v20 with **two appended methods**, `engagement.read` and `engagement.award`, and
nothing else. No existing method, request shape, response key, error code, job kind, answer kind,
verdict, evidence class, vocabulary value or `additionalProperties` moves; `cb.db` stays v13,
`cb.errors` v4, `cb.jobs` v5, `cb.pack` v1 and `cb.projection` v1. `rpc.v20.json` stays
byte-identical on disk (sha256 `81cf882fb6f9dddc5caf7706b9dfe23d1ace2d4dea16c11e4e0281cbdf150f07`)
and `x-supersedes` names `.../rpc/v20`. The remaining Game Mode names stay frozen in
`coursebook/gm_contract.py` and land with their own handlers.

**`engagement.read`** — the Game header read model, and the only surface that may return XP. Request
`{course_id, enrollment_id}`; response `{xp_total, level, progress, recent_events}`. It is refused
with `VALIDATION_FAILED` (`reason: engagement_is_game_only`) outside a `game` course, so a Textbook
or legacy `NULL` course has no engagement surface at all. `level` is a cosmetic object
(`level`, `title`, `xp_into_level`, `xp_for_next_level`, `is_cosmetic: true`) derived from the XP
total; `progress` is `{label: "Game progress", is_play_progress: true, assigned_steps,
completed_steps, feedback_visible}` — counts of assigned objectives and objectives with a committed
pass, never a mastery percentage. `recent_events` is a bounded (≤20) preview of the ledger, empty
while `Game feedback` is off. No key named mastery, proficiency, grade, score, passed, rating or
stars exists anywhere in the payload.

**`engagement.award`** — append one XP event. Request
`{course_id, enrollment_id, action_kind, action_id}`; response `{awarded, points, xp_total, level}`.
It is idempotent on the durable unique key `(enrollment_id, action_kind, action_id)`: a replay
answers `awarded: false, points: 0` and leaves the total unchanged, and the standard envelope
`idempotency_key` replays the stored result while a different payload under the same key is
`IDEMPOTENCY_CONFLICT`. It has **no** `expected_revision`: an append-only play event cannot move an
aggregate revision, so it must not pretend to fence one.

`action_kind` is one of `lesson_step`, `check_submitted`, `review`, `homework_completed`,
`returned`, and `action_id` must name a real durable row this enrollment produced:

| `action_kind` | What `action_id` must be | Points |
|---|---|---|
| `lesson_step` | a `lesson_segments.id` whose `lesson_runs.enrollment_id` is this enrollment | 5 |
| `check_submitted` | a committed `attempts.id` for this enrollment | 20 |
| `review` | a layer-2 `evidence.id` of kind `delayed_retrieval` for this enrollment | 15 |
| `homework_completed` | a `homework_tasks.id` in `self_reported_done` or `parent_reported_done` | 25 |
| `returned` | a `lesson_runs.id` with an earlier run for the same enrollment at least a day before | 10 |

A page open, a click and an idle timer have no row in any of those tables, so they are refused with
`VALIDATION_FAILED` (`reason: not_a_real_action`); the wire enum does not even name them.

**Exposure is a refusal, not a convention.** No evidence, parent, pack, course-export or print read
joins `game_engagement`, and `engagement.read`/`engagement.award` never write an attempt, a
transition, an objective state or an evidence row. `Game feedback` is the declared plugin setting
`game_feedback` (default true); it hides `recent_events` and sets `progress.feedback_visible=false`
without deleting a row. Switching a course to Textbook retains the ledger and hides the surface;
switching back restores the same total.

Regression guard: `tests/test_game_engagement.py` (the seven card-named tests plus the level and
per-action point checks) and `tests/test_contracts.py` for the v21 delta.

## v22 delta (GM-011) — the lesson-bound tutor

`cb.rpc` v22 is v21 with **two appended methods**, `tutor.ask` and `tutor.history`, and nothing
else. No existing method, request shape, response key, error code, job kind, answer kind, verdict,
evidence class, vocabulary value or `additionalProperties` moves; `cb.db` stays v13, `cb.errors` v4,
`cb.jobs` v5, `cb.pack` v1 and `cb.projection` v1. `rpc.v21.json` stays byte-identical on disk
(sha256 `eb17550859d4bbc42541837d32ee17e4594901d4065a17a1f75b6488c2d17282`) and `x-supersedes`
names `.../rpc/v21`.

**One thread per lesson run.** `tutor_threads` is unique on `lesson_run_id` (migration 0013), never
a host chat session id and never global. A changed lesson or a fresh run is a new thread; the old
thread stays readable. `tutor_turns` is append-only with `role` in `learner`/`tutor`.

**`tutor.ask`** — request `{course_id, enrollment_id, objective_id, lesson_run_id, question, mode}`
plus optional `block_id`, `selected_text`; envelope `idempotency_key` **and** `expected_revision`
(the enrollment aggregate, the same fence every learner-facing mutation uses). Response
`{turn, thread_id, citations, assist, state}`.

- **Bounded context.** The envelope is built from the served lesson document (block id, role,
  headline, short, deep, source ids), the authored glossary, the objective title/evidence target,
  the selected block and at most six recent learner turns. It is capped by block count, characters
  per block and total characters. It is built from the served document, not by deleting keys from
  the authored page; the one redaction is the worked example's trailing `Answer:` line, removed
  from the block body after projection so the served content-hash block id is preserved. So
  `checks.reference_json`, `checks.rubric_json`, `stimulus.choices`, `accepted_answers` and
  `worked_example.answer` cannot reach the model, and every block id in the envelope is an id
  `lesson.page` serves.
- **No tools.** The request is a JSON answer + citation ids; the module exposes `TOOLS = ()` and
  never imports a shell, browser, filesystem, network or authoring seam.
- **Citations resolve or are omitted.** The model returns ids; the handler resolves each against
  the blocks and course sources actually in context, drops unknown ids, de-duplicates and caps at
  eight. A citation carries `{kind: block|source, id, label}` and nothing else.
- **No learning-state write.** A turn is not an attempt, a transition or evidence. The command
  writes `tutor_threads`/`tutor_turns` and bumps the enrollment revision; it writes no `attempts`,
  `evidence` or `transitions` row, and it cannot grade.
- **Answer-key guard while a check is open.** The reference is never sent, and the deterministic
  guard also checks the returned answer against the stored reference strings (and the practice
  match clauses). A match replaces the answer with a fixed safe message, drops citations and
  returns `state: "answer_withheld"`; the leaky prose is not persisted.
- **Hint path.** `assist` projects `checks.stimulus_json.assistance_policy` as
  `{kind: "hint_request", label: "Hint", available, policy, evidence_class: "hinted", layer: 1}`.
  It records nothing: the UI sends the learner through the existing `lesson.assist` command,
  which owns the layer-1 row and its revision fence.
- **Provider failure is named.** No bound host model is `HOST_UNAVAILABLE`; a bound model whose
  call fails is `state: "provider_failure"` with `turn: null` and nothing persisted. Retry is a
  new command, never a fabricated answer.
- **Practice mode.** `mode: "practice"` requires an active `practice_sessions` row for the lesson
  run. It appends the learner turn and the in-character tutor reply to `practice_turns` (the
  existing engine) and mirrors both into the rail thread. Only learner turns reach
  `conversation.grade_transcript`; tutor prose is never graded, so a tutor turn containing every
  target expression still cannot produce a pass. `practice.start`/`practice.end` remain the only
  session boundary.

**`tutor.history`** — request `{course_id, enrollment_id, objective_id, lesson_run_id}`; response
`{thread_id, turns, context}`. Read-only, no revision bump. `context` is the compact projection
(objective, block ids, source ids, `check_open`, glossary terms) and never a hidden key. A run with
no thread answers `thread_id: null, turns: []` with a valid context.

**Excluded from export.** `tutor_turns` is learner-owned history. `pack.export`, `course.export`,
print packs and Parent reads never include it; the export regression test plants a unique marker in
a tutor turn and proves it is absent from the archive bytes and file names.

**Regression guard.** `tests/test_tutor.py` — the seven card-named tests plus the hint/withheld
path — drives the real dispatcher against a migrated database and a scripted host LLM.
`tests/test_contracts.py::V22AmendmentTest` pins the append-only enum, the unchanged v21 payloads,
the absence of verdict/score keys and the byte-identity of `rpc.v21.json`. `scripts/gm011_transcript.py`
writes `docs/gm011-tutor-transcript.md`, a real-backend transcript with a cited answer, a withheld
answer and a hint.


## H-194e correction — one export gate, and a revision keeps its check (no wire change)

Measured on the live store by the H-194 pass (card `t_05b53f68`, evidence `audit/h194/live/`): after
`lesson.revise` stored a section page-title revision and `parent.final.approve` returned active, the
review surface answered `data-cb-review-export="ready"` while `parent.export` refused
`POLICY_VIOLATION no_generated_content` ("section '…' has no check"). Two independent defects shared
that moment.

**1. A page revision keeps its check.** `domain.lesson_revise` wrote a new `gen_lessons` row and left
`gen_lesson_checks` — keyed by `lesson_id` — with no row for it, so every authored revision shipped a
section with zero checks. The check belongs to the **objective**, not to one page version: the
revision now copies the previous revision's `gen_lesson_checks` binding (`check_id`, `objective_ref`)
to the new row. The check row itself is never rewritten by an edit, so `lesson.revise` refuses a page
payload that changes the page's `check` projection (`VALIDATION_FAILED`,
`reason: check_not_page_editable`): the learner page would otherwise ask one question while the pack
graded against the stored reference answer. A new check is `lesson.regenerate`, not an edit.

A revision written before this fix (the live `audit/h194/live/` store) carries no binding of its own.
The next revision of that section inherits the newest binding in the section, so the section heals on
one more edit without a data migration; `cb.db` is untouched. Until it is edited again (or
regenerated), such a section still reports `no_generated_content` — an honest reading of the stored
rows, now visible from the review surface as well as the export.

**2. One gate, one order.** `domain._export_status` (what `parent.blueprint.read` and
`parent.review.read` serve as `parent_export_status`) and `pack_flow.parent_export` now call the same
`parent_authoring.export_gate`, so the review surface can no longer call a content set `ready` that
the export refuses. The frozen order is:

1. `plan_not_approved` — the plan is not approved;
2. `no_generated_content` — no composed section has a generated page (the same refusal
   `parent.final.approve` makes);
3. `no_generated_content` — a generated page's section binds no check, or that check declares no
   reference answer. This is checked **before** `no_final_approval` because approving cannot repair
   a checkless section; the refusal carries `problems[]` naming each section;
4. `no_final_approval` — no active `final_approvals` row;
5. `changes_need_review` — the active approval's `content_hash` no longer matches the recomputed one.

The one visible consequence of the ordering: a course with no generated pages and no approval used
to answer `no_final_approval` from `parent.export` and `no_generated_content` from the status read;
both now answer `no_generated_content`, matching what `parent.final.approve` refuses with.
`parent.final.approve` keeps its own refusal set (plan approved, content exists, hash matches): it
binds what a human approved, and exportability is the gate's answer, not a second approval rule.

**No wire change.** No method, request field, response key, error code, job kind, enum value or
`additionalProperties` moves; `blocked_reason` keeps its four values, with the check-level refusal
reported under `no_generated_content`. `cb.rpc` stays **v20** and `cb.db` stays **v12** — the fix is
handler behaviour, not shape. `parent_export_status`'s description ("ready is exactly
`no_final_approval`, `changes_need_review`, `plan_not_approved` and `no_generated_content` all being
absent") remains exact.

Regression guard: `tests/test_h194_fine_tune.py::ExportedPageRevisionTest` — a title revision keeps
its `check_id`, pre-approval both surfaces answer `no_final_approval`, the export succeeds after
approval, a checkless page answers `no_generated_content` from both surfaces (before and after an
approval), and a page payload that rewrites `check` is refused with nothing written.

## cb.db v13 delta (GM-001) — Game Mode storage, additive and unbackfilled

`cb.db` v13 is v12 plus the storage for the Game Mode program, created by
`0013_game_mode_contracts.sql`. Additive only: no v12 table, column, index or unique key is
dropped or retyped, and no lesson, attempt, transition or evidence row is read or rewritten.

* `courses.presentation_mode` — nullable `TEXT` constrained to `game` / `textbook`. Every
  existing course keeps `NULL`, and `NULL` **reads as `textbook`**. There is no backfill: an old
  course has no approved world, so writing `game` would be a fabricated fact. The read fallback
  is `coursebook.gm_contract.read_presentation_mode`; it never writes the fallback back.
* `course_worlds` / `world_assets` — the course-level visual kit, one row per world revision and
  one artifact per `hero` / `cover` / `section` / `lesson_scene` role. `section_key` is non-null
  so the unique key enforces the role budget (one hero, one cover, ≤ 6 sections, ≤ 2 scenes).
  World art carries no evidence class and no export path.
* `takehome_packs` — print artifacts bound to `source_course_id`, `source_objective_id`,
  `source_lesson_version` and `content_hash`. They never clone or mutate the source course;
  export requires a previewed and approved row, fenced on `preview_hash`.
* `homework_tasks` / `homework_events` — one task, one target, one observable success criterion,
  with `estimated_minutes` CHECK-bound to 3..10. Completion is `self_reported_done` or
  `parent_reported_done` and the event trail records the actor; neither is a pass or mastery.
* `game_engagement` — the play layer, keyed by a real `(action_kind, action_id)` and unique per
  enrollment, so a replay cannot double-award. It is not joined by an evidence, parent, pack or
  export read.
* `tutor_threads` / `tutor_turns` — one thread per lesson run and an append-only turn trail.
  Tutor prose is never graded, never an attempt or transition, and never exported.

`cb.rpc` **stayed v20 in GM-001** — the 18 Game Mode method names and one durable mode-setter are
frozen in `coursebook/gm_contract.py` (`GM_RPC_METHODS`) and `docs/GM-CONTRACT.md`. GM-005
registered the take-home family in **v23** (see the v23 delta below); GM-009 had already taken
**v21** for `engagement.read`/`engagement.award`.
`cb.errors`, `cb.jobs`, `cb.vocabulary` and `cb.pack` are unchanged.

Regression guard: `tests/test_gm_contract.py` pins the enum values, the manifest, the additive
`db.v12 -> db.v13` diff, and a real v12-to-v13 round trip on a disposable database proving the
legacy course reads Textbook and the attempt/evidence/check rows are byte-identical afterwards.

## cb.db v14 delta (GM-005) — a pack revision belongs to the pack, not to its source slot

`cb.db` v14 is v13 with **one unique key removed** by
`0014_takehome_pack_revision_scope.sql`; there is no new table, column, index, default, CHECK or
foreign key, and no row is rewritten or backfilled.

* `takehome_packs` in v13 carried `UNIQUE (source_course_id, source_objective_id,
  source_lesson_version, audience, kind, revision)`. A pack's `revision` is its own
  compare-and-swap counter — `takehome.create` starts a new pack at `0` and `approve` / `export`
  increment that same row — so keying it to the source slot made a second pack for a re-opened
  lesson unable to progress: after the first pack was `approved` (revision 1) or `exported`
  (revision 2), the new draft was legal at revision 0 but its first approve/export moved it to a
  revision number the predecessor row already held, and the write failed with `IntegrityError`.
* 0014 rebuilds the table without that key (same rows, same values) and recreates its two indexes.
  Duplicate **drafts** for one source slot are still refused in `takehome.create`, which returns
  the existing draft row instead of inserting a second one; `id` remains the pack identity.
* The storage fix does not move the wire: `cb.rpc` v23 carries the unchanged `takehome.*`
  request/response shapes, error codes and vocabulary.

Regression guard: `tests/test_gm_contract.py::GmTakeHomeRevisionScopeTest` pins the additive
`db.v13 -> db.v14` diff (every other table's columns, indexes and uniques byte-equal), the
append-only migration plan, and a real v13-to-v14 round trip on a disposable database proving
three existing pack rows survive byte-identical and a second draft at revision 0 can be inserted
for the same source slot.

## v23 delta (GM-005) — six take-home pack methods, a print artifact bound to the source lesson

`cb.rpc` v23 is v22 (GM-011's tutor) with **one family appended**: `takehome.sources`, `takehome.preview`,
`takehome.create`, `takehome.approve`, `takehome.export` and `takehome.read`, exactly the names and
field tuples frozen in `coursebook/gm_contract.py::GM_RPC_METHODS`. No v1-v22 method, request
shape, required key, error code, job kind, answer kind, verdict, evidence class or vocabulary
value moves; `cb.errors`, `cb.jobs`, `cb.pack` and `cb.projection` are untouched, and `cb.db` moves
to v14 only in storage (one constraint removed from `takehome_packs`, see the cb.db v14 delta
above).
`rpc.v22.json` stays byte-identical on disk (sha256
`c187728add6c508d5643e42225a64766d4b887cfce58250fb45d04707b6eb956`) and `x-supersedes` names
`.../rpc/v22`. v22 remains the GM-011 tutor delta, unchanged, including `tutor.ask` and
`tutor.history`; v21 remains the GM-009 engagement delta, unchanged.

**The artifact.** A take-home pack is a rendered print artifact, **not** a course, **not**
`cb.pack` and **not** `course.export`. `takehome.create` writes one `takehome_packs` row bound to
`source_course_id`, `source_objective_id`, `source_lesson_version` (the immutable
`gen_lessons.id:vN`) and `content_hash` (sha256 over the source page, section intent, objective and
the check row). The source course is never cloned, rewritten, re-approved or enrolled.

| Method | Kind | What it does |
|---|---|---|
| `takehome.sources` | read | The Parent Studio picker over one learner course: objective, section, validated lesson version, content hash and whether an approved world plate exists. A parent-only authoring course is refused with `POLICY_VIOLATION`, `details.reason = "parent_only_course"`. |
| `takehome.preview` | read | Composes the exact pages and returns `content_hash`, `preview_hash`, `pages` and recorded `sources`; persists nothing. The four base page objects are always present; captioned plate/diagram pages share the contract's 12-page ceiling with them, so a full world kit previews instead of overflowing. The learner page is a separate page object from the answer guide. |
| `takehome.create` | mutate | Binds the draft row. A duplicate **draft** for the same source returns the existing row rather than minting a silent clone; once the previous pack is `approved` or `exported` it is history, so `create` mints a new draft row (never returns a state the create response cannot describe). |
| `takehome.approve` | mutate | Fenced on `preview_hash`: an edit after preview invalidates this approval, not the source course. |
| `takehome.export` | mutate | Renders the bound, approved pages to selectable-text PDF through `artifacts.make_pdf` and the artifact store, filtered to the pack's `audience`: a learner copy prints cover + learner page + captioned plates and never the parent guide or answer guide; a parent copy prints the full pack. A replay of the same idempotency key and payload returns the stored result rather than a false `STALE_REVISION`. A failed render is `HOST_UNAVAILABLE`, never a blank pack; text the built-in print font cannot encode is refused as `POLICY_VIOLATION` with `details.reason = "print_font_cannot_render_text"` and writes no artifact rather than printing corrupted characters. |
| `takehome.read` | read | Returns the stored pack with `parent_guide`, `learner_page` and `answer_guide` as separate page objects, plus plates, diagrams, print profile and export state. It returns no attempts, tutor turns, notes or private observations. |

**The learner page never carries the answer guide.** The answer guide (reference answer, accepted
answers, rubric) is a separate, parent-only page; a defence-in-depth scan refuses a learner page
whose narrative announces a reference answer (`POLICY_VIOLATION`,
`details.reason = "answer_leak_in_learner_page"`).

**Print profile.** Letter, 612 x 792 pt, 56 pt margins, selectable text, low ink, explicit page
breaks between the parent guide and the learner page and the answer guide, no colour-only answers,
no learner answer key. A4 is the same fixed template at 595 x 842 for proofing.

**Visuals.** World art is optional, textless, captioned orientation with provenance and is never
instructional or safety authority. A procedure page's instructional diagram must be a
deterministic `schematic` or a `sourced_technical` figure with at least one recorded source id;
illustration-only procedure art is refused (`details.reason = "ai_art_as_procedure"`). A Textbook
course with no world art prints cleanly with `plates: []`.

Regression guard: `tests/test_gm_takehome.py` (the seven GM-005-named tests plus picker, idempotency,
create lifecycle after approve/export, hash-fence, learner-audience print filtering, strict-font
refusal, export replay, full-world page budget and typed-heading coverage) and
`tests/test_contracts.py` (`V22AmendmentTest`).
