# Review packet — CB-024 contract amendment (cb.rpc v4 + cb.projection v1)

Task: `t_15b5198e` — *Contract v3: list/inspect installed packs; freeze pack-check → check_spec
projection*.
Owner: Atlas (contract). Follow-on implementers: Lattice (`coursebook/pack_flow.py`), Cinder (nothing
in this amendment).
Branch: `wt/cb-024-atlas-rpc-v4`, based on `wt/cb-022-atlas-rpc-v3` @ `a378516` (which is based on
`master` @ `b536e2f`).

## The card says v3; this is v4, deliberately

The card proposes "a v3 additive amendment". By the time it ran, **v3 was already frozen** as the
learning-loop surface (CB-022, `contracts/rpc.v3.json`, 38 methods) and `docs/CONTRACTS.md`
§*Version numbering* records that `pack.list` is explicitly **not** v3 and that no shipped version
file may be extended in place. Adding `pack.list` to v3 now would change a shipped contract's
meaning and break the version cache, which is the one thing the amendment process exists to prevent.

So this amendment is **cb.rpc v4** and it supersedes v3 additively: v1..v3 methods are byte-identical
(asserted), only the wire echo moves and two methods are added. The unowned draft that carried
`pack.list` on `wt/cb-020-rpc-v3` is superseded by this file rather than adopted.

## Why this amendment exists

CB-010 wired `pack.preview` / `pack.import` / `pack.export` / `pack.delete` and found that the
Desktop could not read an **installed** pack:

* `library.list` joins `courses JOIN enrollments`, so a pack that is installed but not enrolled is
  invisible (an import that adopted and then failed its transaction; a pack after
  `enrollment.delete`).
* `pack.preview` needs a `staged_id`, i.e. a freshly granted file, so a manifest from an earlier
  session cannot be re-rendered.

CB-010's consequence was `previewCache`: the export review refused to export a pack it had not
previewed in the same session, turning "export any installed pack" into a re-import. It also had no
wire path to the pack `revision` that `pack.delete` fences on.

The second gap: the manifest-check → kernel `check_spec` mapping was importer-owned. Import is the
first consumer; Parent Studio generation and community upload review are the next two, and two
implementations of one mapping is how a pack starts grading differently in two places.

## Files

| File | State | sha256 |
|---|---|---|
| `contracts/rpc.v4.json` | **new** (40 methods; `$id .../rpc/v4`, `x-supersedes .../rpc/v3`) | `b910c5e4a02015db6d35131e283b10582a4a8d400a24b9f3a6f8b242b538ad49` |
| `contracts/projection.v1.json` | **new** (`cb.projection` v1: rules, schemas, 13 + 2 conformance vectors) | `82fc86324a593bbac720aa6873f0c36c63d3d49772c9833c7ede08d12d281aba` |
| `contracts/rpc.v3.json` | untouched history | `006232ae71b642fd44d6461ce0e0f83f7fd40cf6dfeb4b0730fc4283cb6aad9a` (unchanged) |
| `contracts/rpc.v2.json` | untouched history | `4afc3c5fe0248c32733884dc68295f4a3aff916df7782f437945a8862e4352f4` (unchanged) |
| `contracts/db.v2.json`, `errors.v2.json`, `jobs.v2.json`, `pack-manifest.v1.json`, `vocabulary.v1.json` | untouched | no storage, error, job or manifest change means no bump |
| `coursebook/contracts.py` | modified | `CONTRACT_FILES["cb.rpc"] = "rpc.v4.json"`, `+ "cb.projection"`, `WIRE_CONTRACT_VERSION = 4`; new `definition_schema()` / `validate_definition()` so a `$defs` entry can be validated without restating it |
| `tests/test_contracts.py` | modified | v1/v2/v3 preservation extended to v3; `V4AmendmentTest` (8) + `ProjectionContractTest` (7); 46 tests in the module |
| `scripts/proof_contract_v3.py` | modified | version-agnostic (was pinned to `WIRE_CONTRACT_VERSION == 3`, which v4 would otherwise fail) |
| `scripts/proof_contract_v4.py` | **new** | 11 tests against the real CB-010 pack lifecycle |
| `docs/CONTRACTS.md` | modified | status v4, contract table, v4 delta, projection authority, divergences, UX rows, decision log |

