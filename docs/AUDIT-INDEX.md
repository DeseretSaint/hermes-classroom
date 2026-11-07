# AUDIT-INDEX — Coursebook audit evidence register

Owner: quill. Created by H-19 (`t_ec1d2c15`) at `99da48a` on `wt/harness-audit-index`; refreshed by
H-31 (`t_1c9d0ba6`) on `wt/harness-audit-refresh`, based on `master` at `f17ec54`
(`2e57efa` + the card/review corrections `31b3132`, `6d062e1`, `db5662c`, `f17ec54`, on top of the
merged H-01, H-02, H-03, H-12, H-13 and H-14 work).

Purpose: make every audit claim reproducible from a **commit hash**, not from a working-tree path.
A report is evidence only if the file it lives in resolves to a commit, the probes that produced it
resolve to a commit, and the finding's status names the card that owns the fix.

Rule for citing this index: quote the commit hash and the file path, never a worktree path. If a
file is not reachable with `git cat-file -e <hash>:<path>`, it is not evidence.

## 0. How to read this after merges

Three things are routinely confused. They are not the same:

- **A card being `done` is not a merge.** `done` means the assigned worker finished and reported.
  The branch may still be unmerged. Every ledger row below therefore names a commit *and* says
  whether that commit is an ancestor of `master`.
- **A branch tip is not merged evidence.** A finding flips to FIXED only when its fix is an
  ancestor of `master` (`git merge-base --is-ancestor <commit> master` exits 0) and the merged tree
  passed the frozen gate. A branch-only fix stays OPEN, marked "done, unmerged".
- **Every row must name a commit.** If a row cannot name a commit, its status is `UNMAPPED`, not
  "open" and not "in progress". A status without a hash is an assertion, not evidence.

Two consequence notes for this revision:

- H-19 (`t_ec1d2c15`) is `done` but `wt/harness-audit-index` (`99da48a`) is **not merged**. This file
  reached `master` only through this H-31 branch, and this branch is also unmerged until the
  integrator lands it. A reader on `master` who cannot see this file should treat H-19 as
  branch-only and ask the integrator for its state.
- H-12's card body cites `903a606` as its "merge commit". `903a606` is a **test commit**, not a
  merge: it asserts the fail-closed behaviour in the round-2 audit suite and its parent is the real
  merge. Both hashes are recorded below rather than repeating the mislabel.

## 1. Report register

Every file below is tracked; the verification column names the commit that contains it. Files whose
only commit is on an unmerged branch are marked **branch-only** and are not evidence about merged
behaviour.

