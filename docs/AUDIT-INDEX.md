# AUDIT-INDEX — Coursebook audit evidence register

Owner: quill (H-19, board card `t_ec1d2c15`).
Created: 2026-11-07. Branch: `wt/harness-audit-index`, base `origin/master` at
`7af3bbd` (`200e6d3` + harness docs `2e3508f`, `a8d93b8`, `b4da6d9` + the merge of the round-2
audit `9357c00`). Board card states were read from the `coursebook` board on 2026-11-07 at that
base; they are volatile, so re-read the board before acting on a status column.

Purpose: make every audit claim reproducible from a **commit hash**, not from a working-tree path.
A report is evidence only if the file it lives in resolves to a commit, the probes that produced it
resolve to a commit, and the finding's status names the card that owns the fix.

Rule for citing this index: quote the commit hash and the file path, never a worktree path. If a
file is not reachable with `git cat-file -e <hash>:<path>`, it is not evidence.

**Staleness banner (H-11, 2026-11-07).** The finding ledgers in §4, §5 and §6 were read from the
`coursebook` board at base `7af3bbd`. Several rows have since changed: H-02, H-04, H-05, H-07, H-12
and H-13 are merged to `master`, and H-06/H-08/H-09/H-15/H-18/H-24 remain branch-only. The ledgers
below are left as the record of that base. For current claim-by-claim state use
`docs/HARNESS-STATUS.md`; do not read a row's `card state` column as live. A refreshed index exists
on `wt/harness-audit-refresh` (`512c5f6`) and is not merged.

## 1. Report register

Every file below is tracked on this branch and resolves to a commit.

| report | what it is | introduced in | current content sha256 | verification |
|---|---|---|---|---|
| `docs/ADVERSARIAL-HARNESS-REVIEW.md` | audit round 1 — harness capability verdict (NO-GO as a general harness) | `2e3508f6007684951f81a66960e565e014171a78` | `405e552459f0ca8c993c9c2bde78cbc7fd7ba0988d9bdb621c5f31970e76b7bd` | `git cat-file -e 2e3508f:docs/ADVERSARIAL-HARNESS-REVIEW.md` |
| `docs/ADVERSARIAL-AUDIT-ROUND2.md` | audit round 2 — 14 deterministic probes, 10 findings | master via merge `7af3bbd` (audit commit `9357c00`); provenance corrected on this branch | `5cd5df77e4b5988c544385dfe6875b1aee02524814018fc65e6cf3a9f8bbe029` | `git cat-file -e 7af3bbd:docs/ADVERSARIAL-AUDIT-ROUND2.md`; `git cat-file -e 9357c00:docs/ADVERSARIAL-AUDIT-ROUND2.md` |
| `docs/HARNESS-NEXT-CARDS.md` | board card index / DAG, card-to-finding mapping | `2e3508f` | `8846ffe641882a9ff66f99c31eda5e362e783041b9078d9464bf9c702be40f50` | `git cat-file -e 2e3508f:docs/HARNESS-NEXT-CARDS.md` (also amended in `a8d93b8`, `b4da6d9`, and this card) |
| `docs/REVIEW_CB014.md` | pre-harness adversarial security/state/a11y release review (cb.rpc v6) | `270edae6e7fd8e23a438e590860aa858316a5751` | `4a3b00205761eae6e298cc34c3197c868518a0e6ff98ea922ab4c02449c2a91b` | `git cat-file -e 270edae:docs/REVIEW_CB014.md` (amended in `8e11bd2`) |
| `docs/REVIEW_CB014-telemetry.md` | CB-014 tool-telemetry scope note | `51406ee5381e1725d7fb7be6d398e5acb8964e1c` | — | `git cat-file -e 51406ee:docs/REVIEW_CB014-telemetry.md` |
| `docs/ACCEPTANCE.md` | adversarial acceptance matrix with explicit verified/seam/blocked/pending vocabulary | `b9da9f397723971baef939959461b585d197856d` | `869918a97cb8e64f2c1daaaac9599904644049f138ceb6dd386ce1bb9a889d06` | `git cat-file -e b9da9f3:docs/ACCEPTANCE.md` (re-derived in `7d5a70c`) |
| `docs/CB016-RELEASE-VERIFICATION.md` | clean-export install and route-mount record | `7f80f35b8dec6bb995469dfb915e870cb35fe6f3` | `291b21564292301f07ed0c947a36657079f9762da9e9592a4a999b0ad497a266` | `git cat-file -e 7f80f35:docs/CB016-RELEASE-VERIFICATION.md` |
| `docs/CB017-RELEASE-VERIFICATION.md` | release record re-derived on merged master and re-pinned | `638eb6ba7443c927b5ca21958f956365281a2063` | `55f9b3f07b49dd39dc817181cbddab818fda4ef9335203420b279eb545c79a3f` | `git cat-file -e 638eb6b:docs/CB017-RELEASE-VERIFICATION.md` (amended in `6eb93c2`) |
| `docs/M4-VISUAL-MEDIA-AUDIT.md` | M4-QA visual/accessibility/media truth gate (62 painted frames) | `2b37b5b` | `6f4a109f1fc0f6aae5fe5ecea0ae5c58d6fab5438af629fb32c3591bad606689` | `git cat-file -e 2b37b5b:docs/M4-VISUAL-MEDIA-AUDIT.md` (amended in `27a2e40`) |
| `docs/DEMO.md` | honest demo status; states the prepared pack proves one pack only | `5ad682e` | `27651b66410b54a6381430ae9945196ff78199f74cd0b75c188280b376d084ba` | `git cat-file -e 0e1aca1:docs/DEMO.md` |

