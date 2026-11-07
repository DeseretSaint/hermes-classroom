# AUDIT-INDEX — Coursebook audit evidence register

Owner: quill. Created by H-19 (`t_ec1d2c15`) at `99da48a` on `wt/harness-audit-index`; refreshed by
H-31 (`t_1c9d0ba6`) at `512c5f6` on `wt/harness-audit-refresh`; refreshed by H-31b (`t_a8e017b5`)
at `a671511`/`385ebac` on `master` (its branch tip `2bfeb1c` is **not** an ancestor — the content was
re-landed, see §0); refreshed again by H-41 (`t_ef2600f8`) on `wt/audit-index-h41`, based on
`master` at `1fc0542` (`1fc054292eac1d8565aafebb3c9a71e004cd672c`), the H-38 UX union, whose
`desktop/plugin.js` sha256 is `c206e1c9091400af11594a440a105cda8a6794fe3563ad15a23a10e522232463`.

All earlier revisions are on `master`: `99da48a` through the integration merge `ce95836`,
`512c5f6` through merge `fdecc9e`, `a671511`/`385ebac` through the H-37/H-38 sequence. A reader does
not need a branch to see this file any more; they need the commit above. `docs/AUDIT-INDEX.md` at
`385ebac` is byte-identical to the file at `1fc0542`
(`git diff --stat 385ebac 1fc0542 -- docs/AUDIT-INDEX.md` is empty).

Purpose: make every audit claim reproducible from a **commit hash**, not from a working-tree path.
A report is evidence only if the file it lives in resolves to a commit, the probes that produced it
resolve to a commit, and the finding's status names the card that owns the fix.

Rule for citing this index: quote the commit hash and the file path, never a worktree path. If a
file is not reachable with `git cat-file -e <hash>:<path>`, it is not evidence.

## 0. How to read this after merges

Four things are routinely confused. They are not the same:

- **A card being `done` is not a merge.** `done` means the assigned worker finished and reported.
  The branch may still be unmerged. Every ledger row below names a commit *and* says whether that
  commit is an ancestor of `master` at `1fc0542`.
- **A merge is not an independent re-audit.** A merged fix proves the code landed; it does not
  prove the defect is gone. Where a merged implementation has not been re-probed against the
  commit that carries it, the row says **re-audit required** and names the audit card
  (H-30b `t_9b6742f3` for the harness findings; H-36 `t_48645f63` is an integration repair, not
  an audit).
- **A branch tip is not merged evidence.** A finding flips to FIXED only when its fix is an
  ancestor of `master` (`git merge-base --is-ancestor <commit> 1fc0542` exits 0) and the merged
  tree passed the frozen gate. A branch-only fix stays OPEN, marked "done, unmerged".
- **A content commit is not a merge commit.** Cite both where they differ: merge `2252231`
  carries content `bcd545e`. A squash, a test commit or a rebase is not a merge, and a card body
  that calls one a merge is corrected here rather than repeated.

Correction notes for this revision:

- The previous revision said H-19's index was branch-only. It is merged: `99da48a` is an ancestor
  of `1fc0542` through the integration merge `ce95836`. That note is retired, not deleted, so a
  reader who saw the old text knows which line moved.
- **The H-22/H-28/H-29 P0 framing is retired.** The previous revision recorded those three cards as
  done, green and absent from `master` at `f990cad` — that was true there, and it was the P0 it said
  it was. They are now merged: `47e152c`, `184640a` and `eb8e4c5` are all ancestors of `1fc0542`
  through the H-38 union commit `1fc0542` itself. The frozen §7 disclosure copy is present in the
  shipped `desktop/plugin.js` at `1fc0542` and absent at `c588e4a` (both checked by string count for
  this card). The retired rows stay readable in §12, which records what moved.
- **H-15's integration blocker is closed.** The previous revision's `git merge-tree f990cad 833e335`
  produced five conflicted files and no merged H-15 code. `833e335` is now an ancestor of `1fc0542`
  through the H-36 merge `b75d601`, and `docs/H15-VALIDATOR-INDEPENDENCE.md` resolves on master.
  That is an integration repair, not a re-audit; see §5.
- **The H-35b live-capture gap is closed.** `docs/H35B-LIVE-CHECKLIST-EVIDENCE.md` and
  `docs/h35b-shots/**` are on master at `7a6b4b0`, captured at plugin sha `ab6347…` on `f990cad`.
  The capture was **not** re-taken at the shipped `c206e1c9`; it is evidence about the checklist
  surface, not about the H-38 copy.
- H-12's card body cites `903a606` as its "merge commit". `903a606` is a **test commit**, not a
  merge: it asserts the fail-closed behaviour in the round-2 audit suite. Both hashes are recorded
  below rather than repeating the mislabel.
- H-31b's branch tip `2bfeb1c` is **not** an ancestor of `1fc0542`. The same change exists on master
  as `a671511` and the follow-up `385ebac`; the tree at `385ebac` matches `1fc0542`. Citing
  `2bfeb1c` as merged evidence would fail `git merge-base --is-ancestor` and is not done here.

## 1. Report register

Every file below is tracked; the verification column names the commit that contains it. A report
whose only commit is on an unmerged branch is marked **branch-only** and is not evidence about
merged behaviour.