| report | what it is | introduced in | content sha256 at `f17ec54` | verification |
|---|---|---|---|---|
| `docs/ADVERSARIAL-HARNESS-REVIEW.md` | audit round 1 — harness capability verdict (NO-GO as a general harness) | `2e3508f` | `405e552459f0ca8c993c9c2bde78cbc7fd7ba0988d9bdb621c5f31970e76b7bd` | `git cat-file -e 2e3508f:docs/ADVERSARIAL-HARNESS-REVIEW.md` |
| `docs/ADVERSARIAL-AUDIT-ROUND2.md` | audit round 2 — 14 deterministic probes, 10 findings | master via merge `7af3bbd` (audit commit `9357c00`) | `9fc051fd017ac0cd2e5f44c3f2cc618ddb4198a3005770a03ec391f721270e02` | `git cat-file -e 7af3bbd:docs/ADVERSARIAL-AUDIT-ROUND2.md`; `git cat-file -e 9357c00:docs/ADVERSARIAL-AUDIT-ROUND2.md` |
| `docs/ADVERSARIAL-UX-REVIEW.md` | adversarial UX review — learner and Parent Studio surfaces (GO for a UX pass, not a rewrite) | `2e57efa` | `840d000ecd6bb2d1892af34f9142126864bb0f5cc9c1d37eb43f7f74e4128c94` | `git cat-file -e 2e57efa:docs/ADVERSARIAL-UX-REVIEW.md`; `git merge-base --is-ancestor 2e57efa master` |
| `docs/GENERIC-HARNESS-REVIEW.md` | generic-harness review — can Coursebook teach an arbitrary topic (partially generic), evidence G-01…G-07 | `2e57efa`; amended `31b3132` (card mapping), `6d062e1` (line anchors), `db5662c` | `a8d119aa28763013d90d10f1c11c01f096d9412def17b8b5970e9eaa67e53da4` | `git cat-file -e f17ec54:docs/GENERIC-HARNESS-REVIEW.md`; `git cat-file -e 2e57efa:docs/GENERIC-HARNESS-REVIEW.md` |
| `docs/ASSESSMENT-BREADTH.md` | H-16 assessment construct breadth decision and its B-1/B-2/B-3 defect register | `dd43d82` on `wt/harness-assessment-breadth` — **branch-only, not on master** | `38021edef4d6cafdf9c45eaff0bcfbe17c8e2960150fba70093d99590f9e2c7e` | `git cat-file -e dd43d82:docs/ASSESSMENT-BREADTH.md` (H-16 `t_3c5d969c` is `done`, unmerged) |
| `docs/COURSE-BLUEPRINT.md` | H-03 scope-aware blueprint design (single/short/full); design authority for H-21 | master via merge `54087de` (content `f465a4d`) | `024d860723f188e195a2689e07a3a150708d9951867e761a57b16c69c38403a7` | `git cat-file -e 54087de:docs/COURSE-BLUEPRINT.md`; `git cat-file -e f465a4d:docs/COURSE-BLUEPRINT.md` |
| `docs/HARNESS-NEXT-CARDS.md` | board card index / DAG, card-to-finding mapping, current-wave status | `2e3508f`; amended `a8d93b8`, `b4da6d9`, `31b3132`, `f17ec54`, and this card | `144ca4fb060ecb26d667da7c866001d68e93642b950645fcea7e8a21a6a9b677` (at `f17ec54`, before this card's edit) | `git cat-file -e f17ec54:docs/HARNESS-NEXT-CARDS.md` |
| `docs/REVIEW_CB014.md` | pre-harness adversarial security/state/a11y release review (cb.rpc v6) | `270edae` | `4a3b00205761eae6e298cc34c3197c868518a0e6ff98ea922ab4c02449c2a91b` | `git cat-file -e 270edae:docs/REVIEW_CB014.md` (amended in `8e11bd2`) |
| `docs/REVIEW_CB014-telemetry.md` | CB-014 tool-telemetry scope note | `51406ee` | `3f77fb9ccca8bf87daa904c1f6a9a13d00c3024f5ca970f5b4b16ffde8efbdb9` | `git cat-file -e 51406ee:docs/REVIEW_CB014-telemetry.md`; `git cat-file -e f17ec54:docs/REVIEW_CB014-telemetry.md` |
| `docs/ACCEPTANCE.md` | adversarial acceptance matrix with explicit verified/seam/blocked/pending vocabulary | `b9da9f3` | `869918a97cb8e64f2c1daaaac9599904644049f138ceb6dd386ce1bb9a889d06` | `git cat-file -e b9da9f3:docs/ACCEPTANCE.md` (re-derived in `7d5a70c`) |
| `docs/CB016-RELEASE-VERIFICATION.md` | clean-export install and route-mount record | `7f80f35` | `291b21564292301f07ed0c947a36657079f9762da9e9592a4a999b0ad497a266` | `git cat-file -e 7f80f35:docs/CB016-RELEASE-VERIFICATION.md` |
| `docs/CB017-RELEASE-VERIFICATION.md` | release record re-derived on merged master and re-pinned | `638eb6b` | `55f9b3f07b49dd39dc817181cbddab818fda4ef9335203420b279eb545c79a3f` | `git cat-file -e 638eb6b:docs/CB017-RELEASE-VERIFICATION.md` (amended in `6eb93c2`) |
| `docs/M4-VISUAL-MEDIA-AUDIT.md` | M4-QA visual/accessibility/media truth gate (62 painted frames) | `2b37b5b` | `6f4a109f1fc0f6aae5fe5ecea0ae5c58d6fab5438af629fb32c3591bad606689` | `git cat-file -e 2b37b5b:docs/M4-VISUAL-MEDIA-AUDIT.md` (amended in `27a2e40`) |
| `docs/DEMO.md` | honest demo status; states the prepared pack proves one pack only | `5ad682e` | `27651b66410b54a6381430ae9945196ff78199f74cd0b75c188280b376d084ba` | `git cat-file -e 0e1aca1:docs/DEMO.md` |

Every `content sha256 at f17ec54` value above was computed with
`git show f17ec54:<path> | sha256sum`; the branch-only rows name their own commit instead. A hash
that does not reproduce at the named commit is a stale row, not a rounding error.

This file itself: it was introduced at `fe395f6` and rebased/pinned at `99da48a` (H-19,
branch-only; previous-revision sha256
`03e203c2fc2a77d457178bf9c4f44c3fadab91dd637d42d45ba5c3ecd6c8c26e`) and is refreshed by H-31. A
file cannot pin its own current hash, so the row names the previous revision and the commit that
produced this one is recorded in the card handoff.

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
  `ADVERSARIAL-AUDIT-ROUND2.md` (`tests/test_adversarial_round2.py`, 14 probes at `9357c00`),
  `ADVERSARIAL-UX-REVIEW.md` (source review + repository frames at `54087de`),
  `GENERIC-HARNESS-REVIEW.md` (JSON-Schema and kernel probes at `6779030`), and the `seam` rows of
  `ACCEPTANCE.md`.
- **prepared-pack** — the bundled Japanese L0 pack (`bundled/packs/japanese-affection-context-l0`,
  imported by `scripts/seed-demo-course.py`). It proves a governed loop over **one** prepared pack
  and is **never** proof of arbitrary-topic generation. `docs/DEMO.md` says so itself.

No finding in any audit rests on prepared-pack evidence. Where a report says "not used as
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

Recorded in the H-10 card handoff (`t_1efc158a`). The report and its probe file are in master:
merge `7af3bbd` brings `9357c00`'s `tests/test_adversarial_round2.py` and
`docs/ADVERSARIAL-AUDIT-ROUND2.md` onto `master`. The round-2 plan-approval probe was **updated**
after H-12: `903a606` ("test: assert H-12 fail-closed plan approval in round-2 audit") is on
`master` and changes the probe's expectation from "rejected plan approves" to the refusal. That is
the probe version that matches the merged harness; its test count was not re-measured by this
docs-only card.

### UX review — `docs/ADVERSARIAL-UX-REVIEW.md` @ `54087de`

No command: a source review of `desktop/plugin.js` plus repository frames. The report records its
own limit — the frames predate H-02's create-flow rewrite, so every finding that depends on the
rewritten flow is anchored to code, not to a stale frame. No live Desktop window was launched.

### Generic-harness review — `docs/GENERIC-HARNESS-REVIEW.md` @ `6779030`

```
PLAN_SCHEMA one-objective errors: 2
- ['objectives'] [...] is too short
- ['sections'] [...] is too short
```

The generated-check probe is the H-16 probe set (`probe_breadth_ref.py` / `probe_breadth_closed.py`)
run through the public commands with a fake provider; it did not call a model. Line anchors were
re-pinned to current master in `6d062e1`.

### H-19 — `docs/AUDIT-INDEX.md` creation, docs-only

```
python3 -m unittest tests.test_adversarial_round2       # 14 tests, OK
python3 -m unittest discover -s tests -t .              # Ran 1054 tests, OK (156.1 s)
bash scripts/validate-plugin.sh                         # 3/3 checks on 215e35f, 1219 files
```

### H-31 — this refresh, docs-only

No product code changed in this card, so no test-count or gate claim is made here. The integrator
runs the frozen gate on the merged tree; this record is a docs revision on a branch, not a merge
approval.

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

Status is the state of the **merged** evidence at `master` = `f17ec54` (2026-11-07). A `done` card
means its worker finished; it does **not** mean the branch merged. "FIXED" requires the named merge
commit to be an ancestor of `master`.

| finding | severity | status | owning card | evidence commit | card state |
|---|---|---|---|---|---|
| P0-1 learner create flow never starts generation | P0 | **FIXED** | H-02 `t_867d3b52` | merge `1bbd502` (content `5b74233`) | done, merged |
| P0-2 plan schema caps at 8 sections / forces 4 objectives; no `scope` | P0 | **OPEN — design merged, implementation unmerged** | H-03 `t_577ed286` (design) + H-21 `t_2a2fc90c` (implementation) | design merge `54087de` (content `f465a4d`); impl branch `wt/t_2a2fc90c` @ `5ba4e4c` **unmerged** | H-03 done/merged; H-21 ready |
| P0-3 capability-policy inputs unreachable; locale mistaken for subject | P0 | **FIXED** | H-01 `t_f4f5b26a` (contract) + H-13 `t_543c0767` (threading) | merges `b1f2978` (content `8cbaab3`) and `6779030` (content `ee976ea`) | done, merged |
| P0-4 deep research is a no-op; demo-sized budget | P0 | **OPEN — done, unmerged** | H-04 `t_161d467f` | branch `wt/harness-research-depth` @ `cee1749` **unmerged** | done |
| P0-5 a normal course cannot export itself | P0 | OPEN | H-08 `t_901c8310` | none yet | running |
| P0-6 a technical procedure lesson cannot carry the procedure lens | P0 | OPEN | H-06 `t_7a320d2f` | none yet | running |
| P0-7 no live arbitrary-topic generation | P0 | OPEN | H-09 `t_ebc196db` | none yet | todo |
| P1-1 parent brief stored but mostly ignored by the planner | P1 | **OPEN — done, unmerged** | H-07 `t_2f3cc647` | branch `wt/harness-parent-brief` @ `8a6bedb` **unmerged** | done |
| P1-2 planner does not plan media; policy guesses from prose | P1 | **OPEN — done, unmerged** | H-05 `t_7baa29e2` | branch `wt/harness-media-plan` @ `986190f` **unmerged** | done |
| P1-3 check `count` / `independent_evidence` are decorative | P1 | OPEN — **mapped** | H-21 `t_2a2fc90c` (plan v2 removes both fields) | branch `wt/t_2a2fc90c` @ `5ba4e4c` **unmerged** | ready |
| P1-4 authoring schemas are Japanese-shaped | P1 | OPEN | H-18 `t_8407ea22` (same defect as round-2 P2-7) | none yet | running |
| P1-5 assessment breadth is narrow | P1 | **OPEN — decision done, unmerged** | H-16 `t_3c5d969c`; implementation B-1/B-2/B-3 | branch `wt/harness-assessment-breadth` @ `dd43d82` **unmerged** | H-16 done; B-1 `t_673155b0`, B-2 `t_74d99ca5`, B-3 H-22 `t_966d50f4` all running |
| P1-6 rubric registry is static | P1 | OPEN — **mapped** | H-24 `t_29e6647c` (profile-extension decision, no runtime generator) | branch `wt/harness-rubric-extensibility` @ `2e57efa` (no commits yet) **unmerged** | running |
| P2-1 test matrix proves policy, not generation | P2 | OPEN | H-09 `t_ebc196db` | none yet | todo |
| P2-2 depth/locale not tested through the product surface | P2 | OPEN — **half mapped** | H-04 `t_161d467f` (unmerged `cee1749`) + H-13 `t_543c0767` (**merged** `6779030`) | see left | H-04 done/unmerged; H-13 merged |
| P2-3 procedure/media evidence is static or fixture | P2 | OPEN | H-09 `t_ebc196db` | none yet | todo |

**P1-3 and P1-6 were UNMAPPED in the previous revision.** They are now mapped: P1-3 is owned by
H-21's plan-v2 removal of the decorative `count` / `independent_evidence` fields (card body,
`docs/COURSE-BLUEPRINT.md` §5), and P1-6 by H-24's rubric-registry extensibility decision. Neither
is fixed on `master`; both are recorded as open and owned, not as scheduled or done. **No round-1
finding remains UNMAPPED as of this revision.**

