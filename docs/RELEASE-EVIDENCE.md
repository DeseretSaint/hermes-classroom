# Release evidence — what is measured, on which commit, and what is branch-only

Status: the H-212 freeze pass, re-derived on the frozen `master`
`b9f4a197e42e4f033298d94608fcb5b63640b094` (the H-210-R2 merge over `df052ea`: the live pack
round trip that closed gate 4, plus its capture under `audit/adversarial/h210r2-pack-roundtrip/`).
Every number below was produced by a command in this pass on that commit unless a row names another
commit. The suite count and the contract counts are the exception: they are re-measured on `master`
`07976d8` and the rows name that tree. Machine-readable copy: `docs/release-evidence.json`, checked
against the documents by `python3 scripts/check-docs-truth.py`.

The commit before it, `ab6dc7e`, is the earlier H-209 measurement tree; the numbers attributed to it
below are that pass's record and are left as history rather than rewritten.

**This is not a green release.** The suite passes, but no demo is recorded, no license exists, no
live Desktop window has driven this exact commit, and the operator publication gate in
`docs/SUBMISSION.md` §0 is closed. No tag, catalog pull request or announcement was made.

## Measured on `b9f4a19` (frozen tree)

| Fact | Value | Measured on | Command |
| --- | --- | --- | --- |
| Suite | `Ran 2747 tests in 410.301s`, `OK (skipped=1)` | `b9f4a19` (H-212) | `python3 -m unittest discover -s tests -t .` |
| `cb.rpc` | v20, 73 declared methods | `b9f4a19` (re-asserted, H-212) | `contracts/rpc.v20.json` (`coursebook/contracts.py:51` `WIRE_CONTRACT_VERSION = 20`) |
| Handlers | 73, asserted by the registry; `METHOD_HANDLERS` after importing every registering module | `b9f4a19` (measured, H-212) | `coursebook/api.py`, registry test in the suite |
| `cb.db` | v13, `DB_SCHEMA_VERSION = 13`, migrations `0001`-`0013` | `4e3d6c6` (GM-001 contract freeze) | `coursebook/db.py:230`, `contracts/db.v13.json` |
| Shipped module | `desktop/plugin.js` sha256 `cd862140f0f03783f098326017db5225bb58b400e3595b321200480aa865c516` | `b9f4a19` (re-hashed, H-212) | `sha256sum desktop/plugin.js` |
| M4 audit | 62 frames, 15/15 claims PASS, 2,120 measured text nodes over 56 non-forced frames, worst authored contrast 5.93:1, 0 unnamed of 298 AX controls, 0 px overflow | `ab6dc7e` (H-203) for the `cd862140` release-tree pin; the same audit regenerated for CP-020a `45c7d972`, CP-020b `1aa11577`, CP-043 `04452231` and the shipped module `4087908c` on 2026-11-10, every measurement reproduced (only `generated_at`, branch and pin changed) | `python3 scripts/m4v-audit.py` → `audit/visual/m4-visual/audit.json` |
| Adversarial state matrix | `SUMMARY total=23 fail=0 pass=23`; S13 BLOCKED because the auxiliary grader lane is disabled in this release | `ab6dc7e` (H-203); **not re-run** on `b9f4a19` — carried as the last measurement of this matrix, not a claim about the frozen tree | `python3 tests/adversarial/attack_state.py` |

The `audit.json` carried `plugin_sha256` equal to the `b9f4a19` module's hash (`cd862140…c516`, the same
module as `ab6dc7e`), which is what made the M4 row a claim about that tree rather than a stale pin:
`desktop/plugin.js` is byte-identical on `ab6dc7e` and `b9f4a19`, so the audit was not regenerated in
the H-212 pass. The committed audit has since been regenerated four times — for CP-020a `45c7d972`
(`67ca98b`), CP-020b `1aa11577`, CP-043 `04452231` and the module this tree ships, `4087908c`
(2026-11-10) — and each regeneration changed only `generated_at`, the recorded branch and the pin, so
every measurement and every committed screenshot below reproduced unchanged. The `cd862140` pin is the
release-tree record; re-pinning it to the shipped module is the remaining freeze step.