| report | what it is | introduced in | content sha256 at `1fc0542` | verification |
|---|---|---|---|---|
| `docs/ADVERSARIAL-HARNESS-REVIEW.md` | audit round 1 — harness capability verdict (NO-GO as a general harness) | `2e3508f` | `405e552459f0ca8c993c9c2bde78cbc7fd7ba0988d9bdb621c5f31970e76b7bd` | `git cat-file -e 2e3508f:docs/ADVERSARIAL-HARNESS-REVIEW.md` |
| `docs/ADVERSARIAL-AUDIT-ROUND2.md` | audit round 2 — 14 deterministic probes, 10 findings | master via merge `7af3bbd` (audit commit `9357c00`; probe assertion `903a606`) | `646242073fd0d60f7f70f86e439aae2bc29482afa5d8afe7f9f0d8161e3a8d96` | `git cat-file -e 1fc0542:docs/ADVERSARIAL-AUDIT-ROUND2.md` |
| `docs/ADVERSARIAL-UX-REVIEW.md` | adversarial UX review — learner and Parent Studio surfaces (GO for a UX pass, not a rewrite) | `2e57efa` | `840d000ecd6bb2d1892af34f9142126864bb0f5cc9c1d37eb43f7f74e4128c94` | `git cat-file -e 1fc0542:docs/ADVERSARIAL-UX-REVIEW.md` |
| `docs/GENERIC-HARNESS-REVIEW.md` | generic-harness review — can Coursebook teach an arbitrary topic (partially generic), evidence G-01…G-07 | `2e57efa`; amended `31b3132`, `6d062e1`, `db5662c` | `a8d119aa28763013d90d10f1c11c01f096d9412def17b8b5970e9eaa67e53da4` | `git cat-file -e 1fc0542:docs/GENERIC-HARNESS-REVIEW.md` |
| `docs/GENERIC-ACCEPTANCE-AUDIT.md` | H-30 independent acceptance audit of H-09 (three shapes, checks, routing); base product tree `498b1da` | `ddc71fc`; merged at `090e755` | `19cbe115688e37a5814ee33c5699e1d984965e013f8c6818e6292cec738ecd89` | `git cat-file -e 1fc0542:docs/GENERIC-ACCEPTANCE-AUDIT.md`; `git merge-base --is-ancestor 090e755 1fc0542` |
| `docs/ASSESSMENT-BREADTH.md` | H-16 assessment construct breadth decision and its B-1/B-2/B-3 defect register | `dd43d82`; merged at `fa316c5` | `38021edef4d6cafdf9c45eaff0bcfbe17c8e2960150fba70093d99590f9e2c7e` | `git cat-file -e 1fc0542:docs/ASSESSMENT-BREADTH.md` |
| `docs/COURSE-BLUEPRINT.md` | H-03 scope-aware blueprint design (single/short/full) plus §14, the frozen H-20 prerequisite contract; design authority for H-21 | master via merge `54087de` (content `f465a4d`); §14 added by `516d161` via `d079b4c` | `cf371b0e52ba3606667041889a05885abe07e146a757c774c529f1fd238911e0` | `git cat-file -e 1fc0542:docs/COURSE-BLUEPRINT.md` |
| `docs/PLAN-CEILING.md` | H-21c measured `full` plan ceiling; the probe behind the 40-objective cap | `bcd545e`; merged at `2252231` | `9dc0792ad9eec2e7bafb8a5b974c94ac0dc74532ba4788c417c717f2436efad9` | `git cat-file -e 1fc0542:docs/PLAN-CEILING.md` |
| `docs/GRADING-LANES.md` | H-20 decision + implementation record: every stored check declares its lane (implements B-1) | `ce6c8c1`; merged at `3368c96`, which enters `master` through `4e709d3` | `d4cb723096a513925cf8e7d30ad02b9b9bb4bee24570342e612a23b61a869916` | `git cat-file -e 1fc0542:docs/GRADING-LANES.md`; `git merge-base --is-ancestor 4e709d3 1fc0542` |
| `docs/CHECKLIST-CONFIRMATION.md` | H-33 frozen decision: a verification tick-list is graded `self_reported` | `da53ec1`; merged at `3d46988`, which enters `master` through `4e709d3` | `f559b2f18423f17fac3ae183bb6b9f8b76dec5371b8270498ca00940dd6c7f15` | `git cat-file -e 1fc0542:docs/CHECKLIST-CONFIRMATION.md` |
| `docs/RUBRIC-EXTENSIBILITY.md` | H-24 frozen decision: the gate for a new construct profile (decision only, no runtime generator) | `491443a`; merged at `4f42c3c` | `7c73550ca4bbd9ef7cb55dbc9595c36e6926abcc108b236998da70bbc8c9d153` | `git cat-file -e 1fc0542:docs/RUBRIC-EXTENSIBILITY.md` |
| `docs/STUDENT-MODE.md` | H-25 student-mode design: a companion course aligned to an uploaded syllabus; design only | `3705a7a`; merged at `e978441` | `df4dcdeca230d064e0b7cfc19b785f44ede1c40d862d2c16f4b934408b77deef` | `git cat-file -e 1fc0542:docs/STUDENT-MODE.md` |
| `docs/HARNESS-NEXT-CARDS.md` | board card index / DAG, card-to-finding mapping, current-wave status | `2e3508f`; amended `a8d93b8`, `b4da6d9`, `31b3132`, `f17ec54`, `512c5f6`, `a671511`, `385ebac`, and later cards | `82af6664ba19738d40fa79a3f2da27685c67afea19c5e89d9677f9c41d6838c3` (at `1fc0542`; this card does not edit it. The pin moved from `f990cad` because later cards edited the file, not because the earlier hash was wrong) | `git cat-file -e 1fc0542:docs/HARNESS-NEXT-CARDS.md` |
| `docs/H15-VALIDATOR-INDEPENDENCE.md` | H-36 integration record: H-15's validator identity, `outcome` and no-research waiver landed on cb.rpc v13 | `b75d601` (content on `wt/harness-validator-integration`) | `763c49ed5f50711066b5114c89690e23971a5e49e7f0878144aec833c8fb670a` | `git cat-file -e 1fc0542:docs/H15-VALIDATOR-INDEPENDENCE.md` |
| `docs/H35B-LIVE-CHECKLIST-EVIDENCE.md` | H-35b live installed-Desktop DOM capture of a checklist confirmation on a fresh rig (CDP `127.0.0.1:9351`, backend `44277`) | `7a6b4b0` | `9cbd4d4d2a8e345f6702bf166e399bc695419397d736bf9bea8d835f72ad096c` | `git cat-file -e 1fc0542:docs/H35B-LIVE-CHECKLIST-EVIDENCE.md` |
| `docs/REVIEW_CB014.md` | pre-harness adversarial security/state/a11y release review (cb.rpc v6) | `270edae` | `4a3b00205761eae6e298cc34c3197c868518a0e6ff98ea922ab4c02449c2a91b` | `git cat-file -e 270edae:docs/REVIEW_CB014.md` (amended in `8e11bd2`) |
| `docs/REVIEW_CB014-telemetry.md` | CB-014 tool-telemetry scope note | `51406ee` | `3f77fb9ccca8bf87daa904c1f6a9a13d00c3024f5ca970f5b4b16ffde8efbdb9` | `git cat-file -e 1fc0542:docs/REVIEW_CB014-telemetry.md` |
| `docs/ACCEPTANCE.md` | adversarial acceptance matrix with explicit verified/seam/blocked/pending vocabulary | `b9da9f3` | `869918a97cb8e64f2c1daaaac9599904644049f138ceb6dd386ce1bb9a889d06` | `git cat-file -e 1fc0542:docs/ACCEPTANCE.md` |
| `docs/CB016-RELEASE-VERIFICATION.md` | clean-export install and route-mount record | `7f80f35` | `291b21564292301f07ed0c947a36657079f9762da9e9592a4a999b0ad497a266` | `git cat-file -e 7f80f35:docs/CB016-RELEASE-VERIFICATION.md` |
| `docs/CB017-RELEASE-VERIFICATION.md` | release record re-derived on merged master and re-pinned | `638eb6b` | `55f9b3f07b49dd39dc817181cbddab818fda4ef9335203420b279eb545c79a3f` | `git cat-file -e 638eb6b:docs/CB017-RELEASE-VERIFICATION.md` (amended in `6eb93c2`) |
| `docs/M4-VISUAL-MEDIA-AUDIT.md` | M4-QA visual/accessibility/media truth gate (62 painted frames) | `2b37b5b` | `6f4a109f1fc0f6aae5fe5ecea0ae5c58d6fab5438af629fb32c3591bad606689` | `git cat-file -e 2b37b5b:docs/M4-VISUAL-MEDIA-AUDIT.md` (amended in `27a2e40`) |
| `docs/DEMO.md` | honest demo status; states the prepared pack proves one pack only | `5ad682e` | `27651b66410b54a6381430ae9945196ff78199f74cd0b75c188280b376d084ba` | `git cat-file -e 1fc0542:docs/DEMO.md` |

Every `content sha256 at 1fc0542` value above was computed with
`git show 1fc0542:<path> | sha256sum` for this revision. A hash that does not reproduce at the named
commit is a stale row, not a rounding error. Nineteen of the twenty pins reproduced unchanged from
the H-31b revision even though master moved `f990cad` → `1fc0542`; only `HARNESS-NEXT-CARDS.md`
moved, and only because other cards edited it. That is why the H-31b hashes were trustworthy and
the **statuses** were not: content pins and merge claims are different questions.

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
`tests/test_grading_lanes.py` resolves at `1fc0542`.

### H-35/H-34 checklist confirmation

```
node --check desktop/plugin.js                      # OK
python3 -m unittest discover -s tests -t .          # Ran 1264 tests, OK
bash scripts/validate-plugin.sh                     # 3/3 checks on 1278 files
```

Reported by the H-35 card at `a498969`. `tests/test_checklist_confirmation.py` (12 tests) resolves
at `1fc0542`. This is implementation and fixture evidence. The **live** installed-Desktop DOM
capture was produced afterwards by H-35b: `docs/H35B-LIVE-CHECKLIST-EVIDENCE.md` at `7a6b4b0`
(fresh rig, CDP `127.0.0.1:9351`, backend `44277`, plugin sha `ab6347…` at `f990cad`). It is not a
capture at the shipped `c206e1c9`; it is evidence that the checklist nodes render, not evidence
about the H-38 copy.

### H-31 / H-31b / H-41 — index refresh, docs-only

No product code changed in any of these cards, so no test-count or gate claim is made here. The
integrator runs the frozen gate on the merged tree. Each card verified its own citations with
`git cat-file -e` and `git merge-base --is-ancestor` instead of trusting the previous revision's
table. H-41 additionally re-ran one documentation-claim module,
`python3 -m unittest tests.test_review_evidence` on `1fc0542` (`Ran 24 tests, OK`), to settle
whether the CB-QA-10 line in README is still true; it ran no product gate and no audit probe.

### Recovery merges and the H-38 union on `1fc0542`

```
git merge-base --is-ancestor 18638be 1fc0542   # H-08b authored export — exit 0
git merge-base --is-ancestor acb20f7 1fc0542   # H-06b procedure lens — exit 0
git merge-base --is-ancestor 580bbb6 1fc0542   # H-18b locale scaffolds — exit 0
git merge-base --is-ancestor b75d601 1fc0542   # H-36 validator integration — exit 0
git merge-base --is-ancestor ca1ca4f 1fc0542   # H-27 learner syllabus UI — exit 0
git merge-base --is-ancestor 21e62e5 1fc0542   # H-26b syllabus read projection — exit 0
git merge-base --is-ancestor 7a6b4b0 1fc0542   # H-35b live checklist capture — exit 0
git merge-base --is-ancestor 47e152c 1fc0542   # H-22 copy — exit 0 (through 1fc0542)
git merge-base --is-ancestor 184640a 1fc0542   # H-28 first-run copy — exit 0 (through 1fc0542)
git merge-base --is-ancestor eb8e4c5 1fc0542   # H-29 learning copy — exit 0 (through 1fc0542)
git merge-base --is-ancestor 1fc0542 1fc0542   # H-38 UX union — exit 0 (this is master)
```