## 5. Finding ledger — round 2 (`docs/ADVERSARIAL-AUDIT-ROUND2.md`)

The report proposed its own `H-11`…`H-18` labels. Those labels **collide** with the board keys; the
board keys are authoritative and are the only ids used here.

| finding | severity | status | owning card | evidence commit | card state |
|---|---|---|---|---|---|
| P0-1 validator-rejected plan is stored as an approvable `draft` | P0 | **FIXED** | H-12 `t_dba06898` | merge `13480c4` (content `4b5f3b1`); round-2 probe updated in `903a606` | done, merged |
| P0-2 fetched excerpt is raw prompt content; invented prose URLs pass | P0 | **FIXED** | H-14 `t_031e287f` | merge `a12176b` (content `0ba4dc6`) | done, merged |
| P1-3 "independent validation" is prompt separation; same model upgrades support | P1 | **OPEN — done, unmerged** | H-15 `t_d519643b` | branch `wt/harness-validator-independence` @ `833e335` **unmerged** | done |
| P1-4 factual gate auto-waives when research is unavailable | P1 | **OPEN — done, unmerged** | H-15 `t_d519643b` | branch `wt/harness-validator-independence` @ `833e335` **unmerged** | done |
| P1-5 assessment breadth: three input formats only | P1 | **OPEN — decision done, unmerged; implementations running** | H-16 `t_3c5d969c` → B-1 `t_673155b0`, B-2 `t_74d99ca5`, B-3 H-22 `t_966d50f4` | branch `wt/harness-assessment-breadth` @ `dd43d82` **unmerged** | H-16 done; B-1/B-2/H-22 running |
| P1-6 flat `$0.75` ceiling, no cost-abort recovery | P1 | **OPEN — done, unmerged** | H-17 `t_9a8543ae` | branch `wt/harness-cost-ceilings` @ `722f00f` **unmerged** | done |
| P2-7 Japanese-only scaffold triple; no direction field | P2 | OPEN | H-18 `t_8407ea22` | none yet | running |
| P2-8 no prerequisite edges; adaptation is a state label | P2 | **OPEN — done, unmerged** | H-20 `t_43ca17b8` | branch `wt/harness-prereq-edges` @ `516d161` **unmerged** | done |
| P2-9 green policy matrix supplies contract-rejected dials | P2 | **FIXED** | H-01 `t_f4f5b26a` + H-13 `t_543c0767` | merges `b1f2978` (content `8cbaab3`) and `6779030` (content `ee976ea`) | done, merged |
| P2-10 round-1 review uncommitted at audit time | P2 | **FIXED** | H-19 `t_ec1d2c15` | `2e3508f` on master; index `99da48a` is branch-only | done, index unmerged |