`REVIEW_CB014.md` and `ACCEPTANCE.md` are included because the harness audits inherit their
defect ids (CB-QA-09…13) and their evidence vocabulary. They are **pre-harness** records at
cb.rpc v6 on candidates `e5b9686` / `f4a42f3`; they are not evidence about the harness slice.

## 2. Evidence classes

Every row in the finding ledger carries exactly one class. Mixing them is the failure this index
exists to prevent.

- **live** — a command or capture taken against a running process on a named commit: a backend on a
  port, the Desktop over CDP, an installed plugin in a dedicated test home. Live evidence names the
  port/home/commit and stores its raw output under `docs/` or `docs/*-shots/`.
  In this register: `CB016-RELEASE-VERIFICATION.md`, `CB017-RELEASE-VERIFICATION.md`,
  `M4-VISUAL-MEDIA-AUDIT.md`, and the live half of `REVIEW_CB014.md` (CB-QA-09 reproduction in
  `~/.hermes/coursebook-test/home`, backend `127.0.0.1:44219`, CDP `127.0.0.1:9337`).
- **fixture** — deterministic Python probes with scripted generator/validator doubles and
  hand-authored plan/lesson fixtures, run headless. A fixture result is a property of the harness
  code, not of a model.
  In this register: `ADVERSARIAL-HARNESS-REVIEW.md` (static reading + inline probes at `200e6d3`),
  `ADVERSARIAL-AUDIT-ROUND2.md` (`tests/test_adversarial_round2.py`, 14 probes at `9357c00`), and
  the `seam` rows of `ACCEPTANCE.md`.
- **prepared-pack** — the bundled Japanese L0 pack (`bundled/packs/japanese-affection-context-l0`,
  imported by `scripts/seed-demo-course.py`). It proves a governed loop over **one** prepared pack
  and is **never** proof of arbitrary-topic generation. `docs/DEMO.md` says so itself.

No finding in either audit rests on prepared-pack evidence. Where a report says "not used as
evidence", the index repeats that as a claim about that report only.

## 3. Reproduction commands

Commands are quoted as the reports recorded them. A result is only valid at the commit named next
to it; re-running on a later commit produces a new claim.

