# AUDIT-INDEX — Coursebook audit evidence register

Owner: quill. Created by H-19 (`t_ec1d2c15`) at `99da48a` on `wt/harness-audit-index`; refreshed by
H-31 (`t_1c9d0ba6`) at `512c5f6` on `wt/harness-audit-refresh`; refreshed again by H-31b
(`t_a8e017b5`) on `wt/harness-audit-refresh-2`, based on `master` at `f990cad`
(`f990cadddeb2c44ed9d5b3b907d28862f452f909`).

Both earlier revisions are now on `master`: `99da48a` through the integration merge `ce95836`,
`512c5f6` through merge `fdecc9e`. A reader does not need a branch to see this file any more; they
need the commit above.

Purpose: make every audit claim reproducible from a **commit hash**, not from a working-tree path.
A report is evidence only if the file it lives in resolves to a commit, the probes that produced it
resolve to a commit, and the finding's status names the card that owns the fix.

Rule for citing this index: quote the commit hash and the file path, never a worktree path. If a
file is not reachable with `git cat-file -e <hash>:<path>`, it is not evidence.

## 0. How to read this after merges

Four things are routinely confused. They are not the same:

- **A card being `done` is not a merge.** `done` means the assigned worker finished and reported.
  The branch may still be unmerged. Every ledger row below names a commit *and* says whether that
  commit is an ancestor of `master` at `f990cad`.
- **A merge is not an independent re-audit.** A merged fix proves the code landed; it does not
  prove the defect is gone. Where a merged implementation has not been re-probed against the
  commit that carries it, the row says **re-audit required** and names the audit card
  (H-30b `t_9b6742f3` for the harness findings; H-36 `t_48645f63` is an integration repair, not
  an audit).
- **A branch tip is not merged evidence.** A finding flips to FIXED only when its fix is an
  ancestor of `master` (`git merge-base --is-ancestor <commit> f990cad` exits 0) and the merged
  tree passed the frozen gate. A branch-only fix stays OPEN, marked "done, unmerged".
- **A content commit is not a merge commit.** Cite both where they differ: merge `2252231`
  carries content `bcd545e`. A squash, a test commit or a rebase is not a merge, and a card body
  that calls one a merge is corrected here rather than repeated.

Two correction notes for this revision:

- The previous revision said H-19's index was branch-only. It is merged: `99da48a` is an ancestor
  of `f990cad` through the integration merge `ce95836`. That note is retired, not deleted, so a
  reader who saw the old text knows which line moved.
- H-12's card body cites `903a606` as its "merge commit". `903a606` is a **test commit**, not a
  merge: it asserts the fail-closed behaviour in the round-2 audit suite. Both hashes are recorded
  below rather than repeating the mislabel.

## 1. Report register

Every file below is tracked; the verification column names the commit that contains it. A report
whose only commit is on an unmerged branch is marked **branch-only** and is not evidence about
merged behaviour.