### Why round-2 P0-1 is now FIXED, precisely

H-12's content commit `4b5f3b1` is an ancestor of `master` through merge `13480c4`. The merged
behaviour: `plan.approve` refuses an empty plan with `plan_empty`, refuses a generated plan whose
latest `gen_plan_documents` row is not pass-state with `plan_not_validated`, refuses a stale
content hash with `plan_validation_stale`, and writes no transition or revision on refusal. Edit,
replan and direct objective authoring durably invalidate the prior pass. Manual non-empty plans
approve without claiming validation.

The round-2 probe that used to assert "a rejected plan approves" was rewritten in `903a606` to
assert the refusal. That commit is **not** a merge commit and does not by itself fix anything; it
is the merged test evidence that the fix is asserted. Earlier revisions of this index cited
`4b5f3b1` as branch-only — that was correct at base `7af3bbd` and is stale now.

### P2-10 closure, precisely

The round-1 review was untracked when Sable audited. It is committed in `2e3508f`. The round-2
report's Method section and its P2-10 status line were corrected on the H-19 branch; no finding
text, evidence or severity was changed. H-19 is `done`; `wt/harness-audit-index` (`99da48a`) is
**not merged**, so on `master` the correction reaches a reader only through this H-31 branch.

## 6. Card index findings (D-series)

