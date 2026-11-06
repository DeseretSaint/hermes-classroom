# Review packet — CB-026 contract amendment (cb.rpc v5)

Status: **frozen, nothing pushed**. Branch `wt/cb-026-atlas-rpc-v5`, commit `dc0a22c`, based on
`wt/cb-024-atlas-rpc-v4` @ `4839cb5` (which is based on `wt/cb-022-atlas-rpc-v3` @ `a378516`, which is
based on `master` @ `b536e2f`).

## Why this is v5 and not "v4"

The card asked for "additive v4". **v4 already exists and is frozen**: CB-024 shipped
`contracts/rpc.v4.json` (40 methods, `pack.list` + `pack.inspect`) with its own review packet, and
`docs/CONTRACTS.md` §Version numbering states that no shipped version file may be extended in place
— clients cache by version, and the v4 method set is already referenced by the pack handlers, CB-024's
packet and the CB-024 completion metadata. Bolting three more methods onto v4 would change a shipped
document's meaning.

So the three CB-009 surfaces land as **cb.rpc v5**, additive over v4. Every v1–v4 method schema in
`rpc.v5.json` is byte-identical to its original, and `tests/test_contracts.py` pins the sha256 of
`rpc.v1.json`…`rpc.v4.json` so "v3 stays byte-identical" is a fact about the files, not a claim about
the diff.

## What changed

| File | Change | sha256 |
|---|---|---|
| `contracts/rpc.v5.json` | **new**: `$id .../rpc/v5`, `x-contract-version: 5`, `x-supersedes .../rpc/v4`, 43 methods (+`course.outline`, `check.get`, `lesson.assist`), three new `$defs` (`outline_plan`, `outline_objective`, `check_stimulus`), one new envelope rule for `lesson.assist`; every `contract_version` echo moved 4 → 5 | `sha256:e4dfea0e031b32698e9e354f640b25acfcdf68244ec819a3cedc375e8bd8b156` |
| `coursebook/contracts.py` | `CONTRACT_FILES["cb.rpc"] = "rpc.v5.json"`, `WIRE_CONTRACT_VERSION = 5` | `sha256:f20ed35b1d5663dc252515bf50935e36aaf4ea46dd1ae536e202ff978c6ffe7f` |
| `tests/test_contracts.py` | `V5AmendmentTest` (10 tests): additive-only, verbatim carry-over of v1–v4 schemas, pinned history hashes, outline bounds and derivation, `check.get` stimulus/refusal, `lesson.assist` fencing, no new storage/error code, docs coverage. Wire test is now `test_wire_contract_is_v5`. Handler-restore fix in the four seam tests so the file passes on a branch **with** real handlers (it previously popped them) | `sha256:6df4efd6f97a968017777fb03625c15c277b22e518cf394718805553dcf9d413` |
| `scripts/proof_contract_v5.py` | **new**: 11 tests against the real kernel and a real SQLite database | `sha256:44e2eb71ad5373dfce5a01e17a1dbe933a3517cc1310ca85e15222e52acad0ed` |
| `scripts/proof_contract_v4.py` | version-agnostic (`>= 4`) instead of pinned to 4 | `sha256:f363850d7c97830f8c924eb4035a34cbaf135df87a59f332d60f2bf9475a8448` |
| `docs/CONTRACTS.md` | v5 delta: why, method table, **what each method may not return**, `course.outline`/`check.get`/`lesson.assist` semantics, storage rows, known divergence, handler instructions, version numbering + decision log, UX mapping rows, deliberate omissions | `sha256:22ea1ef26ba091e6d05e0079d91280c52c300b77049ec848eb08188e788f38a5` |

`contracts/rpc.v1.json` … `rpc.v4.json`, `db`, `errors`, `jobs`, `pack`, `projection`, `vocabulary`:
**untouched**. No table, column, migration or error code.

## Contract decisions worth reviewing

1. **`course.outline` has no `section_titles`** (the card asked for one). There is no heading field
   in `cb.db` v2: `lesson_segments.text` is a verbatim assistant transcript (written by
   `turn.record_assistant_snapshot`) and `plans.schedule_json` is `{}` in this build. The section
   index *is* the objective list, and a section's page is `lesson.page`. A label list derived from
   chat prose would be a fabricated UI concept frozen into a contract; it is omitted and recorded in
   §Deliberate omissions instead. **This is the one requested field not delivered** — flagged here so
   Vellum can push back with the exact label source if she has one.
2. **`course.outline` is bounded and honest about it**: `limit` ≤ 400, `objectives` ≤ 400, plus
   `total`/`truncated`. The card's shape had no place to put a truncated list; silent truncation is
   worse than two extra fields.
3. **`check.get` normalizes the stimulus** because storage is heterogeneous: generator checks carry
   `{prompt, format, choices, learner_instructions}`, pack-projected checks carry `{prompt}` only
   (`cb.projection` v1 emits no format). Format defaults to `text`, choices to `[]`. `prompt` is
   bounded at 8000 characters — the `cb.pack` bound — so a legitimate imported check cannot become
   unrenderable. The stimulus is built from a four-key allowlist: unknown stored keys are dropped, so
   a manifest that hides `reference_answer` inside its stimulus cannot reach the pane. A test builds
   exactly that row and asserts it does not leak.
4. **`lesson.assist` bumps the enrollment revision** and writes **no** transitions row, following
   `review.action`'s CB-022 precedent. The bump is not ceremony: `attempt.submit` classifies
   evidence (`cold`/`hinted`) inside its *read* transaction and grades outside any transaction, so a
   hint recorded mid-grade would be invisible and the answer committed as `cold`. The fence makes
   the in-flight submit lose and the resubmit classify `hinted`. Precondition: an **open check** must
   exist — `evidence` has no `check_id` column, so an unconsumed hint would contaminate the next
   check on that objective.