### Round 1 — `docs/ADVERSARIAL-HARNESS-REVIEW.md` @ `200e6d3`

```
python3 -m unittest discover -s tests -t .     # Ran 1040 tests, OK (101.1 s)
node --check desktop/plugin.js                 # syntax OK
```

The review's inline probes (`policy._normalise_domain(None, locale)`, `research.derive_queries` at
`survey`/`working`/`deep`/`thorough`) were run from a Python REPL against the same tree; the report
records the measured output but not a literal one-liner. Treat the outputs as reported values, not
as a copy-pasteable proof. Limit recorded here rather than papered over.

### Round 2 — `docs/ADVERSARIAL-AUDIT-ROUND2.md` @ `9357c00`

```
python3 -m unittest tests.test_adversarial_round2 -v     # 14 tests, OK
python3 -m unittest discover -s tests -t .               # Ran 1054 tests, OK (149.9 s)
bash scripts/validate-plugin.sh                          # 3/3 checks, 1216 files, clean export
```

These results are recorded in the H-10 card handoff (`t_1efc158a`). The report and its probe file
are now in master: merge `7af3bbd` brings `9357c00`'s `tests/test_adversarial_round2.py` (14 tests)
and `docs/ADVERSARIAL-AUDIT-ROUND2.md` onto `origin/master`. H-19 re-ran the probe file on its
rebased branch (`python3 -m unittest tests.test_adversarial_round2` -> 14 tests, OK) and the full
suite (1054 tests, OK). H-19's first run reported 1040 tests because it started from `b4da6d9`,
before that merge landed; the 1054 count supersedes it.

### H-19 — this card, docs-only

```
python3 -m unittest tests.test_adversarial_round2       # 14 tests, OK
python3 -m unittest discover -s tests -t .              # Ran 1054 tests, OK (156.1 s)
bash scripts/validate-plugin.sh                         # 3/3 checks on 215e35f, 1219 files
```

No product code changed in this card. The integrator re-runs the gate on the merged tree — this
record is a measurement on the branch, not a merge approval.

### Pre-harness release gate — `docs/REVIEW_CB014.md` @ `f4a42f3`, `docs/ACCEPTANCE.md` @ `e5b9686`

```
bash scripts/test.sh                              # Ran 636 tests, OK; plugin.js syntax OK; exit 0
python3 tests/adversarial/attack_state.py         # 21 PASS, 1 FAIL (S07/CB-QA-10), 1 BLOCKED
python3 tests/adversarial/attack_packs.py         # 21/21 PASS
bash probes/p1_ids.sh … bash probes/p7_authority.sh   # per-row results in ACCEPTANCE.md
```

Raw outputs are tracked: 72 files under `probes/`, plus `tests/adversarial/evidence/*.json`.
These prove the kernel at cb.rpc v6, not the harness loop.

## 4. Finding ledger — round 1

Status is the state of the **merged** evidence, not of a branch or a running worker. Card state was
read from the `coursebook` board on 2026-11-07 at base `7af3bbd`. A `done` card means its worker
finished; it does **not** mean the branch merged.