`docs/HARNESS-NEXT-CARDS.md` records deeper findings discovered while seeding the board. They are
not a separate audit, but they do carry reproducibility weight, so their status is pinned here
rather than left to prose. Historical D-01…D-06 text is **not** rewritten by this card; only the
status column moves.

| id | status | owning card | evidence commit | note |
|---|---|---|---|---|
| D-01 plan approval is advisory, not fail-closed | **FIXED** | H-12 `t_dba06898` | merge `13480c4` (content `4b5f3b1`) | same defect as round-2 P0-1 |
| D-02 the green suite encodes the defect | **FIXED** | H-12 | tests changed in `4b5f3b1`; audit assertion `903a606` | empty-plan approvals now assert refusal |
| D-02b two plan digests, one approval | **FIXED** | H-12 + H-02 | `13480c4` (durable binding) + `1bbd502` (learner path reads kernel digest via `parent.blueprint.read`) | the fix is a projection, not a digest comparison |
| D-03 the plan job drops contract inputs | **FIXED** | H-13 `t_543c0767` | merge `6779030` (content `ee976ea`) | level/subject_domain/scope reach prompt, research and fingerprint |
| D-04 "adaptation" is a state transition | **OPEN** | H-03 (design, merged `54087de`) + H-20 `t_43ca17b8` (unmerged `516d161`) + H-21 `t_2a2fc90c` (unmerged `5ba4e4c`) | see left | do not market it as adaptive teaching |
| D-05 validation independence is structural only | **OPEN — done, unmerged** | H-15 `t_d519643b` | branch `wt/harness-validator-independence` @ `833e335` **unmerged** | same as round-2 P1-3 |
| D-06 stale CB-QA-10 claim survives in README | OPEN | H-11 `t_6f41e0b0` | none yet | truth pass; reconcile README/PRIVACY_EGRESS/ACCEPTANCE/REVIEW_CB014 |

D-06 also covers the `REVIEW_CB014.md` row for CB-QA-10 ("OPEN"). That row is **not** rewritten
here: the code may already project only `PUBLIC_CRITERION_FIELDS` (per
`tests/test_review_evidence.py`), but this card did not re-derive that, so the public record stays
as it is and H-11 owns the reconciliation.

## 7. Third wave — UX and generic-harness reviews (2026-11-07)

Both reviews are merged at `2e57efa`, amended by `31b3132`, `6d062e1`, `db5662c`. Their findings are mapped
below; the card bodies are the authority for scope.

### Generic-harness findings (G-series, `docs/GENERIC-HARNESS-REVIEW.md`)

