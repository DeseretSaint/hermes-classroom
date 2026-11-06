# Review packet — CB-011 contract amendment (cb.rpc v6, cb.db v3)

Status: **frozen, nothing pushed**. Branch `wt/cb-011-atlas-contract-v6`, commit `3309993`, based on
`master` @ `ce7aded`. Owner: Atlas (contract + kernel). Consumed by CB-011 Parent Studio
(`t_4255b696`, Vellum) and by Cinder's executor/export card (`t_a356c8a8`).

## Why v6 exists

`docs/REVIEW_CB011-GAP.md` on `wt/cb-011-vellum` @ `cbed40b` recorded six verified gaps against
`cb.rpc` v5. Re-verified here on `master` @ `ce7aded` before freezing:

| # | Gap | Verified how |
|---|---|---|
| 1 | `plan`/`lesson` jobs never execute | `grep -rn "run_pending\|run_plan_job\|run_lesson_job" --include=*.py .` → definition sites and tests only |
| 2 | no draft-plan edit command | `record_objective`/`record_observation` have no handler; `plan.replan` only works from an approved plan |
| 3 | no lesson-set approval state | `plans.state` enum is `draft/approved/superseded` (`db.v2.json`); no approvals table |
| 4 | authored courses cannot be exported | `pack_flow.py:770-782` `course_not_pack_backed`; `artifacts.make_pdf` has no caller |
| 5 | blueprint tabs unreadable | `pack.inspect` returns manifest metadata only; `lesson.page` never serves `parent_guide`/`answer_guide` |
| 6 | reflection has no kind; brief not returned by `jobs.get` | `notebook_entries.kind` has no reflection value — **correct**; the second half is **wrong at `ce7aded`**: `domain._job_view` already returns `brief` from `jobs.brief_json` |

Gap 6b is a documentation defect in the gap report, not a kernel gap: the raw brief rides
`jobs.get`'s open `job` object today. The contract does not tighten that preserved payload; it adds
`parent.brief.get`, a *typed* read that also returns the enrollment and the plan job's state, which is
what "Duplicate brief" needs. This packet is the correction record.

## What changed

| File | Change | sha256 |
|---|---|---|
| `contracts/rpc.v6.json` | **new**: `$id .../rpc/v6`, `x-contract-version: 6`, `x-supersedes .../rpc/v5`, 51 methods (+8 `parent.*`), six new `$defs` (`parent_brief`, `parent_approval_status`, `parent_export_status`, `blueprint_file`, `parent_export_file`, `parent_reflection`), five new envelope rules; every `contract_version` echo moved 5 → 6 | `sha256:7fa0ccfe5553c43b249ea370d87fd993e32047092f5be5471b9ddd0dc2bf3397` |
| `contracts/db.v3.json` | **new**: `schema_version: 3`, two additive tables (`final_approvals`, `parent_reflections`), migration_plan entry 3; every v2 table/column/index/unique carried verbatim | `sha256:4c0569e4505f12e5862db6d63effe7363da64c1e0e0c837a49ed278b08ab48b6` |
| `coursebook/migrations/0003_parent_studio_approvals_and_reflections.sql` | **new**: the DDL the contract names, matching column-for-column (types, nullability, defaults, FKs, unique, indexes, CHECKs) | `sha256:bbf1ce923c5c98f91a80d138f81312cd5ea7e2f7b18aa30cbb9295c873b5784b` |
| `coursebook/contracts.py` | `cb.rpc → rpc.v6.json`, `cb.db → db.v3.json`, `WIRE_CONTRACT_VERSION = 6` | `sha256:6283ae115a7944b7c9a86599228a0d4e0e86956668a535b4d9834b164839576a` |
| `tests/test_contracts.py` | `V6AmendmentTest` (15 tests); `test_wire_contract_is_v6`; v5/v4/v3 "adds only" and "no new storage" tests now assert their **own snapshots**; `db.v2` sha256 pins added; explicit `coursebook.domain`/`pack_flow` imports so the seam tests no longer depend on discovery order; two pre-existing V5 tests moved to the v6 file pointer | `sha256:5b2976f6f6a887cad4f7adea74b2bddd0cd7943aded8c95eb1ddb4d370dd3aa7` |
| `tests/test_kernel_v2.py` | registry test gains an explicit `pending_v6` allowance (frozen-but-unwired methods; must shrink to empty when `t_a356c8a8` lands) | `sha256:59fbbe5a5e8d1f9dfd0ac5e9577158e0490c61035f5eb1ec6b517ef8d4dc745b` |
| `docs/CONTRACTS.md` | v6 delta: method table, the scoped answer-text exception, per-method semantics, the `content_hash` definition, the invalidation rule, storage table, the executor decision (`brief.stage`), handler instructions, UX §10 mapping row, migration impact, version log, new deliberate omissions | `sha256:122ca16a8d2afcf0c03d1cd2eef97059fda7f1d30173d06d644e4d6f9e025a2b` |
| `scripts/proof_contract_v3.py`, `proof_contract_v4.py` | storage version is `>= 2` (the snapshot each proof froze against) instead of pinned to 2, so a later additive db version does not fail a historical proof | `sha256:1dd7409ece08433a5d98595e73130d366cabf4602f3aecccac675a86449e7b81`, `sha256:181a63ce6ddee0aade2489b0012a9166539fd84cf2a83f775048dab907aba59d` |