Two measurements moved on the settled `ab6dc7e` tree and are recorded there as measured rather than
carried forward: the text-node count is **2,120** over the 56 non-forced frames (the H-183/H-189
learner-copy sweep and the H-182/D8 objective copy reduced painted prose on those surfaces), and
`C-08` measures **0** animated nodes in the four reduced-motion frames against **70** in the
full-motion frames (H-152's transitions are real, and the preference suppresses them). The AX control
count (298 over the 32 frames with an accessibility tree), the worst authored contrast (5.93:1), and
the overflow/clipping counts (0) are unchanged. A prior record quoting 2,416 text nodes describes the
`eed7dc7` slice, not this tree.

## Suite and contract re-measurement on `master` `07976d8` (2026-11-10)

The table above is the `b9f4a19` H-212 record. The suite and contract counts the release documents
quote are re-measured on the tree the release gate reads, because test-only and contract-only merges
land without moving the release pin:

| Fact | Value | Measured on | Command |
| --- | --- | --- | --- |
| Suite | `Ran 3501 tests in 1134.427s`, `OK (skipped=11)`, exit 0 | `07976d8` (`master`, 2026-11-10, `t_12c5410e`) | `python3 -m unittest discover -s tests -t .` |
| `cb.rpc` | v25, 93 declared methods, 93 handlers, no declared method without a handler and none outside the contract | `07976d8` (`master`, 2026-11-10, `t_12c5410e`) | `contracts/rpc.v25.json`, `coursebook/contracts.py` `WIRE_CONTRACT_VERSION = 25`, `coursebook/api.py` `METHOD_HANDLERS` after importing every registering module |
| `cb.db` | v14, `DB_SCHEMA_VERSION = 14`, migrations `0001`-`0014` | `07976d8` (`master`, 2026-11-10, `t_12c5410e`) | `coursebook/db.py`, `contracts/db.v14.json` |

The previous record quoted `Ran 2880 tests in 540.226s … OK (skipped=1)` measured on the merged
GM-005 tree over `origin/master` `3fb3779`. That count went stale when CP-014, CP-020a, CP-020b,
CP-030, CP-031, CP-044 and CP-042 merged: 3501 is 621 tests above it, and the skip count is 11 on this tree
against 1 in that record. 3501 was measured three times on two trees and agreed every time:
this pass on `07976d8` (1134.427s), the supervisor on `07976d8` (1074.585s), and the supervisor
on `2cf9104` (CP-042 over `7130109`, 1341.510s). The record's `cb.rpc` v23 / 83 methods was stale for the same reason: v24
(world/homework/takehome.html, ten methods) and v25 (CP-005's seven `library_item` shelf facts) had
landed without the record moving, so `coursebook/contracts.py` says 25 and `contracts/rpc.v25.json`
declares 93 while the documents still quoted 23/83. Both were re-derived on `07976d8`; the ten added
methods and the seven added properties are additive, no v1-v23 method or required key moved.
`07976d8` is the CP-042 pack-shipping merge over `ea08a9a`, the docs-only gate 8 commits over
`7130109`, which carries the CP-049 audit re-pin, the CP-044 merge and `916e9c9`'s rig-recipe fix over
`19fec67` (itself the CP-020b merge over `3292679`, docs-only over `81e7642`). CP-042 added
`tests/test_pack_shipping_labels.py` (15 tests) and touched no `coursebook/`, `contracts/`,
`desktop/` or `audit/visual/m4-visual/` path, which is why v25/93, v14 and the module pin are
unchanged; it is also why the 3486 measured on `7130109` could not survive its merge.
The module pin and the M4 row above still describe `b9f4a19`; re-pinning them to the final demo
commit is the remaining freeze step, and `master` may advance again before submission.

## Pack round-trip, measured live on `bc9f607`

Gate 4 was re-driven as a live round trip rather than inferred from the suite. The measurement
commit is `bc9f6072fc0509f151a00e303243ea6f04b47bad` (the H-203 documentation merge over
`ab6dc7e`); `sha256sum desktop/plugin.js` on that commit is
`cd862140f0f03783f098326017db5225bb58b400e3595b321200480aa865c516`, the same module the M4 audit is
pinned to, so the pack bytes and the shipped Desktop half are the same objects the rest of this
document describes.

Two isolated homes were installed from this checkout (`scripts/install-local.sh --home <home>`,
admission gates PASS in both) and each was served by its own `hermes serve --isolated` backend, so
every call below crossed the mounted `POST /api/plugins/coursebook/rpc` route with a `cb.rpc` v20
envelope — no handler was imported into the measuring process. Store A imported
`japanese-affection-context-l0` 2.1.0 and `technical-demo-pack` 2.0.0 from archives built by the
repository's own deterministic writer; store B was a fresh home that received only the two archives
store A exported.

| Step | Store A (`44319`) | Store B (`44320`, fresh) |
| --- | --- | --- |
| `packs.intake` | `available: true`, `can_grant: true` | same route, same answer |
| `pack.preview` (Japanese) | `hashes_match: true`, 8 files, 46,425 expanded bytes, trust `integrity_verified` / `automated_checks_passed` / `model_assessed_support` | identical integrity and manifest |
| `pack.import` (Japanese, `fresh`) | `crs_9a4e2069…` / `enr_502aec74…` | a new course over re-imported bytes |
| `pack.import` (Japanese, `resume`) | returns the same `course_id`/`enrollment_id` — no duplicate course | — |
| `pack.import` (demo, `fresh`) | `crs_a978326b…` / `enr_32e88ca5…` | — |
| Structure after import | Japanese 4 objectives / 4 sections / 4 checks; demo 2 / 2 / 2; lesson pages carry 4 teaching + 3 media + 4 check segments (Japanese) and 2 + 1 + 2 (demo) | the same counts, segment for segment |
| `pack.export` attempt 1 | `content_hash` `sha256:5343526daa29a310df666ca8940d3908b5e507f34b0f83b04afb853cce5449f9`, 8 files, 40,363 bytes, artifact `art_6b4acc2a…` | Japanese export `sha256:5343526d…`, 40,363 bytes |
| `pack.export` attempt 2 (same store) | **identical** `content_hash`, identical `artifact_id`, identical archive sha256 `sha256:4aefd70828dac75dc0082c1b4a055208e674335634412cb07f54914bf48171c0` | demo export also identical on its two attempts: `sha256:ff5594a8…`, 6,516 bytes |
| Re-import input bytes | — | the exported archive is byte-for-byte the archive that was imported (`sha256:4aefd708…` both ways) |

The demo pack exported with `content_hash`
`sha256:ff5594a816570084de47465695f4e1025b4e5d19331589c4e421cebe2a73b95d` and archive
`sha256:747c61fdf39ec5e316608b9b144478a9a7b11fbbea484226544e98baf6f4276e` on both attempts and in
both stores. The export is deterministic because the writer sorts entries and stamps every one with a
fixed `1980-01-01` timestamp; a nondeterministic hash would have shown up as two different archive
digests, and did not.

`course.export` was probed on the pack-backed enrollment and refused with its contract's own typed
reason, `course_pack_backed` ("this course was imported from a pack; use pack.export for its stored
content") — recorded here so the naming in the gate row is not mistaken for a different method
having run.

### Media in the round trip

Four media objects were adopted in each store — the three Japanese links
(`content/cover-16x9.png`, `content/narration-polite-confession.mp3`,
`content/relationship-map.png`) and the demo cover. None was dropped, re-encoded or re-fetched: every
declared file's bytes hash to its manifest entry in both stores (all 8 Japanese files and all 5 demo
files), the artifact object store holds exactly those four content addresses in both stores, and the
`media[]` links carry a path, a section path and a caption only — no URL exists to re-fetch. The
lesson pages carry the media segments at the section the manifest names (2 on Japanese objective 1,
1 on objective 2).

**One defect, measured:** `artifact.get` cannot mint a download handle for a pack media artifact.
All three Japanese media rows answer `INTERNAL_ERROR` — `artifact.get handler returned a result
outside the contract at content_hash: '<64 hex>' does not match '^sha256:[a-f0-9]{64}$'` — because
`coursebook/artifacts.py` stores the digest unprefixed in the `artifacts` row while
`coursebook/domain.py:artifact_get` returns the row value verbatim. The export artifact is
unaffected (it is stored prefixed and returns its handle normally), which is why the round trip and
the export hash is green while the learner-facing media fetch is not. That failing step is why gate
4 stayed `[~]` after that pass; the repair is tracked separately and no product code was changed in
that pass.

### Re-run on the merged release tree `df052eaeced56ddd7238e4fb5804110ea7b36e95` — gate 4 closed

The repair landed as `160c522` (H-210-R1: `artifact.get` labels the stored content hash at every read
boundary; new rows are written labelled, legacy bare rows are normalised on read, and the
`(content_hash, kind)` dedupe matches both spellings) and was folded into this tree as `8fd4ec2`.
The round trip above was then re-driven, live, on
`df052eaeced56ddd7238e4fb5804110ea7b36e95` — `wt/h210r2-pack-recheck`, the merged release tree with
`desktop/plugin.js` still `cd862140f0f03783f098326017db5225bb58b400e3595b321200480aa865c516`. Two
isolated homes were installed from that checkout (`scripts/install-local.sh --home <home>`, admission
gates PASS in both), each served by its own `hermes serve --isolated` (`:44339`, `:44340`), and every
call crossed the mounted `POST /api/plugins/coursebook/rpc` route with a `cb.rpc` v20 envelope.

Every number in the `bc9f607` table above reproduced unchanged: `pack.preview` `hashes_match: true`
(Japanese 8 files / 46,425 expanded bytes, demo 5 files / 10,953), `pack.import` on both stores, the
`resume` replay returning the same `course_id`/`enrollment_id`, Japanese 4 / 4 / 4 and demo 2 / 2 / 2
objectives / sections / checks with lesson pages carrying 4 teaching + 3 media + 4 check segments
(2 + 1 + 2 for the demo), `pack.export` identical on both attempts and in the fresh store
(`content_hash` `sha256:5343526d…`, archive `sha256:4aefd708…` for the Japanese pack;
`sha256:ff5594a8…` / `sha256:747c61fd…` for the demo), the exported archive byte-for-byte equal to
the imported archive, and the same media bytes in both stores. `course.export` on the pack-backed
enrollment still refuses with `course_pack_backed`.

The step that failed on `bc9f607` now passes. `artifact.get` resolved every media segment of both
packs in both stores — four media links, ten live calls, six distinct digests including the two
export archives — each response contract-valid (`kind` in the enum, `mime` matching the contract
pattern, non-negative `bytes`, `sha256:<64 hex>` with exactly one prefix, a session-bound handle
under `/api/plugins/coursebook/artifacts/`), with the answered digest equal to the sha256 of the
bytes the handle returned and equal to the manifest's declared `media[]` digest:

| Pack media | `content_hash` answered = sha256 of the fetched bytes |
| --- | --- |
| Japanese `content/cover-16x9.png` (3,804 bytes) | `sha256:fc5760868a5b0bd3044b796cfec81353b25285bf618d0f9391289197f978f3a8` |
| Japanese `content/relationship-map.png` (6,948 bytes) | `sha256:8fb84ad3d7797f6b11febd8510b4e2fb5f17be3ed573fd31dcb8fb9468f1093d` |
| Japanese `content/narration-polite-confession.mp3` (22,272 bytes) | `sha256:dea7f196f147958a536b41c6ee8f2ff51558f56a74e7f4e8ab86f580db971349` |
| Demo `content/cover-16x9.png` (3,784 bytes) | `sha256:8e5af33049d3d4a7c01cc14e7611c38c568f773e0fb6de27afa8892fa88cd72a` |

The two export artifacts still answer a single-prefixed hash and a fetchable handle
(`sha256:4aefd708…`, 40,363 bytes and `sha256:747c61fd…`, 6,516 bytes) — no double prefix and no
behaviour change. The dual-spelling dedupe was reproduced live rather than assumed: after a
consistent database backup, the four pack media rows in the isolated store were rewritten to the
bare `<64 hex>` spelling they had before `160c522`; `artifact.get` answered the labelled form for
each, the stored spelling stayed bare, and two further imports of the same pack left the `artifacts`
table at six rows, absorbing the labelled writes through `ref_count` instead of adding siblings.

Evidence is committed beside this record at `audit/adversarial/h210r2-pack-roundtrip/`:
`assertions.json` (39 / 39 verdicts computed from the captures), the two backend captures, the
dedupe capture, the input manifest record, and the drivers. That capture is a wire measurement: no
Desktop window was opened, no provider spend was incurred, no media was generated, the gateway was
not restarted, and no M4 pin was touched.

### Frozen tree `b9f4a197e42e4f033298d94608fcb5b63640b094` — H-212 re-pin (2026-11-09)

The round trip above ran on `df052ea`. The frozen tree `b9f4a19` is that commit plus the H-210-R2
merge, and the diff between them is `docs/` and `audit/` only (`docs/RELEASE-EVIDENCE.md`,
`docs/SUBMISSION.md`, `audit/adversarial/h210r2-pack-roundtrip/`) — no product, test or contract
file moved. So the gate-4 captures remain a measurement of this tree's behaviour, and this pass
re-measured the release counts on `b9f4a19` rather than copying the `ab6dc7e` numbers:

| Check | Result on `b9f4a19` | Command |
| --- | --- | --- |
| Suite | `Ran 2747 tests in 410.301s`, `OK (skipped=1)` | `python3 -m unittest discover -s tests -t .` |
| Release gate | 4/4 checks PASS on a 2786-file export (admission, `node --check`, 26 desktop contract tests, runtime contracts) | `bash scripts/validate-plugin.sh` |
| Docs truth | `docs-truth: PASS` | `python3 scripts/check-docs-truth.py` |
| Shipped module | `cd862140f0f03783f098326017db5225bb58b400e3595b321200480aa865c516` — unchanged from the M4 audit pin | `sha256sum desktop/plugin.js` |

The M4 audit and its reproducibility run were **not** regenerated: their pin is the plugin sha, and
that sha is the same byte-for-byte on `ab6dc7e`, `df052ea` and `b9f4a19`. No new visual pass is
claimed. The adversarial state matrix was also not re-run on this tree; the row above says so.

## Reproducibility

`python3 scripts/m4v-repro-check.py` runs the whole audit twice in isolated scratch/out trees (separate
render pass, browser and screenshots) and fails on any difference except `generated_at`. The
reproducibility result is recorded in `docs/M4-VISUAL-MEDIA-AUDIT.md` and in `m4_repro` in
`docs/release-evidence.json`, pinned to the module it was run at. A reproducibility result is only a
claim about the module its `plugin_sha256` line names.

## What this pass did not measure

- No live Desktop window and no mounted backend trace on `b9f4a19`; `scripts/validate.sh` step 5 was
  not run here (it needs a mounted backend and an isolated home).
- `bash scripts/validate-plugin.sh` (the export admission gate) **was** re-run in this pass on
  `b9f4a19`: 4/4 checks PASS on a `git archive` export of 2786 files (admission and security scan,
  `node --check`, 26 desktop contract tests, `hermes plugins doctor`).
- No provider-spend generation, no demo capture, no recording.
- The pack round trip in the `bc9f607` and `df052ea` sections above ran against a mounted backend over
  HTTP, not inside a Desktop window: no rendered lesson was captured, and the media defect it found
  is a wire refusal (`artifact.get`), not a visual observation.
- The adversarial matrix was **not** re-run in this pass. The last measurement is the H-203 run on
  `ab6dc7e` (23/23 PASS, S13 BLOCKED by design); `b9f4a19` is not claimed to have been re-tested.
- The catalog entry **was** re-validated in this pass with the catalog validator from a `hermes-agent`
  checkout: `python3 scripts/validate_plugin_catalog.py catalog/coursebook.yaml` returned `OK: 1
  file(s) valid` (exit 0). Its pinned `sha` moved to this
  pass's docs commit, one commit above the measured code commit `b9f4a19`, because an entry cannot
  carry its own hash. That commit is now on `origin/master` (H-212 merged and pushed 2026-11-09), and
  all seven raw URLs (`docs_url`, `image` and the six `screenshots`) were fetched on 2026-11-09:
  HTTP 200 for each, with every PNG body hashing to the same sha256 as `docs/assets/<name>.png` at
  `61cdb03`. Gate 11 is `[x]` on that evidence; the pull request itself stays closed until gates 5, 7,
  9 and 10 close.

## Keeping this honest

`python3 scripts/check-docs-truth.py` fails when: the recorded plugin hash is not the hash of
`desktop/plugin.js` at the recorded commit; the recorded RPC method count or schema version disagrees
with the contract and `coursebook/db.py`; a document stops quoting the recorded values or still
carries a retired one (`1648`, `1682 tests`, `2,050 text nodes`, `635b7061`, `80725f6`); a cited
40-hex commit does not exist; a historical pin is attributed to the wrong commit; or the suite no
longer reports the recorded test count. `--skip-tests` runs everything except the suite.