| finding | summary | owning card | card state | branch |
|---|---|---|---|---|
| G-01 | One-off shape is schema-rejected (`minItems: 4` objectives, 2 sections) | H-21 `t_2a2fc90c` | ready | `wt/t_2a2fc90c` @ `5ba4e4c`, unmerged |
| G-02 | Generated checks are saved, not graded (no reference `kind`) | B-1 `t_673155b0` (H-16 B-1; card title carries the stale "H-20" collision label) | running | — |
| G-03 | Scope is on the wire but the plan shape caps it | H-21 `t_2a2fc90c` | ready | `wt/t_2a2fc90c`, unmerged |
| G-04 | Media/procedure lens incomplete | H-05 `t_7baa29e2` (`986190f`, unmerged) + H-06 `t_7a320d2f` (running) | done / running | `wt/harness-media-plan`, `wt/harness-procedure-author` |
| G-05 | Only a prepared Japanese pack has run end to end | H-09 `t_ebc196db` (proof) + H-30 `t_178dc615` (independent audit) | todo | `wt/harness-e2e-proof`, `wt/harness-generic-audit` |
| G-06 | Student mode / second import path does not exist | H-25 `t_5535fc66` (design), H-26 `t_da9e472c` (backend), H-27 `t_71ea55ee` (UI) | ready / todo / todo | `wt/harness-student-mode-design`, `wt/harness-student-import`, `wt/harness-student-ui` |
| G-07 | Rubric profiles are static | H-24 `t_29e6647c` (decision, not a runtime generator) | running | `wt/harness-rubric-extensibility` (no commits yet) |

### UX findings (UX-series, `docs/ADVERSARIAL-UX-REVIEW.md`)

| finding | summary | owning card | card state | branch |
|---|---|---|---|---|
| UX-01 | First run explains the system, not the invitation | H-28 `t_271e19e7` | todo | `wt/harness-ux-first-run` |
| UX-02 | "Recipe" is the wrong first question; Japanese-only placeholders | H-28 `t_271e19e7` | todo | `wt/harness-ux-first-run` |
| UX-03 | Create result is a receipt, not a beginning | H-28 `t_271e19e7` | todo | `wt/harness-ux-first-run` |
| UX-04 | Lesson index is a metadata table | H-29 `t_70686b14` | todo | `wt/harness-ux-learning` |
| UX-05 | Result screen is accurate and unkind | H-29 `t_70686b14` | todo | `wt/harness-ux-learning` |
| UX-06 | Library/Import has no plain explanation | H-28 `t_271e19e7` (with H-27) | todo | `wt/harness-ux-first-run` |
| UX-07 | Parent Studio speaks builder vocabulary | H-28 `t_271e19e7` | todo | `wt/harness-ux-first-run` |
| UX-08 | Cross-surface visual language is flat | H-29 `t_70686b14` / host | todo | `wt/harness-ux-learning` |
| UX-09 | Scope and expectation are unclear on screen | H-28 `t_271e19e7` | todo | `wt/harness-ux-first-run` |
| UX-10 | Status and error tone | H-29 `t_70686b14` | todo | `wt/harness-ux-learning` |

### H-16 B-series (defect register inside `docs/ASSESSMENT-BREADTH.md` §11)