`contracts/rpc.v1.json`…`rpc.v5.json`, `db.v1.json`, `db.v2.json`, `errors.*`, `jobs.*`,
`pack-manifest.v1.json`, `projection.v1.json`, `vocabulary.v1.json`, and `desktop/plugin.js`:
**untouched**. `rpc.v5.json` (`e4dfea0e…`) and `db.v2.json` (`873fd56c…`) are pinned by sha256 in
`tests/test_contracts.py`.

## Decisions the card asked for

**(a) Method family.** `parent.brief.create` / `parent.brief.get` / `parent.plan.edit` /
`parent.final.approve` / `parent.blueprint.read` / `parent.export` / `parent.reflection.record` /
`parent.reflection.list`. Eight methods, not the seven proposed: `parent.reflection.list` is added
because a reflection that cannot be read cannot seed the next brief, and `parent.blueprint.read`
carries the Sources tab so `pack.file.read` (below) is unnecessary.

**(b) Final approval representation.** A new additive table `final_approvals`, not a column:
`(course_id, plan_id, plan_hash, content_hash, state, invalidation_reason, approved_at,
superseded_at)`, unique on `(course_id, plan_id, content_hash)`, at most one `active` row per course
(kernel invariant, because SQLite cannot express a partial unique index in the contract vocabulary).
`plans.state` is untouched, so `plan.approve` stays the plan-level gate. **The invalidating
vocabulary value is `state = 'superseded'` with `invalidation_reason` in
`plan_edited | content_changed | course_edited | replaced`**; the wire-facing blocker the studio
renders is `export.blocked_reason = changes_need_review`. Rows are superseded, never deleted.

**(c) Tab content.** Role-scoped payload in `parent.blueprint.read` — **not** a path-addressed
`pack.file.read`. The five tabs are a closed enum resolved server-side inside the already-validated
manifest (pack-backed) or composed from generation staging (authored); the response has no `path`
property at all, and the export file names are pack-internal relative names with `..` refused by
schema. A path-addressed read would be the one wire field carrying a filesystem-shaped string for a
single consumer.

