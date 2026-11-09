# H-210-R2 — pack round trip on the merged release tree

Evidence-only re-drive of gate 4. The defect this pass had to clear was measured on `bc9f607` by
H-210 (`docs/RELEASE-EVIDENCE.md` keeps that record): `artifact.get` answered `INTERNAL_ERROR` for
every pack media artifact because the `artifacts` row stored a bare 64-hex digest while the contract
requires `sha256:<64 hex>`. H-210-R1 (`160c522`) repaired the read boundary; the supervisor fold
`8fd4ec2` placed it on this tree. This capture is the live re-run that flips the gate — not an
inference from that repair's unit tests.

## The measurement

| Item | Value |
| --- | --- |
| Measured commit | `df052eaeced56ddd7238e4fb5804110ea7b36e95` (`wt/h210r2-pack-recheck`, the merged release tree) |
| Code repair under test | `160c522` H-210-R1, an ancestor of the measured commit (folded in as `8fd4ec2`) |
| `desktop/plugin.js` at that commit | `cd862140f0f03783f098326017db5225bb58b400e3595b321200480aa865c516` — the same module the M4 audit is pinned to |
| Route | live HTTP `POST /api/plugins/coursebook/rpc?profile=`, `cb.rpc` v20 envelope; no handler imported into the measuring process |
| Backends | two isolated homes installed from this checkout (`scripts/install-local.sh --home <home>`, admission gates PASS in both), each served by its own `hermes serve --isolated`: store A on `:44339`, store B on `:44340` |
| Store A | imported `japanese-affection-context-l0` 2.1.0 and `technical-demo-pack` 2.0.0 from archives built by the repository's own deterministic writer |
| Store B | a fresh home that received only the two archives store A exported |
| Assertions | `assertions.json` — **39 / 39 PASS**; every verdict is computed from the captures, not restated |

## Every media segment, fetched and hashed

Both packs declare four media links in total (three Japanese, one demo). Each is one `media` segment
on a lesson page; the segment names the artifact, and the artifact was fetched through its
`artifact.get` download handle and hashed outside the backend. The same four resolve in both stores —
ten `artifact.get` calls, six distinct content digests (the four media files plus the two export
archives), none refused.

| Pack | Media path | Kind | `content_hash` answered | Bytes | sha256 of the fetched bytes |
| --- | --- | --- | --- | --- | --- |
| `japanese-affection-context-l0` | `content/cover-16x9.png` | `visual` | `sha256:fc5760868a5b0bd3044b796cfec81353b25285bf618d0f9391289197f978f3a8` | 3,804 | `sha256:fc5760868a5b0bd3044b796cfec81353b25285bf618d0f9391289197f978f3a8` |
| `japanese-affection-context-l0` | `content/relationship-map.png` | `visual` | `sha256:8fb84ad3d7797f6b11febd8510b4e2fb5f17be3ed573fd31dcb8fb9468f1093d` | 6,948 | `sha256:8fb84ad3d7797f6b11febd8510b4e2fb5f17be3ed573fd31dcb8fb9468f1093d` |
| `japanese-affection-context-l0` | `content/narration-polite-confession.mp3` | `audio` | `sha256:dea7f196f147958a536b41c6ee8f2ff51558f56a74e7f4e8ab86f580db971349` | 22,272 | `sha256:dea7f196f147958a536b41c6ee8f2ff51558f56a74e7f4e8ab86f580db971349` |
| `technical-demo-pack` | `content/cover-16x9.png` | `visual` | `sha256:8e5af33049d3d4a7c01cc14e7611c38c568f773e0fb6de27afa8892fa88cd72a` | 3,784 | `sha256:8e5af33049d3d4a7c01cc14e7611c38c568f773e0fb6de27afa8892fa88cd72a` |

Each response is contract-shaped: `artifact_id`, `kind` inside the enum, `mime` matching the
contract pattern, non-negative `bytes`, `content_hash` matching `^sha256:[a-f0-9]{64}$` with exactly
one prefix, and a `download` handle on `/api/plugins/coursebook/artifacts/<handle>` that requires the
session. The digest answered equals the digest of the bytes the handle returned, and the set of
digests fetched in a store is exactly the set both manifests declare — nothing extra, nothing
missing. These four are the digests the pack manifests list under `media[]`; the bodies are the
bundled pack bytes, not re-encoded copies.

The two export artifacts were fetched on the same route and behave as they did before the repair: a
single `sha256:` prefix, and a handle whose bytes hash to the archive on disk.