| finding | summary | owning card | card state | branch |
|---|---|---|---|---|
| B-1 | Generated lesson checks store no reference `kind`; grader falls to the unconfigured open lane | `t_673155b0` (title still says "H-20"; **B-1** is authoritative) | running | — |
| B-2 | `record_observation` has no RPC method, handler or UI; `self_reported`/`parent_reported` unreachable | `t_74d99ca5` (Atlas's earlier label was "H-21"; **B-2** is authoritative) | running | `wt/harness-observation-record` @ `423908f`, unmerged |
| B-3 | `EVIDENCE_CLASS_COPY` covers 4 of 6 evidence classes | H-22 `t_966d50f4` (frozen disclosure copy + labels) | running | `wt/harness-breadth-copy` @ `002a82b`, unmerged |

**H-23 `t_132531da` ("Generated checks are ungradable") is `done` as a duplicate with no product
code:** it was seeded before the B-1 duplicate was noticed. It is not evidence for B-1 and must not
be re-run. B-1's owner is `t_673155b0`. `wt/harness-check-lane` does not exist as a branch with
commits.

## 8. New cards — finding links (H-21…H-32)

Every card created after the second wave, with the findings it owns or audits. This is the mapping
the previous revision of this index did not have.

| card | id | owner | parents | branch | owns / audits |
|---|---|---|---|---|---|
| H-21 | `t_2a2fc90c` | cinder | H-13, H-01 | `wt/t_2a2fc90c` | round-1 P0-2 (plan shape), G-01/G-03, round-1 P1-3 (removes decorative `count`/`independent_evidence`), D-04 sequencing |
| H-22 | `t_966d50f4` | vellum | H-16 | `wt/harness-breadth-copy` | H-16 B-3 (evidence-class copy), §7 frozen breadth disclosure |
| H-23 | `t_132531da` | cinder | H-16 | — | **closed duplicate of B-1, no code**; B-1 owner is `t_673155b0` |
| H-24 | `t_29e6647c` | atlas | H-16 | `wt/harness-rubric-extensibility` | round-1 P1-6 (static rubric registry), G-07 |
| H-25 | `t_5535fc66` | atlas | H-03, H-02 | `wt/harness-student-mode-design` | G-06 design |
| H-26 | `t_da9e472c` | cinder | H-25 | `wt/harness-student-import` | G-06 backend |
| H-27 | `t_71ea55ee` | vellum | H-25, H-26 | `wt/harness-student-ui` | G-06 learner intake/alignment |
| H-28 | `t_271e19e7` | vellum | H-02, H-22, H-21 | `wt/harness-ux-first-run` | UX-01, UX-02, UX-03, UX-06, UX-07, UX-09 |
| H-29 | `t_70686b14` | vellum | H-28 | `wt/harness-ux-learning` | UX-04, UX-05, UX-08, UX-10 |
| H-30 | `t_178dc615` | sentinel | H-09 | `wt/harness-generic-audit` | G-05 independent audit of H-09 (not a second generator) |
| H-31 | `t_1c9d0ba6` | quill | H-12, H-14, H-02, H-03 | `wt/harness-audit-refresh` | this refresh; rewrites no finding |
| H-32 | `t_69873d4c` | cinder | H-07, H-13, H-14 | `wt/harness-parent-brief-rebase` | conflict repair so H-07 (round-1 P1-1) can merge onto H-13/H-14; no new finding |

## 9. Provenance checks this index relies on

Run on `master` at `f17ec54` plus this branch; each must stay true or the index is stale.

```
git cat-file -e f17ec54:docs/ADVERSARIAL-HARNESS-REVIEW.md
git cat-file -e 9357c00:docs/ADVERSARIAL-AUDIT-ROUND2.md
git cat-file -e 2e57efa:docs/ADVERSARIAL-UX-REVIEW.md
git cat-file -e f17ec54:docs/GENERIC-HARNESS-REVIEW.md
git cat-file -e 54087de:docs/COURSE-BLUEPRINT.md
git cat-file -e dd43d82:docs/ASSESSMENT-BREADTH.md      # branch-only: H-16 done, unmerged
git cat-file -e 99da48a:docs/AUDIT-INDEX.md             # branch-only: H-19 done, unmerged
git merge-base --is-ancestor 13480c4 master             # H-12 merge
git merge-base --is-ancestor 903a606 master             # H-12 round-2 audit assertion
git merge-base --is-ancestor b1f2978 master             # H-01 merge
git merge-base --is-ancestor a12176b master             # H-14 merge
git merge-base --is-ancestor 1bbd502 master             # H-02 merge
git merge-base --is-ancestor 54087de master             # H-03 design merge
git merge-base --is-ancestor 6779030 master             # H-13 merge
git merge-base --is-ancestor f17ec54 master             # base of this refresh
```

Rules enforced:

- **No claim cites a file that exists only in a worktree.** Every report above is tracked. The
  branch-only exceptions are labelled: H-16's `ASSESSMENT-BREADTH.md` (`dd43d82`) and H-19's
  `AUDIT-INDEX.md` (`99da48a`). Their cards are `done`; their branches are **not** merged.
- **A branch is not a merge, and a done card is not a merge.** H-04, H-05, H-07, H-15, H-16, H-17,
  H-19 and H-20 are `done` with unmerged branches; each is recorded that way. Their tips are named
  so a reader can check the claim, not so the tips can be treated as merged.
- **A prepared pack is not a topic proof.** No row above derives a harness claim from
  `bundled/packs/japanese-affection-context-l0`.
- **A green suite is not a gate.** The round-2 suite passed at `7af3bbd` while asserting the
  pre-H-12 approval defect (D-02). That is why the index reports test counts together with the
  commit whose assertions they encode.

## 10. What this index does not claim

- It does not claim the harness is fully generic. `docs/GENERIC-HARNESS-REVIEW.md` at `f17ec54`
  says "partially generic"; G-01/G-02/G-03 are still live on `master` because H-21 and B-1 are
  unmerged.
- It does not claim H-04, H-05, H-07, H-15, H-16, H-17, H-19 or H-20 is fixed; their branches are
  unmerged and every such row says so.
- It does not claim H-23 did any work: it was closed as a duplicate with no code.
- It does not re-run, re-grade or extend any audit; probe results are attributed to the card that
  produced them.
- It does not claim the harness is installable, demo-ready, or proven on an arbitrary topic. H-09
  (`t_ebc196db`) is the only card that can establish arbitrary-topic generation, and H-30 audits it.
- It does not use the prepared Japanese pack as evidence for anything.
- It changes no product code, contract, schema, migration or test.

## 11. Changes in this revision (H-31) — every moved status and its commit

Compared with the H-19 revision (`99da48a`). "Merged" was checked against `master` = `f17ec54`
with `git merge-base --is-ancestor`. Rows not listed did not change status in this revision.

| row | previous status | status now | commit that justifies it | merged |
|---|---|---|---|---|
| round-1 P0-1 | OPEN (H-02 running) | **FIXED** | merge `1bbd502` (content `5b74233`) | yes |
| round-1 P0-2 | OPEN (H-03 running) | OPEN — design merged, implementation unmerged | merge `54087de` (content `f465a4d`); H-21 `5ba4e4c` | design yes; impl no |
| round-1 P0-3 | OPEN, H-01 done/unmerged + H-13 ready | **FIXED** | merges `b1f2978` and `6779030` | yes |
| round-1 P0-4 | OPEN (H-04 running) | OPEN — done, unmerged | `cee1749` | no |
| round-1 P1-1 | OPEN (H-07 running) | OPEN — done, unmerged | `8a6bedb` | no |
| round-1 P1-2 | OPEN (H-05 todo) | OPEN — done, unmerged | `986190f` | no |
| round-1 P1-3 | **OPEN — UNMAPPED** | OPEN — mapped to H-21 (plan v2 removes `count`/`independent_evidence`) | `5ba4e4c` | no |
| round-1 P1-5 | OPEN (H-16 todo) | OPEN — decision done, unmerged; B-1/B-2/H-22 running | `dd43d82` | no |
| round-1 P1-6 | **OPEN — PARTIAL** (no owner) | OPEN — mapped to H-24 | `wt/harness-rubric-extensibility` (no commits) | no |
| round-2 P0-1 | OPEN, H-12 done/unmerged | **FIXED** | merge `13480c4` (content `4b5f3b1`); assertion `903a606` | yes |
| round-2 P0-2 | OPEN (H-14 running) | **FIXED** | merge `a12176b` (content `0ba4dc6`) | yes |
| round-2 P1-3 | OPEN (H-15 running) | OPEN — done, unmerged | `833e335` | no |
| round-2 P1-4 | OPEN (H-15 running) | OPEN — done, unmerged | `833e335` | no |
| round-2 P1-5 | OPEN (H-16 todo) | OPEN — decision done, unmerged; implementations running | `dd43d82`; B-1 `t_673155b0`, B-2 `t_74d99ca5`, H-22 `t_966d50f4` | no |
| round-2 P1-6 | OPEN (H-17 running) | OPEN — done, unmerged | `722f00f` | no |
| round-2 P2-8 | OPEN (H-20 todo, conditional) | OPEN — done, unmerged | `516d161` | no |
| round-2 P2-9 | OPEN, H-01 done/unmerged + H-13 ready | **FIXED** | merges `b1f2978` and `6779030` | yes |
| round-2 P2-10 | FIXED (this card, H-19) | **FIXED** — report on master, index branch-only | `2e3508f` (report); `99da48a` (index) | report yes; index no |
| D-01 | OPEN | **FIXED** | merge `13480c4` | yes |
| D-02 | OPEN | **FIXED** | `4b5f3b1` (tests); `903a606` (audit assertion) | yes |
| D-02b | OPEN | **FIXED** | `13480c4` (binding) + `1bbd502` (learner projection) | yes |
| D-03 | OPEN | **FIXED** | merge `6779030` (content `ee976ea`) | yes |
| D-04 | OPEN | OPEN — design merged, implementations unmerged | `54087de`; `516d161`; `5ba4e4c` | design yes; impl no |
| D-05 | OPEN | OPEN — done, unmerged | `833e335` | no |

New rows added by this revision: the UX review (UX-01…UX-10), the generic-harness review
(G-01…G-07), the H-16 B-series (B-1…B-3), and the H-21…H-31 card-to-finding links in §7 and §8.

**Findings still UNMAPPED after this revision: none.** P1-3 and P1-6 were the only two, and both
now name an owning card (H-21 and H-24). That is a routing fact, not a fix: neither has merged
evidence, and both ledgers say so.