**(d) Pack builder + PDF.** `parent.export` builds a `cb.pack` v1 document from
`packs.export_allowlist()` with roles `parent_guide`, `learner_page`, `answer_guide`, `narration`
(all already in `cb.pack`'s role enum) and one `kind: pdf`, `mime: application/pdf` artifact through
`artifacts.make_pdf` plus one `kind: pack` artifact. No new manifest vocabulary, no stored manifest
copied, so `packs.PRIVATE_FIELDS` (attempts, notebook, reflections, transcripts, provider, paths)
stay out by construction.

**(e) Executor owner.** Cinder, sibling card `t_a356c8a8` (already created as this card's child).
**`lesson` is not added to `cb.vocabulary#job_kind`**: every pack manifest references the vocabulary
document, so the addition would force a `cb.pack` v2 and reject already-installed `$schema
.../pack-manifest/v1` packs. The seam is `brief.stage`: a `plan` job runs the plan stage, or
`brief.stage = lessons` with `plan_id` runs `run_lesson_job`. This is recorded in `CONTRACTS.md` and
asserted by `test_v6_adds_no_error_code_and_no_job_kind`.

## The one thing this card changes about an old rule

"No reference answer in any RPC response" becomes "no reference answer in any **learner** view". UX
§10 requires an Answers tab and an approval that covers the answer guide. `parent.blueprint.read` is
the single scoped exception: addressed by `course_id` only (no enrollment, no binding, no session),
answer text inside the declared `text` of an `answer_guide` file, `additionalProperties: false` so a
handler cannot pass stored JSON through. `lesson.page`, `check.get`, `course.outline`,
`evidence.inspect`, `course.get` are unchanged and are asserted to name no answer field.
`answer_guide` is not in `packs.LEARNER_FACING_ROLES`, so an exported pack keeps the key out of the
learner page.

## Evidence (run in `~/Projects/hermes-classroom/.worktrees/t_d54abd38` on `3309993`)

```
$ python3 -m unittest discover -s tests -t .
Ran 583 tests in 61.228s
OK
# master @ ce7aded baseline in the same worktree: 568 tests, OK. +15 = the new V6AmendmentTest.

$ python3 -m unittest tests.test_contracts
Ran 71 tests in 0.077s
OK
# With the original file (no V6 class) run alone on master: 56 tests, 4 failures + 1 error —
# a pre-existing discovery-order dependence on another module having imported coursebook.domain.
# The explicit imports at the top of the file remove it; that is a test-harness fix, not a
# contract change.

$ for m in 3 4 5; do python3 -m unittest scripts.proof_contract_v$m; done
OK (5 tests) / OK (10 tests) / OK (11 tests)

$ node --check desktop/plugin.js
OK

$ hermes plugins validate .
Validation passed.
# The "private core imports" advisory is pre-existing on master (coursebook/db.py:167 open_db,
# probes/*) and untouched by this card.

$ python3 probe_v6.py            # fresh HERMES_HOME
wire version        : 6
audit_contracts     : []
cb.rpc / cb.db      : (6, 'rpc.v6.json') (3, 'db.v3.json')
migrated to         : 3 applied: 3
tables added        : ['final_approvals', 'parent_reflections']
declared tables     : 21 live tables: 21
health.get wire     : True 6
implements parent.*: []
unwired call        : False NOT_IMPLEMENTED
brief missing ack   : False VALIDATION_FAILED

$ python3 probe_upgrade.py       # a real v2 database upgraded in place
v2 only migrated to: 2
v3 migrated to      : 3
preserved row       : {'title': 'Old course', 'revision': 3}
schema_migrations   : [1, 2, 3]
new tables present  : True
health              : {'ready': True, 'schema_version': 3}
```

The two probes are scratch scripts, not committed: they drove a fresh and an upgraded database and
are reproduced above with their real output.

## What is NOT done here (and who owns it)

* **Handlers.** None of the eight `parent.*` methods is registered; `api.dispatch` answers
  `NOT_IMPLEMENTED` (payload still validated first) and the Desktop gates on
  `/runtime.implemented_methods`. The handler contract is `CONTRACTS.md` §v6 "Handlers Cinder must
  register". `tests/test_kernel_v2.py` carries the explicit `pending_v6` allowance, which must
  shrink to empty when the handlers land.
* **Job executor** (`plan`/`lesson` pump, resolver registration, `brief.stage` dispatch): Cinder,
  `t_a356c8a8`.
* **Pack builder + PDF rendering** (`parent.export` body, role file assembly, low-ink layout):
  Cinder, `t_a356c8a8`, against this contract.
* **Desktop wiring.** `desktop/plugin.js` was not touched; Vellum consumes v6 after this lands and
  must merge the frozen files rather than author a contract.
* **No push.** Branch is local (`wt/cb-011-atlas-contract-v6` @ `3309993`); publishing is the
  operator's call.