| finding | severity | status | owning card | card state |
|---|---|---|---|---|
| P0-1 learner create flow never starts generation | P0 | OPEN | H-02 `t_867d3b52` | running |
| P0-2 plan schema caps at 8 sections / forces 4 objectives; no `scope` | P0 | OPEN | H-03 `t_577ed286` | running |
| P0-3 capability-policy inputs unreachable; locale mistaken for subject | P0 | OPEN | H-01 `t_f4f5b26a` (contract) + H-13 `t_543c0767` (threading) | done, unmerged (`8cbaab3`) / ready |
| P0-4 deep research is a no-op; demo-sized budget | P0 | OPEN | H-04 `t_161d467f` | running |
| P0-5 a normal course cannot export itself | P0 | OPEN | H-08 `t_901c8310` | todo |
| P0-6 a technical procedure lesson cannot carry the procedure lens | P0 | OPEN | H-06 `t_7a320d2f` | todo |
| P0-7 no live arbitrary-topic generation | P0 | OPEN | H-09 `t_ebc196db` | todo |
| P1-1 parent brief stored but mostly ignored by the planner | P1 | OPEN | H-07 `t_2f3cc647` | running |
| P1-2 planner does not plan media; policy guesses from prose | P1 | OPEN | H-05 `t_7baa29e2` | todo |
| P1-3 check `count` / `independent_evidence` are decorative | P1 | **OPEN — UNMAPPED** | none of H-01…H-20 owns it | — |
| P1-4 authoring schemas are Japanese-shaped | P1 | OPEN | H-18 `t_8407ea22` (same defect as round-2 P2-7) | todo |
| P1-5 assessment breadth is narrow | P1 | OPEN | H-16 `t_3c5d969c` | todo |
| P1-6 rubric registry is static | P1 | **OPEN — PARTIAL** | H-16 `t_3c5d969c` decides breadth; rubric synthesis is in no card body | todo |
| P2-1 test matrix proves policy, not generation | P2 | OPEN | H-09 `t_ebc196db` | todo |
| P2-2 depth/locale not tested through the product surface | P2 | OPEN | H-04 `t_161d467f` + H-13 `t_543c0767` | running / ready |
| P2-3 procedure/media evidence is static or fixture | P2 | OPEN | H-09 `t_ebc196db` | todo |

