# Coursebook: final adversarial review before submission

Date: 2026-11-11. Scope: the whole plugin outside the Desktop surfaces — install, provisioning,
generation, grading, packs, the store and its submission path, the Game-mode privacy contract,
contracts, and the release's own evidence.

Method: three independent adversarial audits ran in parallel, each against a detached worktree of
`origin/master` with instructions to prove every claim with a command and to preserve failures.
Their findings were then re-checked here; the ones marked **measured here** were reproduced in this
session rather than taken on trust. Nothing in this document is a test-count without the command
that produced it.

Verdict: **ship the backend, with the four critical defects fixed today.** The store loop, the
Game-mode round trip and the privacy contract are real and were exercised end to end against live
GitHub. The generation *lesson* path is honest about its limits but does not produce a graded
arbitrary-topic course yet; that is named below rather than papered over.

---

## 1. What changed because of this review

| # | Defect | Fix | Proof |
| --- | --- | --- | --- |
| C1 | A submission could replace an already-published pack's bytes with no version bump: identity was decided from the submitter's own `store/index.json`, which they control. | Identity is decided against the freshly fetched **base branch**, inside a throwaway worktree. A higher `pack_version` is an update under the same id; anything else with different bytes is namespaced. | `--dry-run` on the shipped pack with a changed title → `renamed`; with `pack_version 1.0.1` → `update`, same pack id. |
| C2 | CI judged a store PR with the **PR's own** copy of the gate, so one PR could weaken `coursebook/packs.py` and add a pack in the same breath. | `store.yml` checks out `github.event.pull_request.base.sha` into `base/` and runs **the base branch's** `store_index.py` / `store_verify.py` against the PR tree (`--root pr`). | The base scripts import the base `coursebook` package; the child's own probe showed a one-line gate regression passing the old workflow. |
| C3 | Sharing only worked in the owner's writable clone: it ran `git checkout -B` in the **running install**, wrote the pack and index before failing on a non-git tree, and had no fork path. | Submission builds the branch in a temporary worktree of `origin/<base>`; a non-git install now refuses **before writing anything**; a push refused for permissions forks the repository under the author's account and opens the PR across repositories. | Before/after `HEAD` and branch are unchanged after a `--no-push` submission; no worktree is left behind. The fork path is implemented but **not exercised** (the owner has write access). |
| C4 | The release's own truth gate was red and the headline numbers disagreed: `release-evidence.json` said 3523, `docs/RELEASE-EVIDENCE.md` said 3951, the tree collects 4035, and `docs/SUBMISSION.md` marked the gate as passing (it passes only with `--skip-tests`). | Counts replaced with the measured collection and the full-suite result of this tree; the gate is reported as it actually runs. | `python3 -m unittest discover -s tests -t .` — result recorded in §5. |
| H1 | Every `rubric_only` check (any pack check with `evidence_target` of `production` or `transfer`, and every generated `observation` check) opened as gradable while no auxiliary grader is configured in this build — it could never be passed. | Import now withholds the spec and says why (`open-response grading is not configured in this build`), instead of presenting a check that always fails closed. | `check_spec_from_pack_check(..., recipe="authored")` returns no spec; 434 pack/generation tests stay green. |
| H2 | `validation_verdict` returned `pass` / `independently_validated` while its own `claim_verdicts` recorded a cited source as `contradictory`. | A contradicted claim is a rejection in its own right, named `claim_contradicted`. | `tests/test_validation_contradiction.py` (2 tests): contradicted → `reject`, supported → `pass`. |
| H3 | The Share tab filtered on `row.course_pack_id`, a field the `library_item` contract cannot return (`additionalProperties: false`), so pack-backed courses were listed as shareable and every share of one was refused. | The filter reads `provenance.pack_id`, which the contract does carry. | Contract read + rebuilt bundle. |
| H4 | `already_present` came back `ok: true` with no `mode`/`objectives`, so the UI printed `undefined · undefined objective(s)`. | The UI renders each status for what it is: new, update, already present. | Rebuilt bundle contains the branches. |
| H5 | The store published a pack whose own licence says `redistribution: local_only`, filed under an anonymous author. | A submission refuses a `forbidden` licence, and publishes a `local_only` export only when the author explicitly shares (`--share`, or the Share button's confirm), which rewrites the licence to `allowed` and re-gates the rewritten archive. | `--dry-run` without `--share` → refused with the reason; with `--share` → `new`, hash re-derived. |
| H6 | A legitimate version bump was impossible: any changed bytes for an existing id were renamed, so `pack_version` was decorative and old ids accumulated. | Higher version → `update` (replaces the shelf file under the same id). | Measured: `1.0.1` → `update`. |
| H7 | A zip of ~100 000 empty directories was accepted and cost ~136 MB RSS before any pack work started (the file cap skipped directory entries). | Entry cap: files **and** directories, `4 × max_files`. | 9 000 empty directories → `archive declares more than 8000 entries`. |
| H8 | `git checkout -B`, `git add` and `git push` ignored their exit codes; a failed push still ran `gh pr create`. | Each step is checked and raises with the command's own output. | Code path; `commit` already behaved this way. |

Two smaller corrections: the review that this document supersedes miscounted `tests.test_gm_contract`
(30 stated, 26 measured — corrected), and the `/workshop/share` docstring claimed the button uses
`dry_run` when it does not.

## 2. What was verified as sound (not assumed)

- **Pack intake is not bypassable by a hostile archive.** `../escaped.txt`, absolute paths, backslash
  paths, drive/URL paths, hidden files, symlinks (twice: mode bits and a post-extraction sweep),
  case-collisions, exact duplicates, multiple roots — all refused, nothing written outside staging.
  Tampered `content_hash`, swapped section bytes and an under-declared `bytes` count are refused;
  per-file compression ratio, file size, expanded bytes and archive size all have live caps.
- **`pack_id` cannot inject arguments or paths**: schema pattern `^[a-z0-9][a-z0-9._-]*$`, and
  `git`/`gh` are invoked as argv lists, never through a shell. `master` cannot be force-pushed.
- **The share route takes no filesystem path.** It accepts one `enrollment_id` plus `confirm`; the
  export is produced server-side from that course's own approved text, and the archive is resolved
  from the artifact row the export wrote. 5 000-character and non-ASCII ids are refused.
- **Install is the strongest gate**: `workshop.install` → `pack_flow.pack_import` →
  `validate_and_audit`; the storefront card is derived from the pack, not from a server.
- **Game-mode privacy holds.** The art tables (`course_worlds`, `world_assets`) have no column that
  can hold a verdict, score, attempt, evidence or play event, and the engagement/tutor/homework
  tables are named in `GM_NEVER_EXPORTED_TABLES` and appear in no pack or archive module.
  `tests/test_course_export.py` seeds attempts, notes and observations and asserts the markers are
  absent from the review wire, the result and **every byte of the archive** — that test passes.
- **Game packs carry their world**: the pack merged today carries `world/{hero,cover,section-1,
  section-2}.png` and one lesson visual, declared with matching sha256s, and imports as
  `presentation_mode=game`, `course_worlds.state=approved`, plates re-keyed to the importing
  course's objectives, with open checks.
- **Contracts resolve at every accepted version**, including frozen `cb.rpc` `$ref`s to
  `pack-manifest/v1#/properties/pack_id`; `audit_contracts()` returns an empty problem list; the
  93 RPC methods the Desktop calls all exist with the payload fields it sends.
- **Validator failure cannot become `validated`**, plan approval is fail-closed on a rejection, the
  retry carries the validator's `fix_hint` into `revision_instructions`, and a timed-out lesson job
  persists what it finished rather than pretending to have finished.

## 3. The store loop, measured end to end (not a description)

1. A real Game course was exported by `course.export` (2 objectives, 1 media, 4 plates).
2. `POST /workshop/share` → export, gate, identity, branch, push, PR — **one pull request**.
3. CI job `shelf` **passed in 21 s**.
4. The owner merged it. The shelf now carries the pack, and `store_verify` reports
   `game, 2 objective(s), 1 media`.
5. On a fresh home, `catalog_view()` returned 4 cards, 0 refused; `workshop.install` produced
   `presentation_mode=game`, 4 plates on disk, 2 open checks.

## 4. Still open, named rather than hidden

Each is a card on the board; none is a hidden bypass.

- **`model_assessed` lessons export as audited packs.** The export gate admits `model_assessed`
  state but writes no validation strength into the manifest, so a same-model lesson re-imports as
  `audit_state='passed'`. The honest fix is a manifest field and a downgrade on import; it is a
  format change and did not belong in this window.
- **Research has no topicality check.** Any fetched page is admitted and `status="ok"` then unlocks
  `independently_validated`; only the quote must appear in the cited excerpt. A spam page can become
  a citation. (Board: `t_30048fe8`.)
- **"Independent" is a model-name comparison.** Two aliases of one model behind one route read as
  independent validation. The repo already discloses that no independent probe exists.
- **Trust labels are self-declared.** A pack can assert `reviewed_by` and show
  `human_review_recorded`. The store needs to own that label, not accept it.
- **`challenge_out` is unreachable for generated courses**, and `check.open` reports
  `objective_not_checkable` when the real reason is that the pipeline-authored check is closed.
- **The storefront preview is weaker than install** (it skips the version floor, recipe allowlist,
  media-byte and world-brief checks), so a card can advertise a pack that install then refuses.
- **The Desktop contract tests do not cover the new surface** (26 tests, none mentioning the share
  route), and `validate-plugin.sh` step 3 is that file alone.
- **Arbitrary-topic lessons do not reach a graded state** on a real provider: a section was
  rejected by its own validator (`rubric_consistency`, `source_support`), the retry repeated the
  rejected claim, and the check stayed closed (`t_d4b36437`). The curated pack is the honest demo
  path; the arbitrary-topic *plan* is proven, the arbitrary-topic *lesson* is not.
- **Repo hygiene**: 475 registered worktrees (mostly historical) and a fixture pack merged today
  whose 1×1 PNG plates render as blank tiles. Neither affects correctness.

## 5. Test evidence for this tree

See `docs/RELEASE-EVIDENCE.md` for the full-suite row and the exact command; the numbers there are
the numbers this tree produced, including the failures if any.