## The two new methods

| Method | Request | Response |
|---|---|---|
| `pack.list` | `pack_id?`, `pack_version?`, `filter` (`all`/`installed`/`frozen`/`removed`, default `all`), `limit` (1–200, default 100) | `items[]` (≤200 `pack_list_item`), `total`, `truncated`, `applied_filter` |
| `pack.inspect` | `pack_id`, `pack_version` (both required) | `pack` (the same item), `manifest`, `integrity` (`hashes_match`, `file_count`, `expanded_bytes`), `trust.labels` |

`pack_list_item` = `pack_id, pack_version, content_hash, recipe, source, state, revision,
installed_at, file_count, expanded_bytes, license`. All required; no optional field.

## Decisions (and the reason)

1. **Two authorities, joined, not duplicated.** The library index is the installed-pack authority
   (adoption writes it); the kernel `packs` row wins for `state` and `revision` when present, index
   values are the fallback. One item per `(pack_id, pack_version)`.
2. **`revision` is in the row on purpose.** `pack.delete` requires `expected_revision`; nothing else
   on the wire exposed a pack's revision, so deletion was unreachable from a cold client. Proven
   end to end in `proof_contract_v4`: list → `pack.delete` dry_run → confirm (revision + 1) → list
   shows `frozen` with the new revision.
3. **No filesystem path, no enrollment claim, no manifest in the list.** The index stores an absolute
   `directory`; it is storage. Enrollment state stays `library.list`'s answer (one authority per
   fact). The list is a bounded index read; `pack.inspect` is the read that returns the manifest.
4. **Bounded, not paged.** `limit` ≤ 200, `total` always the full count, `truncated` says rows were
   omitted. No cursor: a 200+ identity library is narrowed by filter, not scrolled. Ordering is
   documented (`installed_at` desc, then `pack_id`, `pack_version`) because JSON Schema cannot say it.
5. **`pack.inspect` reports drift, it does not raise.** `archive.PackLibrary.read()` verifies the
   whole tree and raises `PackRejected` on any drift; the handler must catch that and return
   `hashes_match: false` with the stored manifest, so one damaged file disables export instead of
   killing the library pane. Unknown/unreadable identity is `NOT_FOUND`.
6. **`pack.inspect` is what replaces `previewCache`.** Its `content_hash` is the identity
   `pack.export` checks against `options.expected_content_hash`, so the UI can show the hash it
   inspected and export in a later session.
7. **The projection is a new contract id (`cb.projection` v1), not `cb.pack` v2.** The manifest did
   not change; the derivation from it is now frozen. `$defs.check_spec` and
   `$defs.objective_criterion` make the stored shapes machine-checkable.
8. **A pack's declaration can refuse gradability, never grant it.** `audit_state: failed` withholds
   (R6); `audit_state: passed` on a leaking check still withholds (R1–R5). The deterministic audit is
   the only gate.