5. **`kind` is `hint_request` / `answer_shown`, not `attempt.assist`.** The card allowed either
   name; `lesson.assist` is the pane side of the `lesson.*` family and the payload is exactly the
   event the hook already writes.

## Evidence

Contract branch (`wt/cb-026-atlas-rpc-v5` @ this commit):

* `python3 -m unittest discover -s tests -t .` → **247 tests OK** (was 237 on the base).
* `python3 -m unittest tests.test_contracts` → **56 tests OK**.
* `node --check desktop/plugin.js` → OK; `hermes plugins validate .` → **Validation passed**.
* `python3 scripts/probe-backend.py` → **9/9 backend expectations passed** against an isolated
  `HERMES_HOME`; `/runtime` reports `contract_methods: 43`, `wire_version: 5`,
  `implemented_methods: [binding.get, health.get, schema.get]` — i.e. the three new methods are
  frozen and honestly unimplemented, which is what the Desktop gates on.

Real-backend proof (copy of `wt/cb-023-cinder` @ `9c23428` with this contract set overlaid):

* `python3 -m unittest scripts.proof_contract_v5 -v` → **11 tests OK**, real SQLite built by the real
  migrations, real commands:
  * outline from a real draft plan (2 objectives, ordinals, hash, `check_state: none`), then
    `check_state: open` after `check.open`, and after a hinted pass `closed` / `attempt_count: 1` /
    `independent: false` / `state: introduced`, versus a cold pass reaching
    `independent_evidence`;
  * bounded list with `total`/`truncated`;
  * `check.get` by id == by objective; kernel spec with no format served as `text`;
    a selection item with `learner_instructions` rendered, with a smuggled `reference_answer` and
    `rubric` dropped;
  * cross-course `check_id` → `VALIDATION_FAILED` / `check_not_in_enrollment_course`, unknown id →
    `NOT_FOUND`;
  * `lesson.assist` writes a layer-1 event with `attempt_id NULL`, bumps the revision, the next
    `attempt.submit` is classified `hinted` and consumes the event (`evidence.attempt_id` set), and
    a stale `expected_revision` submit is refused with `STALE_REVISION`/`CHECK_STALE` with zero
    attempts written;
  * `assist` without an open check → `VALIDATION_FAILED` / `no_open_check`;
  * the migrated table set equals `cb.db` v2's `tables` — v5 added no storage.
* Same proof tree, full suite: `416 tests`, **1 failure**, and it is Cinder's own registry test
  (`tests.test_kernel_v2.RegistryTest.test_every_v2_method_is_registered_unless_another_package_owns_it`,
  `unregistered: [check.get, course.outline, lesson.assist, pack.inspect, pack.list]`). That is the
  correct signal: the methods are frozen and the handlers are the next card. The pack methods are
  Lattice's CB-024 follow-up, the three v5 methods are Cinder's CB-026 card.

## Known divergences and limits (recorded, not silently accepted)

1. **The chat hook's hint path does not bump the revision.** `turn.pre_turn` records the same
   `hint_request` / `answer_shown` evidence without a bump, so the chat path keeps the narrow race
   the pane path closes. Changing `pre_turn` is Cinder's session-lifecycle code and is out of scope
   for a contract freeze; it is on Cinder's card as a separate, explicitly optional item.
2. **No handler is registered for the three methods in this amendment.** By design: the card assigns
   registration to Cinder. `api.dispatch` answers `NOT_IMPLEMENTED` after validating the payload, and
   the Desktop's `/runtime.implemented_methods` gate keeps every control in its honest "not in this
   build" state.
3. **`section_titles` not delivered** — see decision 1.
4. **No live Desktop screenshot.** The pane wiring is CB-009/Vellum; this amendment is the contract
   and its proof.

## Handoff

* **Cinder** — register `course.outline`, `check.get`, `lesson.assist` (card created; exact
  derivations and refusals are in `docs/CONTRACTS.md` §v5 delta → *Handlers Cinder must register*).
  Factor the assist insert out of `turn._record_assist` into `evidence.record_assist` so the hook and
  the pane cannot drift. Rebase onto this contract branch (or merge it) before registering; the
  v4 pack reads and `cb.projection` are on `wt/cb-024-atlas-rpc-v4`.
* **Vellum** — the three methods are on the wire; keep the `/runtime.implemented_methods` gate until
  Cinder's card lands, then the pane's check prompt and Hint/Show answer stop being "not in this
  build". `course.outline` gives the Textbook/Plan list; it does not give per-objective sub-headings.
* **Lattice** — unaffected; `pack.list`/`pack.inspect` are unchanged and still need their handlers
  (CB-024 follow-up).
* **Sentinel** — the new attack surfaces worth probing: a check whose stored stimulus carries an
  answer (must not render); assist events with no open check; two concurrent assists and a submit
  racing them; an outline for an enrollment whose plan is a draft.

## Registration note (Cinder, t_b13f5b47)

The three handlers are registered in `coursebook/domain.py` and share one writer
(`evidence.record_assist`) with the chat hook; `scripts/proof_contract_v5.py` now drives them
through `api.dispatch` (11/11) and `tests/test_kernel_v5_handlers.py` pins replay, conflict, stale
fencing, no transitions row and the read-only revision 0.

The existing divergence 1 above was left as recorded, deliberately: `turn.pre_turn` still writes
the assist event without bumping the revision, because `pre_turn` is the session-lifecycle path and
a bump there changes the post-turn observer's compare-and-swap for every chat turn, not just the
hint path; the pane path is fenced separately and the two paths still write the same row.