H-41 ran all ten and no product gate. It re-ran one module to settle a documentation claim:
`python3 -m unittest tests.test_review_evidence` on `1fc0542` → `Ran 24 tests, OK`, including
`test_evidence_inspect_never_carries_the_reference_answer`. That is a documentation-claim probe, not
a re-audit of any finding.

### H-40 arbitrary-topic packet — branch-only @ `9f2de53`

```
git cat-file -e 9f2de53:audit/adversarial/harness-e2e/STATUS.md        # exit 0
git cat-file -e 9f2de53:tests/test_harness_e2e.py                      # exit 0
git cat-file -e 1fc0542:audit/adversarial/harness-e2e/STATUS.md ; test $? -eq 1   # absent from master
git cat-file -e 1fc0542:tests/test_harness_e2e.py ; test $? -eq 1                # absent from master
git merge-base --is-ancestor 9f2de53 1fc0542 ; test $? -eq 1                     # not merged
```

`9f2de53` is based on `c588e4a` and records **3/3 scenarios PASS** (`bicycle_single`,
`music_short`, `soldering_full`) with recorded transcripts, recorded pages through the real search
seam, and `labels.provider_calls = 0`, `provider_spend_usd = 0.0`. Its own STATUS.md names six
honest gaps: no live provider, no live web research, course export out of scope, no language-goal
audio path, only plan acceptance proven at the 40-objective bound, and no Desktop renderer run. Its
focused suite is 11 tests and its full suite is 1422 tests on the branch. **None of that is evidence
about `1fc0542`** until the supervisor merges it.

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

Status is the state of the **merged** evidence at `master` = `1fc0542` (2026-11-07). A `done` card
means its worker finished; it does **not** mean the branch merged. "FIXED" requires the named merge
commit to be an ancestor of `1fc0542`. "FIXED — re-audit required" means the implementation is
merged but no independent probe has run against the merged line yet. The ancestor verdict in the
fifth column was re-run for this revision; rows that moved are listed in §12.

| finding | severity | status | owning card | evidence commit — ancestor of `1fc0542`? | card state |
|---|---|---|---|---|---|
| P0-1 learner create flow never starts generation | P0 | **FIXED** | H-02 `t_867d3b52` | merge `1bbd502` (content `5b74233`) — **yes** | done, merged |
| P0-2 plan schema caps at 8 sections / forces 4 objectives; no `scope` | P0 | **FIXED — implementation merged; re-audit required** | H-03 `t_577ed286` (design) + H-21a/b/c (`t_27867486`, `t_fb8b9622`, `t_6576b611`) | design merge `54087de` (content `f465a4d`) — **yes**; implementation merge `2252231` (content `bcd545e`; slices `8eb83d8`, `7f46e17`) — **yes** | done, merged |
| P0-3 capability-policy inputs unreachable; locale mistaken for subject | P0 | **FIXED** | H-01 `t_f4f5b26a` (contract) + H-13 `t_543c0767` (threading) | merges `b1f2978` (content `8cbaab3`) and `6779030` (content `ee976ea`) — **yes** | done, merged |
| P0-4 deep research is a no-op; demo-sized budget | P0 | **FIXED** | H-04 `t_161d467f` | content `cee1749`, merged at `341cc18` into `ce95836` — **yes** | done, merged |
| P0-5 a normal course cannot export itself | P0 | **FIXED** | H-08 `t_901c8310`; recovery H-08b `t_092cc689` | pre-recovery tip `c9c6cec` — **no** (branch history, superseded); recovery merge `18638be` — **yes**. On `1fc0542` `contracts/rpc.v13.json` carries 11 `course.export` hits and `tests/test_course_export.py` resolves | recovered, merged |
| P0-6 a technical procedure lesson cannot carry the procedure lens | P0 | **FIXED** | H-06 `t_7a320d2f`; recovery H-06b `t_6cd9e57c` | original tip `00b502f` — **yes** (landed through the H-06b line); recovery merge `acb20f7` — **yes**. `lesson_procedure_problems` resolves in `coursebook/generation.py` at `1fc0542` | recovered, merged |
| P0-7 no live arbitrary-topic generation | P0 | **OPEN — packet re-run on v2; merge pending supervisor** | H-09 `t_ebc196db`; re-run H-40 | H-09 `111c7e9` — **no**; H-40 `9f2de53` on `wt/h09-e2e-rerun` (base `c588e4a`) — **no**. The packet reports 3/3 PASS with recorded transcripts and 0 provider calls | done; neither branch merged |
| P1-1 parent brief stored but mostly ignored by the planner | P1 | **FIXED** | H-07 `t_2f3cc647` (+ H-32b regression) | content `8a6bedb` merged at `afac32c` into `ce95836` — **yes**; conflict regression `8d018e4` via `c7461fc` — **yes** | done, merged |
| P1-2 planner does not plan media; policy guesses from prose | P1 | **FIXED** | H-05 `t_7baa29e2` | content `986190f` merged at `a30487e` into `ce95836` — **yes** | done, merged |
| P1-3 check `count` / `independent_evidence` are decorative | P1 | **FIXED — re-audit required** | H-21c `t_6576b611` | merge `2252231` (content `bcd545e`) — **yes**; `CHECK_PLAN_SCHEMA_V2` drops both fields | done, merged |
| P1-4 authoring schemas are Japanese-shaped | P1 | **FIXED** | H-18 `t_8407ea22`; recovery H-18b (same defect as round-2 P2-7) | pre-recovery tip `2aca201` — **no**; recovery merge `580bbb6` — **yes**. `tests/test_locale_scaffolds.py` resolves at `1fc0542` | recovered, merged |
| P1-5 assessment breadth is narrow | P1 | **OPEN — B-1 and B-3 merged; B-2 unmerged** | H-16 `t_3c5d969c`; B-1 `t_673155b0`; B-2 `t_74d99ca5`; B-3 H-22 `t_966d50f4` | decision `dd43d82` via `fa316c5` — **yes**; B-1 `ce6c8c1` via `4e709d3` — **yes**; B-3 `47e152c` via `1fc0542` — **yes**; B-2 `423908f` — **no** | all four done; three merged, B-2 not |
| P1-6 rubric registry is static | P1 | **FIXED (decision) — re-audit not applicable** | H-24 `t_29e6647c` | merge `4f42c3c` (content `491443a`), `docs/RUBRIC-EXTENSIBILITY.md` — **yes** | done, merged |
| P2-1 test matrix proves policy, not generation | P2 | **OPEN — blocked on the H-40 packet merging** | H-09 `t_ebc196db`; re-run H-40 | `111c7e9` — **no**; `9f2de53` — **no** | done, unmerged |
| P2-2 depth/locale not tested through the product surface | P2 | **FIXED** | H-04 `t_161d467f` + H-13 `t_543c0767` | `cee1749` via `ce95836` — **yes**; `6779030` — **yes** | done, merged |
| P2-3 procedure/media evidence is static or fixture | P2 | **OPEN — blocked on the H-40 packet merging** | H-09 `t_ebc196db`; re-run H-40 | `111c7e9` — **no**; `9f2de53` — **no** | done, unmerged |

**P1-3 and P1-6 were UNMAPPED two revisions ago; both now name a merged owner.** P1-3 is closed by
`CHECK_PLAN_SCHEMA_V2` in `bcd545e`, which removes `count` and `independent_evidence` from the v2
check plan; P1-6 is closed as a *decision* by `docs/RUBRIC-EXTENSIBILITY.md`, which deliberately
declines a runtime rubric generator. The P1-6 row is FIXED in the sense the finding asked for
(a gate exists); it is not a runtime feature and no row here implies one. **No round-1 finding
remains UNMAPPED.**

## 5. Finding ledger — round 2 (`docs/ADVERSARIAL-AUDIT-ROUND2.md`)

The report proposed its own `H-11`…`H-18` labels. Those labels **collide** with the board keys; the
board keys are authoritative and are the only ids used here. Status is the merged state at
`1fc0542`; the fifth column is the ancestor verdict re-checked for this revision.