Two round-1 findings have no owning card. They are recorded as open, and neither is allowed to be
described as scheduled: **P1-3** (one check per section regardless of the plan's declared `count`)
and **P1-6** (no mechanism to synthesize and validate a new rubric profile). Routing them is an
Atlas decision, not something this docs card can assign.

## 5. Finding ledger — round 2 (`docs/ADVERSARIAL-AUDIT-ROUND2.md`)

The report proposed its own `H-11`…`H-18` labels. Those labels **collide** with the board keys; the
board keys are authoritative and are the only ids used here (mapping kept in
`docs/HARNESS-NEXT-CARDS.md` §"Second wave").

| finding | severity | status | owning card | card state |
|---|---|---|---|---|
| P0-1 validator-rejected plan is stored as an approvable `draft` | P0 | **OPEN** | H-12 `t_dba06898` | board `done`; branch `4b5f3b1` **unmerged** |
| P0-2 fetched excerpt is raw prompt content; invented prose URLs pass | P0 | OPEN | H-14 `t_031e287f` | running |
| P1-3 "independent validation" is prompt separation; same model upgrades support | P1 | OPEN | H-15 `t_d519643b` | running |
| P1-4 factual gate auto-waives when research is unavailable | P1 | OPEN | H-15 `t_d519643b` | running |
| P1-5 assessment breadth: three input formats only | P1 | OPEN | H-16 `t_3c5d969c` | todo |
| P1-6 flat `$0.75` ceiling, no cost-abort recovery | P1 | OPEN | H-17 `t_9a8543ae` | running |
| P2-7 Japanese-only scaffold triple; no direction field | P2 | OPEN | H-18 `t_8407ea22` | todo |
| P2-8 no prerequisite edges; adaptation is a state label | P2 | OPEN | H-20 `t_43ca17b8` | todo (conditional on H-03) |
| P2-9 green policy matrix supplies contract-rejected dials | P2 | OPEN | H-01 `t_f4f5b26a` + H-13 `t_543c0767` | done, unmerged (`8cbaab3`) / ready |
| P2-10 round-1 review uncommitted at audit time | P2 | **FIXED** | H-19 `t_ec1d2c15` | this card |

### Why P0-1 is still open

The card is explicit: mark the plan-gate finding fixed by H-12 **only after its merged evidence
exists**. Observed on 2026-11-07 at base `7af3bbd`:

```
git rev-list --count origin/master..wt/harness-plan-approval          -> 1
git log -1 --format='%h %s' wt/harness-plan-approval                  -> 4b5f3b1 H-12: fail-closed plan approval
git merge-base --is-ancestor wt/harness-plan-approval origin/master   -> exit 1 (NOT an ancestor)
```

The board card `t_dba06898` is now `done`, and its branch carries one commit, `4b5f3b1` (6 files,
+743/−6: `coursebook/domain.py`, `coursebook/generation.py`, `docs/PLAN-APPROVAL.md`, three test
files). None of that is merged into `origin/master`. A card marked done and a commit on a branch
are **not** merged evidence, so the finding stays OPEN and continues to link to `t_dba06898`.
When H-12's merge commit is on `origin/master` and the merged tree passes the gate, this row flips
to FIXED with that merge hash recorded here. `docs/HARNESS-NEXT-CARDS.md` D-01/D-02/D-02b describe
the same defect and its two plan digests; they are covered by the same card and inherit the same
OPEN status.

### P2-10 closure, precisely

The round-1 review was untracked when Sable audited. It is committed in
`2e3508f6007684951f81a66960e565e014171a78`. The round-2 report's Method section and its P2-10
status line were corrected on this branch; no finding text, evidence or severity was changed.

## 6. Card index findings (D-series)

`docs/HARNESS-NEXT-CARDS.md` records seven deeper findings discovered while seeding the board.
They are not a separate audit, but they do carry reproducibility weight, so their status is pinned
here rather than left to prose.

| id | status | owning card | note |
|---|---|---|---|
| D-01 plan approval is advisory, not fail-closed | OPEN | H-12 `t_dba06898` | same defect as round-2 P0-1 |
| D-02 the green suite encodes the defect | OPEN | H-12 | two kernel tests approve an empty plan |
| D-02b two plan digests, one approval | OPEN | H-12 + H-02 | generation digest ≠ kernel digest |
| D-03 the plan job drops contract inputs | OPEN | H-13 `t_543c0767` | `run_plan_job` reads goal/recipe/dials/locale only |
| D-04 "adaptation" is a state transition | OPEN | H-03 `t_577ed286` + H-20 `t_43ca17b8` | do not market it as adaptive teaching |
| D-05 validation independence is structural only | OPEN | H-15 `t_d519643b` | same as round-2 P1-3 |
| D-06 stale CB-QA-10 claim survives in README | **FIXED** | H-11 `t_6f41e0b0` | re-derived: S07 probe PASS on `498b1da`, `evidence.py` projects `PUBLIC_CRITERION_FIELDS`; README, `PRIVACY_EGRESS.md` and `SUBMISSION.md` §7 corrected, historical reports untouched — `docs/HARNESS-STATUS.md` §4 |

D-06 also covered the `REVIEW_CB014.md` row for CB-QA-10 ("OPEN"). That row is **not** rewritten,
because it is the record of `f4a42f3`. The re-derivation happened on `master` at `498b1da` and is
recorded in `docs/HARNESS-STATUS.md` §4: `python3 tests/adversarial/attack_state.py` →
`scenario=S07 verdict=PASS … secret_present=False`, `SUMMARY total=22 fail=0 pass=22`.
`ACCEPTANCE.md`'s table is likewise left as its own commit's record (`e5b9686`).

## 7. Provenance checks this index relies on

Run on this branch; each must stay true or the index is stale.

```
git ls-files docs/ADVERSARIAL-HARNESS-REVIEW.md docs/ADVERSARIAL-AUDIT-ROUND2.md \
               docs/HARNESS-NEXT-CARDS.md docs/REVIEW_CB014.md docs/ACCEPTANCE.md
git log --format='%H %ad %s' --date=short -1 -- docs/ADVERSARIAL-HARNESS-REVIEW.md
git rev-list --count origin/master..wt/harness-plan-approval
git merge-base --is-ancestor wt/harness-plan-approval origin/master; echo $?
git status --porcelain docs/
```

Rules enforced:

- **No claim cites a file that exists only in a worktree.** Every report above is tracked, and the
  round-1 and round-2 reports plus the round-2 probe file now resolve to commits on `origin/master`
  (`2e3508f`, `7af3bbd` / `9357c00`). The only branch-only commits this index names are the two
  unmerged product commits H-12 (`4b5f3b1`) and H-01 (`8cbaab3`), cited solely to show why their
  findings are still OPEN.
- **A branch is not a merge, and a done card is not a merge.** `wt/harness-plan-approval` carries
  `4b5f3b1` but is not an ancestor of `origin/master`; that is why H-12 is listed OPEN even though
  its board card reads `done`. The same holds for H-01 (`8cbaab3`).
- **A prepared pack is not a topic proof.** No row above derives a harness claim from
  `bundled/packs/japanese-affection-context-l0`.
- **A green suite is not a gate.** 1054 tests pass at `7af3bbd` with the empty-plan approvals
  asserted as success (D-02); the index therefore reports the count and the defect together.

## 8. Harness-slice evidence register (branch evidence, not merged)

The harness slice produced evidence packets that do not live on `master`. They are registered here
so a reader can reach them by commit, and so no one mistakes them for merged state. Status of the
claims themselves: `docs/HARNESS-STATUS.md`.

| card | branch | commit | evidence file | reproduction | merged? |
|---|---|---|---|---|---|
| H-06 procedure authoring | `wt/harness-procedure-author` | `00b502f` | `docs/M4-PROCEDURE-LAYOUT.md` (§authoring), `tests/test_procedure_authoring.py` | `git show 00b502f:tests/test_procedure_authoring.py` | no |
| H-08 general authored export | `wt/harness-authored-export` | `c9c6cec` | `docs/PACK-AUTHORING.md` §5, `tests/test_course_export.py` | `git show c9c6cec:docs/PACK-AUTHORING.md` | no |
| H-09 arbitrary-topic end-to-end proof | `wt/harness-e2e-proof` | `4dd0f18` content, `111c7e9` tip | `docs/HARNESS-E2E.md`, `audit/adversarial/harness-e2e/STATUS.md`, `evidence/*.json` | `PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py` on that branch | no |
| H-15 validator independence | `wt/harness-validator-independence` | `833e335` | decision doc on the branch | `git log -1 833e335` | no |
| H-18 locale scaffolds | `wt/harness-locale-scaffolds` | `2aca201` | scaffold schema + refreshed M4 frames | `git log -1 2aca201` | no |
| H-24 rubric extensibility | `wt/harness-rubric-extensibility` | `491443a` | decision doc on the branch | `git log -1 491443a` | no |

Rules that apply to this register:

- A branch commit is not a merge. Verify with
  `git merge-base --is-ancestor <commit> master; echo $?` — `1` means it is not on the merged tree.
- H-09's model half is a **recorded transcript** (`labels.model` in each `evidence/*.json`), and its
  research is a **recorded page** served through the real seam. 0 provider calls, $0 spend. It
  proves the pipeline, not model or research quality.
- No row here uses the prepared Japanese pack as evidence.

## 9. What this index does not claim

- It does not claim any finding is fixed except P2-10 and D-06, and it records H-12 as merged to
  `master` only because `plan_approve` on this tree refuses empty plans and binds a durable
  validation pass to the content hash (`coursebook/domain.py:678`); the ledger rows above still
  describe `7af3bbd`.
- It does not re-run, re-grade or extend either audit; probe results are attributed to the card
  that produced them. The one re-derivation it does record is CB-QA-10 (S07) in
  `docs/HARNESS-STATUS.md` §4, because four live documents carried a stale present-tense claim.
- It does not claim the harness is installable, demo-ready, or proven on an arbitrary topic. H-09
  (`t_ebc196db`) is the only card that speaks to arbitrary-topic generation, its evidence is on
  branch `wt/harness-e2e-proof` (`111c7e9`) with recorded transcripts, and it is not merged.
- It does not use the prepared Japanese pack as evidence for anything.
- It changes no product code, contract, schema, migration or test.
