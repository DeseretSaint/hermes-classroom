# GM-005 round 6 — the re-opened pack can progress (cb.db v14 / migration 0014)

Review finding (round 5): `takehome.create` correctly minted a fresh draft for a source whose pack
was `approved` or `exported`, but that draft could never be approved or exported. `takehome_packs`
carried `UNIQUE (source_course_id, source_objective_id, source_lesson_version, audience, kind,
revision)` from `0013_game_mode_contracts.sql`, while `revision` is the pack's own
compare-and-swap counter. The second pack's first `approve`/`export` moved it onto the revision
number the predecessor row still held, and the write died with `IntegrityError`.

## Reproduction (red, before the fix)

Command, from this worktree at `deb0a00` with only the two new tests added:

```text
python3 -m unittest \
  tests.test_gm_takehome.TakeHomeBindingTest.test_takehome_reopened_pack_approves_after_an_approved_pack \
  tests.test_gm_takehome.TakeHomeBindingTest.test_takehome_reopened_pack_exports_after_an_exported_pack -v
```

```text
AssertionError: False is not true : takehome.approve failed: {'code': 'INTERNAL_ERROR',
  'category': 'internal', 'message': 'takehome.approve failed: IntegrityError', 'retryable': False}
AssertionError: False is not true : takehome.export failed: {'code': 'INTERNAL_ERROR',
  'category': 'internal', 'message': 'takehome.export failed: IntegrityError', 'retryable': False}
Ran 2 tests in 1.858s
FAILED (failures=2)
```

That is the reviewer's `gm005_progress_probe.py` and `gm005_constraint_probe.py` failure, reduced to
two permanent regression tests.

## Fix

- `coursebook/migrations/0014_takehome_pack_revision_scope.sql` rebuilds `takehome_packs` without
  that key and recreates its two indexes. Same columns, types, nullability, defaults, CHECKs,
  foreign keys, indexes and rows; `INSERT ... SELECT` copies every row unchanged.
- `contracts/db.v14.json` is the additive v14 inventory (v13 stays on disk byte-identical); the
  `takehome_packs.unique` entry is gone and the migration plan gains its 14/13 entry.
- `coursebook/db.py` `DB_SCHEMA_VERSION = 14`, `coursebook/contracts.py` current `cb.db` file
  `db.v14.json`.
- `docs/CONTRACTS.md` gains the cb.db v14 delta section and the updated inventory row.
- Duplicate-*draft* protection stays in `takehome.create` (it returns the existing draft row); the
  dropped key was never that guard.

## Verification (green, after the fix)

```text
python3 -m unittest \
  tests.test_gm_takehome.TakeHomeBindingTest.test_takehome_reopened_pack_approves_after_an_approved_pack \
  tests.test_gm_takehome.TakeHomeBindingTest.test_takehome_reopened_pack_exports_after_an_exported_pack -v
  Ran 2 tests ... OK
```

- `tests.test_gm_contract.GmTakeHomeRevisionScopeTest` (3 tests): v14 is v13 minus only that key
  (every other table's columns/indexes/uniques equal), the migration plan is append-only, and a real
  v13-to-v14 round trip on a disposable database preserves three pack rows byte-identically and then
  accepts a second draft at revision 0 for the same source slot.
- Reviewer's probes re-run against this tree:
  - `gm005_progress_probe.py` → 3/3 OK: second pack approves after an approved pack (both rows
    `approved`/revision 1), second pack approves+exports after an exported pack (both rows
    `exported`/revision 2, distinct artifact ids), second pack approves after an approved-only pack.
  - `gm005_constraint_probe.py` → the export it used to prove the defect now **succeeds** (its
    assertion is inverted by design; the probe fails because the bug is gone).
  - `gm005_probe.py`, `gm005_probe2.py`, `gm005_probe3.py`, `gm005_review2_probe.py`,
    `gm005_round4_probe.py`, `gm005_round5_probes.py` → all OK (no regression).
- Focused combined run (`test_gm_takehome`, `test_contracts`, `test_gm_contract`, `test_artifacts`,
  `test_parent_studio`, `test_kernel_schema`, `test_plan_units`, `test_hook_snapshot_loss`,
  `test_hook_provisioning`, `test_rpc`) → 346 tests OK.
- Full suite `python3 -m unittest discover -s tests -t . -q` → **Ran 2805, OK (skipped=1)** in
  575 s.
- `audit/gm-005/make_pdf_proof.py` re-run exit 0; the eight proof PDFs, `evidence.json` and
  `PROOF.md` are regenerated from the real RPC flow (page order, MediaBoxes, answer-free learner
  sheet, long-title bbox and accented-text checks unchanged).
- `contracts/rpc.v20.json` remains byte-identical; `contracts/db.v13.json` is not modified.

## Correction to the round-5 handoff

The round-5 STATUS.md note said the H-45 evidence diff was "8 sites". The measured diff is
`contract_version: 20 -> 21` at **5 sites** (1 in `bicycle_single.json`, 2 in `music_short.json`,
2 in `soldering_full.json`) plus **3** `manifest.json` hashes. `audit/adversarial/harness-e2e/STATUS.md`
now states the measured count; the packet itself is untouched by this round and still verifies
FRESH.