| finding | severity | status | owning card | evidence commit — ancestor of `1fc0542`? | card state |
|---|---|---|---|---|---|
| P0-1 validator-rejected plan is stored as an approvable `draft` | P0 | **FIXED** | H-12 `t_dba06898` | merge `13480c4` (content `4b5f3b1`) — **yes**; round-2 probe `903a606` — **yes** | done, merged |
| P0-2 fetched excerpt is raw prompt content; invented prose URLs pass | P0 | **FIXED** | H-14 `t_031e287f` | merge `a12176b` (content `0ba4dc6`) — **yes** | done, merged |
| P1-3 "independent validation" is prompt separation; same model upgrades support | P1 | **FIXED — implementation merged; re-audit required** | H-15 `t_d519643b`; integration H-36 `t_48645f63` | `833e335` — **yes** (through the merge); merge `b75d601` — **yes**; `docs/H15-VALIDATOR-INDEPENDENCE.md` resolves at `1fc0542` | done, merged; independent re-audit is H-30b |
| P1-4 factual gate auto-waives when research is unavailable | P1 | **FIXED — implementation merged; re-audit required** | H-15 `t_d519643b`; integration H-36 `t_48645f63` | `833e335` — **yes**; merge `b75d601` — **yes**; `outcome`/`facts_unverified` are in `validation_verdict()` at `1fc0542` | done, merged; independent re-audit is H-30b |
| P1-5 assessment breadth: three input formats only | P1 | **OPEN — B-1 and B-3 merged; B-2 unmerged** | H-16 `t_3c5d969c` → B-1 `t_673155b0`, B-2 `t_74d99ca5`, B-3 H-22 `t_966d50f4` | decision `dd43d82` via `fa316c5` — **yes**; B-1 `ce6c8c1` via `4e709d3` — **yes**; B-3 `47e152c` via `1fc0542` — **yes**; B-2 `423908f` — **no** | three done and merged; B-2 open |
| P1-6 flat `$0.75` ceiling, no cost-abort recovery | P1 | **FIXED** | H-17 `t_9a8543ae` (+ `t_d50cb007` v10 brief fix) | content `722f00f` merged at `4dd68cb` into `ce95836` — **yes**; `fbf96fe` — **yes** | done, merged |
| P2-7 Japanese-only scaffold triple; no direction field | P2 | **FIXED** | H-18 `t_8407ea22`; recovery H-18b | pre-recovery tip `2aca201` — **no**; recovery merge `580bbb6` — **yes**; `tests/test_locale_scaffolds.py` resolves at `1fc0542` | recovered, merged |
| P2-8 no prerequisite edges; adaptation is a state label | P2 | **FIXED — re-audit required** | H-20 `t_43ca17b8` (frozen contract) + H-21c `t_6576b611` (implementation) | contract `516d161` via `d079b4c` — **yes**; implementation merge `2252231` (content `bcd545e`) — **yes** | done, merged |
| P2-9 green policy matrix supplies contract-rejected dials | P2 | **FIXED** | H-01 `t_f4f5b26a` + H-13 `t_543c0767` | merges `b1f2978` (content `8cbaab3`) and `6779030` (content `ee976ea`) — **yes** | done, merged |
| P2-10 round-1 review uncommitted at audit time | P2 | **FIXED** | H-19 `t_ec1d2c15` | `2e3508f` on master — **yes**; index `99da48a` merged via `ce95836` — **yes** | done, merged |

### H-15's integration blocker — closed by H-36 at `b75d601`

The previous revision recorded this blocker, and it is kept so a reader can see what changed:

```
git merge-tree --write-tree f990cad 833e335     # exit 1, five conflicted files
CONFLICT (content): coursebook/generation.py
CONFLICT (content): coursebook/research.py
CONFLICT (content): docs/GENERATION.md
CONFLICT (content): tests/fixtures/generation/validation_pass.json
CONFLICT (content): tests/test_generation.py
```

H-36 `t_48645f63` performed the semantic union and merged it as `b75d601`. `833e335` is now an
ancestor of `1fc0542`, so the H-15 code is **on master**; `docs/H15-VALIDATOR-INDEPENDENCE.md`
(`coursebook/generation.py` markers `INDEPENDENCE_INDEPENDENT`, `OUTCOME_INDEPENDENT`,
`validation_independence()`, `facts_unverified`) resolves at `1fc0542`, and
`tests/test_validator_independence.py` resolves at `1fc0542`.

Two limits survive the merge, and neither is papered over:

- **Integration is not re-audit.** H-36 united H-15 with H-21c/H-35; it did not independently
  probe the result. No row here calls validator independence "independently proven" on `1fc0542`.
  The re-audit card is H-30b, and its tip `f92d5f8` is **not** an ancestor of `1fc0542`.
- **Merged code is not a passed claim about a live model.** `validation_independence()` reads the
  identities the provider *reported*; a missing model on either side is `unidentified`, never
  `independent`. The recorded-transcript packet does not prove a live model behaves this way.

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
commit `99da48a` is now an ancestor of `1fc0542` via `ce95836`, so the correction and this register
both reach a reader on `master`.

## 6. Card index findings (D-series)

`docs/HARNESS-NEXT-CARDS.md` records deeper findings discovered while seeding the board. They are
not a separate audit, but they do carry reproducibility weight, so their status is pinned here
rather than left to prose. Historical D-01…D-06 text is **not** rewritten by this card; only the
status column moves.

| id | status | owning card | evidence commit — ancestor of `1fc0542`? | note |
|---|---|---|---|---|
| D-01 plan approval is advisory, not fail-closed | **FIXED** | H-12 `t_dba06898` | merge `13480c4` (content `4b5f3b1`) — **yes** | same defect as round-2 P0-1 |
| D-02 the green suite encodes the defect | **FIXED** | H-12 | tests changed in `4b5f3b1` — **yes**; audit assertion `903a606` — **yes** | empty-plan approvals now assert refusal |
| D-02b two plan digests, one approval | **FIXED** | H-12 + H-02 | `13480c4` (durable binding) — **yes** + `1bbd502` (learner path reads kernel digest via `parent.blueprint.read`) — **yes** | the fix is a projection, not a digest comparison |
| D-03 the plan job drops contract inputs | **FIXED** | H-13 `t_543c0767` | merge `6779030` (content `ee976ea`) — **yes** | level/subject_domain/scope reach prompt, research and fingerprint |
| D-04 "adaptation" is a state transition | **OPEN — narrowed** | H-03 (design, merged `54087de`), H-20 (contract `516d161`, merged `d079b4c`), H-21c (`bcd545e`, merged `2252231`) | all three — **yes** | prerequisite sequencing now exists; there is still **no** dynamic re-plan, no choice among remediation/examples/next objective and no attempt-driven content change. Do not market it as adaptive teaching. Re-audit required (H-30b, unmerged). |
| D-05 validation independence is structural only | **FIXED — implementation merged; re-audit required** | H-15 `t_d519643b`; integration H-36 `t_48645f63` | `833e335` — **yes**; merge `b75d601` — **yes** | same defect as round-2 P1-3/P1-4. The integration landed; the independent re-audit did not (H-30b `f92d5f8` — **no**). |
| D-06 stale CB-QA-10 claim survives in README | **OPEN — documentation defect on master; fix branch unmerged** | H-11 `t_6f41e0b0` | branch `wt/harness-docs` @ `b2233ac` — **no** | The stale claim is still on master **and is now also false**: `README.md:97` and `:202`, `docs/PRIVACY_EGRESS.md:167`, `docs/ACCEPTANCE.md:32` (S07 FAIL row) and `docs/REVIEW_CB014.md:31`/`:114` still call CB-QA-10 open. At `1fc0542` `coursebook/evidence.py:45`/`:57` projects only `PUBLIC_CRITERION_FIELDS`, and `tests/test_review_evidence.py::test_evidence_inspect_never_carries_the_reference_answer` passes (H-41 ran the module: 24 tests OK). `docs/HARNESS-STATUS.md`, the H-11 deliverable, does not resolve on master. |