| report | what it is | introduced in | content sha256 at `f990cad` | verification |
|---|---|---|---|---|
| `docs/ADVERSARIAL-HARNESS-REVIEW.md` | audit round 1 — harness capability verdict (NO-GO as a general harness) | `2e3508f` | `405e552459f0ca8c993c9c2bde78cbc7fd7ba0988d9bdb621c5f31970e76b7bd` | `git cat-file -e 2e3508f:docs/ADVERSARIAL-HARNESS-REVIEW.md` |
| `docs/ADVERSARIAL-AUDIT-ROUND2.md` | audit round 2 — 14 deterministic probes, 10 findings | master via merge `7af3bbd` (audit commit `9357c00`; probe assertion `903a606`) | `646242073fd0d60f7f70f86e439aae2bc29482afa5d8afe7f9f0d8161e3a8d96` | `git cat-file -e f990cad:docs/ADVERSARIAL-AUDIT-ROUND2.md` |
| `docs/ADVERSARIAL-UX-REVIEW.md` | adversarial UX review — learner and Parent Studio surfaces (GO for a UX pass, not a rewrite) | `2e57efa` | `840d000ecd6bb2d1892af34f9142126864bb0f5cc9c1d37eb43f7f74e4128c94` | `git cat-file -e f990cad:docs/ADVERSARIAL-UX-REVIEW.md` |
| `docs/GENERIC-HARNESS-REVIEW.md` | generic-harness review — can Coursebook teach an arbitrary topic (partially generic), evidence G-01…G-07 | `2e57efa`; amended `31b3132`, `6d062e1`, `db5662c` | `a8d119aa28763013d90d10f1c11c01f096d9412def17b8b5970e9eaa67e53da4` | `git cat-file -e f990cad:docs/GENERIC-HARNESS-REVIEW.md` |
| `docs/GENERIC-ACCEPTANCE-AUDIT.md` | H-30 independent acceptance audit of H-09 (three shapes, checks, routing); base product tree `498b1da` | `ddc71fc`; merged at `090e755` | `19cbe115688e37a5814ee33c5699e1d984965e013f8c6818e6292cec738ecd89` | `git cat-file -e f990cad:docs/GENERIC-ACCEPTANCE-AUDIT.md`; `git merge-base --is-ancestor 090e755 f990cad` |
| `docs/ASSESSMENT-BREADTH.md` | H-16 assessment construct breadth decision and its B-1/B-2/B-3 defect register | `dd43d82`; merged at `fa316c5` | `38021edef4d6cafdf9c45eaff0bcfbe17c8e2960150fba70093d99590f9e2c7e` | `git cat-file -e f990cad:docs/ASSESSMENT-BREADTH.md` |
| `docs/COURSE-BLUEPRINT.md` | H-03 scope-aware blueprint design (single/short/full) plus §14, the frozen H-20 prerequisite contract; design authority for H-21 | master via merge `54087de` (content `f465a4d`); §14 added by `516d161` via `d079b4c` | `cf371b0e52ba3606667041889a05885abe07e146a757c774c529f1fd238911e0` | `git cat-file -e f990cad:docs/COURSE-BLUEPRINT.md` |
| `docs/PLAN-CEILING.md` | H-21c measured `full` plan ceiling; the probe behind the 40-objective cap | `bcd545e`; merged at `2252231` | `9dc0792ad9eec2e7bafb8a5b974c94ac0dc74532ba4788c417c717f2436efad9` | `git cat-file -e f990cad:docs/PLAN-CEILING.md` |
| `docs/GRADING-LANES.md` | H-20 decision + implementation record: every stored check declares its lane (implements B-1) | `ce6c8c1`; merged at `3368c96`, which enters `master` through `4e709d3` | `d4cb723096a513925cf8e7d30ad02b9b9bb4bee24570342e612a23b61a869916` | `git cat-file -e f990cad:docs/GRADING-LANES.md`; `git merge-base --is-ancestor 4e709d3 f990cad` |
| `docs/CHECKLIST-CONFIRMATION.md` | H-33 frozen decision: a verification tick-list is graded `self_reported` | `da53ec1`; merged at `3d46988`, which enters `master` through `4e709d3` | `f559b2f18423f17fac3ae183bb6b9f8b76dec5371b8270498ca00940dd6c7f15` | `git cat-file -e f990cad:docs/CHECKLIST-CONFIRMATION.md` |
| `docs/RUBRIC-EXTENSIBILITY.md` | H-24 frozen decision: the gate for a new construct profile (decision only, no runtime generator) | `491443a`; merged at `4f42c3c` | `7c73550ca4bbd9ef7cb55dbc9595c36e6926abcc108b236998da70bbc8c9d153` | `git cat-file -e f990cad:docs/RUBRIC-EXTENSIBILITY.md` |
| `docs/STUDENT-MODE.md` | H-25 student-mode design: a companion course aligned to an uploaded syllabus; design only | `3705a7a`; merged at `e978441` | `df4dcdeca230d064e0b7cfc19b785f44ede1c40d862d2c16f4b934408b77deef` | `git cat-file -e f990cad:docs/STUDENT-MODE.md` |
| `docs/HARNESS-NEXT-CARDS.md` | board card index / DAG, card-to-finding mapping, current-wave status | `2e3508f`; amended `a8d93b8`, `b4da6d9`, `31b3132`, `f17ec54`, `512c5f6`, and this card | `345480ac1dc8d71cedb041483df6836faa9c08eca3de8ec0bb1568108975f04e` (at `f990cad`, before this card's edit) | `git cat-file -e f990cad:docs/HARNESS-NEXT-CARDS.md` |
| `docs/REVIEW_CB014.md` | pre-harness adversarial security/state/a11y release review (cb.rpc v6) | `270edae` | `4a3b00205761eae6e298cc34c3197c868518a0e6ff98ea922ab4c02449c2a91b` | `git cat-file -e 270edae:docs/REVIEW_CB014.md` (amended in `8e11bd2`) |
| `docs/REVIEW_CB014-telemetry.md` | CB-014 tool-telemetry scope note | `51406ee` | `3f77fb9ccca8bf87daa904c1f6a9a13d00c3024f5ca970f5b4b16ffde8efbdb9` | `git cat-file -e f990cad:docs/REVIEW_CB014-telemetry.md` |
| `docs/ACCEPTANCE.md` | adversarial acceptance matrix with explicit verified/seam/blocked/pending vocabulary | `b9da9f3` | `869918a97cb8e64f2c1daaaac9599904644049f138ceb6dd386ce1bb9a889d06` | `git cat-file -e f990cad:docs/ACCEPTANCE.md` |
| `docs/CB016-RELEASE-VERIFICATION.md` | clean-export install and route-mount record | `7f80f35` | `291b21564292301f07ed0c947a36657079f9762da9e9592a4a999b0ad497a266` | `git cat-file -e 7f80f35:docs/CB016-RELEASE-VERIFICATION.md` |
| `docs/CB017-RELEASE-VERIFICATION.md` | release record re-derived on merged master and re-pinned | `638eb6b` | `55f9b3f07b49dd39dc817181cbddab818fda4ef9335203420b279eb545c79a3f` | `git cat-file -e 638eb6b:docs/CB017-RELEASE-VERIFICATION.md` (amended in `6eb93c2`) |
| `docs/M4-VISUAL-MEDIA-AUDIT.md` | M4-QA visual/accessibility/media truth gate (62 painted frames) | `2b37b5b` | `6f4a109f1fc0f6aae5fe5ecea0ae5c58d6fab5438af629fb32c3591bad606689` | `git cat-file -e 2b37b5b:docs/M4-VISUAL-MEDIA-AUDIT.md` (amended in `27a2e40`) |
| `docs/DEMO.md` | honest demo status; states the prepared pack proves one pack only | `5ad682e` | `27651b66410b54a6381430ae9945196ff78199f74cd0b75c188280b376d084ba` | `git cat-file -e f990cad:docs/DEMO.md` |

Every `content sha256 at f990cad` value above was computed with
`git show f990cad:<path> | sha256sum`. A hash that does not reproduce at the named commit is a stale
row, not a rounding error. Two pins moved in this revision because the files changed, not because
the hashes were wrong: `ADVERSARIAL-AUDIT-ROUND2.md` (`903a606` probe update) and
`COURSE-BLUEPRINT.md` (§14 appended at `516d161`).

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
  `GENERIC-HARNESS-REVIEW.md` (JSON-Schema and kernel probes at `6779030`),
  `GENERIC-ACCEPTANCE-AUDIT.md` (recorded-transcript pipeline plus deterministic shape/grading
  probes at `498b1da`), and the `seam` rows of `ACCEPTANCE.md`.
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

### H-30 acceptance audit — `docs/GENERIC-ACCEPTANCE-AUDIT.md` @ `498b1da`

```
PYTHONPATH=. python3 audit/adversarial/generic-harness/probe_shape.py <plan.json>
PYTHONPATH=. python3 audit/adversarial/generic-harness/probe_grading.py <harness> <home>
python3 -m unittest tests.test_harness_e2e -v      # Ran 9 tests … OK   (on 111c7e9)
python3 -m unittest discover -s tests -t .         # Ran 1052 tests … FAILED (failures=3, skipped=15)
```

Neither the audit commit (`ddc71fc`) nor the audited product tree (`498b1da`) is the merged line;
the audit is still reproducible at those commits and its findings are re-audited by H-30b.

### H-21c blueprint v2 — `docs/PLAN-CEILING.md` @ `bcd545e`

```
python3 scripts/measure_plan_ceiling.py --live --out <probe.json>
python3 scripts/measure_plan_ceiling.py --report <probe.json>    # no spend
python3 -m unittest tests.test_prerequisite_gating -v            # 13 tests (§14.4) OK
```

Reported by the H-21c card: full suite `Ran 1223 tests, OK`; `bash scripts/validate-plugin.sh`
3/3 on 1262 files. One provider call, 2,920 input / 5,859 output tokens, `nous` /
`deepseek/deepseek-v4.1-flash-1017`, provider cost not reported. Those numbers are the card's
measurement; this index did not re-run them.

### H-20 grading lanes — `docs/GRADING-LANES.md` @ `ce6c8c1`

```
python3 -m unittest tests.test_grading_lanes -v     # Ran 15 tests … OK
```

Recorded in H-30 §5 (R6) at `ce6c8c1`. The fix is now merged (`3368c96` → `4e709d3`); the test file
`tests/test_grading_lanes.py` resolves at `f990cad`.

### H-35/H-34 checklist confirmation

```
node --check desktop/plugin.js                      # OK
python3 -m unittest discover -s tests -t .          # Ran 1264 tests, OK
bash scripts/validate-plugin.sh                     # 3/3 checks on 1278 files
```

Reported by the H-35 card at `a498969`. `tests/test_checklist_confirmation.py` (12 tests) resolves
at `f990cad`. This is implementation and fixture evidence; the **live** installed-Desktop DOM
capture was not produced (stale plugin module in the existing rig) and is owned by H-35b
`t_db0b76f8`. No row below claims a live checklist capture.

### H-31 / H-31b — index refresh, docs-only

No product code changed in either card, so no test-count or gate claim is made here. The integrator
runs the frozen gate on the merged tree. H-31b verified its own citations with `git cat-file -e`
and `git merge-base --is-ancestor`; it ran no product tests.

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

Status is the state of the **merged** evidence at `master` = `f990cad` (2026-11-07). A `done` card
means its worker finished; it does **not** mean the branch merged. "FIXED" requires the named merge
commit to be an ancestor of `f990cad`. "FIXED — re-audit required" means the implementation is
merged but no independent probe has run against the merged line yet.

| finding | severity | status | owning card | evidence commit | card state |
|---|---|---|---|---|---|
| P0-1 learner create flow never starts generation | P0 | **FIXED** | H-02 `t_867d3b52` | merge `1bbd502` (content `5b74233`) | done, merged |
| P0-2 plan schema caps at 8 sections / forces 4 objectives; no `scope` | P0 | **FIXED — implementation merged; re-audit required** | H-03 `t_577ed286` (design) + H-21a/b/c (`t_27867486`, `t_fb8b9622`, `t_6576b611`) | design merge `54087de` (content `f465a4d`); implementation merge `2252231` (content `bcd545e`; slices `8eb83d8`, `7f46e17`) | H-21 `t_2a2fc90c` superseded by H-21a/b/c; all done, merged |
| P0-3 capability-policy inputs unreachable; locale mistaken for subject | P0 | **FIXED** | H-01 `t_f4f5b26a` (contract) + H-13 `t_543c0767` (threading) | merges `b1f2978` (content `8cbaab3`) and `6779030` (content `ee976ea`) | done, merged |
| P0-4 deep research is a no-op; demo-sized budget | P0 | **FIXED** | H-04 `t_161d467f` | content `cee1749`, merged at `341cc18` into integration merge `ce95836` | done, merged |
| P0-5 a normal course cannot export itself | P0 | **OPEN — done, unmerged** | H-08 `t_901c8310` | branch `wt/harness-authored-export` @ `c9c6cec` **unmerged** | done |
| P0-6 a technical procedure lesson cannot carry the procedure lens | P0 | **OPEN — done, unmerged** | H-06 `t_7a320d2f` | branch `wt/harness-procedure-author` @ `00b502f` **unmerged** | done |
| P0-7 no live arbitrary-topic generation | P0 | **OPEN — done, unmerged** | H-09 `t_ebc196db` | branch `wt/harness-e2e-proof` @ `111c7e9` **unmerged**; audited by H-30 at `498b1da` | done, unmerged |
| P1-1 parent brief stored but mostly ignored by the planner | P1 | **FIXED** | H-07 `t_2f3cc647` (+ H-32b regression) | content `8a6bedb` merged at `afac32c` into `ce95836`; conflict regression `8d018e4` via `c7461fc` | done, merged |
| P1-2 planner does not plan media; policy guesses from prose | P1 | **FIXED** | H-05 `t_7baa29e2` | content `986190f` merged at `a30487e` into `ce95836` | done, merged |
| P1-3 check `count` / `independent_evidence` are decorative | P1 | **FIXED — re-audit required** | H-21c `t_6576b611` | merge `2252231` (content `bcd545e`); `CHECK_PLAN_SCHEMA_V2` drops both fields | done, merged |
| P1-4 authoring schemas are Japanese-shaped | P1 | **OPEN — done, unmerged** | H-18 `t_8407ea22` (same defect as round-2 P2-7) | branch `wt/harness-locale-scaffolds` @ `2aca201` **unmerged** | done |
| P1-5 assessment breadth is narrow | P1 | **OPEN — decision merged; B-1 merged; B-2/B-3 unmerged** | H-16 `t_3c5d969c`; B-1 `t_673155b0`; B-2 `t_74d99ca5`; B-3 H-22 `t_966d50f4` | decision `dd43d82` via `fa316c5`; B-1 `ce6c8c1` via `4e709d3`; B-2 `423908f`, H-22 `47e152c` **unmerged** | all four done; two merged, two not |
| P1-6 rubric registry is static | P1 | **FIXED (decision) — re-audit not applicable** | H-24 `t_29e6647c` | merge `4f42c3c` (content `491443a`), `docs/RUBRIC-EXTENSIBILITY.md` | done, merged |
| P2-1 test matrix proves policy, not generation | P2 | **OPEN — blocked on H-09** | H-09 `t_ebc196db` | `111c7e9` **unmerged** | done, unmerged |
| P2-2 depth/locale not tested through the product surface | P2 | **FIXED** | H-04 `t_161d467f` + H-13 `t_543c0767` | `cee1749` via `ce95836`; `6779030` | done, merged |
| P2-3 procedure/media evidence is static or fixture | P2 | **OPEN — blocked on H-09** | H-09 `t_ebc196db` | `111c7e9` **unmerged** | done, unmerged |

**P1-3 and P1-6 were UNMAPPED two revisions ago; both now name a merged owner.** P1-3 is closed by
`CHECK_PLAN_SCHEMA_V2` in `bcd545e`, which removes `count` and `independent_evidence` from the v2
check plan; P1-6 is closed as a *decision* by `docs/RUBRIC-EXTENSIBILITY.md`, which deliberately
declines a runtime rubric generator. The P1-6 row is FIXED in the sense the finding asked for
(a gate exists); it is not a runtime feature and no row here implies one. **No round-1 finding
remains UNMAPPED.**

## 5. Finding ledger — round 2 (`docs/ADVERSARIAL-AUDIT-ROUND2.md`)

The report proposed its own `H-11`…`H-18` labels. Those labels **collide** with the board keys; the
board keys are authoritative and are the only ids used here.

| finding | severity | status | owning card | evidence commit | card state |
|---|---|---|---|---|---|
| P0-1 validator-rejected plan is stored as an approvable `draft` | P0 | **FIXED** | H-12 `t_dba06898` | merge `13480c4` (content `4b5f3b1`); round-2 probe updated in `903a606` | done, merged |
| P0-2 fetched excerpt is raw prompt content; invented prose URLs pass | P0 | **FIXED** | H-14 `t_031e287f` | merge `a12176b` (content `0ba4dc6`) | done, merged |
| P1-3 "independent validation" is prompt separation; same model upgrades support | P1 | **OPEN — done, unmerged; integration blocked** | H-15 `t_d519643b`; recovery H-36 `t_48645f63` | branch `wt/harness-validator-independence` @ `833e335` **unmerged** | done; H-36 running |
| P1-4 factual gate auto-waives when research is unavailable | P1 | **OPEN — done, unmerged; same blocker** | H-15 `t_d519643b`; recovery H-36 `t_48645f63` | `833e335` **unmerged** | done; H-36 running |
| P1-5 assessment breadth: three input formats only | P1 | **OPEN — decision merged; B-1 merged; B-2/B-3 unmerged** | H-16 `t_3c5d969c` → B-1 `t_673155b0`, B-2 `t_74d99ca5`, B-3 H-22 `t_966d50f4` | `dd43d82` via `fa316c5`; B-1 `ce6c8c1` via `4e709d3`; B-2 `423908f`/H-22 `47e152c` unmerged | all done; two merged |
| P1-6 flat `$0.75` ceiling, no cost-abort recovery | P1 | **FIXED** | H-17 `t_9a8543ae` (+ `t_d50cb007` v10 brief fix) | content `722f00f` merged at `4dd68cb` into `ce95836`; `fbf96fe` | done, merged |
| P2-7 Japanese-only scaffold triple; no direction field | P2 | **OPEN — done, unmerged** | H-18 `t_8407ea22` | branch `wt/harness-locale-scaffolds` @ `2aca201` **unmerged** | done |
| P2-8 no prerequisite edges; adaptation is a state label | P2 | **FIXED — re-audit required** | H-20 `t_43ca17b8` (frozen contract) + H-21c `t_6576b611` (implementation) | contract `516d161` via `d079b4c`; implementation merge `2252231` (content `bcd545e`) | done, merged |
| P2-9 green policy matrix supplies contract-rejected dials | P2 | **FIXED** | H-01 `t_f4f5b26a` + H-13 `t_543c0767` | merges `b1f2978` (content `8cbaab3`) and `6779030` (content `ee976ea`) | done, merged |
| P2-10 round-1 review uncommitted at audit time | P2 | **FIXED** | H-19 `t_ec1d2c15` | `2e3508f` on master; index `99da48a` now merged via `ce95836` | done, merged |

### H-15's exact integration blocker

H-15 (`t_d519643b`) is `done` at `833e335` on `wt/harness-validator-independence` and it is **not
on master**. A merge-tree against `f990cad` was run for this revision:

```
git merge-tree --write-tree f990cad 833e335     # exit 1
CONFLICT (content): coursebook/generation.py
CONFLICT (content): coursebook/research.py
CONFLICT (content): docs/GENERATION.md
CONFLICT (content): tests/fixtures/generation/validation_pass.json
CONFLICT (content): tests/test_generation.py
```

Five conflicted files (the H-36 card body counts 15 hunks inside them). H-15 was authored before
H-13/H-14, H-21c and H-35 landed, so its validator identity/outcome/`facts_unverified` additions sit
on the same functions the blueprint plan path and the checklist/grading lanes now own. The supervisor
never forced a resolution: `master` contains no partial H-15 code. **H-36 `t_48645f63` is the
recovery card** and its brief is a semantic union, not `ours`/`theirs`. Until H-36 lands, no row here
may say validator independence is fixed.

### Why round-2 P0-1 is FIXED, precisely

H-12's content commit `4b5f3b1` is an ancestor of `master` through merge `13480c4`. The merged
behaviour: `plan.approve` refuses an empty plan with `plan_empty`, refuses a generated plan whose
latest `gen_plan_documents` row is not pass-state with `plan_not_validated`, refuses a stale
content hash with `plan_validation_stale`, and writes no transition or revision on refusal. Edit,
replan and direct objective authoring durably invalidate the prior pass. Manual non-empty plans
approve without claiming validation.

The round-2 probe that used to assert "a rejected plan approves" was rewritten in `903a606` to
assert the refusal. That commit is **not** a merge commit and does not by itself fix anything; it
is the merged test evidence that the fix is asserted.

### P2-10 closure, precisely

The round-1 review was untracked when Sable audited. It is committed in `2e3508f`. The round-2
report's Method section and its P2-10 status line were corrected on the H-19 branch. H-19's index
commit `99da48a` is now an ancestor of `f990cad` via `ce95836`, so the correction and this register
both reach a reader on `master`.

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
| D-04 "adaptation" is a state transition | **OPEN — narrowed** | H-03 (design, merged `54087de`), H-20 (contract `516d161`, merged `d079b4c`), H-21c (`bcd545e`, merged `2252231`) | see left | prerequisite sequencing now exists; there is still **no** dynamic re-plan, no choice among remediation/examples/next objective and no attempt-driven content change. Do not market it as adaptive teaching. Re-audit required (H-30b). |
| D-05 validation independence is structural only | **OPEN — done, unmerged; integration blocked** | H-15 `t_d519643b`; recovery H-36 `t_48645f63` | branch `wt/harness-validator-independence` @ `833e335` **unmerged** | same as round-2 P1-3/P1-4. Master carries no H-15 code. |
| D-06 stale CB-QA-10 claim survives in README | **OPEN — done, unmerged** | H-11 `t_6f41e0b0` | branch `wt/harness-docs` @ `b2233ac` **unmerged** | truth pass delivered on the branch; README/PRIVACY_EGRESS/ACCEPTANCE/REVIEW_CB014 reconciliation is not on `master` |

D-06 also covers the `REVIEW_CB014.md` row for CB-QA-10 ("OPEN"). That row is **not** rewritten
here: the code may already project only `PUBLIC_CRITERION_FIELDS` (per
`tests/test_review_evidence.py`), but this card did not re-derive that, so the public record stays
as it is and H-11 owns the reconciliation.

## 7. Third wave — UX, generic-harness and acceptance findings

`docs/ADVERSARIAL-UX-REVIEW.md` and `docs/GENERIC-HARNESS-REVIEW.md` are merged at `2e57efa`
(amended by `31b3132`, `6d062e1`, `db5662c`). `docs/GENERIC-ACCEPTANCE-AUDIT.md` (`ddc71fc`) is
merged at `090e755` but audits `498b1da`, not `f990cad`. Card bodies are the authority for scope.

### Generic-harness findings (G-series, `docs/GENERIC-HARNESS-REVIEW.md`)

| finding | summary | owning card | merged state | re-audit |
|---|---|---|---|---|
| G-01 | One-off shape is schema-rejected (`minItems: 4` objectives, 2 sections) | H-21a/b/c (`t_27867486`, `t_fb8b9622`, `t_6576b611`) | **merged** `2252231` — `PLAN_SCHEMA_V2` objectives `minItems: 1`, and `SCOPE_EXPECTATIONS["single"]["blueprint_objectives"] = (1, 1)` | required, H-30b |
| G-02 | Generated checks are saved, not graded (no reference `kind`) | B-1 `t_673155b0` (H-16 B-1; the card title carries a stale "H-20" collision label) | **merged** `4e709d3` (content `ce6c8c1`), `docs/GRADING-LANES.md`, `tests/test_grading_lanes.py` | required, H-30b |
| G-03 | Scope is on the wire but the plan shape caps it | H-21a/b/c | **merged** `2252231` — v2 `objectives` `maxItems: 40`, `units` `minItems: 1` | required, H-30b |
| G-04 | Media/procedure lens incomplete | H-05 `t_7baa29e2` (merged) + H-06 `t_7a320d2f` (done, unmerged) | H-05 merged `ce95836`; H-06 `00b502f` branch-only | required when H-06 lands |
| G-05 | Only a prepared Japanese pack has run end to end | H-09 `t_ebc196db` (packet) + H-30 `t_178dc615` (audit) | H-09 `111c7e9` branch-only; H-30 merged `090e755` but audits `498b1da` | **required**, H-30b |
| G-06 | Student mode / second import path does not exist | H-25 `t_5535fc66` (design), H-26a `t_faad26cf` (backend), H-27 `t_71ea55ee` (UI) | design **merged** `e978441` (content `3705a7a`); backend and UI unmerged | n/a until backend lands |
| G-07 | Rubric profiles are static | H-24 `t_29e6647c` (decision, not a runtime generator) | **merged** `4f42c3c` (content `491443a`), `docs/RUBRIC-EXTENSIBILITY.md` | decision only; no runtime to audit |

### H-30 acceptance findings (D1…D8, `docs/GENERIC-ACCEPTANCE-AUDIT.md` @ `498b1da`)

H-30 ran on `498b1da`, before `2252231`/`4e709d3`. Its P0 findings are therefore **re-audit
required** against `f990cad`, owned by H-30b `t_9b6742f3`. Do not quote them as current.

| id | H-30 verdict at `498b1da` | what changed on `f990cad` | status |
|---|---|---|---|
| D1 | `single` padded to 4 objectives — FAIL | `PLAN_SCHEMA_V2` `minItems: 1`; `blueprint_objectives` for `single` = (1, 1) in `bcd545e` | **re-audit required** (H-30b) |
| D2 | `full` truncated at 8, no units/prereqs — BLOCKED | `maxItems: 40`, `plan_units` in `db.v7` migration `0007_plan_units.sql`, §14 gating in `bcd545e` | **re-audit required** (H-30b) |
| D3 | generated checks return `needs_retry` for both answers — FAIL | fix `ce6c8c1` merged at `4e709d3` | **re-audit required** (H-30b) |
| D4 | language goal with no locale/domain silently `general` | unchanged; no merged card closes it | OPEN — Atlas to route (nearest H-13/H-18) |
| D5 | H-09 evidence docs do not name the evidence commit; test count environment-dependent | unchanged | OPEN — H-09 / H-11 |
| D6 | H-09 `scope_matches_documented_bounds` compares the code to itself | unchanged | OPEN — H-09 |
| D7 | evidence packet not byte-reproducible (verdict-only freshness guard) | unchanged | OPEN — H-09 |
| D8 | lesson validator accepted truncated authored texts | unchanged | OPEN — H-09 / lesson-validator owner |

### UX findings (UX-series, `docs/ADVERSARIAL-UX-REVIEW.md`)

None of these has merged code. H-28 (`t_271e19e7`) and H-29 (`t_70686b14`) are the owning cards;
H-28 is running, H-29 is todo.

| finding | summary | owning card | card state |
|---|---|---|---|
| UX-01 | First run explains the system, not the invitation | H-28 `t_271e19e7` | running |
| UX-02 | "Recipe" is the wrong first question; Japanese-only placeholders | H-28 `t_271e19e7` | running |
| UX-03 | Create result is a receipt, not a beginning | H-28 `t_271e19e7` | running |
| UX-04 | Lesson index is a metadata table | H-29 `t_70686b14` | todo |
| UX-05 | Result screen is accurate and unkind | H-29 `t_70686b14` | todo |
| UX-06 | Library/Import has no plain explanation | H-28 `t_271e19e7` (with H-27) | running |
| UX-07 | Parent Studio speaks builder vocabulary | H-28 `t_271e19e7` | running |
| UX-08 | Cross-surface visual language is flat | H-29 `t_70686b14` / host | todo |
| UX-09 | Scope and expectation are unclear on screen | H-28 `t_271e19e7` | running |
| UX-10 | Status and error tone | H-29 `t_70686b14` | todo |

### H-16 B-series (defect register inside `docs/ASSESSMENT-BREADTH.md` §11)

The decision document is on master (`fa316c5`, content `dd43d82`). The three implementation
defects split: B-1 merged, B-2 and B-3 not.

| finding | summary | owning card | merged state |
|---|---|---|---|
| B-1 | Generated lesson checks store no reference `kind`; grader falls to the unconfigured open lane | `t_673155b0` (title still says "H-20"; **B-1** is authoritative) | **merged** `4e709d3` (content `ce6c8c1`); `docs/GRADING-LANES.md`, `tests/test_grading_lanes.py` (15 tests) |
| B-2 | `record_observation` has no RPC method, handler or UI; `self_reported`/`parent_reported` unreachable | `t_74d99ca5` (Atlas's earlier label was "H-21"; **B-2** is authoritative) | done, **unmerged**: `wt/harness-observation-record` @ `423908f` (its cb.rpc v12 is not on `f990cad`) |
| B-3 | `EVIDENCE_CLASS_COPY` covers 4 of 6 evidence classes | H-22 `t_966d50f4` (frozen disclosure copy + labels) | done, **unmerged**: `wt/harness-breadth-copy` @ `47e152c` |

**H-23 `t_132531da` ("Generated checks are ungradable") is `done` as a duplicate with no product
code:** it was seeded before the B-1 duplicate was noticed. It is not evidence for B-1 and must not
be re-run. B-1's owner is `t_673155b0`, and B-1's fix is `ce6c8c1`.

## 8. Card index — H-21…H-36

Every card created after the second wave, with the findings it owns or audits, its branch, and its
**merged** state at `f990cad`.

| card | id | owner | parents | branch | merged at `f990cad` | owns / audits |
|---|---|---|---|---|---|---|
| H-21 (original) | `t_2a2fc90c` | cinder | H-13, H-01 | `wt/t_2a2fc90c` @ `5ba4e4c` | **no — superseded, no merge** | closed and split; the branch tip is history, not evidence |
| H-21a | `t_27867486` | cinder | H-21 | `wt/h21a-contract-migration` @ `8eb83d8` | **yes** — `2252231` | cb.rpc v11, cb.db v7, migration `0007_plan_units.sql`, legacy-hash invariance |
| H-21b | `t_fb8b9622` | cinder | H-21a | `wt/h21b-unit-stages` @ `7f46e17` | **yes** — `2252231` | `PLAN_SCHEMA` v2 (`coursebook.plan.v2`), unit-scoped plan/lesson stages |
| H-21c | `t_6576b611` | cinder | H-21b | `wt/h21c-prereq-gating` @ `bcd545e` | **yes** — `2252231` | R1–R9 prerequisite gating, §14.4 tests, `docs/PLAN-CEILING.md` |
| H-22 | `t_966d50f4` | vellum | H-16 | `wt/harness-breadth-copy` @ `47e152c` | no | H-16 B-3 (evidence-class copy), §7 frozen breadth disclosure |
| H-23 | `t_132531da` | cinder | H-16 | — | — | **closed duplicate of B-1, no code**; B-1 owner is `t_673155b0` |
| H-24 | `t_29e6647c` | atlas | H-16 | `wt/harness-rubric-extensibility` @ `491443a` | **yes** — `4f42c3c` | round-1 P1-6, G-07 (decision only) |
| H-25 | `t_5535fc66` | atlas | H-03, H-02 | `wt/harness-student-mode-design` @ `3705a7a` | **yes** — `e978441` | G-06 design (`docs/STUDENT-MODE.md`) |
| H-26 (original) | `t_da9e472c` | cinder | H-25 | `wt/harness-student-import` @ `2d7ecde` (salvage) | **no — superseded** | timed out at 150 iterations; WIP salvaged; **not implemented** |
| H-26a | `t_faad26cf` | cinder | H-26, H-25 | `wt/harness-student-import` | no (running) | rebase/renumber the salvage onto cb.rpc v11; finish parse → map → companion course |
| H-27 | `t_71ea55ee` | vellum | H-25, H-26a | `wt/harness-student-ui` | no (running) | G-06 learner intake/alignment |
| H-28 | `t_271e19e7` | vellum | H-02, H-22, H-21 | `wt/harness-ux-first-run` | no (running) | UX-01, UX-02, UX-03, UX-06, UX-07, UX-09 |
| H-29 | `t_70686b14` | vellum | H-28 | `wt/harness-ux-learning` | no (todo) | UX-04, UX-05, UX-08, UX-10 |
| H-30 | `t_178dc615` | sentinel | H-09 | `wt/harness-generic-audit` @ `ddc71fc` | **yes** — `090e755` | G-05 independent audit, **of `498b1da`** |
| H-30b | `t_9b6742f3` | sentinel | H-30, H-21c | `wt/harness-generic-audit` | no (running) | **re-audit** of the single/short/full findings against `f990cad` |
| H-31 | `t_1c9d0ba6` | quill | H-12, H-14, H-02, H-03 | `wt/harness-audit-refresh` @ `512c5f6` | **yes** — `fdecc9e` | first index refresh; rewrites no finding |
| H-31b | `t_a8e017b5` | quill | H-31, H-21c, H-35 | `wt/harness-audit-refresh-2` | no (this card) | this revision: merged-vs-card reconciliation, H-30b re-audit marker |
| H-32 | `t_69873d4c` | cinder | H-07, H-13, H-14 | `wt/harness-parent-brief-rebase` @ `bc508ce` | **not as its own tip** — the union landed as `afac32c` inside `ce95836`; `bc508ce` is branch-only | conflict repair so H-07 can merge onto H-13/H-14 |
| H-32b | `t_71f53265` | cinder | H-32 | `wt/h32-parent-brief-regression` @ `8d018e4` | **yes** — `c7461fc` | ports the parent-brief × H-13 × H-14 conflict regression onto master |
| H-33 | `t_6aafc7f2` | atlas | H-20 | `wt/harness-checklist-confirmation` @ `da53ec1` | **yes** — `4e709d3` | frozen checklist-confirmation decision |
| H-34 | `t_82c24349` | cinder | H-33 | `wt/harness-checklist-ui` @ `78c6019` | **yes** — `4e709d3` | checklist tick-list graded `self_reported` (kernel) |
| H-35 | `t_65e7d83a` | vellum | H-34 | `wt/harness-checklist-ui` @ `a498969` | **yes** — `4e709d3` | checklist confirmation surface (checkboxes, selection payload) |
| H-35b | `t_db0b76f8` | vellum | H-35 | — | no (running) | **live installed-Desktop DOM capture on a fresh rig** — evidence only |
| H-36 | `t_48645f63` | atlas | H-15, H-21c, H-35 | `wt/harness-validator-integration` (created at `f990cad`, no integration commit yet) | no (running) | integrate `833e335` onto `f990cad`; recovery, not a new design |

## 9. Provenance checks this index relies on

Run on `master` at `f990cad`. Each must stay true or the index is stale.

```
git cat-file -e f990cad:docs/ADVERSARIAL-HARNESS-REVIEW.md
git cat-file -e f990cad:docs/ADVERSARIAL-AUDIT-ROUND2.md
git cat-file -e f990cad:docs/ADVERSARIAL-UX-REVIEW.md
git cat-file -e f990cad:docs/GENERIC-HARNESS-REVIEW.md
git cat-file -e f990cad:docs/GENERIC-ACCEPTANCE-AUDIT.md
git cat-file -e f990cad:docs/ASSESSMENT-BREADTH.md
git cat-file -e f990cad:docs/COURSE-BLUEPRINT.md
git cat-file -e f990cad:docs/PLAN-CEILING.md
git cat-file -e f990cad:docs/GRADING-LANES.md
git cat-file -e f990cad:docs/CHECKLIST-CONFIRMATION.md
git cat-file -e f990cad:docs/RUBRIC-EXTENSIBILITY.md
git cat-file -e f990cad:docs/STUDENT-MODE.md
git cat-file -e f990cad:contracts/rpc.v11.json
git cat-file -e f990cad:contracts/db.v7.json
git cat-file -e f990cad:coursebook/migrations/0007_plan_units.sql
git cat-file -e f990cad:tests/test_prerequisite_gating.py
git cat-file -e f990cad:tests/test_grading_lanes.py
git cat-file -e f990cad:tests/test_checklist_confirmation.py

git merge-base --is-ancestor 13480c4 f990cad   # H-12 merge
git merge-base --is-ancestor 903a606 f990cad   # H-12 round-2 audit assertion (test commit)
git merge-base --is-ancestor b1f2978 f990cad   # H-01 merge
git merge-base --is-ancestor a12176b f990cad   # H-14 merge
git merge-base --is-ancestor 1bbd502 f990cad   # H-02 merge
git merge-base --is-ancestor 54087de f990cad   # H-03 design merge
git merge-base --is-ancestor 6779030 f990cad   # H-13 merge
git merge-base --is-ancestor ce95836 f990cad   # integration merge: H-04/H-05/H-07/H-17/H-19
git merge-base --is-ancestor fa316c5 f990cad   # H-16 decision
git merge-base --is-ancestor d079b4c f990cad   # H-20 frozen contract
git merge-base --is-ancestor 2252231 f990cad   # H-21a/b/c implementation merge
git merge-base --is-ancestor 4e709d3 f990cad   # H-20/H-33/H-34/H-35 checklist + grading merge
git merge-base --is-ancestor e978441 f990cad   # H-25 design merge
git merge-base --is-ancestor 090e755 f990cad   # H-30 audit merge
git merge-base --is-ancestor c7461fc f990cad   # H-32b merge
git merge-base --is-ancestor 4f42c3c f990cad   # H-24 decision merge
git merge-base --is-ancestor fdecc9e f990cad   # H-31 index merge

# must NOT be ancestors — a merged fix must not be claimed where it is not
git merge-base --is-ancestor 833e335 f990cad ; test $? -eq 1   # H-15 unmerged
git merge-base --is-ancestor b2233ac f990cad ; test $? -eq 1   # H-11 unmerged
git merge-base --is-ancestor 111c7e9 f990cad ; test $? -eq 1   # H-09 unmerged
git merge-base --is-ancestor 00b502f f990cad ; test $? -eq 1   # H-06 unmerged
git merge-base --is-ancestor c9c6cec f990cad ; test $? -eq 1   # H-08 unmerged
git merge-base --is-ancestor 2aca201 f990cad ; test $? -eq 1   # H-18 unmerged
git merge-base --is-ancestor 423908f f990cad ; test $? -eq 1   # B-2 unmerged
git merge-base --is-ancestor 47e152c f990cad ; test $? -eq 1   # B-3/H-22 unmerged
git merge-base --is-ancestor 2d7ecde f990cad ; test $? -eq 1   # H-26 salvage unmerged
```

Rules enforced:

- **No claim cites a file that exists only in a worktree.** Every report above is tracked at
  `f990cad`. The rows that describe a branch-only fix name the tip so a reader can check it, not so
  it can be treated as merged.
- **A branch is not a merge, and a done card is not a merge.** H-06, H-08, H-09, H-11, H-15, H-18,
  H-22, B-2 and H-26's salvage are `done` with unmerged branches; each is recorded that way.
- **A merged fix is not a passed re-audit.** H-30's single/full findings are marked re-audit
  required until H-30b probes `f990cad`. The row is not allowed to read as closed.
- **A prepared pack is not a topic proof.** No row above derives a harness claim from
  `bundled/packs/japanese-affection-context-l0`.
- **A live capture is not implied by a merged surface.** H-35's surface is merged; no live DOM
  capture exists and H-35b owns it.

## 10. What this index does not claim

- It does not claim the harness is fully generic. `docs/GENERIC-HARNESS-REVIEW.md` at `f990cad`
  says "partially generic". The shape blockers G-01/G-03 are *implemented* at `2252231`, but no
  independent probe has re-run them against `f990cad`; H-30b owns that.
- It does not claim H-06, H-08, H-09, H-11, H-15, H-18, H-22 or B-2 is fixed; their branches are
  unmerged and every such row says so.
- It does not claim H-15's validator independence is on master. It is not, and H-36 exists only to
  attempt the integration.
- It does not claim H-23 did any work: it was closed as a duplicate with no code.
- It does not claim H-26 was implemented. The original card timed out; its WIP was salvaged at
  `2d7ecde` and H-26a owns the continuation.
- It does not claim the checklist confirmation has a live Desktop capture. H-35 is
  implementation + fixture evidence only; H-35b owns the live evidence.
- It does not claim any finding is closed because a card is `done`.
- It does not re-run, re-grade or extend any audit; probe results are attributed to the card that
  produced them.
- It does not claim the harness is installable, demo-ready, or proven on an arbitrary topic. H-09
  (`t_ebc196db`) is the only card that can establish arbitrary-topic generation; its packet is
  unmerged, H-30 audited an older tree, and H-30b re-audits.
- It does not use the prepared Japanese pack as evidence for anything.
- It changes no product code, contract, schema, migration or test.

## 11. Changes in this revision (H-31b) — every moved row and its commit

Compared with the H-31 revision (`512c5f6`). "Merged" was checked against `master` = `f990cad` with
`git merge-base --is-ancestor`. Rows not listed did not change status in this revision.

| row | previous status (H-31) | status now | commit that justifies it | merged |
|---|---|---|---|---|
| round-1 P0-2 | OPEN — design merged, implementation unmerged (`5ba4e4c`) | **FIXED — implementation merged; re-audit required** | `2252231` (content `bcd545e`; slices `8eb83d8`, `7f46e17`) | yes |
| round-1 P0-4 | OPEN — done, unmerged (`cee1749`) | **FIXED** | `cee1749` via `ce95836` | yes |
| round-1 P0-5 | OPEN (H-08 running) | OPEN — done, unmerged | `c9c6cec` | no |
| round-1 P0-6 | OPEN (H-06 running) | OPEN — done, unmerged | `00b502f` | no |
| round-1 P0-7 | OPEN (H-09 todo) | OPEN — done, unmerged | `111c7e9` | no |
| round-1 P1-1 | OPEN — done, unmerged (`8a6bedb`) | **FIXED** | `8a6bedb` via `ce95836`; regression `8d018e4` via `c7461fc` | yes |
| round-1 P1-2 | OPEN — done, unmerged (`986190f`) | **FIXED** | `986190f` via `ce95836` | yes |
| round-1 P1-3 | OPEN — mapped to H-21 (`5ba4e4c`) | **FIXED — re-audit required** | `bcd545e` via `2252231` (`CHECK_PLAN_SCHEMA_V2`) | yes |
| round-1 P1-4 | OPEN (H-18 running) | OPEN — done, unmerged | `2aca201` | no |
| round-1 P1-5 | OPEN — decision unmerged, B-1/B-2/H-22 running | OPEN — decision merged; B-1 merged; B-2/B-3 unmerged | `fa316c5`; `4e709d3`; `423908f`; `47e152c` | mixed |
| round-1 P1-6 | OPEN — mapped to H-24, no commits | **FIXED (decision)** | `491443a` via `4f42c3c` | yes |
| round-1 P2-1 | OPEN (H-09 todo) | OPEN — blocked on H-09 | `111c7e9` | no |
| round-1 P2-2 | OPEN — half mapped | **FIXED** | `cee1749` via `ce95836` + `6779030` | yes |
| round-1 P2-3 | OPEN (H-09 todo) | OPEN — blocked on H-09 | `111c7e9` | no |
| round-2 P1-3 | OPEN — done, unmerged | OPEN — done, unmerged; **integration blocked, H-36** | `833e335` | no |
| round-2 P1-4 | OPEN — done, unmerged | OPEN — done, unmerged; **integration blocked, H-36** | `833e335` | no |
| round-2 P1-5 | OPEN — decision unmerged; implementations running | OPEN — decision merged; B-1 merged; B-2/B-3 unmerged | `fa316c5`; `4e709d3`; `423908f`; `47e152c` | mixed |
| round-2 P1-6 | OPEN — done, unmerged (`722f00f`) | **FIXED** | `722f00f` via `4dd68cb` → `ce95836` | yes |
| round-2 P2-7 | OPEN (H-18 running) | OPEN — done, unmerged | `2aca201` | no |
| round-2 P2-8 | OPEN — done, unmerged (`516d161`) | **FIXED — re-audit required** | `516d161` via `d079b4c`; impl `bcd545e` via `2252231` | yes |
| round-2 P2-10 | FIXED — index branch-only | **FIXED** — index now merged | `99da48a` via `ce95836` | yes |
| D-04 | OPEN — design merged, implementations unmerged | **OPEN — narrowed** (sequencing merged, adaptation claim unchanged) | `516d161`; `bcd545e` | partial |
| D-05 | OPEN — done, unmerged | OPEN — done, unmerged; **H-36 recovery named** | `833e335` | no |
| D-06 | OPEN (H-11 running) | OPEN — done, unmerged | `b2233ac` | no |
| G-01 | ready, `5ba4e4c` unmerged | **merged** `2252231`; re-audit required | `8eb83d8`/`7f46e17`/`bcd545e` | yes |
| G-02 | running (B-1) | **merged** `4e709d3`; re-audit required | `ce6c8c1` | yes |
| G-03 | ready, unmerged | **merged** `2252231`; re-audit required | `bcd545e` | yes |
| G-04 | H-05 done/unmerged + H-06 running | H-05 **merged** `ce95836`; H-06 done/unmerged | `986190f`; `00b502f` | partial |
| G-05 | H-09/H-30 todo | H-09 done/unmerged; H-30 audit **merged** on `498b1da`; **H-30b re-audit required** | `111c7e9`; `ddc71fc`; `090e755` | partial |
| G-06 | H-25 ready | H-25 design **merged**; H-26 superseded → H-26a running; H-27 running | `3705a7a` via `e978441` | design yes |
| G-07 | running, no commits | **merged** (decision) | `491443a` via `4f42c3c` | yes |
| B-1 | running | **merged** `4e709d3` | `ce6c8c1` | yes |
| B-2 | running (`423908f`) | done, unmerged | `423908f` | no |
| B-3 | running (`002a82b`) | done, unmerged | `47e152c` — the branch was rebased onto `f17ec54` (`8ef1cc1`); the old tip `002a82b` is history | no |
| §0 note on H-19 | "index is branch-only, ask the integrator" | retired — `99da48a` is merged via `ce95836` | `ce95836` | yes |

New rows added by this revision: the H-30 acceptance report (§1, §7), the H-24/H-25/H-33/H-34/H-35
decision documents (§1), H-21a/b/c and H-26a/H-30b/H-31b/H-35b/H-36 card rows (§8), the
implementation-versus-re-audit distinction (§0, §7, §10), and the eight-fold provenance block in §9.

**Findings still UNMAPPED after this revision: none.** The change from the last revision is not
routing — every finding already had an owner — but **state**: fourteen rows that read "open" or
"unmerged" were in fact merged at `f990cad`, and three merged implementations now carry an explicit
"re-audit required" marker instead of reading as closed. Fixing the first without the second would
have replaced one overstatement with another.
