# AUDIT-INDEX — Coursebook audit evidence register

Owner: quill (H-19, board card `t_ec1d2c15`).
Created: 2026-11-07. Branch: `wt/harness-audit-index`, base `master` at `b4da6d9`
(`200e6d3` + the three harness-doc commits `2e3508f`, `a8d93b8`, `b4da6d9`).

Purpose: make every audit claim reproducible from a **commit hash**, not from a working-tree path.
A report is evidence only if the file it lives in resolves to a commit, the probes that produced it
resolve to a commit, and the finding's status names the card that owns the fix.

Rule for citing this index: quote the commit hash and the file path, never a worktree path. If a
file is not reachable with `git cat-file -e <hash>:<path>`, it is not evidence.

## 1. Report register

Every file below is tracked on this branch and resolves to a commit.

| report | what it is | introduced in | current content sha256 | verification |
|---|---|---|---|---|
| `docs/ADVERSARIAL-HARNESS-REVIEW.md` | audit round 1 — harness capability verdict (NO-GO as a general harness) | `2e3508f6007684951f81a66960e565e014171a78` | `405e552459f0ca8c993c9c2bde78cbc7fd7ba0988d9bdb621c5f31970e76b7bd` | `git cat-file -e 2e3508f:docs/ADVERSARIAL-HARNESS-REVIEW.md` |
| `docs/ADVERSARIAL-AUDIT-ROUND2.md` | audit round 2 — 14 deterministic probes, 10 findings | content from audit commit `9357c00d2631384728d1dc34f904b028653b0ec7`; imported verbatim in `23d1504e1d9302828807952885ba850e14a625a9` | `5cd5df77e4b5988c544385dfe6875b1aee02524814018fc65e6cf3a9f8bbe029` | `git cat-file -e 9357c00:docs/ADVERSARIAL-AUDIT-ROUND2.md`; `git cat-file -e 23d1504:docs/ADVERSARIAL-AUDIT-ROUND2.md` |
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

These results are recorded in the H-10 card handoff (`t_1efc158a`), not re-run by H-19. Two
honesty notes:

1. `tests/test_adversarial_round2.py` exists **only** at `9357c00` on `wt/harness-adversarial-2`
   (1 commit ahead of `200e6d3`; not merged to master). It resolves to a commit — it is not a
   working-tree file — but it is not in the master tree. Reproduce it with
   `git show 9357c00:tests/test_adversarial_round2.py > /tmp/test_adversarial_round2.py` or by
   checking out the branch. On this branch the suite is therefore 1040 tests, not 1054.
2. The 1054 count includes those 14 probes; 1040 is the master-tree count at `b4da6d9`.

### H-19 — this card, docs-only

```
python3 -m unittest discover -s tests -t .               # Ran 1040 tests, OK (156.7 s) at HEAD 90f338f
bash scripts/validate-plugin.sh --worktree               # 3/3 checks, 1217 files (pre-commit tree)
bash scripts/validate-plugin.sh                          # 3/3 checks on 90f338f, 1218 files (HEAD mode)
```

The 1040/1217 difference from the round-2 record is the docs files this card adds plus the absence
of the 14 probe tests; no product code changed in either card. The integrator re-runs the gate on
the merged tree — this record is a measurement on the branch, not a merge approval.

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
read from the `coursebook` board database on 2026-11-07.