D-06 also covers the `REVIEW_CB014.md` row for CB-QA-10 ("OPEN"). That row is **not** rewritten in
this file — the index pins status, it does not edit the review — but H-41 did re-derive the code
claim: at `1fc0542` `coursebook/evidence.py` projects only `PUBLIC_CRITERION_FIELDS` and
`tests/test_review_evidence.py` passes (24 tests OK, including
`test_evidence_inspect_never_carries_the_reference_answer`). So `README.md`, `docs/ACCEPTANCE.md`,
`docs/PRIVACY_EGRESS.md` and `docs/REVIEW_CB014.md` now describe a defect the merged code no longer
has. H-11 owns recanonicalising them; until `b2233ac` merges, a reader must treat those four files
as stale rather than as evidence about master.

## 7. Third wave — UX, generic-harness and acceptance findings

`docs/ADVERSARIAL-UX-REVIEW.md` and `docs/GENERIC-HARNESS-REVIEW.md` are merged at `2e57efa`
(amended by `31b3132`, `6d062e1`, `db5662c`). `docs/GENERIC-ACCEPTANCE-AUDIT.md` (`ddc71fc`) is
merged at `090e755` but audits `498b1da`, not `1fc0542`. Card bodies are the authority for scope.
Every "merged" cell below names a commit that is an ancestor of `1fc0542`; the two packets that are
not (H-30b's `f92d5f8`, H-40's `9f2de53`) are marked branch-only.

### Generic-harness findings (G-series, `docs/GENERIC-HARNESS-REVIEW.md`)

| finding | summary | owning card | merged state at `1fc0542` | re-audit |
|---|---|---|---|---|
| G-01 | One-off shape is schema-rejected (`minItems: 4` objectives, 2 sections) | H-21a/b/c (`t_27867486`, `t_fb8b9622`, `t_6576b611`) | **merged** `2252231` — `PLAN_SCHEMA_V2` objectives `minItems: 1`, and `SCOPE_EXPECTATIONS["single"]["blueprint_objectives"] = (1, 1)` | required, H-30b (unmerged) |
| G-02 | Generated checks are saved, not graded (no reference `kind`) | B-1 `t_673155b0` (H-16 B-1; the card title carries a stale "H-20" collision label) | **merged** `4e709d3` (content `ce6c8c1`), `docs/GRADING-LANES.md`, `tests/test_grading_lanes.py` | required, H-30b (unmerged) |
| G-03 | Scope is on the wire but the plan shape caps it | H-21a/b/c | **merged** `2252231` — v2 `objectives` `maxItems: 40`, `units` `minItems: 1` | required, H-30b (unmerged) |
| G-04 | Media/procedure lens incomplete | H-05 `t_7baa29e2` + H-06 `t_7a320d2f`; recovery H-06b | **merged** — H-05 `ce95836`; H-06 `00b502f`; H-06b `acb20f7` (all ancestors). `lesson_procedure_problems` resolves at `1fc0542` | required, H-30b (unmerged) |
| G-05 | Only a prepared Japanese pack has run end to end | H-09 `t_ebc196db` (packet) + H-30 `t_178dc615` (audit); re-run H-40 | H-09 `111c7e9` branch-only; H-40 `9f2de53` branch-only (3/3 PASS, recorded transcripts, 0 provider calls); H-30 `090e755` merged but audits `498b1da` | **required**, H-30b; H-40 packet merge is the first step |
| G-06 | Student mode / second import path does not exist | H-25 `t_5535fc66` (design), H-26a `t_faad26cf` (backend), H-27 `t_71ea55ee` (UI), H-26b (read projection) | design **merged** `e978441` (content `3705a7a`); backend **merged** `d0ca064`; UI **merged** `ca1ca4f`; projection **merged** `21e62e5` — all ancestors. `syllabus.intake.create` resolves in `contracts/rpc.v13.json` and `desktop/plugin.js` at `1fc0542` | implementation merged; no independent G-06 re-audit exists |
| G-07 | Rubric profiles are static | H-24 `t_29e6647c` (decision, not a runtime generator) | **merged** `4f42c3c` (content `491443a`), `docs/RUBRIC-EXTENSIBILITY.md` | decision only; no runtime to audit |

### H-30 acceptance findings (D1…D8, `docs/GENERIC-ACCEPTANCE-AUDIT.md` @ `498b1da`)

H-30 ran on `498b1da`, before `2252231`/`4e709d3`. Its P0 findings are therefore **re-audit
required** against `1fc0542`, owned by H-30b `t_9b6742f3`. Do not quote them as current.

| id | H-30 verdict at `498b1da` | what changed on `1fc0542` | status |
|---|---|---|---|
| D1 | `single` padded to 4 objectives — FAIL | `PLAN_SCHEMA_V2` `minItems: 1`; `blueprint_objectives` for `single` = (1, 1) in `bcd545e` | **re-audit required** (H-30b, unmerged) |
| D2 | `full` truncated at 8, no units/prereqs — BLOCKED | `maxItems: 40`, `plan_units` in `db.v7` migration `0007_plan_units.sql`, §14 gating in `bcd545e` | **re-audit required** (H-30b, unmerged) |
| D3 | generated checks return `needs_retry` for both answers — FAIL | fix `ce6c8c1` merged at `4e709d3` | **re-audit required** (H-30b, unmerged) |
| D4 | language goal with no locale/domain silently `general` | unchanged; no merged card closes it | OPEN — Atlas to route (nearest H-13/H-18b) |
| D5 | H-09 evidence docs do not name the evidence commit; test count environment-dependent | the H-40 packet (`9f2de53`, branch-only) names base `c588e4a`, its evidence commit and 11/1422 test counts | **addressed on an unmerged branch only** — H-40 packet; H-11 (`b2233ac`, unmerged) owns the doc reconciliation |
| D6 | H-09 `scope_matches_documented_bounds` compares the code to itself | unchanged | OPEN — H-40 packet, unmerged |
| D7 | evidence packet not byte-reproducible (verdict-only freshness guard) | unchanged | OPEN — H-40 packet, unmerged |
| D8 | lesson validator accepted truncated authored texts | unchanged | OPEN — H-40 / lesson-validator owner |

### UX findings (UX-series, `docs/ADVERSARIAL-UX-REVIEW.md`)

H-28 (`t_271e19e7`) and H-29 (`t_70686b14`) are merged through the H-38 union commit `1fc0542`;
their tips `184640a` and `eb8e4c5` are ancestors of it. **Merged implementation is not an
independent UX re-audit**: no UX row below has been re-probed against the shipped module. What H-41
did verify is the copy the review demanded: at `1fc0542` `desktop/plugin.js` contains
"First try, no hints" ×2, "Start with a goal" ×1, "What Coursebook can check" ×1, "How will you use
it" ×1, "Reported by you — not independently verified." ×1 and "Your answer is text, a choice, or a
checklist" ×1; at `c588e4a` every one of those counts is 0.

| finding | summary | owning card | merged state at `1fc0542` |
|---|---|---|---|
| UX-01 | First run explains the system, not the invitation | H-28 `t_271e19e7` | merged — `184640a` via `1fc0542`; copy verified, no re-audit |
| UX-02 | "Recipe" is the wrong first question; Japanese-only placeholders | H-28 `t_271e19e7` | merged — `184640a` via `1fc0542`; no re-audit |
| UX-03 | Create result is a receipt, not a beginning | H-28 `t_271e19e7` | merged — `184640a` via `1fc0542`; no re-audit |
| UX-04 | Lesson index is a metadata table | H-29 `t_70686b14` | merged — `eb8e4c5` via `1fc0542`; no re-audit |
| UX-05 | Result screen is accurate and unkind | H-29 `t_70686b14` | merged — `eb8e4c5` via `1fc0542`; evidence-class copy verified, no re-audit |
| UX-06 | Library/Import has no plain explanation | H-28 `t_271e19e7` (with H-27) | merged — `184640a` via `1fc0542`; no re-audit |
| UX-07 | Parent Studio speaks builder vocabulary | H-28 `t_271e19e7` | merged — `184640a` via `1fc0542`; no re-audit |
| UX-08 | Cross-surface visual language is flat | H-29 `t_70686b14` / host | module merged — `eb8e4c5` via `1fc0542`; the 460 px host rail gap stays a host claim in README (`wt/host-narrow-rail`, not merged) |
| UX-09 | Scope and expectation are unclear on screen | H-28 `t_271e19e7` | merged — `184640a` via `1fc0542`; no re-audit |
| UX-10 | Status and error tone | H-29 `t_70686b14` | merged — `eb8e4c5` via `1fc0542`; no re-audit |

### H-16 B-series (defect register inside `docs/ASSESSMENT-BREADTH.md` §11)

The decision document is on master (`fa316c5`, content `dd43d82`). The three implementation
defects split: B-1 and B-3 are merged at `1fc0542`, B-2 is not.