| Export | Artifact | `content_hash` answered | Bytes | sha256 of the fetched bytes |
| --- | --- | --- | --- | --- |
| Japanese | `art_7c6342ddeef5425ea19cff786dcedfff` | `sha256:4aefd70828dac75dc0082c1b4a055208e674335634412cb07f54914bf48171c0` | 40,363 | `sha256:4aefd70828dac75dc0082c1b4a055208e674335634412cb07f54914bf48171c0` |
| Demo | `art_56453b5d198446009db2c75d6743da80` | `sha256:747c61fdf39ec5e316608b9b144478a9a7b11fbbea484226544e98baf6f4276e` | 6,516 | `sha256:747c61fdf39ec5e316608b9b144478a9a7b11fbbea484226544e98baf6f4276e` |

## Round trip, unchanged by the repair

| Step | Store A | Store B (fresh) |
| --- | --- | --- |
| `pack.preview` Japanese | `hashes_match: true`, 8 files, 46,425 expanded bytes, `content_hash` `sha256:5343526d…` | identical integrity and manifest |
| `pack.preview` demo | `hashes_match: true`, 5 files, 10,953 expanded bytes, `content_hash` `sha256:ff5594a8…` | identical integrity and manifest |
| `pack.import` | Japanese `crs_252007eb…` / `enr_27534a2e…`; demo `crs_380690ea…` / `enr_9f01ec51…` | a new course over re-imported bytes |
| `pack.import` (resume, same pack) | returns the same `course_id` / `enrollment_id` — no duplicate course | — |
| Structure | Japanese 4 objectives / 4 sections / 4 checks, pages carrying 4 teaching + 3 media + 4 check segments; demo 2 / 2 / 2 with 2 + 1 + 2 | the same counts, segment for segment |
| `pack.export` ×2 (same store) | identical `content_hash`, identical `artifact_id`, identical archive bytes on both attempts | Japanese export from the fresh store matches `sha256:5343526d…`, 40,363 bytes |
| Archive sha256 | Japanese `sha256:4aefd70828dac75dc0082c1b4a055208e674335634412cb07f54914bf48171c0`, demo `sha256:747c61fdf39ec5e316608b9b144478a9a7b11fbbea484226544e98baf6f4276e` | the same two digests |
| Imported vs exported bytes | the Japanese export archive equals the imported archive byte-for-byte (`sha256:4aefd708…` both ways); demo likewise (`sha256:747c61fd…`) | — |

`course.export` on the pack-backed enrollment still refuses with its contract's typed reason
(`course_pack_backed`, "this course was imported from a pack; use pack.export for its stored
content"), recorded rather than hidden.

## Dedupe across both stored spellings

The repair introduced a second legitimate storage spelling: new rows are written labelled, rows that
predate it hold the bare digest. That was reproduced faithfully in isolated store A — after a
consistent database backup, the four pack media rows were rewritten from `sha256:<hex>` to the bare
`<hex>` they had before `160c522`, and the live route was driven against them:

- `artifact.get` on each bare row answers the labelled `sha256:<64 hex>` and a fetchable handle whose
  bytes hash to that digest — read-boundary normalisation, with the row's stored spelling untouched;
- two further `pack.import` calls of the same pack into that store left the `artifacts` table at six
  rows: no duplicate `(content_hash, kind)` in either spelling, and the three legacy Japanese media
  rows absorbed the labelled writes through `ref_count` (2 → 4) instead of gaining siblings;
- the same four legacy rows still resolve after those imports.

The backup of the pre-injection database and its sha256 are recorded in `evidence-dedupe.json`; the
injected rows are named there as injected.

## What this pass did and did not do

- Driven: the pack preview/import/export/re-import round trip, the media fetch and byte hash for
  every segment, the export artifact fetch, and the dual-spelling dedupe — all over the mounted HTTP
  route against two isolated backends on the commit named above.
- Not done: no Desktop window was opened (this is a wire measurement), no provider spend, no media
  was generated, no gateway was restarted, no M4 pin was touched, and nothing was pushed or
  published.

## Files

| File | What it is |
| --- | --- |
| `assertions.json` | 39 computed verdicts, the ten artifact resolutions, and the hash record |
| `evidence-storeA.json` | the raw store-A capture: runtime, intake, grants, previews, imports, exports, pages, artifact handles |
| `evidence-storeB.json` | the raw fresh-store capture: re-import of store A's exports, pages, media handles, re-export |
| `evidence-dedupe.json` | the dual-spelling capture: backup, injected legacy rows, reads, re-imports, row snapshots |
| `inputs/inputs.json` | the bundled pack manifests as built into archives, with declared media digests |
| `build_inputs.py`, `drive_a.py`, `drive_b.py`, `legacy_dedupe.py`, `assertions.py`, `h210r2lib.py`, `serve.sh` | the drivers, kept so the run can be repeated against another tree |
| `assertions-run.txt` | the assertion run's stdout: 39 PASS, exit 0 |