| finding | severity | status | owning card | card state |
|---|---|---|---|---|
| P0-1 learner create flow never starts generation | P0 | OPEN | H-02 `t_867d3b52` | todo |
| P0-2 plan schema caps at 8 sections / forces 4 objectives; no `scope` | P0 | OPEN | H-03 `t_577ed286` | todo |
| P0-3 capability-policy inputs unreachable; locale mistaken for subject | P0 | OPEN | H-01 `t_f4f5b26a` (contract) + H-13 `t_543c0767` (threading) | running / todo |
| P0-4 deep research is a no-op; demo-sized budget | P0 | OPEN | H-04 `t_161d467f` | todo |
| P0-5 a normal course cannot export itself | P0 | OPEN | H-08 `t_901c8310` | todo |
| P0-6 a technical procedure lesson cannot carry the procedure lens | P0 | OPEN | H-06 `t_7a320d2f` | todo |
| P0-7 no live arbitrary-topic generation | P0 | OPEN | H-09 `t_ebc196db` | todo |
| P1-1 parent brief stored but mostly ignored by the planner | P1 | OPEN | H-07 `t_2f3cc647` | todo |
| P1-2 planner does not plan media; policy guesses from prose | P1 | OPEN | H-05 `t_7baa29e2` | todo |
| P1-3 check `count` / `independent_evidence` are decorative | P1 | **OPEN — UNMAPPED** | none of H-01…H-20 owns it | — |
| P1-4 authoring schemas are Japanese-shaped | P1 | OPEN | H-18 `t_8407ea22` (same defect as round-2 P2-7) | todo |
| P1-5 assessment breadth is narrow | P1 | OPEN | H-16 `t_3c5d969c` | todo |
| P1-6 rubric registry is static | P1 | **OPEN — PARTIAL** | H-16 `t_3c5d969c` decides breadth; rubric synthesis is in no card body | todo |
| P2-1 test matrix proves policy, not generation | P2 | OPEN | H-09 `t_ebc196db` | todo |
| P2-2 depth/locale not tested through the product surface | P2 | OPEN | H-04 `t_161d467f` + H-13 `t_543c0767` | todo |
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
| P0-1 validator-rejected plan is stored as an approvable `draft` | P0 | **OPEN** | H-12 `t_dba06898` | running; **no merged evidence** |
| P0-2 fetched excerpt is raw prompt content; invented prose URLs pass | P0 | OPEN | H-14 `t_031e287f` | running |
| P1-3 "independent validation" is prompt separation; same model upgrades support | P1 | OPEN | H-15 `t_d519643b` | running |
| P1-4 factual gate auto-waives when research is unavailable | P1 | OPEN | H-15 `t_d519643b` | running |
| P1-5 assessment breadth: three input formats only | P1 | OPEN | H-16 `t_3c5d969c` | todo |
| P1-6 flat `$0.75` ceiling, no cost-abort recovery | P1 | OPEN | H-17 `t_9a8543ae` | running |
| P2-7 Japanese-only scaffold triple; no direction field | P2 | OPEN | H-18 `t_8407ea22` | todo |
| P2-8 no prerequisite edges; adaptation is a state label | P2 | OPEN | H-20 `t_43ca17b8` | todo (conditional on H-03) |
| P2-9 green policy matrix supplies contract-rejected dials | P2 | OPEN | H-01 `t_f4f5b26a` + H-13 `t_543c0767` | running / todo |
| P2-10 round-1 review uncommitted at audit time | P2 | **FIXED** | H-19 `t_ec1d2c15` | this card |

### Why P0-1 is still open

The card is explicit: mark the plan-gate finding fixed by H-12 **only after its merged evidence
exists**. On 2026-11-07 the evidence does not exist:

```
git rev-list --count 200e6d3..wt/harness-plan-approval   -> 0
```

The H-12 branch is at the unmodified `master` merge base; the board card is `running`. A running
worker is not merged evidence. The finding therefore stays OPEN and continues to link to
`t_dba06898`. `docs/HARNESS-NEXT-CARDS.md` D-01/D-02/D-02b describe the same defect and its two
plan digests; they are covered by the same card and inherit the same OPEN status.

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
| D-06 stale CB-QA-10 claim survives in README | OPEN | H-11 `t_6f41e0b0` | truth pass; reconcile README/PRIVACY_EGRESS/ACCEPTANCE/REVIEW_CB014 |

D-06 also covers the `REVIEW_CB014.md` row for CB-QA-10 ("OPEN"). That row is **not** rewritten
here: the code may already project only `PUBLIC_CRITERION_FIELDS` (per
`tests/test_review_evidence.py`), but this card did not re-derive that, so the public record stays
as it is and H-11 owns the reconciliation.

## 7. Provenance checks this index relies on

Run on this branch; each must stay true or the index is stale.

```
git ls-files docs/ADVERSARIAL-HARNESS-REVIEW.md docs/ADVERSARIAL-AUDIT-ROUND2.md \
               docs/HARNESS-NEXT-CARDS.md docs/REVIEW_CB014.md docs/ACCEPTANCE.md
git log --format='%H %ad %s' --date=short -1 -- docs/ADVERSARIAL-HARNESS-REVIEW.md
git rev-list --count 200e6d3..wt/harness-plan-approval
git status --porcelain docs/
```

Rules enforced:

- **No claim cites a file that exists only in a worktree.** Every report above is tracked. The two
  branch-only artifacts this index names — `tests/test_adversarial_round2.py` and the audit-time
  base of `docs/ADVERSARIAL-AUDIT-ROUND2.md` — both resolve to `9357c00`, a commit on
  `wt/harness-adversarial-2`.
- **A branch is not a merge.** `wt/harness-plan-approval` at zero commits ahead is why H-12 is
  listed OPEN.
- **A prepared pack is not a topic proof.** No row above derives a harness claim from
  `bundled/packs/japanese-affection-context-l0`.
- **A green suite is not a gate.** 1040 tests pass with the empty-plan approvals asserted as
  success (D-02); the index therefore reports the count and the defect together.

## 8. What this index does not claim

- It does not claim any finding is fixed except P2-10, and it does not claim H-12 has landed.
- It does not re-run, re-grade or extend either audit; probe results are attributed to the card
  that produced them.
- It does not claim the harness is installable, demo-ready, or proven on an arbitrary topic. H-09
  (`t_ebc196db`) is the only card that can establish arbitrary-topic generation, and it is `todo`.
- It does not use the prepared Japanese pack as evidence for anything.
- It changes no product code, contract, schema, migration or test.