| finding | summary | owning card | merged state at `1fc0542` |
|---|---|---|---|
| B-1 | Generated lesson checks store no reference `kind`; grader falls to the unconfigured open lane | `t_673155b0` (title still says "H-20"; **B-1** is authoritative) | **merged** `4e709d3` (content `ce6c8c1`); `docs/GRADING-LANES.md`, `tests/test_grading_lanes.py` (15 tests) |
| B-2 | `record_observation` has no RPC method, handler or UI; `self_reported`/`parent_reported` unreachable | `t_74d99ca5` (Atlas's earlier label was "H-21"; **B-2** is authoritative) | done, **unmerged**: `wt/harness-observation-record` @ `423908f` — **not** an ancestor of `1fc0542` |
| B-3 | `EVIDENCE_CLASS_COPY` covers 4 of 6 evidence classes | H-22 `t_966d50f4` (frozen disclosure copy + labels) | **merged** — `47e152c` via `1fc0542` (H-38 union). `EVIDENCE_CLASS_COPY` at `1fc0542` has all six keys: `cold`, `hinted`, `answer_shown`, `self_reported`, `parent_reported`, `override` |

**H-23 `t_132531da` ("Generated checks are ungradable") is `done` as a duplicate with no product
code:** it was seeded before the B-1 duplicate was noticed. It is not evidence for B-1 and must not
be re-run. B-1's owner is `t_673155b0`, and B-1's fix is `ce6c8c1`.

## 8. Card index — H-21…H-41

Every card created after the second wave, with the findings it owns or audits, its branch, and its
**merged** state at `1fc0542`.

| card | id | owner | parents | branch | merged at `1fc0542` | owns / audits |
|---|---|---|---|---|---|---|
| H-21 (original) | `t_2a2fc90c` | cinder | H-13, H-01 | `wt/t_2a2fc90c` @ `5ba4e4c` | **no — superseded, no merge** | closed and split; the branch tip is history, not evidence |
| H-21a | `t_27867486` | cinder | H-21 | `wt/h21a-contract-migration` @ `8eb83d8` | **yes** — `2252231` | cb.rpc v11, cb.db v7, migration `0007_plan_units.sql`, legacy-hash invariance |
| H-21b | `t_fb8b9622` | cinder | H-21a | `wt/h21b-unit-stages` @ `7f46e17` | **yes** — `2252231` | `PLAN_SCHEMA` v2 (`coursebook.plan.v2`), unit-scoped plan/lesson stages |
| H-21c | `t_6576b611` | cinder | H-21b | `wt/h21c-prereq-gating` @ `bcd545e` | **yes** — `2252231` | R1–R9 prerequisite gating, §14.4 tests, `docs/PLAN-CEILING.md` |
| H-22 | `t_966d50f4` | vellum | H-16 | `wt/harness-breadth-copy` @ `47e152c` | **yes** — `1fc0542` (H-38 union) | H-16 B-3 (evidence-class copy), §7 frozen breadth disclosure |
| H-23 | `t_132531da` | cinder | H-16 | — | — | **closed duplicate of B-1, no code**; B-1 owner is `t_673155b0` |
| H-24 | `t_29e6647c` | atlas | H-16 | `wt/harness-rubric-extensibility` @ `491443a` | **yes** — `4f42c3c` | round-1 P1-6, G-07 (decision only) |
| H-25 | `t_5535fc66` | atlas | H-03, H-02 | `wt/harness-student-mode-design` @ `3705a7a` | **yes** — `e978441` | G-06 design (`docs/STUDENT-MODE.md`) |
| H-26 (original) | `t_da9e472c` | cinder | H-25 | `wt/harness-student-import` @ `2d7ecde` (salvage) | **yes as salvage** — `2d7ecde` landed through the H-26a line (`d0ca064`); the original card timed out and did not finish the work itself | salvage only; implementation is H-26a |
| H-26a | `t_faad26cf` | cinder | H-26, H-25 | `wt/harness-student-import-recovery` | **yes** — `d0ca064` | rebase/renumber the salvage onto cb.rpc v12 / cb.db v8; parse → map → companion course |
| H-26b | — | cinder | H-26a | `wt/harness-syllabus-read-projection` @ `1d025ae` | **yes** — `21e62e5` | stated syllabus due/weight as item fields in cb.rpc v13 |
| H-27 | `t_71ea55ee` | vellum | H-25, H-26a | `wt/harness-student-ui` @ `73c64ad` | **yes** — `ca1ca4f` | G-06 learner intake/alignment |
| H-28 | `t_271e19e7` | vellum | H-02, H-22, H-21 | `wt/harness-ux-first-run` @ `184640a` | **yes** — `1fc0542` | UX-01, UX-02, UX-03, UX-06, UX-07, UX-09 |
| H-29 | `t_70686b14` | vellum | H-28 | `wt/harness-ux-learning` @ `eb8e4c5` | **yes** — `1fc0542` | UX-04, UX-05, UX-08, UX-10 |
| H-30 | `t_178dc615` | sentinel | H-09 | `wt/harness-generic-audit` @ `ddc71fc` | **yes** — `090e755` | G-05 independent audit, **of `498b1da`** |
| H-30b | `t_9b6742f3` | sentinel | H-30, H-21c | `wt/harness-generic-audit-2` @ `f92d5f8` | **no** | **re-audit** of the single/short/full findings; its four P3 findings are reproduced in the H-40 packet STATUS.md |
| H-31 | `t_1c9d0ba6` | quill | H-12, H-14, H-02, H-03 | `wt/harness-audit-refresh` @ `512c5f6` | **yes** — `fdecc9e` | first index refresh; rewrites no finding |
| H-31b | `t_a8e017b5` | quill | H-31, H-21c, H-35 | `wt/harness-audit-refresh-2` @ `2bfeb1c` | **yes, not as its own tip** — content re-landed as `a671511` + `385ebac`; `2bfeb1c` is **not** an ancestor | previous revision: merged-vs-card reconciliation, H-30b re-audit marker |
| H-32 | `t_69873d4c` | cinder | H-07, H-13, H-14 | `wt/harness-parent-brief-rebase` @ `bc508ce` | **not as its own tip** — the union landed as `afac32c` inside `ce95836`; `bc508ce` is branch-only | conflict repair so H-07 can merge onto H-13/H-14 |
| H-32b | `t_71f53265` | cinder | H-32 | `wt/h32-parent-brief-regression` @ `8d018e4` | **yes** — `c7461fc` | ports the parent-brief × H-13 × H-14 conflict regression onto master |
| H-33 | `t_6aafc7f2` | atlas | H-20 | `wt/harness-checklist-confirmation` @ `da53ec1` | **yes** — `4e709d3` | frozen checklist-confirmation decision |
| H-34 | `t_82c24349` | cinder | H-33 | `wt/harness-checklist-ui` @ `78c6019` | **yes** — `4e709d3` | checklist tick-list graded `self_reported` (kernel) |
| H-35 | `t_65e7d83a` | vellum | H-34 | `wt/harness-checklist-ui` @ `a498969` | **yes** — `4e709d3` | checklist confirmation surface (checkboxes, selection payload) |
| H-35b | `t_db0b76f8` | vellum | H-35 | evidence-only, no branch | **yes** — `7a6b4b0` | live installed-Desktop DOM capture on a fresh rig, at `f990cad` plugin sha `ab6347…`; **not** re-taken at the shipped `c206e1c9` |
| H-36 | `t_48645f63` | atlas | H-15, H-21c, H-35 | `wt/harness-validator-integration` @ `833e335` | **yes** — merge `b75d601` | integrate H-15 onto v13; recovery, not a new design |
| H-37 (student/syllabus union) | — (id not recorded here) | supervisor | H-25, H-26b, H-27 | `wt/harness-student-ui` @ `73c64ad`; `wt/harness-syllabus-read-projection` @ `1d025ae` | **yes** — merges `ca1ca4f` (H-27) and `21e62e5` (H-26b), then `c588e4a` (M4-V regeneration) | G-06 second import path |
| H-38 (UX union) | `t_4adb4907` | supervisor | H-22, H-28, H-29 | `wt/ux-union` @ `1fc0542` | **yes** — `1fc0542` is the merge commit on master | six `desktop/plugin.js` conflicts resolved as a union; the frozen §7 copy lands |
| H-39 (M4-V re-pin) | `t_5fb93891` | — | H-38 | `wt/m4v-determinism` @ `8ba5704`; `wt/m4v-landing` @ `7404e9c` | **no** | re-pin the M4-V frames against the shipped plugin sha `c206e1c9` |
| H-40 (H-09 re-run) | `t_e32900ef` | sentinel | H-09 | `wt/h09-e2e-rerun` @ `9f2de53` | **no** | arbitrary-topic packet on blueprint v2 — 3/3 PASS, recorded transcripts, 0 provider calls, 11 focused / 1422 full tests on the branch |
| H-41 (this card) | `t_ef2600f8` | quill | H-38 | `wt/audit-index-h41` | no (this card) | this revision: audit-index truth pass on `1fc0542` |

## 9. Provenance checks this index relies on

Run on `master` at `1fc0542`. Each must stay true or the index is stale.

```
git cat-file -e 1fc0542:docs/ADVERSARIAL-HARNESS-REVIEW.md
git cat-file -e 1fc0542:docs/ADVERSARIAL-AUDIT-ROUND2.md
git cat-file -e 1fc0542:docs/ADVERSARIAL-UX-REVIEW.md
git cat-file -e 1fc0542:docs/GENERIC-HARNESS-REVIEW.md
git cat-file -e 1fc0542:docs/GENERIC-ACCEPTANCE-AUDIT.md
git cat-file -e 1fc0542:docs/ASSESSMENT-BREADTH.md
git cat-file -e 1fc0542:docs/COURSE-BLUEPRINT.md
git cat-file -e 1fc0542:docs/PLAN-CEILING.md
git cat-file -e 1fc0542:docs/GRADING-LANES.md
git cat-file -e 1fc0542:docs/CHECKLIST-CONFIRMATION.md
git cat-file -e 1fc0542:docs/RUBRIC-EXTENSIBILITY.md
git cat-file -e 1fc0542:docs/STUDENT-MODE.md
git cat-file -e 1fc0542:docs/H15-VALIDATOR-INDEPENDENCE.md
git cat-file -e 1fc0542:docs/H35B-LIVE-CHECKLIST-EVIDENCE.md
git cat-file -e 1fc0542:contracts/rpc.v13.json
git cat-file -e 1fc0542:contracts/db.v7.json
git cat-file -e 1fc0542:coursebook/migrations/0007_plan_units.sql
git cat-file -e 1fc0542:tests/test_prerequisite_gating.py
git cat-file -e 1fc0542:tests/test_grading_lanes.py
git cat-file -e 1fc0542:tests/test_checklist_confirmation.py
git cat-file -e 1fc0542:tests/test_course_export.py
git cat-file -e 1fc0542:tests/test_procedure_authoring.py
git cat-file -e 1fc0542:tests/test_locale_scaffolds.py
git cat-file -e 1fc0542:tests/test_validator_independence.py
git cat-file -e 1fc0542:desktop/plugin.js

git merge-base --is-ancestor 13480c4 1fc0542   # H-12 merge
git merge-base --is-ancestor 903a606 1fc0542   # H-12 round-2 audit assertion (test commit)
git merge-base --is-ancestor b1f2978 1fc0542   # H-01 merge
git merge-base --is-ancestor a12176b 1fc0542   # H-14 merge
git merge-base --is-ancestor 1bbd502 1fc0542   # H-02 merge
git merge-base --is-ancestor 54087de 1fc0542   # H-03 design merge
git merge-base --is-ancestor 6779030 1fc0542   # H-13 merge
git merge-base --is-ancestor ce95836 1fc0542   # integration merge: H-04/H-05/H-07/H-17/H-19
git merge-base --is-ancestor fa316c5 1fc0542   # H-16 decision
git merge-base --is-ancestor d079b4c 1fc0542   # H-20 frozen contract
git merge-base --is-ancestor 2252231 1fc0542   # H-21a/b/c implementation merge
git merge-base --is-ancestor 4e709d3 1fc0542   # H-20/H-33/H-34/H-35 checklist + grading merge
git merge-base --is-ancestor e978441 1fc0542   # H-25 design merge
git merge-base --is-ancestor 090e755 1fc0542   # H-30 audit merge
git merge-base --is-ancestor c7461fc 1fc0542   # H-32b merge
git merge-base --is-ancestor 4f42c3c 1fc0542   # H-24 decision merge
git merge-base --is-ancestor fdecc9e 1fc0542   # H-31 index merge
git merge-base --is-ancestor a671511 1fc0542   # H-31b content re-landed
git merge-base --is-ancestor 385ebac 1fc0542   # H-31b follow-up
git merge-base --is-ancestor 18638be 1fc0542   # H-08b authored export
git merge-base --is-ancestor acb20f7 1fc0542   # H-06b procedure lens
git merge-base --is-ancestor 00b502f 1fc0542   # H-06 original tip (landed through H-06b)
git merge-base --is-ancestor 580bbb6 1fc0542   # H-18b locale scaffolds
git merge-base --is-ancestor b75d601 1fc0542   # H-36 validator integration (H-15 tip 833e335 inside)
git merge-base --is-ancestor 833e335 1fc0542   # H-15 itself, now merged through H-36
git merge-base --is-ancestor d0ca064 1fc0542   # H-26a student intake
git merge-base --is-ancestor 2d7ecde 1fc0542   # H-26 salvage, landed through H-26a
git merge-base --is-ancestor ca1ca4f 1fc0542   # H-27 / H-37 student UI merge
git merge-base --is-ancestor 21e62e5 1fc0542   # H-26b / H-37 read projection merge
git merge-base --is-ancestor c588e4a 1fc0542   # M4-V regeneration before the H-38 union
git merge-base --is-ancestor 47e152c 1fc0542   # H-22 copy, merged by H-38
git merge-base --is-ancestor 184640a 1fc0542   # H-28 first-run copy, merged by H-38
git merge-base --is-ancestor eb8e4c5 1fc0542   # H-29 learning copy, merged by H-38
git merge-base --is-ancestor 7a6b4b0 1fc0542   # H-35b live checklist capture
git merge-base --is-ancestor 1fc0542 1fc0542   # H-38 itself is master

# must NOT be ancestors — a merged fix must not be claimed where it is not
! git merge-base --is-ancestor b2233ac 1fc0542                  # H-11 docs truth pass unmerged
! git merge-base --is-ancestor 111c7e9 1fc0542                  # H-09 pre-v2 packet unmerged
! git merge-base --is-ancestor 9f2de53 1fc0542                  # H-40 re-run packet unmerged
! git merge-base --is-ancestor f92d5f8 1fc0542                  # H-30b re-audit unmerged
! git merge-base --is-ancestor 423908f 1fc0542                  # B-2 unmerged
! git merge-base --is-ancestor c9c6cec 1fc0542                  # H-08 pre-recovery tip
! git merge-base --is-ancestor 2aca201 1fc0542                  # H-18 pre-recovery tip
! git merge-base --is-ancestor 2bfeb1c 1fc0542                  # H-31b branch tip (content re-landed)
! git merge-base --is-ancestor 8ba5704 1fc0542                  # H-39 M4-V determinism branch
! git merge-base --is-ancestor 7404e9c 1fc0542                  # H-39 M4-V landing branch
```

Every line above was run for this revision under `set -e`: the block exits 0. Ancestor lines must
succeed; `!` lines assert the commit is **not** an ancestor. A reader can re-run the block and get
the same verdicts, or the index is stale.

Rules enforced:

- **No claim cites a file that exists only in a worktree.** Every report above is tracked at
  `1fc0542`. The rows that describe a branch-only fix or a branch-only packet name the tip so a
  reader can check it, not so it can be treated as merged.
- **A branch is not a merge, and a done card is not a merge.** After this revision the only named
  work whose commit is not an ancestor of `1fc0542` is H-09 (`111c7e9`), H-40 (`9f2de53`), H-30b
  (`f92d5f8`), H-11 (`b2233ac`), B-2 (`423908f`), H-39 (`8ba5704`/`7404e9c`) and the superseded
  pre-recovery tips `c9c6cec`/`2aca201`/`2bfeb1c`. Every other card row above names an ancestor.
- **A merged fix is not a passed re-audit.** H-30's single/full findings and H-15's validator
  independence are marked re-audit required until H-30b probes `1fc0542`. The rows are not allowed
  to read as closed.
- **A prepared pack is not a topic proof.** No row above derives a harness claim from
  `bundled/packs/japanese-affection-context-l0`.
- **A live capture is not implied by a merged surface.** H-35's surface is merged, and H-35b's live
  capture is merged at `7a6b4b0` — but at plugin sha `ab6347…` on `f990cad`, not at the shipped
  `c206e1c9`. It proves the checklist nodes render; it does not re-prove the H-38 copy in a browser.

## 10. What this index does not claim

- It does not claim the harness is fully generic. `docs/GENERIC-HARNESS-REVIEW.md` at `1fc0542`
  says "partially generic". The shape blockers G-01/G-03 are *implemented* at `2252231`, but no
  independent probe has re-run them against `1fc0542`; H-30b owns that.
- It does not claim H-09 or H-11 is fixed; both branches are unmerged and every such row says so.
  H-06, H-08, H-15, H-18, H-22, B-3 and the H-26 line are merged — being merged is not the same as
  having passed a re-audit, and the rows that need one say so.
- It does not claim H-15's validator independence has been independently re-audited on master. The
  integration is merged at `b75d601`; the re-audit card H-30b is unmerged at `f92d5f8`.
- It does not claim H-23 did any work: it was closed as a duplicate with no code.
- It does not claim H-26's original card completed. It timed out; its WIP was salvaged at `2d7ecde`
  and the work was finished by H-26a, whose merge `d0ca064` is an ancestor of `1fc0542`. The code is
  on master; the card that shipped it is H-26a.
- It does not claim the checklist confirmation has a live Desktop capture **at the shipped plugin
  sha**. H-35b's capture exists and is merged (`7a6b4b0`), but it was taken at `f990cad` plugin sha
  `ab6347…`; nothing re-takes it at `c206e1c9`.
- It does not claim any finding is closed because a card is `done`.
- It does not re-run, re-grade or extend any audit; probe results are attributed to the card that
  produced them.
- It does not claim the harness is installable, demo-ready, or proven on an arbitrary topic. H-40's
  re-run packet (`9f2de53`) reports 3/3 PASS on blueprint v2, but it is **branch-only**, its model
  half is a recorded transcript, it called no provider and it did not exercise course export. H-30
  audited an older tree; H-30b's re-audit is also unmerged.
- It does not use the prepared Japanese pack as evidence for anything.
- It changes no product code, contract, schema, migration or test.

## 11. Changes in the H-31b revision (historical) — every moved row and its commit

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

## 12. Changes in this revision (H-41) — every moved row and its commit

Compared with the H-31b revision (the file at `385ebac`, byte-identical to `f990cad`). "Ancestor"
was checked against `master` = `1fc0542` with `git merge-base --is-ancestor` for this card; do not
copy the verdicts, re-run them. Rows not listed did not change status.

| row | previous status (H-31b) | status now | commit that justifies it | ancestor of `1fc0542` |
|---|---|---|---|---|
| round-1 P0-5 | OPEN — done, unmerged (`c9c6cec`) | **FIXED** | `18638be` (H-08b merge); `contracts/rpc.v13.json` carries 11 `course.export` hits | yes |
| round-1 P0-6 | OPEN — done, unmerged (`00b502f`) | **FIXED** | `acb20f7` (H-06b merge); `lesson_procedure_problems` resolves | yes |
| round-1 P0-7 | OPEN — done, unmerged (`111c7e9`) | OPEN — packet re-run on v2, merge pending supervisor | `111c7e9` — no; `9f2de53` (H-40, `wt/h09-e2e-rerun`, base `c588e4a`) | no |
| round-1 P1-4 | OPEN — done, unmerged (`2aca201`) | **FIXED** | `580bbb6` (H-18b merge); `tests/test_locale_scaffolds.py` resolves | yes |
| round-1 P1-5 | OPEN — decision merged; B-1 merged; B-2/B-3 unmerged | OPEN — three of four merged; B-2 unmerged | `dd43d82`; `ce6c8c1` via `4e709d3`; `47e152c` via `1fc0542` | yes; B-2 `423908f` — no |
| round-1 P2-1 | OPEN — blocked on H-09 | OPEN — blocked on the H-40 packet merging | `9f2de53` | no |
| round-1 P2-3 | OPEN — blocked on H-09 | OPEN — blocked on the H-40 packet merging | `9f2de53` | no |
| round-2 P1-3 | OPEN — done, unmerged; integration blocked, H-36 | **FIXED — implementation merged; re-audit required** | `833e335` via merge `b75d601` | yes |
| round-2 P1-4 | OPEN — done, unmerged; integration blocked, H-36 | **FIXED — implementation merged; re-audit required** | `833e335` via merge `b75d601` | yes |
| round-2 P1-5 | OPEN — decision merged; B-1 merged; B-2/B-3 unmerged | OPEN — B-3 merged; B-2 unmerged | `47e152c` via `1fc0542` | yes |
| round-2 P2-7 | OPEN — done, unmerged (`2aca201`) | **FIXED** | `580bbb6` | yes |
| D-05 | OPEN — done, unmerged; H-36 recovery named | **FIXED — implementation merged; re-audit required** | `833e335` via `b75d601` | yes |
| D-06 | OPEN — done, unmerged (`b2233ac`) | OPEN — documentation defect on master, now also false; fix branch unmerged | `b2233ac` | no |
| G-04 | H-05 merged; H-06 done/unmerged | **merged** — H-06b `acb20f7`; re-audit still H-30b | `acb20f7` | yes |
| G-05 | H-09 done/unmerged; H-30 merged on `498b1da`; H-30b required | H-40 packet re-run on v2, branch-only; H-30b still unmerged | `9f2de53`; `f92d5f8` | no |
| G-06 | design merged; backend and UI unmerged | **implementation merged** — backend, UI and read projection | `d0ca064`, `ca1ca4f`, `21e62e5`, `c588e4a` | yes |
| B-3 | done, unmerged (`47e152c`) | **merged** | `47e152c` via `1fc0542`; six `EVIDENCE_CLASS_COPY` keys at `plugin.js:5879` | yes |
| B-2 | done, unmerged (`423908f`) | unchanged | `423908f` | no |
| UX-01 … UX-10 | running / todo (no merged code) | **merged** — implementation only; no UX re-audit | `184640a` (H-28), `eb8e4c5` (H-29) via `1fc0542` | yes |
| H-35b live-capture claim | "live capture was not produced; H-35b owns it" | **produced and merged**, at `f990cad` plugin sha `ab6347…`; not re-taken at the shipped `c206e1c9` | `7a6b4b0` | yes |
| H-31b §0 note | index refresh "not on master" | retired — content re-landed as `a671511`/`385ebac`; branch tip `2bfeb1c` is not an ancestor | `a671511`, `385ebac` | yes (not `2bfeb1c`) |
| §1 register pins | hashes taken at `f990cad` | recomputed at `1fc0542`; 19 of 20 reproduced unchanged, `HARNESS-NEXT-CARDS.md` moved with later edits | `1fc0542` | — |
| §9 ancestor list | `833e335`, `2d7ecde`, `00b502f`, `47e152c` required **not** to be ancestors | all four are now ancestors; `b2233ac`, `111c7e9`, `9f2de53`, `f92d5f8`, `423908f`, `2bfeb1c`, `c9c6cec`, `2aca201`, `8ba5704`, `7404e9c` are not | see §9 | mixed |

New rows added by this revision: the two report-register rows for
`docs/H15-VALIDATOR-INDEPENDENCE.md` and `docs/H35B-LIVE-CHECKLIST-EVIDENCE.md` (§1), the H-40
branch-only packet subsection (§3), and the H-26b/H-37/H-38/H-39/H-40/H-41 card rows plus the
H-36 and H-35b merged states (§8).

**What this revision is, and is not.** It is a status reconciliation against a new master, not a new
audit: it re-ran `git merge-base --is-ancestor`, `git cat-file -e` and one documentation-claim test
module, and it re-ran no product gate and no audit probe. Two things it deliberately refuses:

- **A merged fix is not a passed re-audit.** Six ledger rows now read "FIXED — implementation
  merged; re-audit required" (round-1 P0-2/P1-3, round-2 P1-3/P1-4/P2-8, D-05) and every UX row
  says "no re-audit" for exactly that reason. H-30b is unmerged at `f92d5f8`, so the merged harness
  has not been independently re-probed on `1fc0542`.
- **A green branch is not merged evidence.** H-40's 3/3 PASS packet is recorded with its commit and
  its branch, not promoted into a FIXED row, because `9f2de53` is not an ancestor of `1fc0542`.

The release gate reads this file. After this revision the only rows that can support a release
claim are those naming an ancestor of `1fc0542`, and every ledger row that names one also says
whether an independent re-audit exists.