9. **The frozen projection is not a wire payload.** `check_spec` / `reference_answer` appear in no
   RPC response (asserted across every method's response schema).

## Evidence from real runs

* `python3 -m unittest discover -s tests -t .` → **237 tests OK** on this branch (222 on v3 branch;
  +15 new, no regression from the wire bump).
* `python3 -m unittest tests.test_contracts` → **46 tests OK**; includes a new assertion that every
  `contract_version` const in `rpc.v4.json` (both response envelopes, `health.get`) equals
  `WIRE_CONTRACT_VERSION` — this caught a real miss during development (both response envelopes were
  still `3` and every `ok` envelope failed its own schema).
* Preservation, asserted mechanically: every v1, v2 and v3 method schema in `rpc.v4.json` is
  byte-identical except the `health.get` wire constant; the two envelope constants moved 3 → 4.
* `contracts.audit_contracts()` → `[]` (ids, versions, `$ref` targets, error catalog, method
  enum ↔ payload schemas, wire constant).
* **Contract ↔ backend proof** (`scripts/proof_contract_v4.py` run in a copy of `wt/cb-010-lattice`
  @ `47695df` with this branch's contract files, real SQLite, real migrations, real zip archives,
  real staging grant and adoption): **11 tests OK**. It established:
  * `pack.list` rows validate **as composed** from a real adopted pack and its `packs` row; the
    Japanese and parent demo packs both appear with their real recipes, file counts, byte totals and
    content hashes;
  * a pack adopted **without** an import (the real "installed, not enrolled" state) is invisible to
    the enrollment join (`0` rows) and visible in `pack.list` (`total = 1`, index fallback
    `state=installed`, `revision=0`);
  * `filter`/`limit` bound rows without hiding the total (`1` row, `total = 2`, `truncated = true`);
  * `pack.delete` preview → confirm works off the list's `revision`, and the list then reports
    `frozen` with `revision + 1`;
  * `pack.inspect` validates, matches `pack`/`integrity` counts, carries three trust labels
    (`human_review_recorded` correctly absent), and `manifest.content_hash == pack.content_hash`;
  * appending one byte to a declared file makes `pack.inspect` return `hashes_match: false` and drop
    `integrity_verified`, then restoring the bytes returns `true` — no exception, no lie;
  * 11 of 13 projection vectors match `check_spec_from_pack_check` exactly; both `objective_examples`
    match `objective_criteria` exactly; every criteria entry validates against
    `cb.projection#/$defs/objective_criterion`.

## Two importer divergences found by the freeze (Lattice must fix)

Both are recorded in `cb.projection`'s `x-known-divergences` and pinned by their own vectors, so a
third, undocumented divergence fails the proof.

| Id | Current importer | Contract requires | Observable consequence |
|---|---|---|---|
| `empty-alternatives` | `all(...)` over an empty list is vacuously true, so **any** check with no `accepted_alternatives` is withheld | an empty/whitespace-only list is not a flaw; the reference answer is an accepted form | **the shipped demo pack is affected**: `chk-register-transfer-1` declares `accepted_alternatives: []`, so `obj-register-transfer` is written with `check_spec_withheld: true`, `check.open` refuses it with `VALIDATION_FAILED` / `reason: objective_not_checkable`, and the learner can never be assessed on the pack's transfer objective. Proved through the real dispatcher in `proof_contract_v4`. |
| `declared-audit-failed` | a check declaring `audit_state: failed` is projected when the automated audit passes → spec says `audit_state: passed`, `declared_audit_state: failed` | the author's `failed` withholds | the stored spec contradicts its own provenance; an item its author marked failed can be graded |

Fix is in `coursebook/pack_flow.py` only (R5 guard + R6 check). Follow-up card filed for Lattice with
the exact vectors and the two negative assertions to invert.

## Integration notes

* **Numbering.** v3 is untouched; v4 supersedes it. Cinder's `review.*` / `evidence.*` handler work
  from CB-022 is unaffected — those method schemas are byte-identical in v4, so registration can land
  against either file.
* **CB-010's cross-owner edit to `dashboard/plugin_api.py`** (three host seams: `GET /packs/intake`,
  `POST /packs/grant`, `GET /artifacts/{handle}`): the seams are host transport, which is Sable's
  surface. Adjudication: they may stand until Sable's transport branch is merged, and Sable must
  either adopt or supersede them in that merge — no contract change is implied either way, because
  the seams carry no contract payload of their own.
* **Desktop.** `desktop/plugin.js` reads `result.contract_version` dynamically; no client edit is
  implied by the wire bump. The export panel can now call `pack.inspect` before `pack.export`; that
  wiring is Lattice's (CB-010 follow-up), not part of this freeze.

## Not verified here

* The two handlers do not exist on this branch. Until Lattice registers them, `dispatch` answers
  `NOT_IMPLEMENTED` (asserted in `tests/test_contracts.py`) — never a convincing empty list.
* No live Desktop screenshot: this card is a contract freeze, and the installed-profile capture is
  CB-020.
* The projection proof ran against a **copy** of `wt/cb-010-lattice`; that branch was not modified.
* Nothing pushed to GitHub.

## Rollback

One line each in `coursebook/contracts.py`: `CONTRACT_FILES["cb.rpc"] = "rpc.v3.json"`,
`WIRE_CONTRACT_VERSION = 3`, and drop the `cb.projection` entry. `rpc.v4.json` and
`projection.v1.json` can stay on disk as history; nothing else reads them.
