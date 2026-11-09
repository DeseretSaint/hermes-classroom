# AUDIT-INDEX — Coursebook audit evidence register

Owner: quill. Created by H-19 (`t_ec1d2c15`) at `99da48a` on `wt/harness-audit-index`; refreshed by
H-31 (`t_1c9d0ba6`) at `512c5f6` on `wt/harness-audit-refresh`; refreshed by H-31b (`t_a8e017b5`)
at `a671511`/`385ebac` on `master` (its branch tip `2bfeb1c` is **not** an ancestor — the content was
re-landed, see §0); refreshed again by H-41 (`t_ef2600f8`) on `wt/audit-index-h41`, based on
`master` at `1fc0542` (`1fc054292eac1d8565aafebb3c9a71e004cd672c`), the H-38 UX union, whose
`desktop/plugin.js` sha256 is `c206e1c9091400af11594a440a105cda8a6794fe3563ad15a23a10e522232463`.

Refreshed again by H-50 (`t_37df1fb9`) on `wt/h50-audit-refresh`, based on `master` at `54dd2eb`
(`54dd2eb48f5f3410cb9f591f4a2d9a283e20672c`). Every live status cell and every ancestor verdict
below was re-run against `54dd2eb` for that card. `1fc0542` stays the stated base of the §11/§12
history, which is not rewritten.

All earlier revisions are on `master`: `99da48a` through the integration merge `ce95836`,
`512c5f6` through merge `fdecc9e`, `a671511`/`385ebac` through the H-37/H-38 sequence. A reader does
not need a branch to see this file any more; they need the commit above. `docs/AUDIT-INDEX.md` at
`385ebac` is byte-identical to the file at `1fc0542`
(`git diff --stat 385ebac 1fc0542 -- docs/AUDIT-INDEX.md` is empty).

Re-derived again by H-163 (`t_d10c4279`) on `wt/h163-audit-index`, based on `master` at `a674356`
(`a67435647c43c69bbfe3f03bddf5c25d7cfcf376`, 2026-11-08). The brief was every status cell that reads
"unmerged" or "OPEN — done". The cells that said it as a *current* state are in §11's H-31b record
(base `f990cad`); §12–§14 carry the phrase in their "previous status" columns and in verbatim quotes
of the text they correct, and the live ledgers in §4–§7 had already been moved by H-50/H-58/H-59.
H-163 therefore did three things and no more: it re-ran every hash in
this file as an ancestor test against `a674356` (§15), it annotated each §11 cell that still read
"unmerged" with its state at `a674356` **without rewriting the historical verdict of that base**, and
it corrected the two live sentences that were still stale (§6 D-04's H-30b marker and §7's B-series
intro). No finding changed state at `a674356`; the three that are genuinely open (P0-7, P1-5, D-04)
stay open with the evidence measured in §15.

Re-derived again by H-209 (`t_db87fea5`) on `wt/h209-audit-index`, based on `master` at `4dacf07`
(`4dacf07299d056227fea4ca8967e861411abf0e4`, 2026-11-08 20:39 MST), the settled union that carries
the H-208 integration `d9b1f3c`, the H-182/D8 merge `a81567b` and the H-182/D6 merge `d626c16`.
`desktop/plugin.js` at that commit is sha256
`a11a769f6131b365555b9a4efae9cf942baa843f78bcdd0237f0170d6a0aba61`, and
`audit/visual/m4-visual/audit.json` pins that same module with 15 claims, all PASS, over 62 frames
(§16). H-209 re-ran every hash in this file as an ancestor test against `4dacf07`, re-derived every
live cell that could move, entered the fixes that landed since `a674356`, and kept §11–§15 as
base-stamped history. The three genuinely open findings (P0-7, P1-5, D-04) are still OPEN; §16 says
what evidence exists at `4dacf07` and which card would have to re-probe them. H-203's
re-measurement of `docs/release-evidence.json` on the same tree is a separate card and is not
pre-empted here.

Purpose: make every audit claim reproducible from a **commit hash**, not from a working-tree path.
A report is evidence only if the file it lives in resolves to a commit, the probes that produced it
resolve to a commit, and the finding's status names the card that owns the fix.

Rule for citing this index: quote the commit hash and the file path, never a worktree path. If a
file is not reachable with `git cat-file -e <hash>:<path>`, it is not evidence.

## 0. How to read this after merges

Four things are routinely confused. They are not the same:

- **A card being `done` is not a merge.** `done` means the assigned worker finished and reported.
  The branch may still be unmerged. Every ledger row below names a commit *and* says whether that
  commit is an ancestor of `master` at `4dacf07` (re-derived by H-209 for every hash in this file;
  §16; H-163 ran the same test at `a674356`, §15).
- **A merge is not an independent re-audit.** A merged fix proves the code landed; it does not
  prove the defect is gone. Where a merged implementation has not been re-probed against the
  commit that carries it, the row says **re-audit required** and names the audit card
  (H-30b `t_9b6742f3` for the harness findings; H-36 `t_48645f63` is an integration repair, not
  an audit).
- **A branch tip is not merged evidence.** A finding flips to FIXED only when its fix is an
  ancestor of `master` (`git merge-base --is-ancestor <commit> 4dacf07` exits 0; H-209 re-ran this
  for every hash named here, §16) and the merged
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
- **The H-50 base is `54dd2eb`, not `1fc0542`.** Five lines this index called branch-only or
  unmerged became ancestors: H-40 `9f2de53`, H-30b `f92d5f8`, the H-11 docs line `b2233ac` (landed
  again as `097c32c`), H-39 `7404e9c`/`4945061`, and the H-42/H-43/H-44/H-45/H-46/H-46b line ending
  at `74978ca`. Every row they own was re-verified against `54dd2eb` and is listed in §13. At that
  revision four rows stayed open or partial with a stated reason: P0-7 (the packet's model half is a
  recorded transcript, so no live provider authoring is proven), P2-3/G-04's media half (no media
  scenario exists), §6 D-06 (H-11 reconciled the live docs but `README.md` was still stale; H-52
  `a044fb4` has since rewritten it, so the row now reads FIXED) and B-2 (the sha in the row is wrong
  and the `observation.record` RPC half still does not exist). D-04 is deliberately untouched.

## 1. Report register

Every file below is tracked; the verification column names the commit that contains it. A report
whose only commit is on an unmerged branch is marked **branch-only** and is not evidence about
merged behaviour.

| report | what it is | introduced in | content sha256 at `54dd2eb` | verification |
|---|---|---|---|---|
| `docs/ADVERSARIAL-HARNESS-REVIEW.md` | audit round 1 — harness capability verdict (NO-GO as a general harness) | `2e3508f` | `405e552459f0ca8c993c9c2bde78cbc7fd7ba0988d9bdb621c5f31970e76b7bd` | `git cat-file -e 2e3508f:docs/ADVERSARIAL-HARNESS-REVIEW.md` |
| `docs/ADVERSARIAL-AUDIT-ROUND2.md` | audit round 2 — 14 deterministic probes, 10 findings | master via merge `7af3bbd` (audit commit `9357c00`; probe assertion `903a606`) | `646242073fd0d60f7f70f86e439aae2bc29482afa5d8afe7f9f0d8161e3a8d96` | `git cat-file -e 54dd2eb:docs/ADVERSARIAL-AUDIT-ROUND2.md` |
| `docs/ADVERSARIAL-UX-REVIEW.md` | adversarial UX review — learner and Parent Studio surfaces (GO for a UX pass, not a rewrite) | `2e57efa` | `840d000ecd6bb2d1892af34f9142126864bb0f5cc9c1d37eb43f7f74e4128c94` | `git cat-file -e 54dd2eb:docs/ADVERSARIAL-UX-REVIEW.md` |
| `docs/GENERIC-HARNESS-REVIEW.md` | generic-harness review — can Coursebook teach an arbitrary topic (partially generic), evidence G-01…G-07 | `2e57efa`; amended `31b3132`, `6d062e1`, `db5662c` | `a8d119aa28763013d90d10f1c11c01f096d9412def17b8b5970e9eaa67e53da4` | `git cat-file -e 54dd2eb:docs/GENERIC-HARNESS-REVIEW.md` |
| `docs/GENERIC-ACCEPTANCE-AUDIT.md` | H-30 independent acceptance audit of H-09 (three shapes, checks, routing); base product tree `498b1da` | `ddc71fc`; merged at `090e755` | `19cbe115688e37a5814ee33c5699e1d984965e013f8c6818e6292cec738ecd89` | `git cat-file -e 54dd2eb:docs/GENERIC-ACCEPTANCE-AUDIT.md`; `git merge-base --is-ancestor 090e755 54dd2eb` |
| `docs/GENERIC-ACCEPTANCE-AUDIT-2.md` | H-30b independent re-audit of the generic harness after blueprint v2 (`single`/`short`/`full`) | `f92d5f8`; merged at `90e1f0d` | `b9b53721887af49579336bff43b1eb8834768f4a871f79dbbfd42f464dd2f275` | `git cat-file -e 54dd2eb:docs/GENERIC-ACCEPTANCE-AUDIT-2.md` |
| `docs/ASSESSMENT-BREADTH.md` | H-16 assessment construct breadth decision and its B-1/B-2/B-3 defect register | `dd43d82`; merged at `fa316c5` | `38021edef4d6cafdf9c45eaff0bcfbe17c8e2960150fba70093d99590f9e2c7e` | `git cat-file -e 54dd2eb:docs/ASSESSMENT-BREADTH.md` |
| `docs/COURSE-BLUEPRINT.md` | H-03 scope-aware blueprint design (single/short/full) plus §14, the frozen H-20 prerequisite contract; design authority for H-21 | master via merge `54087de` (content `f465a4d`); §14 added by `516d161` via `d079b4c` | `e3db7ac502ce65f70d53eb03ccbcf913197e54751df5b2a94adefeb669b345dd` | `git cat-file -e 54dd2eb:docs/COURSE-BLUEPRINT.md` |
| `docs/PLAN-CEILING.md` | H-21c measured `full` plan ceiling; the probe behind the 40-objective cap | `bcd545e`; merged at `2252231` | `9dc0792ad9eec2e7bafb8a5b974c94ac0dc74532ba4788c417c717f2436efad9` | `git cat-file -e 54dd2eb:docs/PLAN-CEILING.md` |
| `docs/GRADING-LANES.md` | H-20 decision + implementation record: every stored check declares its lane (implements B-1) | `ce6c8c1`; merged at `3368c96`, which enters `master` through `4e709d3` | `d4cb723096a513925cf8e7d30ad02b9b9bb4bee24570342e612a23b61a869916` | `git cat-file -e 54dd2eb:docs/GRADING-LANES.md`; `git merge-base --is-ancestor 4e709d3 54dd2eb` |
| `docs/CHECKLIST-CONFIRMATION.md` | H-33 frozen decision: a verification tick-list is graded `self_reported` | `da53ec1`; merged at `3d46988`, which enters `master` through `4e709d3` | `f559b2f18423f17fac3ae183bb6b9f8b76dec5371b8270498ca00940dd6c7f15` | `git cat-file -e 54dd2eb:docs/CHECKLIST-CONFIRMATION.md` |
| `docs/RUBRIC-EXTENSIBILITY.md` | H-24 frozen decision: the gate for a new construct profile (decision only, no runtime generator) | `491443a`; merged at `4f42c3c` | `7c73550ca4bbd9ef7cb55dbc9595c36e6926abcc108b236998da70bbc8c9d153` | `git cat-file -e 54dd2eb:docs/RUBRIC-EXTENSIBILITY.md` |
| `docs/STUDENT-MODE.md` | H-25 student-mode design: a companion course aligned to an uploaded syllabus; design only | `3705a7a`; merged at `e978441` | `df4dcdeca230d064e0b7cfc19b785f44ede1c40d862d2c16f4b934408b77deef` | `git cat-file -e 54dd2eb:docs/STUDENT-MODE.md` |
| `docs/HARNESS-NEXT-CARDS.md` | board card index / DAG, card-to-finding mapping, current-wave status | `2e3508f`; amended `a8d93b8`, `b4da6d9`, `31b3132`, `f17ec54`, `512c5f6`, `a671511`, `385ebac`, and later cards | `82af6664ba19738d40fa79a3f2da27685c67afea19c5e89d9677f9c41d6838c3` (at `1fc0542`; this card does not edit it. The pin moved from `f990cad` because later cards edited the file, not because the earlier hash was wrong) | `git cat-file -e 54dd2eb:docs/HARNESS-NEXT-CARDS.md` |
| `docs/HARNESS-STATUS.md` | H-11 status truth pass: build-complete vs proven vs fixture-only, plus the CB-QA-10 reconciliation | doc branch `b2233ac`; landed at `097c32c` (H-47) | `a959a83530a38318b9f2e27c25d9026d13b4877f8f909526f73ea0cc453a6b99` | `git cat-file -e 54dd2eb:docs/HARNESS-STATUS.md` |
| `docs/HARNESS-E2E.md` | H-40 packet method and its honest gaps, as landed | `9f2de53`; merged at `be08495` | `27ec514a003b261b5580782c50198782f2d45081d2678fd58c95dc512cae64d0` | `git cat-file -e 54dd2eb:docs/HARNESS-E2E.md` |
| `docs/H15-VALIDATOR-INDEPENDENCE.md` | H-36 integration record: H-15's validator identity, `outcome` and no-research waiver landed on cb.rpc v13 | `b75d601` (content on `wt/harness-validator-integration`) | `763c49ed5f50711066b5114c89690e23971a5e49e7f0878144aec833c8fb670a` | `git cat-file -e 54dd2eb:docs/H15-VALIDATOR-INDEPENDENCE.md` |
| `docs/H35B-LIVE-CHECKLIST-EVIDENCE.md` | H-35b live installed-Desktop DOM capture of a checklist confirmation on a fresh rig (CDP `127.0.0.1:9351`, backend `44277`) | `7a6b4b0` | `9cbd4d4d2a8e345f6702bf166e399bc695419397d736bf9bea8d835f72ad096c` | `git cat-file -e 54dd2eb:docs/H35B-LIVE-CHECKLIST-EVIDENCE.md` |
| `docs/REVIEW_CB014.md` | pre-harness adversarial security/state/a11y release review (cb.rpc v6) | `270edae` | `4a3b00205761eae6e298cc34c3197c868518a0e6ff98ea922ab4c02449c2a91b` | `git cat-file -e 270edae:docs/REVIEW_CB014.md` (amended in `8e11bd2`) |
| `docs/REVIEW_CB014-telemetry.md` | CB-014 tool-telemetry scope note | `51406ee` | `3f77fb9ccca8bf87daa904c1f6a9a13d00c3024f5ca970f5b4b16ffde8efbdb9` | `git cat-file -e 54dd2eb:docs/REVIEW_CB014-telemetry.md` |
| `docs/ACCEPTANCE.md` | adversarial acceptance matrix with explicit verified/seam/blocked/pending vocabulary | `b9da9f3` | `869918a97cb8e64f2c1daaaac9599904644049f138ceb6dd386ce1bb9a889d06` | `git cat-file -e 54dd2eb:docs/ACCEPTANCE.md` |
| `docs/CB016-RELEASE-VERIFICATION.md` | clean-export install and route-mount record | `7f80f35` | `291b21564292301f07ed0c947a36657079f9762da9e9592a4a999b0ad497a266` | `git cat-file -e 7f80f35:docs/CB016-RELEASE-VERIFICATION.md` |
| `docs/CB017-RELEASE-VERIFICATION.md` | release record re-derived on merged master and re-pinned | `638eb6b` | `55f9b3f07b49dd39dc817181cbddab818fda4ef9335203420b279eb545c79a3f` | `git cat-file -e 638eb6b:docs/CB017-RELEASE-VERIFICATION.md` (amended in `6eb93c2`) |
| `docs/M4-VISUAL-MEDIA-AUDIT.md` | M4-QA visual/accessibility/media truth gate (62 painted frames) | `2b37b5b` | `fd4328e2775d0d71fd9b53116ee8dc037e9403fadd150d949014b810c3c5286b` | `git cat-file -e 2b37b5b:docs/M4-VISUAL-MEDIA-AUDIT.md` (amended in `27a2e40`) |
| `docs/DEMO.md` | honest demo status; states the prepared pack proves one pack only | `5ad682e` | `c9f94a892e222c3a28100c26c04bafb345e156a9851f6d96eb2db49bd23770a8` | `git cat-file -e 54dd2eb:docs/DEMO.md` |

Every `content sha256 at 54dd2eb` value above was computed with
`git show 54dd2eb:<path> | sha256sum` for this revision. A hash that does not reproduce at the named
commit is a stale row, not a rounding error. Of the twenty-two rows the H-41 revision pinned,
nineteen reproduced unchanged even though master moved `1fc0542` → `54dd2eb`; three moved, each
because a merged card edited that file (`COURSE-BLUEPRINT.md` by H-43, `M4-VISUAL-MEDIA-AUDIT.md`
by H-39, `DEMO.md` by H-11). Three further rows are new (the H-30b, H-11 and H-40 reports). That is
why the H-41 pins were trustworthy and many of its **statuses** were not: content pins and merge
claims are different questions.

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

### H-40 arbitrary-topic packet — merged @ `9f2de53` via `be08495`

```
git cat-file -e 9f2de53:audit/adversarial/harness-e2e/STATUS.md        # exit 0
git cat-file -e 9f2de53:tests/test_harness_e2e.py                      # exit 0
git merge-base --is-ancestor 9f2de53 54dd2eb                           # exit 0 — merged
git cat-file -e 54dd2eb:audit/adversarial/harness-e2e/STATUS.md        # exit 0
git cat-file -e 54dd2eb:tests/test_harness_e2e.py                      # exit 0
```

`9f2de53` is based on `c588e4a` and records **3/3 scenarios PASS** (`bicycle_single`,
`music_short`, `soldering_full`) with recorded transcripts, recorded pages through the real search
seam, and `labels.provider_calls = 0`, `provider_spend_usd = 0.0`. Its own STATUS.md names six
honest gaps: no live provider, no live web research, course export out of scope, no language-goal
audio path, only plan acceptance proven at the 40-objective bound, and no Desktop renderer run. Its
focused suite is 11 tests and its full suite is 1422 tests **on its own branch**.

**What changed at the H-50 base.** The H-41 revision titled this subsection "branch-only @
`9f2de53`" and closed it "None of that is evidence about `1fc0542` until the supervisor merges
it". `9f2de53` is now an ancestor of `54dd2eb` through the merge `be08495`, so the packet, its
`docs/HARNESS-E2E.md` method note and `tests/test_harness_e2e.py` all resolve on master. The
11/1422 branch counts are **not** the current ones, because four later cards changed the tool and
then re-derived the evidence: H-45 `5d251cb` content-addressed the packet (`manifest.json` plus
`harness_e2e.py --verify`), H-46 `cd818fa` made the lesson validator reject truncated authored
text, which rejected the recorded shorts, H-46b `74978ca` re-authored them, and H-49 `54dd2eb`
regenerated the evidence on the merged tree after H-44 added `domain_provenance` to the plan
record. The current run is recorded with its commands in
`audit/adversarial/harness-e2e/STATUS.md` §H-49 — manifest **FRESH**, 3/3 scenarios PASS, 24 added
evidence lines, and no verdict, lesson, check or grading row changed. This index cross-references
that section rather than copying its counts; the packet a reader should quote is `9f2de53`'s tree
**as re-derived at `54dd2eb`**.

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

Status is the state of the **merged** evidence at `master` = `54dd2eb` (2026-11-07), re-derived
unchanged at `a674356` by H-163 (§15) and re-run at `4dacf07` by H-209 (§16; every verdict in the
fifth column is unchanged). A `done` card means its worker finished; it does **not** mean
the branch merged. "FIXED" requires the named merge commit to be an ancestor of `4dacf07`. "FIXED —
re-audit required" means the implementation is merged but no independent probe has run against that
behaviour on the merged line yet. The ancestor verdict in the fifth column was re-run for this
revision; rows that moved are listed in §16.

| finding | severity | status | owning card | evidence commit — ancestor of `4dacf07`? | card state |
|---|---|---|---|---|---|
| P0-1 learner create flow never starts generation | P0 | **FIXED** | H-02 `t_867d3b52` | merge `1bbd502` (content `5b74233`) — **yes** | done, merged |
| P0-2 plan schema caps at 8 sections / forces 4 objectives; no `scope` | P0 | **FIXED — implementation merged; re-audit required** | H-03 `t_577ed286` (design) + H-21a/b/c (`t_27867486`, `t_fb8b9622`, `t_6576b611`) | design merge `54087de` (content `f465a4d`) — **yes**; implementation merge `2252231` (content `bcd545e`; slices `8eb83d8`, `7f46e17`) — **yes** | done, merged |
| P0-3 capability-policy inputs unreachable; locale mistaken for subject | P0 | **FIXED** | H-01 `t_f4f5b26a` (contract) + H-13 `t_543c0767` (threading) | merges `b1f2978` (content `8cbaab3`) and `6779030` (content `ee976ea`) — **yes** | done, merged |
| P0-4 deep research is a no-op; demo-sized budget | P0 | **FIXED** | H-04 `t_161d467f` | content `cee1749`, merged at `341cc18` into `ce95836` — **yes** | done, merged |
| P0-5 a normal course cannot export itself | P0 | **FIXED** | H-08 `t_901c8310`; recovery H-08b `t_092cc689` | pre-recovery tip `c9c6cec` — **no** (branch history, superseded); recovery merge `18638be` — **yes**. On `1fc0542` `contracts/rpc.v13.json` carries 11 `course.export` hits and `tests/test_course_export.py` resolves | recovered, merged |
| P0-6 a technical procedure lesson cannot carry the procedure lens | P0 | **FIXED** | H-06 `t_7a320d2f`; recovery H-06b `t_6cd9e57c` | original tip `00b502f` — **yes** (landed through the H-06b line); recovery merge `acb20f7` — **yes**. `lesson_procedure_problems` resolves in `coursebook/generation.py` at `1fc0542` | recovered, merged |
| P0-7 no live arbitrary-topic generation | P0 | **OPEN — the merged packet is recorded-input only (`provider_calls = 0`); a live RPC-path call is proven separately by H-68, but with no validation record and no approved plan** (before H-166 this cell read `OPEN — packet merged, but no live provider call exists`) | H-09 `t_ebc196db`; re-run H-40; live re-run H-68 `t_f178ba3d` | H-09 `111c7e9` — **no** (deliberately unmerged, superseded by H-40); H-40 `9f2de53` via merge `be08495` — **yes**; re-derived by H-49 at `54dd2eb`. The packet reports 3/3 PASS with **recorded** transcripts and `provider_calls = 0` — a statement about the H-40 packet run (`audit/adversarial/harness-e2e/STATUS.md:31,33`), not about the product. The live half is H-68 (2026-11-07): under a real `hermes serve --isolated` on the H-63F RPC path, job `job_18e2916bd1684036b1ee0df26c8e950c` reached `completed` in 165 s with research `ok` (2 queries, 4 sources, `failures: []`), persisting plan `752bb7935176cbdc` at `draft` / `needs_review`; it required host commit `c02e6e0180` on `~/.hermes/hermes-agent` branch `wt/h68-serve-secret-scope`, a **source backup, not on any pushed line**. Copies of the four evidence files: `audit/adversarial/h63-live-generation/h68-host-scope/`. Still OPEN — no validation record was produced, so nothing was approved or taught (§15). H-209 (§16) records the newer in-tree live measurement on `f0be341` and why it still does not close this row | H-09 done, branch abandoned; H-40 merged; H-68 done (host fix source-backup only) |
| P1-1 parent brief stored but mostly ignored by the planner | P1 | **FIXED** | H-07 `t_2f3cc647` (+ H-32b regression) | content `8a6bedb` merged at `afac32c` into `ce95836` — **yes**; conflict regression `8d018e4` via `c7461fc` — **yes** | done, merged |
| P1-2 planner does not plan media; policy guesses from prose | P1 | **FIXED** | H-05 `t_7baa29e2` | content `986190f` merged at `a30487e` into `ce95836` — **yes** | done, merged |
| P1-3 check `count` / `independent_evidence` are decorative | P1 | **FIXED — re-audit required** | H-21c `t_6576b611` | merge `2252231` (content `bcd545e`) — **yes**; `CHECK_PLAN_SCHEMA_V2` drops both fields | done, merged |
| P1-4 authoring schemas are Japanese-shaped | P1 | **FIXED** | H-18 `t_8407ea22`; recovery H-18b (same defect as round-2 P2-7) | pre-recovery tip `2aca201` — **no**; recovery merge `580bbb6` — **yes**. `tests/test_locale_scaffolds.py` resolves at `1fc0542` | recovered, merged |
| P1-5 assessment breadth is narrow | P1 | **OPEN — the B-series is closed but construct breadth is still three input formats** (was `OPEN — B-1 and B-3 merged; B-2 unmerged` at `54dd2eb`) | H-16 `t_3c5d969c`; B-1 `t_673155b0`; B-2 `t_74d99ca5`; B-3 H-22 `t_966d50f4` | decision `dd43d82` via `fa316c5` — **yes**; B-1 `ce6c8c1` via `4e709d3` — **yes**; B-3 `47e152c` via `1fc0542` — **yes**; B-2 `b13890c` via `d20a7a6`, `a729e36` via `b7ff866`, `76a59ed` via `bbebd96` — **yes** | all four done and merged; B-2 closed at `bbebd96` (§14) |
| P1-6 rubric registry is static | P1 | **FIXED (decision) — re-audit not applicable** | H-24 `t_29e6647c` | merge `4f42c3c` (content `491443a`), `docs/RUBRIC-EXTENSIBILITY.md` — **yes** | done, merged |
| P2-1 test matrix proves policy, not generation | P2 | **FIXED — packet merged; its model half is a recorded transcript** | H-09 `t_ebc196db`; re-run H-40 | `111c7e9` — **no**; `9f2de53` via `be08495` — **yes**; `tests/test_harness_e2e.py` resolves at `54dd2eb` (26 tests in the H-49 run) | done, merged |
| P2-2 depth/locale not tested through the product surface | P2 | **FIXED** | H-04 `t_161d467f` + H-13 `t_543c0767` | `cee1749` via `ce95836` — **yes**; `6779030` — **yes** | done, merged |
| P2-3 procedure/media evidence is static or fixture | P2 | **PARTIAL — procedure lane now runs through the merged pipeline; media lane still unproven** | H-09 `t_ebc196db`; re-run H-40 | `111c7e9` — **no**; `9f2de53` via `be08495` — **yes**; `soldering_full` exercises the procedure lens end to end on recorded transcripts. No scenario exercises image or speech media, so the media half of this finding is not closed | done, merged (packet) |

**P1-3 and P1-6 were UNMAPPED two revisions ago; both now name a merged owner.** P1-3 is closed by
`CHECK_PLAN_SCHEMA_V2` in `bcd545e`, which removes `count` and `independent_evidence` from the v2
check plan; P1-6 is closed as a *decision* by `docs/RUBRIC-EXTENSIBILITY.md`, which deliberately
declines a runtime rubric generator. The P1-6 row is FIXED in the sense the finding asked for
(a gate exists); it is not a runtime feature and no row here implies one. **No round-1 finding
remains UNMAPPED.**

## 5. Finding ledger — round 2 (`docs/ADVERSARIAL-AUDIT-ROUND2.md`)

The report proposed its own `H-11`…`H-18` labels. Those labels **collide** with the board keys; the
board keys are authoritative and are the only ids used here. Status is the merged state at
`54dd2eb`, re-derived unchanged at `a674356` by H-163 (§15) and re-run at `4dacf07` by H-209 (§16;
every verdict unchanged); the fifth column is the ancestor verdict checked at `4dacf07`.

| finding | severity | status | owning card | evidence commit — ancestor of `4dacf07`? | card state |
|---|---|---|---|---|---|
| P0-1 validator-rejected plan is stored as an approvable `draft` | P0 | **FIXED** | H-12 `t_dba06898` | merge `13480c4` (content `4b5f3b1`) — **yes**; round-2 probe `903a606` — **yes** | done, merged |
| P0-2 fetched excerpt is raw prompt content; invented prose URLs pass | P0 | **FIXED** | H-14 `t_031e287f` | merge `a12176b` (content `0ba4dc6`) — **yes** | done, merged |
| P1-3 "independent validation" is prompt separation; same model upgrades support | P1 | **FIXED — implementation merged; no independent probe of the verdict exists** | H-15 `t_d519643b`; integration H-36 `t_48645f63` | `833e335` — **yes** (through the merge); merge `b75d601` — **yes**; `docs/H15-VALIDATOR-INDEPENDENCE.md` resolves at `54dd2eb` | done, merged. H-30b (`f92d5f8` via `90e1f0d`) re-audited shape, grading and the approval gate; it ran **no** cross-model identity probe, so this row's re-audit is still missing |
| P1-4 factual gate auto-waives when research is unavailable | P1 | **FIXED — implementation merged; no independent probe of the verdict exists** | H-15 `t_d519643b`; integration H-36 `t_48645f63` | `833e335` — **yes**; merge `b75d601` — **yes**; `outcome`/`facts_unverified` are in `validation_verdict()` at `54dd2eb` | done, merged. H-30b merged (`90e1f0d`) but its recorded research page was a recording, so the no-research waiver was not re-probed |
| P1-5 assessment breadth: three input formats only | P1 | **OPEN — the B-series is closed but construct breadth is still three input formats** (was `OPEN — B-1 and B-3 merged; B-2 unmerged` at `54dd2eb`) | H-16 `t_3c5d969c` → B-1 `t_673155b0`, B-2 `t_74d99ca5`, B-3 H-22 `t_966d50f4` | decision `dd43d82` via `fa316c5` — **yes**; B-1 `ce6c8c1` via `4e709d3` — **yes**; B-3 `47e152c` via `1fc0542` — **yes**; B-2 `b13890c` via `d20a7a6`, `a729e36` via `b7ff866`, `76a59ed` via `bbebd96` — **yes** | all done and merged; B-2 closed at `bbebd96` (§14) |
| P1-6 flat `$0.75` ceiling, no cost-abort recovery | P1 | **FIXED** | H-17 `t_9a8543ae` (+ `t_d50cb007` v10 brief fix) | content `722f00f` merged at `4dd68cb` into `ce95836` — **yes**; `fbf96fe` — **yes** | done, merged |
| P2-7 Japanese-only scaffold triple; no direction field | P2 | **FIXED** | H-18 `t_8407ea22`; recovery H-18b | pre-recovery tip `2aca201` — **no**; recovery merge `580bbb6` — **yes**; `tests/test_locale_scaffolds.py` resolves at `1fc0542` | recovered, merged |
| P2-8 no prerequisite edges; adaptation is a state label | P2 | **FIXED — re-audited by H-30b** | H-20 `t_43ca17b8` (frozen contract) + H-21c `t_6576b611` (implementation) | contract `516d161` via `d079b4c` — **yes**; implementation merge `2252231` (content `bcd545e`) — **yes** | done, merged; H-30b `f92d5f8` via `90e1f0d` proves `course.outline` projects `prereq_unit_ordinals` and a `prerequisite_state` per unit in `short` and `full`. The state-label half of the finding (no dynamic re-plan) stays OPEN under D-04 |
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
  probe the result. No row here calls validator independence "independently proven" on `54dd2eb`.
  H-30b's tip `f92d5f8` **is** an ancestor now (merge `90e1f0d`), but its re-audit measured the
  three shapes, the grading lanes and the approval gate; it did not re-probe cross-model identity,
  so the independence claim still has no independent audit.
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

| id | status | owning card | evidence commit — ancestor of `4dacf07`? | note |
|---|---|---|---|---|
| D-01 plan approval is advisory, not fail-closed | **FIXED** | H-12 `t_dba06898` | merge `13480c4` (content `4b5f3b1`) — **yes** | same defect as round-2 P0-1 |
| D-02 the green suite encodes the defect | **FIXED** | H-12 | tests changed in `4b5f3b1` — **yes**; audit assertion `903a606` — **yes** | empty-plan approvals now assert refusal |
| D-02b two plan digests, one approval | **FIXED** | H-12 + H-02 | `13480c4` (durable binding) — **yes** + `1bbd502` (learner path reads kernel digest via `parent.blueprint.read`) — **yes** | the fix is a projection, not a digest comparison |
| D-03 the plan job drops contract inputs | **FIXED** | H-13 `t_543c0767` | merge `6779030` (content `ee976ea`) — **yes** | level/subject_domain/scope reach prompt, research and fingerprint |
| D-04 "adaptation" is a state transition | **OPEN — narrowed** | H-03 (design, merged `54087de`), H-20 (contract `516d161`, merged `d079b4c`), H-21c (`bcd545e`, merged `2252231`) | all three — **yes** | prerequisite sequencing now exists; there is still **no** dynamic re-plan, no choice among remediation/examples/next objective and no attempt-driven content change. Do not market it as adaptive teaching. H-30b is merged (`f92d5f8` via `90e1f0d`) but measured plan shape, grading and the approval gate — not adaptation — so no probe of this finding exists; `docs/COURSE-BLUEPRINT.md` §9 still states the state-transition claim. Re-derived OPEN at `a674356` (§15) and again at `4dacf07` (§16). |
| D-05 validation independence is structural only | **FIXED — implementation merged; no independent probe of the verdict exists** | H-15 `t_d519643b`; integration H-36 `t_48645f63` | `833e335` — **yes**; merge `b75d601` — **yes** | same defect as round-2 P1-3/P1-4. The integration landed. H-30b merged too (`f92d5f8` via `90e1f0d`), but it did not re-probe validator identity, so the "independently validated" claim is still implementation-plus-review, not an independent audit. |
| D-06 stale CB-QA-10 claim survives in README | **FIXED — both README passages rewritten by H-52 `a044fb4`; the reference is withheld on the wire** | H-11 `t_6f41e0b0`; closure H-52 `t_58ae1236` | `b2233ac` via `097c32c` (H-47) — **yes**; `a044fb4` (H-52) | H-52 rewrote `README.md:98-101` ("two backend defects are open") and `:204-205` (the L2 projection returns the reference): the projection now carries `id`, `description`, `check_id` and a `check_spec_withheld` marker from `PUBLIC_CRITERION_FIELDS`, so the `check_spec` holding the reference never leaves the backend, and CB-QA-11 (auxiliary grader, S13 `BLOCKED`) is named as the one open item. Re-derived by H-52 on `40bd4eb`, not copied: `attack_state.py` S07 reads `open_check_reference_leaks=[] post_submit_reference_leaks=[] secret_present=False` and the run ends `SUMMARY total=22 fail=0 pass=22`; `tests/test_review_evidence.py:378,384` assert `check_spec` is absent. `docs/ACCEPTANCE.md` and `docs/REVIEW_CB014.md` stay as historical records of their own commits and are not rewritten. H-50's status cell, kept verbatim: "**PARTIAL — H-11 docs merged and reconcile the live docs; `README.md` still carries the stale claim**". |

D-06 also covers the `REVIEW_CB014.md` row for CB-QA-10 ("OPEN"). That row is **not** rewritten in
this file — the index pins status, it does not edit the review — but H-41 did re-derive the code
claim: at `1fc0542` `coursebook/evidence.py` projects only `PUBLIC_CRITERION_FIELDS` and
`tests/test_review_evidence.py` passes (24 tests OK, including
`test_evidence_inspect_never_carries_the_reference_answer`). So `README.md`, `docs/ACCEPTANCE.md`,
`docs/PRIVACY_EGRESS.md` and `docs/REVIEW_CB014.md` now describe a defect the merged code no longer
has. H-11 owned recanonicalising them; `b2233ac` merged via `097c32c`, and H-52 (`a044fb4`) has
since rewritten the two README passages, so the live docs agree with the code. `docs/ACCEPTANCE.md`
and `docs/REVIEW_CB014.md` remain historical records at their own commits and are deliberately not
rewritten (`docs/HARNESS-STATUS.md` §4).

## 7. Third wave — UX, generic-harness and acceptance findings

`docs/ADVERSARIAL-UX-REVIEW.md` and `docs/GENERIC-HARNESS-REVIEW.md` are merged at `2e57efa`
(amended by `31b3132`, `6d062e1`, `db5662c`). `docs/GENERIC-ACCEPTANCE-AUDIT.md` (`ddc71fc`) is
merged at `090e755` but audits `498b1da`, not `1fc0542`. Card bodies are the authority for scope.
Every "merged" cell below names a commit that is an ancestor of `4dacf07` (H-163 re-ran all of them
at `a674356`; H-209 re-ran them at `4dacf07` in §16 and every verdict is unchanged). The two packets
that were branch-only at the H-41 base — H-30b's `f92d5f8` and H-40's `9f2de53` — are both ancestors
of `4dacf07` (merges `90e1f0d` and `be08495`).

One limit on every H-30b verdict below: H-30b measured `f990cad`, which is an ancestor of
`54dd2eb` but not the tip. It ran before H-42/H-43/H-44/H-45/H-46, so it cannot confirm those
cards' fixes and did not re-test them; the D4…D8 rows below are closed from the later cards'
own commits, not from H-30b.

### Generic-harness findings (G-series, `docs/GENERIC-HARNESS-REVIEW.md`)

| finding | summary | owning card | merged state at `4dacf07` | re-audit |
|---|---|---|---|---|
| G-01 | One-off shape is schema-rejected (`minItems: 4` objectives, 2 sections) | H-21a/b/c (`t_27867486`, `t_fb8b9622`, `t_6576b611`) | **merged** `2252231` — `PLAN_SCHEMA_V2` objectives `minItems: 1`, and `SCOPE_EXPECTATIONS["single"]["blueprint_objectives"] = (1, 1)` (H-43 renamed the v1 key `v1_objectives` so it cannot be read as the v2 band) | **done** — H-30b `f92d5f8` via `90e1f0d`: a 1-objective `single` is ACCEPTED, a padded 4-objective `single` is refused by the rules |
| G-02 | Generated checks are saved, not graded (no reference `kind`) | B-1 `t_673155b0` (H-16 B-1; the card title carries a stale "H-20" collision label) | **merged** `4e709d3` (content `ce6c8c1`), `docs/GRADING-LANES.md`, `tests/test_grading_lanes.py` | **done** — H-30b `f92d5f8` via `90e1f0d`: every generated quiz check stores `reference.kind = exact`; correct → `pass`, wrong → `not_yet`, neither `needs_retry` |
| G-03 | Scope is on the wire but the plan shape caps it | H-21a/b/c | **merged** `2252231` — v2 `objectives` `maxItems: 40`, `units` `minItems: 1` | **done** — H-30b `f92d5f8` via `90e1f0d`: 12/24/40-objective `full` plans accepted, 41 rejected at the declared cap |
| G-04 | Media/procedure lens incomplete | H-05 `t_7baa29e2` + H-06 `t_7a320d2f`; recovery H-06b | **merged** — H-05 `ce95836`; H-06 `00b502f`; H-06b `acb20f7` (all ancestors). `lesson_procedure_problems` resolves at `54dd2eb` | **partly done** — the merged H-40 packet (`9f2de53` via `be08495`) runs the procedure lens end to end with recorded content; no scenario exercises image or speech media, so the media half still has no probe |
| G-05 | Only a prepared Japanese pack has run end to end | H-09 `t_ebc196db` (packet) + H-30 `t_178dc615` (audit); re-run H-40 | H-09 `111c7e9` deliberately unmerged (superseded); H-40 `9f2de53` **merged** via `be08495` (3/3 PASS, recorded transcripts, 0 provider calls), re-derived by H-49 at `54dd2eb`; H-30 `090e755` merged but audits `498b1da` | **done** for three non-Japanese goals, on recorded transcripts. Still not done: live provider authoring, live research, course export in the packet (`docs/HARNESS-E2E.md` § gaps) |
| G-06 | Student mode / second import path does not exist | H-25 `t_5535fc66` (design), H-26a `t_faad26cf` (backend), H-27 `t_71ea55ee` (UI), H-26b (read projection) | design **merged** `e978441` (content `3705a7a`); backend **merged** `d0ca064`; UI **merged** `ca1ca4f`; projection **merged** `21e62e5` — all ancestors. `syllabus.intake.create` resolves in `contracts/rpc.v13.json` and `desktop/plugin.js` at `54dd2eb` | implementation merged; no independent G-06 re-audit exists |
| G-07 | Rubric profiles are static | H-24 `t_29e6647c` (decision, not a runtime generator) | **merged** `4f42c3c` (content `491443a`), `docs/RUBRIC-EXTENSIBILITY.md` | decision only; no runtime to audit |

### H-30 acceptance findings (D1…D8, `docs/GENERIC-ACCEPTANCE-AUDIT.md` @ `498b1da`)

H-30 ran on `498b1da`, before `2252231`/`4e709d3`. H-30b `t_9b6742f3` re-ran these shapes after
blueprint v2; its report `docs/GENERIC-ACCEPTANCE-AUDIT-2.md` is on master (`f92d5f8` via merge
`90e1f0d`) and says the H-30 result is stale. D1/D2/D3 no longer reproduce. D4…D8 were closed by
later cards and are verified against `54dd2eb` below.

Two numbering traps, both live: H-30b's **own** P3 findings are also called D1…D4 (partial unit
batch, self-reported one-off check, stale `full` prompt sentence, v1 ranges in `SCOPE_EXPECTATIONS`)
and they collide with this table's H-30 D1…D8. H-42 `a24b566` closed H-30b-D1, H-43 `a326d22`
closed H-30b-D3 and H-30b-D4, and H-30b-D2 is open by design (a tick-list is self-report). Those
four are *not* rows in this table.

| id | H-30 verdict at `498b1da` | what changed on `54dd2eb` | status |
|---|---|---|---|
| D1 | `single` padded to 4 objectives — FAIL | `PLAN_SCHEMA_V2` `minItems: 1`; `blueprint_objectives` for `single` = (1, 1) in `bcd545e` | **re-audited — no longer reproduces** (H-30b `f92d5f8` via `90e1f0d`: 1 unit / 1 objective accepted, 4-objective `single` refused by the rules) |
| D2 | `full` truncated at 8, no units/prereqs — BLOCKED | `maxItems: 40`, `plan_units` in `db.v7` migration `0007_plan_units.sql`, §14 gating in `bcd545e` | **re-audited — no longer reproduces** (H-30b `f92d5f8` via `90e1f0d`: 6 units / 24 objectives with backward-only prereq edges; 40 accepted, 41 rejected) |
| D3 | generated checks return `needs_retry` for both answers — FAIL | fix `ce6c8c1` merged at `4e709d3` | **re-audited — fixed and proven** (H-30b `f92d5f8` via `90e1f0d`: every generated quiz check stores `reference.kind = exact`; correct → `pass`, wrong → `not_yet`) |
| D4 | language goal with no locale/domain silently `general` | H-44 `67fdf4f`: `_domain_provenance()` in `coursebook/generation.py`, copied into the job checkpoint by `coursebook/executor.py`. The authoring result is still `general` by design, but it now reports `source: default` plus the declared locale/domain and appends a human note to the warnings | **FIXED** — the fallback is recorded, not silent. H-44 deliberately does **not** infer a language from goal text (`docs/COURSE-BLUEPRINT.md` §15) |
| D5 | H-09 evidence docs do not name the evidence commit; test count environment-dependent | the H-40 packet is merged (`9f2de53` via `be08495`), names base `c588e4a` and, after H-45, pins every evidence file and harness input by sha256 in `manifest.json`; the H-11 docs line is merged too (`b2233ac` via `097c32c`) and `docs/HARNESS-STATUS.md` resolves | **FIXED** — the packet's own 11/1422 counts are branch-era and §3 says so; the current counts are the H-49 run's |
| D6 | H-09 `scope_matches_documented_bounds` compares the code to itself | H-45 `5d251cb`: the check now reads `contracts/rpc.v13.json`, `PLAN_SCHEMA_V2` and the published `blueprint_*` band, fails when those declarations disagree, and records the bound and every violation. Negative tests refuse a padded 4-objective `single`, a 6-objective `full` and a 41-objective plan | **FIXED** — `5d251cb` via `5917bfb` |
| D7 | evidence packet not byte-reproducible (verdict-only freshness guard) | H-45 `5d251cb`: deterministic id minting plus `manifest.json`, and `harness_e2e.py --verify` compares hashes (`PacketManifestTest` at `tests/test_harness_e2e.py:238`, docstring "D7"). H-49 regenerated the evidence on the merged tree and the manifest reads **FRESH** | **FIXED** — `5d251cb` via `5917bfb`; re-verified at `54dd2eb` |
| D8 | lesson validator accepted truncated authored texts | H-46 `cd818fa` adds `coursebook/text_completeness.py` as a structural ending gate inside `lesson_document.validate_blocks`, used by both unit-section and lesson enforcement; `tests/test_text_completeness.py` pins one truncation per shape. H-46b `74978ca` re-authored the recorded shorts the new gate rejected, and H-49 re-derived the packet | **FIXED** — `cd818fa` via `57dcd97`. Known residue: the gate false-positives on a complete sentence ending in a stranded preposition, recorded in `audit/adversarial/harness-e2e/STATUS.md` and owned by H-46/H-51 |

### UX findings (UX-series, `docs/ADVERSARIAL-UX-REVIEW.md`)

H-28 (`t_271e19e7`) and H-29 (`t_70686b14`) are merged through the H-38 union commit `1fc0542`;
their tips `184640a` and `eb8e4c5` are ancestors of it. **Merged implementation is not an
independent UX re-audit**: no UX row below has been re-probed against the shipped module. What H-41
did verify is the copy the review demanded: at `1fc0542` `desktop/plugin.js` contains
"First try, no hints" ×2, "Start with a goal" ×1, "What Coursebook can check" ×1, "How will you use
it" ×1, "Reported by you — not independently verified." ×1 and "Your answer is text, a choice, or a
checklist" ×1; at `c588e4a` every one of those counts is 0.

| finding | summary | owning card | merged state at `4dacf07` |
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

The decision document is on master (`fa316c5`, content `dd43d82`). All three implementation defects
are merged: B-1 at `4e709d3`, B-3 at `1fc0542`, and B-2 at `bbebd96` (H-58, §14) — all ancestors of
`a674356` (H-163, §15) and re-run at `4dacf07` (H-209, §16; every verdict unchanged). The sha the earlier revisions recorded for B-2 (`423908f`) is still wrong and
stays recorded as wrong; the landing shas are `b13890c`, `a729e36` and `76a59ed`.

| finding | summary | owning card | merged state at `4dacf07` |
|---|---|---|---|
| B-1 | Generated lesson checks store no reference `kind`; grader falls to the unconfigured open lane | `t_673155b0` (title still says "H-20"; **B-1** is authoritative) | **merged** `4e709d3` (content `ce6c8c1`); `docs/GRADING-LANES.md`, `tests/test_grading_lanes.py` (15 tests) |
| B-2 | `record_observation` has no RPC method, handler or UI; `self_reported`/`parent_reported` unreachable | `t_74d99ca5` (Atlas's earlier label was "H-21"; **B-2** is authoritative) | **FIXED at `bbebd96` (2026-11-07, H-58 `t_85135fc7`).** The H-50 status cell, quoted: "**OPEN, and the row's sha is wrong.** `423908f` is **not** an ancestor of `54dd2eb` … `observation.record` appears nowhere in `contracts/rpc.v13.json` … `desktop/plugin.js` has zero `observation.record` hits … were never merged". Those sentences are true of `54dd2eb` and stay as history; the full cell is still readable at `54dd2eb` and in §13. At `bbebd96` all three halves exist: `contracts/rpc.v14.json` declares `observation.record` among 64 methods (frozen by H-53 `b13890c`, merged `d20a7a6`); `coursebook/domain.py:3754` registers `@_handler("observation.record")` (H-54 `a729e36`, merged `b7ff866`) and `implemented_methods()` returns 64 of 64 with no gap; `desktop/plugin.js` mounts `ParentObservation` on a parent-recipe `SectionPage` (H-55 `76a59ed`, merged `bbebd96`) and carries six `observation.record` hits. `cb.db` v9's `0009_evidence_note.sql` (also `b13890c`) gives the record a `note` column, so a note round-trips instead of being dropped (`tests/test_kernel_transitions.py:361`). Commands and their output: §14 |
| B-3 | `EVIDENCE_CLASS_COPY` covers 4 of 6 evidence classes | H-22 `t_966d50f4` (frozen disclosure copy + labels) | **merged** — `47e152c` via `1fc0542` (H-38 union). `EVIDENCE_CLASS_COPY` at `1fc0542` has all six keys: `cold`, `hinted`, `answer_shown`, `self_reported`, `parent_reported`, `override` |

**H-23 `t_132531da` ("Generated checks are ungradable") is `done` as a duplicate with no product
code:** it was seeded before the B-1 duplicate was noticed. It is not evidence for B-1 and must not
be re-run. B-1's owner is `t_673155b0`, and B-1's fix is `ce6c8c1`.

## 8. Card index — H-21…H-50

Every card created after the second wave, with the findings it owns or audits, its branch, and its
**merged** state at `4dacf07` (re-derived by H-163 at `a674356` and re-run by H-209 at `4dacf07`,
§16). Cards with no commit and no evidence on
that tree (H-48 has neither, and the numbering skips it) are not listed.

| card | id | owner | parents | branch | merged at `4dacf07` | owns / audits |
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
| H-30b | `t_9b6742f3` | sentinel | H-30, H-21c | `wt/harness-generic-audit-2` @ `f92d5f8` | **yes** — `90e1f0d`; report `docs/GENERIC-ACCEPTANCE-AUDIT-2.md` | **re-audit** of the single/short/full findings — PASS for all three shapes on `f990cad`; no P0/P1/P2 defect. Its four P3 items were later routed: D1 → H-42, D3/D4 → H-43, D2 open by design |
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
| H-39 (M4-V re-pin) | `t_5fb93891` | — | H-38 | `wt/m4v-determinism` @ `8ba5704`; `wt/m4v-landing` @ `7404e9c` | **yes** — `7404e9c` and `4945061` via `be08495`; both tips are now ancestors | re-pin the M4-V frames against the shipped plugin sha `c206e1c9`; `docs/M4-VISUAL-MEDIA-AUDIT.md` re-pinned (content sha moved) |
| H-40 (H-09 re-run) | `t_e32900ef` | sentinel | H-09 | `wt/h09-e2e-rerun` @ `9f2de53` | **yes** — `be08495`; packet re-derived by H-49 at `54dd2eb` | arbitrary-topic packet on blueprint v2 — 3/3 PASS, recorded transcripts, 0 provider calls. The 11/1422 counts are branch-era; see §3 and `audit/adversarial/harness-e2e/STATUS.md` §H-49 |
| H-41 (audit index) | `t_ef2600f8` | quill | H-38 | `wt/audit-index-h41` @ `7163903` | **yes** — `7163903` via `be08495` | the H-41 revision re-landed on the merged tree; §12 is its record |
| H-42 (partial unit batch) | `t_590a6be4` | cinder | H-40 | — | **yes** — `a24b566` via `be08495` | H-30b P3-D1: the unit_sections stage is transactional; a rule violation or validator rejection discards the batch and fails the job with typed reasons |
| H-43 (stale v1 scope copy) | `t_d71f9441` | cinder | H-40 | — | **yes** — `a326d22` via `be08495` | H-30b P3-D3/D4: the `full` note makes no numeric claim; the v1 ranges are renamed `v1_objectives`; `tests/test_scope_copy.py` pins the rendered v2 prompt |
| H-44 (silent general domain) | `t_c1faf526` | atlas | — | — | **yes** — `67fdf4f` via `8e7ebc4` | records `domain_provenance` (`source`, `resolved_domain`, `declared_subject_domain`, `declared_locale`, `target_language`) on the plan job and checkpoint; freezes the no-inference choice in `docs/COURSE-BLUEPRINT.md` §15 |
| H-45 (scope contract + packet freshness) | `t_645ad886` | cbqa | — | — | **yes** — `5d251cb` via `5917bfb` | H-30 acceptance D6 and D7: scope judged against the declared contracts; deterministic ids + `manifest.json` + `--verify` freshness |
| H-46 (truncated lesson text) | `t_8977ce2c` | cinder | — | — | **yes** — `cd818fa` via `57dcd97` | H-30 acceptance D8: `coursebook/text_completeness.py` in the shared lesson validator; `tests/test_text_completeness.py` |
| H-46b (recorded shorts) | `t_4e1efe01` | sentinel | H-46 | — | **yes** — `74978ca` via `57dcd97` | re-authored the recorded shorts the H-46 gate rejected; regenerated the packet on `cd818fa` + H-45 |
| H-47 (H-11 docs landing) | `t_0d97c3e7` | quill | — | `wt/h47-docs-union` @ `13b60ae` | **yes** — `097c32c`/`13b60ae` via `43daf21` | landed the H-11 docs (`docs/HARNESS-STATUS.md` + DEFECTS/PRIVACY_EGRESS/SUBMISSION/DEMO/INSTALL) on `be08495` without regressing H-41's index; §5.1 records the landing gate |
| H-49 (packet re-run on merged tree) | (card id not recorded here) | sentinel | — | — | **yes** — `54dd2eb` is the commit itself | regenerated the H-40 packet after H-44 added `domain_provenance`; manifest FRESH, 3/3 PASS, 24 added evidence lines, no verdict changed |
| H-50 (this card) | `t_37df1fb9` | quill | — (top-level) | `wt/h50-audit-refresh` | no (this card) | this revision: audit-index truth pass on `54dd2eb` |

## 9. Provenance checks this index relies on

Run on `master` at `54dd2eb`. Each must stay true or the index is stale. H-163 re-ran the ancestor
lines against `a674356` and resolved all 33 file paths at `a674356` as well: every one still exits 0
(§15).

```
git cat-file -e 54dd2eb:docs/ADVERSARIAL-HARNESS-REVIEW.md
git cat-file -e 54dd2eb:docs/ADVERSARIAL-AUDIT-ROUND2.md
git cat-file -e 54dd2eb:docs/ADVERSARIAL-UX-REVIEW.md
git cat-file -e 54dd2eb:docs/GENERIC-HARNESS-REVIEW.md
git cat-file -e 54dd2eb:docs/GENERIC-ACCEPTANCE-AUDIT.md
git cat-file -e 54dd2eb:docs/GENERIC-ACCEPTANCE-AUDIT-2.md
git cat-file -e 54dd2eb:docs/ASSESSMENT-BREADTH.md
git cat-file -e 54dd2eb:docs/COURSE-BLUEPRINT.md
git cat-file -e 54dd2eb:docs/PLAN-CEILING.md
git cat-file -e 54dd2eb:docs/GRADING-LANES.md
git cat-file -e 54dd2eb:docs/CHECKLIST-CONFIRMATION.md
git cat-file -e 54dd2eb:docs/RUBRIC-EXTENSIBILITY.md
git cat-file -e 54dd2eb:docs/STUDENT-MODE.md
git cat-file -e 54dd2eb:docs/HARNESS-STATUS.md
git cat-file -e 54dd2eb:docs/HARNESS-E2E.md
git cat-file -e 54dd2eb:docs/H15-VALIDATOR-INDEPENDENCE.md
git cat-file -e 54dd2eb:docs/H35B-LIVE-CHECKLIST-EVIDENCE.md
git cat-file -e 54dd2eb:contracts/rpc.v13.json
git cat-file -e 54dd2eb:contracts/db.v7.json
git cat-file -e 54dd2eb:coursebook/migrations/0007_plan_units.sql
git cat-file -e 54dd2eb:coursebook/text_completeness.py
git cat-file -e 54dd2eb:tests/test_prerequisite_gating.py
git cat-file -e 54dd2eb:tests/test_grading_lanes.py
git cat-file -e 54dd2eb:tests/test_checklist_confirmation.py
git cat-file -e 54dd2eb:tests/test_course_export.py
git cat-file -e 54dd2eb:tests/test_procedure_authoring.py
git cat-file -e 54dd2eb:tests/test_locale_scaffolds.py
git cat-file -e 54dd2eb:tests/test_validator_independence.py
git cat-file -e 54dd2eb:tests/test_text_completeness.py
git cat-file -e 54dd2eb:tests/test_harness_e2e.py
git cat-file -e 54dd2eb:audit/adversarial/harness-e2e/STATUS.md
git cat-file -e 54dd2eb:audit/adversarial/harness-e2e/manifest.json
git cat-file -e 54dd2eb:desktop/plugin.js

git merge-base --is-ancestor 13480c4 54dd2eb   # H-12 merge
git merge-base --is-ancestor 903a606 54dd2eb   # H-12 round-2 audit assertion (test commit)
git merge-base --is-ancestor b1f2978 54dd2eb   # H-01 merge
git merge-base --is-ancestor a12176b 54dd2eb   # H-14 merge
git merge-base --is-ancestor 1bbd502 54dd2eb   # H-02 merge
git merge-base --is-ancestor 54087de 54dd2eb   # H-03 design merge
git merge-base --is-ancestor 6779030 54dd2eb   # H-13 merge
git merge-base --is-ancestor ce95836 54dd2eb   # integration merge: H-04/H-05/H-07/H-17/H-19
git merge-base --is-ancestor fa316c5 54dd2eb   # H-16 decision
git merge-base --is-ancestor d079b4c 54dd2eb   # H-20 frozen contract
git merge-base --is-ancestor 2252231 54dd2eb   # H-21a/b/c implementation merge
git merge-base --is-ancestor 4e709d3 54dd2eb   # H-20/H-33/H-34/H-35 checklist + grading merge
git merge-base --is-ancestor e978441 54dd2eb   # H-25 design merge
git merge-base --is-ancestor 090e755 54dd2eb   # H-30 audit merge
git merge-base --is-ancestor c7461fc 54dd2eb   # H-32b merge
git merge-base --is-ancestor 4f42c3c 54dd2eb   # H-24 decision merge
git merge-base --is-ancestor fdecc9e 54dd2eb   # H-31 index merge
git merge-base --is-ancestor a671511 54dd2eb   # H-31b content re-landed
git merge-base --is-ancestor 385ebac 54dd2eb   # H-31b follow-up
git merge-base --is-ancestor 18638be 54dd2eb   # H-08b authored export
git merge-base --is-ancestor acb20f7 54dd2eb   # H-06b procedure lens
git merge-base --is-ancestor 00b502f 54dd2eb   # H-06 original tip (landed through H-06b)
git merge-base --is-ancestor 580bbb6 54dd2eb   # H-18b locale scaffolds
git merge-base --is-ancestor 9e6c5e4 54dd2eb   # H-18b locale test line
git merge-base --is-ancestor 8600bcd 54dd2eb   # locale dir/lang test rendered through the shipped plugin
git merge-base --is-ancestor b75d601 54dd2eb   # H-36 validator integration (H-15 tip 833e335 inside)
git merge-base --is-ancestor 833e335 54dd2eb   # H-15 itself, now merged through H-36
git merge-base --is-ancestor d0ca064 54dd2eb   # H-26a student intake
git merge-base --is-ancestor 2d7ecde 54dd2eb   # H-26 salvage, landed through H-26a
git merge-base --is-ancestor ca1ca4f 54dd2eb   # H-27 / H-37 student UI merge
git merge-base --is-ancestor 21e62e5 54dd2eb   # H-26b / H-37 read projection merge
git merge-base --is-ancestor c588e4a 54dd2eb   # M4-V regeneration before the H-38 union
git merge-base --is-ancestor 47e152c 54dd2eb   # H-22 copy, merged by H-38
git merge-base --is-ancestor 184640a 54dd2eb   # H-28 first-run copy, merged by H-38
git merge-base --is-ancestor eb8e4c5 54dd2eb   # H-29 learning copy, merged by H-38
git merge-base --is-ancestor 7a6b4b0 54dd2eb   # H-35b live checklist capture
git merge-base --is-ancestor 1fc0542 54dd2eb   # H-38 UX union, the previous index base
git merge-base --is-ancestor 8ba5704 54dd2eb   # H-39 M4-V determinism branch
git merge-base --is-ancestor 7404e9c 54dd2eb   # H-39 M4-V landing branch
git merge-base --is-ancestor 7163903 54dd2eb   # H-41 index truth pass
git merge-base --is-ancestor 9f2de53 54dd2eb   # H-40 arbitrary-topic packet
git merge-base --is-ancestor be08495 54dd2eb   # merge of H-41/H-40/H-39/H-43/H-42
git merge-base --is-ancestor f92d5f8 54dd2eb   # H-30b re-audit
git merge-base --is-ancestor 90e1f0d 54dd2eb   # merge of H-30b
git merge-base --is-ancestor b2233ac 54dd2eb   # H-11 docs truth pass
git merge-base --is-ancestor 097c32c 54dd2eb   # H-47 landing of the H-11 docs
git merge-base --is-ancestor 13b60ae 54dd2eb   # H-47 landing-gate note
git merge-base --is-ancestor a24b566 54dd2eb   # H-42 transactional unit stage
git merge-base --is-ancestor a326d22 54dd2eb   # H-43 scope copy
git merge-base --is-ancestor 67fdf4f 54dd2eb   # H-44 domain provenance
git merge-base --is-ancestor 5d251cb 54dd2eb   # H-45 scope contract + packet manifest
git merge-base --is-ancestor cd818fa 54dd2eb   # H-46 text-completeness gate
git merge-base --is-ancestor 74978ca 54dd2eb   # H-46b complete-sentence shorts
git merge-base --is-ancestor 54dd2eb 54dd2eb   # master itself

# must NOT be ancestors — a merged fix must not be claimed where it is not
! git merge-base --is-ancestor 111c7e9 54dd2eb                  # H-09 pre-v2 packet, deliberately superseded
! git merge-base --is-ancestor 423908f 54dd2eb                  # B-2 branch (not the commit that introduced _OBSERVATION_CLASSES)
! git merge-base --is-ancestor c9c6cec 54dd2eb                  # H-08 pre-recovery tip
! git merge-base --is-ancestor 2aca201 54dd2eb                  # H-18 pre-recovery tip (replacement 8600bcd)
! git merge-base --is-ancestor 2bfeb1c 54dd2eb                  # H-31b branch tip (content re-landed)
```

Every line above was run for this revision under `set -e`: the block exits 0. Ancestor lines must
succeed; `!` lines assert the commit is **not** an ancestor. A reader can re-run the block and get
the same verdicts, or the index is stale.

Rules enforced:

- **No claim cites a file that exists only in a worktree.** Every report above is tracked at
  `54dd2eb`. The rows that describe an unmerged branch name its tip so a reader can check it, not
  so it can be treated as merged.
- **A branch is not a merge, and a done card is not a merge.** After this revision the only named
  work whose commit is not an ancestor of `54dd2eb` is H-09 (`111c7e9`), B-2 (`423908f`) and the
  superseded pre-recovery tips `c9c6cec`/`2aca201`/`2bfeb1c`. Everything else the ledger names is
  an ancestor. H-09 and `2aca201` are **deliberately** unmerged: H-09's packet measured a harness
  three generations old and is replaced by `9f2de53` (re-derived by `74978ca`), and `2aca201`'s
  locale scaffolds are replaced by `580bbb6` with the shipped-plugin rendering test `8600bcd`.
  Being superseded is not the same as being merged.
- **A merged fix is not a passed re-audit.** H-30b (`f92d5f8` via `90e1f0d`) has now probed the
  single/short/full shapes and the grading lanes on `f990cad`, so D1…D3 and G-01…G-03 moved. It
  did **not** probe validator identity or the no-research waiver, so those rows still read
  "no independent probe exists" rather than "closed". A re-audit on one behaviour is not a
  re-audit of every behaviour that shares a card.
- **A prepared pack is not a topic proof.** No row above derives a harness claim from
  `bundled/packs/japanese-affection-context-l0`.
- **A live capture is not implied by a merged surface.** H-35's surface is merged, and H-35b's live
  capture is merged at `7a6b4b0` — but at plugin sha `ab6347…` on `f990cad`, not at the shipped
  `c206e1c9`. It proves the checklist nodes render; it does not re-prove the H-38 copy in a browser.

## 10. What this index does not claim

- It does not claim the harness is fully generic. `docs/GENERIC-HARNESS-REVIEW.md` at `54dd2eb`
  says "partially generic". The shape blockers G-01/G-03 are *implemented* at `2252231` and were
  re-probed by H-30b (`f92d5f8` via `90e1f0d`) on `f990cad`; H-30b's model half is a scripted
  double and its research page is a recording, so "generic" here means the contract and pipeline
  accept the three shapes, not that a live model authors them.
- It does not claim H-09's branch is merged: `111c7e9` is deliberately superseded and stays out.
  H-11's docs **are** merged (`b2233ac` via `097c32c`), and H-52 (`a044fb4`) has since rewritten the
  two stale README passages, so the D-06 row now reads FIXED.
  H-06, H-08, H-15, H-18, H-22, B-3, H-40 and the H-26 line are merged — being merged is not the
  same as having passed a re-audit, and the rows that need one say so.
- It does not claim H-15's validator independence has been independently re-audited on master. The
  integration is merged at `b75d601`. H-30b is merged too (`f92d5f8` via `90e1f0d`), but its
  re-audit measured shape, grading and the approval gate, not the reported model identities, so no
  independent probe of the independence claim exists.
- It does not claim H-23 did any work: it was closed as a duplicate with no code.
- It does not claim H-26's original card completed. It timed out; its WIP was salvaged at `2d7ecde`
  and the work was finished by H-26a, whose merge `d0ca064` is an ancestor of `54dd2eb`. The code is
  on master; the card that shipped it is H-26a.
- It does not claim the checklist confirmation has a live Desktop capture **at the shipped plugin
  sha**. H-35b's capture exists and is merged (`7a6b4b0`), but it was taken at `f990cad` plugin sha
  `ab6347…`; nothing re-takes it at `c206e1c9`.
- It does not claim any finding is closed because a card is `done`.
- It does not re-run, re-grade or extend any audit; probe results are attributed to the card that
  produced them.
- It does not claim the harness is installable, demo-ready, or proven on a **live** arbitrary
  topic. H-40's packet is merged (`9f2de53` via `be08495`) and re-derived at `54dd2eb`, and reports
  3/3 PASS on blueprint v2 — but its model half is a recorded transcript, it called no provider,
  and it did not exercise course export or a media lane. H-30 audited an older tree; H-30b
  re-audited shape and grading with a scripted model.
- It does not claim the fixes that landed between `a674356` and `4dacf07` — H-183/H-189, H-206,
  H-192b/H-192c, H-199, H-194e, H-182/D1-D3, H-182/D6 and H-182/D8 — passed a re-audit on the
  settled tree. For each, the implementation is an ancestor; §16 says which live re-walk exists,
  at which module pin, and which one is still owed.
- It does not use the prepared Japanese pack as evidence for anything.
- It changes no product code, contract, schema, migration or test.

## 11. Changes in the H-31b revision (historical) — every moved row and its commit

Compared with the H-31 revision (`512c5f6`). "Merged" was checked against `master` = `f990cad` with
`git merge-base --is-ancestor`. Rows not listed did not change status in this revision.

**This table is the H-31b record at `f990cad`, not a current status.** Its "status at `f990cad`"
cells that read "unmerged" were true of that base; H-163 re-derived each one against `a674356` and
annotated the cell with its state there, keeping the historical verdict intact. Current status is
§4–§7; the full re-derivation with commands is §15.

| row | previous status (H-31) | status at `f990cad` (this record) | commit that justifies it | ancestor of `f990cad` |
|---|---|---|---|---|
| round-1 P0-2 | OPEN — design merged, implementation unmerged (`5ba4e4c`) | **FIXED — implementation merged; re-audit required** | `2252231` (content `bcd545e`; slices `8eb83d8`, `7f46e17`) | yes |
| round-1 P0-4 | OPEN — done, unmerged (`cee1749`) | **FIXED** | `cee1749` via `ce95836` | yes |
| round-1 P0-5 | OPEN (H-08 running) | OPEN — done, unmerged at `f990cad`; **content on `a674356`** — H-08b `18638be` (ancestor) carries the authored export: `contracts/rpc.v16.json` declares `course.export.read` and `tests/test_course_export.py` resolves. `c9c6cec` never landed: content landed as `18638be`; branch abandoned (§15) | `c9c6cec` | no (`c9c6cec` at this base) |
| round-1 P0-6 | OPEN (H-06 running) | OPEN — done, unmerged at `f990cad`; **merged at `a674356`** — `00b502f` **is** an ancestor and H-06b `acb20f7` merged; `lesson_procedure_problems` resolves (§15) | `00b502f` | no (`00b502f` at this base) |
| round-1 P0-7 | OPEN (H-09 todo) | OPEN — done, unmerged at `f990cad`; **still OPEN at `a674356`** — `111c7e9` is not an ancestor and no live provider call is recorded in the tree (H-68's live RPC-path run is off-tree — §4, §15); the merged packet `9f2de53` records `provider_calls = 0` (§15) | `111c7e9` | no |
| round-1 P1-1 | OPEN — done, unmerged (`8a6bedb`) | **FIXED** | `8a6bedb` via `ce95836`; regression `8d018e4` via `c7461fc` | yes |
| round-1 P1-2 | OPEN — done, unmerged (`986190f`) | **FIXED** | `986190f` via `ce95836` | yes |
| round-1 P1-3 | OPEN — mapped to H-21 (`5ba4e4c`) | **FIXED — re-audit required** | `bcd545e` via `2252231` (`CHECK_PLAN_SCHEMA_V2`) | yes |
| round-1 P1-4 | OPEN (H-18 running) | OPEN — done, unmerged at `f990cad`; **content on `a674356`** — H-18b `580bbb6` merged and `tests/test_locale_scaffolds.py` resolves. `2aca201` was an M4 frame refresh superseded by later M4 regenerations: content landed as `580bbb6`; branch abandoned (§15) | `2aca201` | no (`2aca201` at this base) |
| round-1 P1-5 | OPEN — decision unmerged, B-1/B-2/H-22 running | OPEN — decision merged; B-1 merged; B-2/B-3 unmerged at `f990cad`; **at `a674356` B-1, B-2 and B-3 are all merged and P1-5 stays OPEN** on construct breadth (§15) | `fa316c5`; `4e709d3`; `423908f`; `47e152c` | mixed |
| round-1 P1-6 | OPEN — mapped to H-24, no commits | **FIXED (decision)** | `491443a` via `4f42c3c` | yes |
| round-1 P2-1 | OPEN (H-09 todo) | OPEN — blocked on H-09 at `f990cad`; **packet merged at `a674356`** — `9f2de53` via `be08495`, re-derived by H-49 (§15) | `111c7e9` | no (`111c7e9` at this base) |
| round-1 P2-2 | OPEN — half mapped | **FIXED** | `cee1749` via `ce95836` + `6779030` | yes |
| round-1 P2-3 | OPEN (H-09 todo) | OPEN — blocked on H-09 at `f990cad`; **PARTIAL at `a674356`** — the merged packet runs the procedure lens end to end; no scenario exercises image or speech media, so the media half is still unproven (§15) | `111c7e9` | no (`111c7e9` at this base) |
| round-2 P1-3 | OPEN — done, unmerged | OPEN — done, unmerged at `f990cad`; **merged at `a674356`** — `833e335` is an ancestor through H-36 `b75d601`; no independent probe of validator identity exists (§15) | `833e335` | no (`833e335` at this base) |
| round-2 P1-4 | OPEN — done, unmerged | OPEN — done, unmerged at `f990cad`; **merged at `a674356`** — `833e335` is an ancestor through `b75d601`; the no-research waiver has no independent probe (§15) | `833e335` | no (`833e335` at this base) |
| round-2 P1-5 | OPEN — decision unmerged; implementations running | OPEN — decision merged; B-1 merged; B-2/B-3 unmerged at `f990cad`; **all three merged and P1-5 still OPEN at `a674356`** on construct breadth (§15) | `fa316c5`; `4e709d3`; `423908f`; `47e152c` | mixed |
| round-2 P1-6 | OPEN — done, unmerged (`722f00f`) | **FIXED** | `722f00f` via `4dd68cb` → `ce95836` | yes |
| round-2 P2-7 | OPEN (H-18 running) | OPEN — done, unmerged at `f990cad`; **FIXED at `a674356`** — H-18's product half is merged as H-18b `580bbb6`. `2aca201` was an M4 frame refresh that later M4 regenerations superseded: content landed as `580bbb6`; branch abandoned, and `2aca201` is not credited (§15) | `2aca201` | no (`2aca201` at this base) |
| round-2 P2-8 | OPEN — done, unmerged (`516d161`) | **FIXED — re-audit required** | `516d161` via `d079b4c`; impl `bcd545e` via `2252231` | yes |
| round-2 P2-10 | FIXED — index branch-only | **FIXED** — index now merged | `99da48a` via `ce95836` | yes |
| D-04 | OPEN — design merged, implementations unmerged | **OPEN — narrowed** (sequencing merged, adaptation claim unchanged); still OPEN at `a674356`, no attempt-driven re-plan exists (§15) | `516d161`; `bcd545e` | partial |
| D-05 | OPEN — done, unmerged | OPEN — done, unmerged at `f990cad`; **merged at `a674356`** — `833e335` via `b75d601`; no independent validator-identity probe (§15) | `833e335` | no (`833e335` at this base) |
| D-06 | OPEN (H-11 running) | OPEN — done, unmerged at `f990cad`; **FIXED at `a674356`** — `b2233ac` via `097c32c`, and H-52 `a044fb4` rewrote both README passages (§15) | `b2233ac` | no (`b2233ac` at this base) |
| G-01 | ready, `5ba4e4c` unmerged | **merged** `2252231`; re-audit required | `8eb83d8`/`7f46e17`/`bcd545e` | yes |
| G-02 | running (B-1) | **merged** `4e709d3`; re-audit required | `ce6c8c1` | yes |
| G-03 | ready, unmerged | **merged** `2252231`; re-audit required | `bcd545e` | yes |
| G-04 | H-05 done/unmerged + H-06 running | H-05 **merged** `ce95836`; H-06 `00b502f` and H-06b `acb20f7` merged at `a674356`; media half still unproven (§15) | `986190f`; `00b502f` | partial |
| G-05 | H-09/H-30 todo | H-09 `111c7e9` branch abandoned; H-30 audit **merged** on `498b1da`; H-40 `9f2de53` and H-30b `f92d5f8` **merged** via `be08495`/`90e1f0d` at `a674356` (§15) | `9f2de53`; `ddc71fc`; `090e755` | partial |
| G-06 | H-25 ready | H-25 design **merged**; H-26 superseded → H-26a running; H-27 running | `3705a7a` via `e978441` | design yes |
| G-07 | running, no commits | **merged** (decision) | `491443a` via `4f42c3c` | yes |
| B-1 | running | **merged** `4e709d3` | `ce6c8c1` | yes |
| B-2 | running (`423908f`) | done, unmerged at `f990cad`; **FIXED at `a674356`** — `b13890c`, `a729e36` and `76a59ed` are all ancestors; `423908f` is not (§15) | `423908f` | no (`423908f` at this base) |
| B-3 | running (`002a82b`) | done, unmerged at `f990cad`; **merged at `a674356`** — `47e152c` via `1fc0542`. The branch was rebased onto `f17ec54` (`8ef1cc1`); the old tip `002a82b` is history (§15) | `47e152c` | no (`002a82b` at this base) |
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
copy the verdicts, re-run them. Rows not listed did not change status. Its "status now" cells are the
`1fc0542` record: the cells that read "merge pending supervisor" were true of that base, and H-163
re-derived them at `a674356` (§15). Current status is §4–§7.

| row | previous status (H-31b) | status at `1fc0542` (this record) | commit that justifies it | ancestor of `1fc0542` |
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

## 13. Changes in the H-50 revision — every moved row and its commit

Base: `master` = `54dd2eb` (`54dd2eb48f5f3410cb9f591f4a2d9a283e20672c`), the H-49 packet re-run.
That base is the parent of the merge that carried this revision onto `master`: `40bd4eb` merges
H-50 (`aaa267a`) and H-51 (`2620c95`), and both of those have `54dd2eb` as their parent — so H-50
verified these rows at `54dd2eb` and `40bd4eb` is the merge that carried them.
This is the H-50 record at that base. Its quoted "unmerged" cells are the old text it was correcting,
kept verbatim by that revision's own rule; H-163 re-derived the same cells at `a674356` in §15, and
the current status is §4–§7.
Compared with the H-41 revision: commit `7163903`, whose parent is `1fc0542`. `be08495` merged it
without changing the file (`git diff 7163903 be08495 -- docs/AUDIT-INDEX.md` is empty). Every
verdict below was re-run against `54dd2eb` for this card; do not copy them, re-run them. Rows not
listed did not change status. §11/§12 are untouched.

| row | previous status (H-41) | status now | commit that justifies it | ancestor of `54dd2eb` |
|---|---|---|---|---|
| round-1 P0-7 no live arbitrary-topic generation | OPEN — packet re-run on v2; merge pending supervisor | **OPEN — packet merged, but no live provider call exists** | `9f2de53` via merge `be08495`; re-derived by H-49 at `54dd2eb` | yes (packet); the *live* half is still unproven, so the row stays open |
| round-1 P2-1 test matrix proves policy, not generation | OPEN — blocked on the H-40 packet merging | **FIXED — packet merged; model half is a recorded transcript** | `9f2de53` via `be08495`; `tests/test_harness_e2e.py` resolves at `54dd2eb` | yes |
| round-1 P2-3 procedure/media evidence is static or fixture | OPEN — blocked on the H-40 packet merging | **PARTIAL — procedure lane proven; media lane unproven** | `9f2de53` via `be08495` (`soldering_full`); no media scenario exists | yes for procedure; media has no evidence |
| H-30 D1 `single` padded to 4 objectives | re-audit required (H-30b, unmerged) | **re-audited — no longer reproduces** | `f92d5f8` via merge `90e1f0d`; `docs/GENERIC-ACCEPTANCE-AUDIT-2.md` | yes |
| H-30 D2 `full` truncated at 8 | re-audit required (H-30b, unmerged) | **re-audited — no longer reproduces** (6 units / 24 objectives; 40 accepted, 41 rejected) | `f92d5f8` via `90e1f0d` | yes |
| H-30 D3 checks `needs_retry` for both answers | re-audit required (H-30b, unmerged) | **re-audited — fixed and proven** | `f92d5f8` via `90e1f0d`; fix `ce6c8c1` via `4e709d3` | yes |
| H-30 D4 language goal silently `general` | OPEN — Atlas to route | **FIXED — fallback recorded with provenance, not silent** | H-44 `67fdf4f` via `8e7ebc4` | yes |
| H-30 D5 H-09 evidence docs / test count | addressed on an unmerged branch only | **FIXED — packet and H-11 docs both merged** | `9f2de53` via `be08495`; `b2233ac` via `097c32c` | yes |
| H-30 D6 scope compared to itself | OPEN — H-40 packet, unmerged | **FIXED — judged against the declared contracts** | H-45 `5d251cb` via `5917bfb` | yes |
| H-30 D7 packet not byte-reproducible | OPEN — H-40 packet, unmerged | **FIXED — content-addressed manifest; `--verify` reads FRESH** | H-45 `5d251cb` via `5917bfb`; re-verified by H-49 at `54dd2eb` | yes |
| H-30 D8 validator accepted truncated text | OPEN — H-40 / lesson-validator owner | **FIXED — structural ending gate in the shared lesson validator** | H-46 `cd818fa` via `57dcd97`; evidence by H-46b `74978ca` | yes |
| §6 D-05 validation independence | FIXED — implementation merged; re-audit required | **FIXED — implementation merged; no independent probe of the verdict exists** | `833e335` via `b75d601`; H-30b `f92d5f8` merged but did not probe identity | yes (fix); re-audit still missing |
| §6 D-06 stale CB-QA-10 claim in README | OPEN — documentation defect on master; fix branch unmerged | **FIXED — both README passages rewritten by H-52; the reference is withheld on the wire** | `b2233ac` via `097c32c`; closure `a044fb4` (H-52) | yes |
| G-01 one-off shape rejected | re-audit required, H-30b (unmerged) | **done — 1-objective `single` accepted, 4-objective refused** | `f92d5f8` via `90e1f0d` | yes |
| G-02 checks saved, not graded | re-audit required, H-30b (unmerged) | **done — every generated check carries `reference.kind`** | `f92d5f8` via `90e1f0d`; fix `ce6c8c1` | yes |
| G-03 plan shape caps scope | re-audit required, H-30b (unmerged) | **done — 12/24/40 accepted, 41 rejected** | `f92d5f8` via `90e1f0d` | yes |
| G-04 media/procedure lens | required, H-30b (unmerged) | **partly done — procedure proven, media unproven** | `9f2de53` via `be08495` | yes for procedure |
| G-05 only the Japanese pack ran end to end | required, H-30b; H-40 merge is the first step | **done for three non-Japanese goals, on recorded transcripts** | `9f2de53` via `be08495`; H-49 `54dd2eb` | yes |
| round-2 P1-3 / §6 D-05 re-audit marker | "independent re-audit is H-30b" (unmerged) | **H-30b merged; it did not cover validator identity** | `f92d5f8` via `90e1f0d` | yes |
| round-2 P2-8 prerequisite edges | FIXED — re-audit required | **FIXED — re-audited by H-30b** | `f92d5f8` via `90e1f0d`; `2252231` | yes |
| §7 B-2 row sha | done, unmerged: `423908f` | **FIXED at `bbebd96`** — cb.rpc v14 declares the method, H-54 dispatches it (`implemented_methods()` 64/64), cb.db v9 persists the note, H-55 mounts the control (was `OPEN, and the sha is wrong` — … `no observation.record RPC, handler or UI exists at 54dd2eb`) | `b13890c` via `d20a7a6`; `a729e36` via `b7ff866`; `76a59ed` via `bbebd96` | not at `54dd2eb` (the closure is later); all four are ancestors of `bbebd96` |
| §8 H-30b card | no | **yes** — `90e1f0d` | `f92d5f8` | yes |
| §8 H-39 card | no | **yes** — `7404e9c`, `4945061` via `be08495` | `4945061` | yes |
| §8 H-40 card | no | **yes** — `be08495` | `9f2de53` | yes |
| §8 H-41 card | no (this card) | **yes** — `7163903` via `be08495` | `7163903` | yes |
| §1 register pins | hashes at `1fc0542` | **recomputed at `54dd2eb`**; 19 of 22 reproduced, three moved (`COURSE-BLUEPRINT.md` by H-43, `M4-VISUAL-MEDIA-AUDIT.md` by H-39, `DEMO.md` by H-11); three rows added | `54dd2eb` | — |
| §9 ancestor block | `b2233ac`, `9f2de53`, `f92d5f8`, `423908f` asserted **not** ancestors | the first three **are** ancestors now; `423908f`, `111c7e9`, `2aca201`, `c9c6cec`, `2bfeb1c` are not; H-09's and H-18's old tips are recorded as deliberately superseded | see §9 | mixed |

New rows added by this revision: the three report-register rows (§1), the H-42/H-43/H-44/H-45/H-46/
H-46b/H-47/H-49/H-50 card rows and the corrected H-30b/H-39/H-40/H-41 states (§8), and the
numbering note in §7 that distinguishes H-30b's own P3 D1…D4 from this index's H-30 D1…D8.

### The rows whose wording changed materially — old text kept verbatim

The H-41 cells below are quoted from `git show 54dd2eb:docs/AUDIT-INDEX.md` as it stood before this
card, so a reader can see what was claimed and why it moved. Nothing here is deleted from history:
the same cells remain readable at `54dd2eb` and in §12.

- round-1 P0-7: `OPEN — packet re-run on v2; merge pending supervisor` … `H-40 9f2de53 on
  wt/h09-e2e-rerun (base c588e4a) — no. The packet reports 3/3 PASS with recorded transcripts and 0
  provider calls` … `done; neither branch merged`.
- round-1 P2-1: `OPEN — blocked on the H-40 packet merging` … `111c7e9 — no; 9f2de53 — no` …
  `done, unmerged`.
- round-1 P2-3: `OPEN — blocked on the H-40 packet merging` … `111c7e9 — no; 9f2de53 — no` …
  `done, unmerged`.
- §6 D-06: `OPEN — documentation defect on master; fix branch unmerged` … `branch wt/harness-docs
  @ b2233ac — no` … `The stale claim is still on master and is now also false: README.md:97 and
  :202, docs/PRIVACY_EGRESS.md:167, docs/ACCEPTANCE.md:32 (S07 FAIL row) and docs/REVIEW_CB014.md:31
  /:114 still call CB-QA-10 open. At 1fc0542 coursebook/evidence.py:45/:57 projects only
  PUBLIC_CRITERION_FIELDS … docs/HARNESS-STATUS.md, the H-11 deliverable, does not resolve on
  master.` Two corrections: the README lines are `:99` and `:204` at `54dd2eb` (this card measured
  them), and `docs/HARNESS-STATUS.md` **does** resolve on master. The claim that the README text was
  still stale was the reason the row read PARTIAL until H-52. **Moved to FIXED by H-52**
  (`a044fb4`, branch `wt/h52-docs-truth`): both README passages were rewritten, so the L2 projection
  carries `check_spec_withheld` instead of the reference and the row reads FIXED. The H-50 cell
  quoted in this bullet stays as the record of why it read PARTIAL; the H-50 status cell is quoted
  verbatim in the §6 row.
- §7 B-2: `done, unmerged: wt/harness-observation-record @ 423908f — not an ancestor of 1fc0542`. The "not an ancestor" half is still true at `54dd2eb`; the implied "this is the fix"
  reading was never true and is corrected above. **Superseded at `bbebd96` (H-58):** B-2 is closed by
  `b13890c`/`d20a7a6`, `a729e36`/`b7ff866` and `76a59ed`/`bbebd96`; the quoted cell stays as the record
  of what the H-50 revision said about `54dd2eb`. See §14.
- §3 H-40 heading: `### H-40 arbitrary-topic packet — branch-only @ 9f2de53`, whose command block
  asserted `git cat-file -e 1fc0542:audit/adversarial/harness-e2e/STATUS.md ; test $? -eq 1 # absent
  from master` and `git merge-base --is-ancestor 9f2de53 1fc0542 ; test $? -eq 1 # not merged`. Both
  were true at `1fc0542` and are false at `54dd2eb`; the block is replaced, not deleted, in §3.

### The verifying commands and what they printed

Run for this card, in this worktree, at `54dd2eb`:

```text
$ for c in 9f2de53 f92d5f8 b2233ac 097c32c 67fdf4f 5d251cb cd818fa 74978ca 423908f 111c7e9 2aca201 8600bcd; do
    git merge-base --is-ancestor $c 54dd2eb; echo "$?  $c"; done
0  9f2de53
0  f92d5f8
0  b2233ac
0  097c32c
0  67fdf4f
0  5d251cb
0  cd818fa
0  74978ca
1  423908f
1  111c7e9
1  2aca201
0  8600bcd

$ git log --reverse -S'_OBSERVATION_CLASSES' --format='%h %s' 54dd2eb -- coursebook/domain.py
cde58c6 CB-002: authoritative SQLite kernel, grading gate and transactional commands
0f6310b CB-002: authoritative SQLite kernel, grading gate and transactional commands

$ git show 54dd2eb:coursebook/domain.py | grep -n '^_OBSERVATION_CLASSES'
3684:_OBSERVATION_CLASSES = ("self_reported", "parent_reported")
$ git show 54dd2eb:coursebook/domain.py | grep -c '^def record_observation'
1
$ git show 54dd2eb:contracts/rpc.v13.json | grep -c 'observation.record'
0                    # exit 1 — no such RPC method in the contract
$ grep -c 'observation.record' desktop/plugin.js
0

$ git cat-file -e 54dd2eb:docs/HARNESS-STATUS.md                                    # exit 0
$ grep -n 'CB-QA-10' README.md
99: ... two backend defects are open ... (CB-QA-10), ...
204: - `evidence.inspect` returns an open check's reference in the L2 projection (CB-QA-10).
$ grep -n 'CB-QA-10' docs/PRIVACY_EGRESS.md DEFECTS.md docs/SUBMISSION.md
167: ... Fixed on this tree and re-derived ...
21:  ... CB-QA-10 is fixed ...
220: ... (CB-QA-10, **fixed**) ...

$ git merge-base --is-ancestor 1fc0542 54dd2eb ; echo $?
0                    # the H-41 base is inside this master, so its history is readable here
$ git diff --stat 1fc0542 54dd2eb -- docs/
 docs/AUDIT-INDEX.md                | 602 +++++++++++++-----
 docs/COURSE-BLUEPRINT.md           |  52 ++
 docs/DEMO.md                       |  21 +
 docs/GENERIC-ACCEPTANCE-AUDIT-2.md | 188 +++++
 docs/HARNESS-E2E.md                | 109 +++
 docs/HARNESS-STATUS.md             | 158 +++++
 docs/INSTALL.md                    |  11 +-
 docs/M4-VISUAL-MEDIA-AUDIT.md      |  24 +-
 docs/PRIVACY_EGRESS.md             |   9 +-
 docs/PRODUCT-LINE-RELEASE-NOTES.md |  14 +-
 docs/SUBMISSION.md                 |   9 +-
```

Two claims in this revision are **card-measured, not re-run here**: the H-49 packet (manifest FRESH,
3/3 PASS, 26 focused / 1524 full tests) is quoted from
`audit/adversarial/harness-e2e/STATUS.md` §H-49 with its own commands, and H-30b's verdicts are
quoted from `docs/GENERIC-ACCEPTANCE-AUDIT-2.md` at `f92d5f8`. This card ran no product gate, no
provider call and no harness run.

### Rows deliberately left open, with the reason

- **round-1 P0-7 — no live arbitrary-topic generation.** The merged packet's model half is a
  recorded transcript and `labels.provider_calls = 0`. Merging the evidence does not create the
  live provenance the finding asks for.
- **round-1 P2-3 / G-04 — the media half.** `soldering_full` proves the procedure lens; no packet
  scenario exercises image or speech media, so "media evidence is static or fixture" is still true.
- **B-2 — the row's sha is wrong and the behaviour it asks for is still missing.** Naming
  `cde58c6` (which introduced the constant long before B-2) would have been the easy fix and would
  have closed a finding that is not closed: there is no `observation.record` RPC method, no handler
  dispatch and no UI at `54dd2eb`. **Closed at `bbebd96` by H-58; see §14.** Every sentence of the
  paragraph above is true of `54dd2eb` and is kept as history.
- **§6 D-06 — README (resolved after this revision).** H-11 reconciled `PRIVACY_EGRESS.md`,
  `DEFECTS.md` and `SUBMISSION.md` and landed `docs/HARNESS-STATUS.md`; `README.md:99` and `:204`
  still called CB-QA-10 open at the H-50 base. Flipping the row to FIXED would have required editing
  README, which was a docs change H-50 did not own; H-52 (`a044fb4`) made that edit and the row now
  reads FIXED.
- **D-04 — untouched by instruction.** The "do not market it as adaptive teaching" warning and its
  requalification stand exactly as written; nothing in H-30b's shape re-audit, H-42's transactional
  unit stage or H-43's scope copy adds dynamic re-plan or attempt-driven content change.
- **The demo gate `t_6a32ffe9` — untouched.** No row here reports a demo result.

### What this revision is, and is not

It is a status reconciliation against a new master, not a new audit. It re-ran `git merge-base
--is-ancestor`, `git cat-file -e`, `git log -S`, and file-level greps at `54dd2eb`; it ran no product
gate and no audit probe, and it changed no product code, contract, schema, migration or test. It
keeps §11/§12 exactly as written so the H-31b and H-41 claims stay readable next to the
correction, rather than being silently deleted.

**The release gate reads this file.** After this revision the only rows that can support a release
claim are those naming an ancestor of `54dd2eb`, and every ledger row that names one also says
whether an independent re-audit exists. The two rows that most invite overstatement — P0-7 and
P2-3's media half — stay OPEN on purpose.

## 14. Changes in the H-58 revision — B-2 closed at `bbebd96`; P1-5 held OPEN by H-59

Base: `master` = `bbebd96` (`bbebd96bd6873c2b22970fd240d0fe410c9ee6b8`), the merge that carried H-55
(`76a59ed`, "parent-observation control calls observation.record") onto master. This revision moves
**B-2** from OPEN to FIXED and amends the two P1-5 rows whose B-2 half it closes — but it does
**not** close P1-5, because P1-5's finding is construct breadth (code, performance, artifact), and
that is still three text input formats. This is the H-58 record at `bbebd96`: its "previous status
(H-50)" cells quote older text by design, and H-163 re-derived the same rows at `a674356` in §15.
Rows not listed did not change status. §11/§12/§13 are kept
as the H-31b, H-41 and H-50 records; §9 of `docs/ASSESSMENT-BREADTH.md` (the H-53 authorization
paragraph) is untouched.

The B-2 closure is three work commits — `b13890c`, `a729e36`, `76a59ed` — carried by the merges
`d20a7a6`, `b7ff866` and `bbebd96`, and each commit carries a different half of the defect:

| row | previous status (H-50) | status now | commit that justifies it | ancestor of `bbebd96` |
|---|---|---|---|---|
| §7 B-2 (H-16 B-series) | `OPEN, and the row's sha is wrong` — no `observation.record` RPC method, handler or UI at `54dd2eb` | **FIXED** — declared in `cb.rpc` v14, dispatched by a registered handler, persisted with its note, and mounted in Desktop | `b13890c` (cb.rpc v14 + cb.db v9 + `0009_evidence_note.sql`) via merge `d20a7a6`; `a729e36` (handler) via merge `b7ff866`; `76a59ed` (Desktop) via merge `bbebd96` | yes |
| §4 round-1 P1-5 | `OPEN — B-1 and B-3 merged; B-2 unmerged` | **OPEN — B-1, B-2 and B-3 are all closed; construct breadth is still three input formats** | the same closure commits; B-1 `ce6c8c1` via `4e709d3`, B-3 `47e152c` via `1fc0542` | yes |
| §5 round-2 P1-5 | `OPEN — B-1 and B-3 merged; B-2 unmerged` | **OPEN — B-1, B-2 and B-3 are all closed; construct breadth is still three input formats** | the same closure commits | yes |

**Why P1-5 still reads OPEN.** Its finding is not "the B-series is unmerged": it is that a course can
only be assessed through three text-shaped input formats (authored prompt item, structured
`stimulus.items[]` checklist, and free text), so code, recorded performance and submitted artifacts
cannot be graded at all. `docs/ASSESSMENT-BREADTH.md` §10 makes each of those a gated construct whose
implementation needs a spike that produces real gate evidence, and nothing has landed: at `bbebd96`,
`grep -c` for `code.run`, `performance.submit` and `artifact.submit` returns **0** in
`contracts/rpc.v14.json`, **0** in `coursebook/domain.py` and **0** in `desktop/plugin.js`, and
`docs/ASSESSMENT-BREADTH.md` §10 still opens "Nothing below is authorized now." Closing B-2 makes an
*existing* evidence class reachable — §9's paragraph is explicit that this is a reachability repair,
not a fourth construct. So B-2 is FIXED, the B-series is closed, and P1-5 stays OPEN.

### The verifying commands and what they printed

Run for this card, in this worktree, at `bbebd96`:

```text
$ for sha in b13890c d20a7a6 a729e36 b7ff866 76a59ed; do
    git merge-base --is-ancestor $sha HEAD && echo "$sha YES" || echo "$sha NO"; done
b13890c YES
d20a7a6 YES
a729e36 YES
b7ff866 YES
76a59ed YES

$ jq '.["$defs"].method.enum|length' contracts/rpc.v14.json
64
$ jq -r '.["$defs"].method.enum[]|select(.=="observation.record")' contracts/rpc.v14.json
observation.record

$ python3 ~/.hermes/profiles/quill/cache/scratch/probe_impl_methods.py
implemented_methods count: 64 unique: 64
contract method_names count: 64
observation.record present: True
missing handlers: []
extra handlers: []

$ grep -n '@_handler("observation.record")' coursebook/domain.py
3754:@_handler("observation.record")
$ grep -c 'observation.record' desktop/plugin.js
6
$ sha256sum desktop/plugin.js
a850b2bf0aee89a9d6765bbdc4218e65ca900a523c8afc8a48c4b1f2c1f076f3  desktop/plugin.js
$ grep -n 'function ParentObservation(' desktop/plugin.js
6464:function ParentObservation({ enrollmentId, objectiveId, onRecorded }) {
$ grep -c 'ParentObservation' tests/test_desktop_contracts.py
11

$ git log --oneline --diff-filter=A -- coursebook/migrations/0009_evidence_note.sql
b13890c H-53: cb.rpc v14 + cb.db v9 — freeze observation.record (contract and migration only)
$ grep -n 'def test_the_note_is_persisted_verbatim' tests/test_kernel_transitions.py
361:    def test_the_note_is_persisted_verbatim(self) -> None:

$ git show 54dd2eb:contracts/rpc.v13.json | jq '.["$defs"].method.enum|length'
63
$ git show 54dd2eb:desktop/plugin.js | grep -c 'observation.record'
0
```

Two readings matter and neither is a formality. **`implemented_methods()` is not 64 after a bare
`import coursebook.domain`:** the registry is populated by import side effects, and `pack_flow`
registers its seven `pack.*` / `course.export*` handlers only when it is imported, so the naive
probe returns 57. The probe above imports `coursebook.domain`, `coursebook.pack_flow`,
`coursebook.pronunciation` and `coursebook.syllabus` first — the same set the suite's parity test
relies on — and then the registry has 64 of 64 with no gap. **The B-2 row's open status was measured,
not assumed:** at `54dd2eb` the same `grep -c 'observation.record' desktop/plugin.js` printed `0`, and
the H-50 cell above records it.

### What this revision is, and is not

It is a status reconciliation, not a new audit. It re-ran `git merge-base --is-ancestor`, `jq` on the
frozen contract enum, the handler registry, `git log --diff-filter=A` on the migration and file-level
greps at `bbebd96`; the full suite was run, and it touched no product code, contract, schema,
migration or test. B-2 is closed because all three surfaces exist on this tree and the note
round-trips — not because the finding's prose was re-read and found agreeable. The one thing this
revision does **not** claim is a live learner session: the evidence is the contract enum, the
registry, the migration, the Desktop mount and the suite, and §10's construct gates in
`docs/ASSESSMENT-BREADTH.md` still have to be met separately.

### H-59 correction — P1-5 stays OPEN (`wt/h59-ledger-p1-5`)

The H-58 revision as first written set both P1-5 rows to "FIXED — B-1, B-2 and B-3 all merged". That
reads the finding as its defect register: closing all three B-cards would then close P1-5. It does
not. B-1 fixed a grading lane, B-2 made an existing evidence class reachable and B-3 completed the
disclosure copy; none of them added a construct. The finding's own text — "three input formats only"
— is still true at `bbebd96`, and its construct gates in `docs/ASSESSMENT-BREADTH.md` §10 remain
unauthorized. H-59 therefore restores both §4/§5 cells and both §14 table cells to **OPEN**, changes
only status wording, and adds the measured `grep -c` evidence above. No other row moved, no product
code was touched, and the B-2 closure itself stands unchanged.

## 15. Changes in the H-163 revision — every "unmerged" cell re-derived against `a674356`

Base: `master` = `a674356` (`a67435647c43c69bbfe3f03bddf5c25d7cfcf376`), 2026-11-08, 208 commits
after `54dd2eb` (the H-50 base); the UI batch union H-145…H-158 is the largest thing in that range.
This revision is a status re-derivation, not an audit. It ran ancestry, file resolution and three
targeted greps, and it changed no product code, contract or test.

### The census: where "unmerged" actually lives

`grep -n 'unmerged\|OPEN — done' docs/AUDIT-INDEX.md` does not distinguish a live status from a
quoted historical one. The matches split into four kinds, and only one kind was a live status:

| where | what it is | what H-163 did |
|---|---|---|
| §0, §1, §9 prose | the rules ("a branch-only fix stays OPEN, marked \"done, unmerged\"") and the negative provenance assertions | left unchanged; every §9 assertion re-verified below |
| **§11** (18 status cells) | the H-31b record's status column, base `f990cad` — the cells the brief quoted | annotated with the `a674356` verdict inside the cell, historical verdict kept verbatim; the header now names the base |
| §12 / §13 / §14 | "previous status" columns and verbatim quotes of the text those revisions were correcting | left as history; each section now says it is a base-stamped record and points here |
| §4 / §5 / §6 / §7 | live ledgers | two stale prose sentences corrected (§6 D-04's "H-30b, unmerged"; §7's "B-1 and B-3 are merged, B-2 is not"); base headers re-stated at `a674356`; no other cell moved |

So the live ledgers were **not** reporting merged work as unmerged — H-50/H-58/H-59 had moved
them — but §11's historical table still read as if it were current, and two live sentences were
genuinely stale. Both are fixed above; neither by touching a historical verdict.

### Every hash in the file, tested against `a674356`

145 hex tokens appear in this file. 144 resolve to commits; the one that does not is the
`desktop/plugin.js` sha256 prefix `c206e1c9…`, which is a file hash, not a commit. Of the 144,
**136 are ancestors of `a674356`** and **8 are not** — exactly the eight this index already called
branch-only or superseded:

```text
$ git rev-parse a674356
a67435647c43c69bbfe3f03bddf5c25d7cfcf376

$ for sha in 833e335 00b502f 18638be 580bbb6 9f2de53 f92d5f8 b2233ac 76a59ed b13890c \
             a729e36 47e152c 2252231 b75d601 90e1f0d be08495 097c32c a044fb4; do
    printf '%s ' "$sha"; git merge-base --is-ancestor "$sha" a674356 && echo YES || echo NO; done
833e335 YES
00b502f YES
18638be YES
580bbb6 YES
9f2de53 YES
f92d5f8 YES
b2233ac YES
76a59ed YES
b13890c YES
a729e36 YES
47e152c YES
2252231 YES
b75d601 YES
90e1f0d YES
be08495 YES
097c32c YES
a044fb4 YES

$ for sha in 111c7e9 2aca201 c9c6cec 423908f 002a82b 5ba4e4c bc508ce 2bfeb1c; do
    printf '%s ' "$sha"; git merge-base --is-ancestor "$sha" a674356 && echo YES || echo NO; done
111c7e9 NO
2aca201 NO
c9c6cec NO
423908f NO
002a82b NO
5ba4e4c NO
bc508ce NO
2bfeb1c NO
```

The eight "NO" lines are not a defect in the index; they are the branch tips it explicitly refuses
to credit: H-09's pre-v2 packet `111c7e9`, H-18's pre-recovery tips `2aca201`/`002a82b`, H-08's
pre-recovery tip `c9c6cec`, B-2's wrong sha `423908f`, H-21 original `5ba4e4c`, H-32's branch tip
`bc508ce`, and H-31b's own tip `2bfeb1c`.

### The five rows the brief spot-checked

| row | cell before this revision | verdict on `a674356` |
|---|---|---|
| round-2 P1-3 | `OPEN — done, unmerged; integration blocked, H-36` (`833e335`) | **merged** — `833e335` exit 0, carried by H-36 `b75d601`. Still no independent probe of validator identity (§5) |
| round-2 P1-4 | same | **merged** — same commit; the no-research waiver still has no independent probe (§5) |
| round-2 P2-7 | `OPEN — done, unmerged` (`2aca201`) | **FIXED product half** — `2aca201` exit 1; H-18b `580bbb6` exit 0. `2aca201` was an M4 frame refresh that later M4 regenerations superseded: content landed as `580bbb6`; branch abandoned. `2aca201` is not credited |
| round-1 P0-5 | `OPEN — done, unmerged` (`c9c6cec`) | **content landed as `18638be`; branch abandoned** — `c9c6cec` exit 1, `18638be` exit 0. At `a674356` `contracts/rpc.v16.json` declares `course.export.read` and `tests/test_course_export.py` resolves |
| round-1 P0-6 / P1-4 / P2-1 / P2-3 | `OPEN — done, unmerged` | P0-6: `00b502f` **is** an ancestor (exit 0), and H-06b `acb20f7` too. P1-4: `2aca201` is not; content landed as `580bbb6`; branch abandoned. P2-1: `111c7e9` is not; the packet that replaced it, `9f2de53` (H-40), is. P2-3: PARTIAL — the procedure lane is merged and exercised; no media scenario exists |

Files on the base, checked with `git cat-file -e a674356:<path>`: `contracts/rpc.v16.json`,
`coursebook/generation.py`, `tests/test_course_export.py`, `tests/test_locale_scaffolds.py`,
`audit/adversarial/harness-e2e/STATUS.md` — all exit 0.

### The rows that stay open, with today's evidence

**P0-7 — no live arbitrary-topic provider call in the shipped tree. OPEN.** *(Rewritten by H-166
`t_cd419083`; the previous sentence here read "no live arbitrary-topic provider call exists" and
drew the wrong conclusion from `harness-e2e/STATUS.md`. The correction record is at the end of this
section.)* The basis has two halves, and they are different strengths of evidence.

*Recorded half.* At `a674356` `audit/adversarial/harness-e2e/STATUS.md:31,33` records
`labels.provider_calls = 0`, `provider_spend_usd = 0.0` and validator identity `recorded-validator-h40`,
a **RECORDED TRANSCRIPT**. Those lines describe the **H-40 packet run** (`9f2de53`, merged via
`be08495`), not the product, and they stay true of it. The merged packet proves the pipeline on
recorded inputs; it does not prove a provider call. Being merged is not the claim.

*Live half.* A live arbitrary-topic provider call is proven separately, off this tree, by H-68
(`t_f178ba3d`, 2026-11-07 14:25). Under a real `hermes serve --isolated` on the H-63F RPC path —
`course.create` → `enrollment.create` → `jobs.create` — plan job
`job_18e2916bd1684036b1ee0df26c8e950c` reached `completed` in **165 s** (created `21:15:37Z`,
updated `21:18:22Z`) with research ledger `114a08e40b09c49a` at `status: "ok"`, **2 queries**,
**4 fetched sources**, `failures: []`, persisting plan `752bb7935176cbdc` at `draft` /
`generation_state: needs_review`, `approved_at: null`. The probe from the same run made a real
`web_search` (3 results) and `web_extract` (1 document, 4523 chars) through `ctx.dispatch_tool`
inside the serve process. It required a host-side launch-scope fix, `c02e6e0180` on
`~/.hermes/hermes-agent` branch `wt/h68-serve-secret-scope` — a **source backup: not merged, not
pushed, and contained by no remote ref in that host repo** (verified 2026-11-08: 0 of 2842
`refs/remotes` entries contain it). H-166 copied the four evidence files to
`audit/adversarial/h63-live-generation/h68-host-scope/`; they are transcripts, not a reproduction.

**It stays OPEN, for three separate reasons, and all three have to be named.** (a) The live plan
ended `draft` / `needs_review` and **no validation record was produced** — `gen_validation_records`
had no row for the run — so no arbitrary-topic plan has been approved, and none taught. (b) The
proof depends on host commit `c02e6e0180`, which is in no repository branch this project can cite:
not in this tree, not on `master`, not on any pushable line. (c) Until H-166 the evidence lived only
in kanban attachments, not in `audit/` on `master`; the copies are committed transcripts of the
card's attachments with their sha256s recorded in a README, and nothing here re-runs them.

**What the shipped tree does and does not contain.** `audit/adversarial/h63-live-generation/STATUS.md`
(base `ea5f15d`) is an in-tree record of live provider calls: three in-process runs with a live
`nous` provider and a live `web_search`/`web_extract` seam — two **rejected** by independent
cross-model validation, one cancelled before it produced an approvable artifact — plus a fourth run
over the live HTTP `cb.rpc` path that recorded research `unavailable`, no validation call and a
deterministic-rule rejection (D-H63-1, the defect H-68's host fix later unblocked). So the tree has
never lacked a record of live calls; what it has never contained is a committed record of a live
arbitrary-topic plan that passed independent validation and was approved. That is the claim P0-7
makes, and it stays unproven.

*Not claimed:* the host fix is not merged, shipped, on `master`, or on any pushed branch; P0-7 is
not closed.

**P1-5 — construct breadth is still three input formats. OPEN.** At `a674356` the three construct
methods are absent from every surface, counted on the base itself:

| file at `a674356` | `code.run` | `performance.submit` | `artifact.submit` |
|---|---|---|---|
| `contracts/rpc.v16.json` | 0 | 0 | 0 |
| `coursebook/domain.py` | 0 | 0 | 0 |
| `desktop/plugin.js` | 0 | 0 | 0 |

`contracts/rpc.v16.json` declares 68 methods; none is a construct method, and `plan.replan` is a
whole-plan regeneration, not an assessment construct. B-2's closure made an existing evidence class
reachable; it did not add a construct.

**D-04 — no attempt-driven re-plan. OPEN — narrowed.** `plan.replan` exists
(`coursebook/domain.py:1033`) and is a manual whole-plan regeneration: "the new version is approved
— a replan is never silently effective." No handler chooses a remediation, an example or a next
objective from an attempt. `docs/COURSE-BLUEPRINT.md` §9 ("Adaptation, honestly") still says the
current claim is a state transition, and its exclusions list still names "dynamic re-planning from
an attempt, a learner model, style inference or any claim of adaptive teaching". H-30b is merged
(`f92d5f8` via `90e1f0d`) but measured shape, grading and the approval gate — not adaptation — so
this finding has no re-audit either.

### What this revision is, and is not

It is a status re-derivation at `a674356`, run on `wt/h163-audit-index`. It is not a new audit: it
ran no probe, no gate module and no live call; every status it asserts is either an ancestry exit
code, a file that resolves on the base, or a `grep -c` quoted above. It did not change a status
because a card is `done`, it did not rewrite the historical verdicts in §11–§14, and it touched
nothing that `scripts/check-docs-truth.py` asserts — that gate passes on this tree.

### H-166 correction — P0-7's basis, not its verdict (`wt/h166-p0-7-basis`, docs only)

The H-163 revision above concluded P0-7 from `harness-e2e/STATUS.md` alone and wrote "no live
arbitrary-topic provider call exists". That was a present-tense claim about the product drawn from a
file that describes one **recorded** packet run. H-166 changes the basis and leaves the verdict
alone: P0-7 is still OPEN, as of the same three reasons stated in "The rows that stay open".

Wording moved, exactly:

| where | before | after |
|---|---|---|
| §4 ledger cell, status column | `OPEN — packet merged, but no live provider call exists` | `OPEN — the merged packet is recorded-input only (`provider_calls = 0`); a live RPC-path call is proven separately by H-68, but with no validation record and no approved plan` |
| §4 ledger, evidence column | ended at "…`provider_calls = 0`" | adds the H-40-scoping sentence, the H-68 run (`job_18e2916b…`, research `ok`, 2 queries, 4 sources, 165 s, plan `752bb7935176cbdc` at `draft`/`needs_review`), host commit `c02e6e0180` as a **source backup, not on any pushed line**, and the copied evidence directory |
| §4 ledger, card-state column | `H-09 done, branch abandoned; H-40 merged` | `H-09 done, branch abandoned; H-40 merged; H-68 done (host fix source-backup only)` |
| §11 H-31b record, round-1 P0-7 cell | `… and no live provider call exists; the merged packet …` | `… and no live provider call is recorded in the tree (H-68's live RPC-path run is off-tree — §4, §15); the merged packet …` — historical verdict otherwise untouched |
| §15, this section | `**P0-7 — no live arbitrary-topic provider call. OPEN.** … contains no line naming a live provider.` | the two-half basis, the three reasons it stays OPEN, and what the shipped tree does and does not contain |

What was verified, and how (this revision ran no probe and no live call):

```text
$ date -u -d "2026-11-07T21:18:22Z" +%s   # 1794086302  (plan-job.json updated_at)
$ date -u -d "2026-11-07T21:15:37Z" +%s   # 1794086137  (plan-job.json created_at)
$ echo $((1794086302 - 1794086137))       # 165
$ git merge-base --is-ancestor 9f2de53 HEAD && echo yes   # yes
$ git cat-file -t 9f2de53                  # commit
$ git -C ~/.hermes/hermes-agent for-each-ref --contains c02e6e0180 --format='%(refname)' refs/remotes | wc -l   # 0
$ git -C ~/.hermes/hermes-agent log -1 --format='%h %ad %s' --date=iso c02e6e0180
  c02e6e0180 2026-11-07 14:24:24 -0700 fix(gateway): serve-owned plugin workers resolve the launch profile's secrets (H-68)
$ grep -n "provider_calls\|provider_spend\|recorded-validator" audit/adversarial/harness-e2e/STATUS.md
  31:| validator identity | **RECORDED TRANSCRIPT**, a distinct recorded identity (`recorded-validator-h40`) | …
  33:| provider calls / spend | **none** | `labels.provider_calls = 0`, `provider_spend_usd = 0.0` |
$ sha256sum audit/adversarial/h63-live-generation/h68-host-scope/*   # equal to the four t_f178ba3d attachments
```

The research and plan numbers come from `research-run.json` and `plan-job.json` copied into
`audit/adversarial/h63-live-generation/h68-host-scope/`; the copy's `README.md` records their
sha256s, states that they are transcripts rather than a reproduction, and notes that
`EVIDENCE.md`'s `audit/h68/create-h68.json` and `validation-records.json` were never attached to the
card — which is itself the "no validation record" evidence, not a gap in the copy.

Not done here: no probe was run, no host source was copied, `audit/adversarial/harness-e2e/STATUS.md`
was not edited (its `provider_calls = 0` line describes the H-40 packet and stays true), the host
repository was not pushed and no gateway was restarted, and no other row was re-derived. The §13 and
§14 tables still quote "packet merged, but no live provider call exists" as the **status at those
base-stamped revisions**; that is history, and those cells were not moved.

## 16. Changes in the H-209 revision — re-derived against the settled union `4dacf07`

Base: `master` = `4dacf07` (`4dacf07299d056227fea4ca8967e861411abf0e4`), 2026-11-08 20:39 MST. This is
the commit the product is now settled on, and every live cell above was read at it. The last
three index revisions pointed at bases nobody ships any more: §13 at `54dd2eb`, §14 at `bbebd96`,
§15 at `a674356`. `a674356` is an ancestor of `4dacf07`, so every verdict that was true there is
still true here unless a row moved, and §11–§15 keep their base-stamped wording verbatim.

The union, named by the commits rather than by a branch:

- `d9b1f3c` — "H-208: serve the recorded 81-char answer to the pass that owns its rejection" —
  carries H-183 `0b01f33` (merge `6601734`), H-189 `82200c2` (merge `b8fa387`), H-206
  `5d11721`/`ce363ce` (merge `0c717b4`), H-192b `f0be341`, H-192c `8204311` (merge `0d91a74`) and
  its fixture-alignment repair `b304e16` (merge `91d7a58`), H-199 `9596045`, H-194e `7e15963` and
  H-182/D1-D3 `502051d` (merge `2cd0331`); `d176efb` is the integration merge that brought the
  H-183/H-189/H-192c/H-199 line onto H-194e.
- `a81567b` — merge of H-182/D8 `d3f9f8d`.
- `d626c16` — merge of H-182/D6 `39f1396`.
- `4dacf07` — re-pin of the M4 visual audit to the settled module.

This revision is a status re-derivation, not an audit. It ran ancestry, file resolution,
`jq`/`grep -c` against the base and the docs-truth gate; it did not run a product gate, a live call,
a browser render or a re-audit. It changed no product code, contract, test, `desktop/plugin.js` or
`docs/release-evidence.json` (H-203 `t_ec805fc0` owns that file and is measuring this same tree).

### The desktop module and the M4 pin at `4dacf07`

`desktop/plugin.js` at `4dacf07` is sha256
`a11a769f6131b365555b9a4efae9cf942baa843f78bcdd0237f0170d6a0aba61`.
`audit/visual/m4-visual/audit.json` at that commit pins the same module: **15 claims (C-01…C-15), 15
PASS / 0 not PASS, 62 frames**, `plugin_sha256 = a11a769f…`. The re-pin commit `4dacf07` changed only
`generated_at`, `plugin_sha256` and `branch` in that file, and its own commit message records that the
62 screenshots were byte-identical in the repro check (`python3 scripts/m4v-repro-check.py`). **This
card did not re-run the render or the repro check**; it verified the pin against the file and read the
claim counts out of `audit.json` and the re-pin diff.

The module settled at the D8 merge, not at the union: `d9b1f3c` carries `desktop/plugin.js`
`2790d1c0…`, while `a81567b`, `d626c16` and `4dacf07` all carry `a11a769f…`. (H-182/D8's own commit
`d3f9f8d` carries `1e5289c2…`; the merge resolved the module to `a11a769f…`.) Two module hashes named
earlier in this file are therefore history, not current pins: `179db275…` on `eed7dc7` and `2790d1c0…`
on the union are the module of their own commits.

One live inconsistency is recorded rather than hidden: `docs/M4-VISUAL-MEDIA-AUDIT.md` at `4dacf07`
still states the previous pin `179db275…` on `eed7dc7`, because that document is re-derived by H-203
in the same window this card ran. Do not read the M4 document as the `4dacf07` pin; read
`audit/visual/m4-visual/audit.json`. This card deliberately edited neither document nor
`docs/release-evidence.json`.

### Every hash in the file, tested against `4dacf07`

The file now contains 193 distinct hex tokens of 7–40 characters. 171 resolve to commits that are
ancestors of `4dacf07`, 11 resolve to commits that are **not**, and 11 are not commit ids in this
repository. Eight of the eleven non-ancestors are exactly the branch tips and superseded shas this
index already refuses to credit; the other three are evidence-branch tips this revision names for the
first time and also refuses to credit. No previously-unmerged sha became an ancestor.

```text
$ git rev-parse 4dacf07
4dacf07299d056227fea4ca8967e861411abf0e4

$ for sha in 111c7e9 2aca201 c9c6cec 423908f 002a82b 5ba4e4c bc508ce 2bfeb1c \
             aaaff15 c08a90b e313d37; do
    printf '%s ' "$sha"; git merge-base --is-ancestor "$sha" 4dacf07 && echo YES || echo NO; done
111c7e9 NO
2aca201 NO
c9c6cec NO
423908f NO
002a82b NO
5ba4e4c NO
bc508ce NO
2bfeb1c NO
aaaff15 NO
c08a90b NO
e313d37 NO
```

`aaaff15` is H-194e's branch tip, whose content was re-landed as `7e15963`; `c08a90b` is the H-194e
live re-probe branch and `e313d37` is the H-188 live-media branch. All three are evidence about a
commit this index names, none is a merge, and none is credited as one. The non-commit tokens are the
`desktop/plugin.js` sha256 prefixes (`c206e1c9…`, `179db275…`, `1e5289c2…`, `2790d1c0…`, `47e04fd5…`,
`a11a769f…`), the H-68 research ledger id `114a08e40b09c49a`, the plan id `752bb7935176cbdc`, the two
epoch stamps `1794086137`/`1794086302`, and the host-repo commit `c02e6e0180`, which is not a commit
in this repository at all.

### Fixes that landed between `a674356` and `4dacf07`

Every row below names a content commit **and** says whether it is an ancestor of `4dacf07`. The
fifth column says what the base actually carries; the last says whether a probe exists at the
settled module. None of these rows existed in this index before this pass — the index stopped at
H-166 — so they are entered here, not flipped from an older cell.

| row | fix commit — ancestor of `4dacf07`? | what `4dacf07` carries | status | re-audit at the settled tree |
|---|---|---|---|---|
| H-183 learner truth sweep — no job/queue/id/typed code in a learner sentence; no dead learner controls | `0b01f33` via merge `6601734`, in `d9b1f3c` — **yes** | `tests/test_desktop_h183_copy_inventory.py` renders the shipped components and scans visible text; `audit/visual/h183-copy/` frames at the card's own pin | **FIXED — implementation merged** | none on `4dacf07`; the card's frames are at its own pin, not at `a11a769f…` |
| H-189 living home — route settle, authored node list, one notes line | `82200c2` via merge `b8fa387`, in `d9b1f3c` — **yes** | `tests/test_desktop_h189_living_home.py`; `audit/visual/h189-living-home/` | **FIXED — implementation merged** | none on `4dacf07`; same pin limit |
| H-206 hint control gets a used state; one completion-count copy | content `ce363ce`, merge `5d11721` via `0c717b4`, in `d9b1f3c` — **yes** | `scripts/h206-recheck.mjs`, `audit/visual/h206-recheck/sequence.json` | **FIXED — implementation merged** | the recheck sequence pins module `47e04fd5…`, **not** `a11a769f…`; no capture at the settled module |
| H-192b — parse each validator answer against its own pass schema; label shape/content rejections `VALIDATION_FAILED`; record the repaired pass | `f0be341` (with `0bd5cf2`, `c58c05a`, `e9825a4`, `e22592a`), carried into the union `d9b1f3c` — **yes** | `tests/test_validation_shape_repair.py`; `audit/adversarial/live-generation-2026-11-08-h192/STATUS-h192b.md` | **PARTIAL — the card's own status.** Defects 2 and 3 are fixed and proven; defect 1 (the criteria pass's total output) was carried to H-192c and is bounded there | the card's live run is recorded in `STATUS-h192b.md` (see P0-7 below); no re-run on `4dacf07` |
| H-192c — bound the validator's own output on the nous route | content `8204311`, fixture alignment `b304e16`, in `d9b1f3c` — **yes** | `tests/test_h192c_validator_output_bound.py`; `audit/adversarial/live-generation-2026-11-08-h192/STATUS-h192c.md` and `evidence/h192c-single.json` record the live before/after token counts | **FIXED — implementation merged, live numbers recorded in-tree** | the recorded live proof is at `8204311`/`c58c05a`; no re-run on `4dacf07` |
| H-199 — enforce the lesson provider deadline on the call path, with a wait heartbeat | `9596045` via merge `1e3b59a`/`0d91a74`, in `d9b1f3c` — **yes** | `coursebook/deadline.py`; `tests/test_h199_lesson_deadline.py` | **FIXED — implementation merged** | none; the deadline behaviour has not been re-measured live on the settled tree |
| H-194e — a page revision keeps its check; one gate answers for the review surface and the export | content `7e15963` — **yes**; branch tip `aaaff15` — **no** | `tests/test_h194_fine_tune.py`; `audit/h194/live/MANIFEST.md` | **FIXED — content re-landed at `7e15963`; ancestry of `aaaff15` is a false negative** (its diff against `7e15963` is additions only) | live re-probe on base `7e15963` is recorded at `c08a90b` on `wt/h194e-live` (**not merged**): title-only revision → check kept → approve → export with matching content hash |
| H-182/D1-D3 — a refused plan is repairable, a retry is a real attempt, approval fails closed | `502051d` (content `9c712cd`, `d5b8cf5`, `4633bd3`) via merge `2cd0331` — **yes** | `tests/test_h182_plan_repair.py`; `audit/visual/h182-repair/EVIDENCE.md` | **FIXED — implementation merged** | **live re-walk required** — H-182/D1-D3 live `t_31571135` (sentinel). The card's own walk was blocked on provider latency and no plan job completed, so it is a repair path pinned by tests, not a walked loop. A green test file is not that walk |
| H-182/D8 — the three residual learner-surface copy strings | `d3f9f8d` via merge `a81567b` — **yes** | `tests/test_desktop_h183_copy_inventory.py` (D8 extension); `docs/H182-D8-INTEGRATION-DECISION.md`; `scripts/probe_d8_estimate_first_arrival.py` | **FIXED — implementation merged; this is the commit whose module the M4 pin names** | no re-walk at `a11a769f…` |
| H-182/D6 — the job reaper reads the RPC's store scope and never spams before first migration | `39f1396` via merge `d626c16` — **yes** | `tests/test_h182_reaper_scope.py` (real SQLite store, real reaper thread); `tests/test_h182_lesson_check_unbound.py`; `scripts/h182d6_seed_expired_job.py` | **FIXED — implementation merged** | none |

Three things the table deliberately does not say:

- It does not say any of these is independently re-audited on `4dacf07`. A merge is not a re-audit,
  and a test file added by the card that also wrote the fix is that card's own evidence, not an
  independent probe.
- It does not credit `aaaff15` for H-194e, and it does not credit `d3f9f8d`/`39f1396` as merges:
  they are content commits, carried by `a81567b`/`d626c16`.
- It does not treat the H-192b card as a pass. Its own status line is **PARTIAL** and its summary
  says "do not treat this card as acceptance".

### The rows that stay open at `4dacf07`

**P0-7 — no live arbitrary-topic generation with a validation record and an approved plan. OPEN,
unchanged.** The 165 s H-68 run recorded in §4 is still the only RPC-path live call in this file, and
it still produced no validation record and no approval. There is newer live material in the tree,
and it is recorded here because a reader will find it: `STATUS-h192b.md` at `f0be341` (an ancestor of
`4dacf07`) records a **live** second measurement — author `nous/deepseek-v4.1-flash-1017`, validator
`nous/z-ai/glm-5.3-flash` — in which the **single** scope reached `plan.approve` **ok** with
`independently_validated` provenance (validate 43.8 s/3 004 tokens + 344.8 s/9 881 tokens; unit
validate 320.6 s/23 096 + 214.5 s/16 051), the **short** scope also approved its plan, and the
**full** scope failed with `HOST_UNAVAILABLE` at the validation deadline and was refused
`plan_empty`. That is real live generation with a validation record and an approval, and it still
does not close P0-7: the card declares the result **PARTIAL**, no full-scope plan exists, the one
authored single-scope lesson was parked `needs_review` by the text-completeness gate so **no
`lesson.page` was served**, and nothing in that run was re-played on `4dacf07`. A three-scope live
re-walk on the settled tree is the missing probe. No card for that re-walk was open on the board
when this pass ran; the closest are H-182/D1-D3 live `t_31571135` and H-192 acceptance
`t_cb4641bf`, whose own record (`audit/adversarial/live-generation-2026-11-08-h192/STATUS.md` at
`4dacf07`) is **FAIL 0/3 on base `127cce1`** and is not superseded by anything merged.

**P1-5 — construct breadth is still three input formats. OPEN, unchanged.** At `4dacf07` the three
construct methods remain absent from every surface, counted on the base itself:

| file at `4dacf07` | `code.run` | `performance.submit` | `artifact.submit` |
|---|---|---|---|
| `contracts/rpc.v20.json` | 0 | 0 | 0 |
| `coursebook/domain.py` | 0 | 0 | 0 |
| `desktop/plugin.js` | 0 | 0 | 0 |

`contracts/rpc.v20.json` declares 73 methods; none is a construct method. The version/declared-method
numbers moved from §15's v16/68 because H-194b/c took the contract to v20; the finding did not move.
B-2's closure made an existing evidence class reachable; it added no construct.

**D-04 — no attempt-driven re-plan. OPEN — narrowed, unchanged.** `@_handler("plan.replan")` is at
`coursebook/domain.py:1123` and is a manual whole-plan regeneration; no handler chooses a remediation,
an example or a next objective from an attempt. `docs/COURSE-BLUEPRINT.md` §9 still states the
state-transition claim and its exclusions still name dynamic re-plan, a learner model, style inference
and any claim of adaptive teaching. Nothing merged since `a674356` changes that, so no re-audit card
exists for it and none is implied.

Two partials that also stay where they are, for completeness: **round-1 P2-3 / G-04's media half**
remains unproven in the shipped tree. H-188 (`t_740005f6`) did capture a real live image and audio
artifact, but its evidence is at `e313d37` on `wt/h188-media-proof` — **not merged, not pushed** — and
the lesson text beside it is script-authored `model_assessed` with a null validation id, so it is a
live media tool proof, not a shipped media lane. And **§6 D-06** stays FIXED on its own evidence;
nothing here re-opened it.

### What this revision is, and is not

It is a status re-derivation at `4dacf07`, run on `wt/h209-audit-index`. It is not a new audit: it
ran no probe, no gate module, no live call and no browser render; every status it asserts is either an
ancestry exit code, a file that resolves on the base, a count read from the base's own files, or a
recorded number quoted from a file that names its own commit. It did not flip a finding to FIXED on
the strength of a merge alone, it did not rewrite any historical verdict in §11–§15, and it touched
nothing that `scripts/check-docs-truth.py` asserts.

**The release gate reads this file.** After this revision the rows that can support a release claim
are those naming an ancestor of `4dacf07`, and every ledger row that names one also says whether an
independent re-audit exists — which, for the ten fixes above, is mostly *no, and here is the card that
owes it*.

### The verifying commands and what they printed

Run for this card, in this worktree, at `4dacf07`:

```text
$ git rev-parse HEAD
4dacf07299d056227fea4ca8967e861411abf0e4
$ git rev-parse master
4dacf07299d056227fea4ca8967e861411abf0e4

$ for s in d9b1f3c 5d11721 0c717b4 f0be341 8204311 9596045 7e15963 502051d d3f9f8d 39f1396; do
    printf '%-9s ' "$s"; git merge-base --is-ancestor "$s" 4dacf07 && echo ANCESTOR || echo NOT; done
d9b1f3c   ANCESTOR
5d11721   ANCESTOR
0c717b4   ANCESTOR
f0be341   ANCESTOR
8204311   ANCESTOR
9596045   ANCESTOR
7e15963   ANCESTOR
502051d   ANCESTOR
d3f9f8d   ANCESTOR
39f1396   ANCESTOR

$ git show 4dacf07:desktop/plugin.js | sha256sum
a11a769f6131b365555b9a4efae9cf942baa843f78bcdd0237f0170d6a0aba61  -
$ jq -r '.summary.plugin_sha256' audit/visual/m4-visual/audit.json
a11a769f6131b365555b9a4efae9cf942baa843f78bcdd0237f0170d6a0aba61
$ jq -r '[.claims[].verdict]|group_by(.)|map({v:.[0],n:length})' audit/visual/m4-visual/audit.json
[{"v":"PASS","n":15}]
$ jq -r '.frames|length' audit/visual/m4-visual/audit.json
62

$ jq -r '.["$defs"].method.enum|length' contracts/rpc.v20.json
73
$ for m in code.run performance.submit artifact.submit; do
    printf '%s contract=' "$m"; grep -c "$m" contracts/rpc.v20.json
    printf '%s domain='   "$m"; grep -c "$m" coursebook/domain.py
    printf '%s plugin='   "$m"; grep -c "$m" desktop/plugin.js
  done
code.run contract=0 … domain=0 … plugin=0
performance.submit contract=0 … domain=0 … plugin=0
artifact.submit contract=0 … domain=0 … plugin=0
$ grep -n '@_handler("plan.replan")' coursebook/domain.py
1123:@_handler("plan.replan")

$ python3 scripts/check-docs-truth.py --skip-tests
… docs-truth: PASS
```

The full suite was run for this card on the same tree; it reads the docs-truth modules:

```text
$ python3 -m unittest discover -s tests -t .
Ran 2708 tests in 460.203s

OK
```

### The cells this revision changed, old → new

| where | before | after |
|---|---|---|
| header, current base | the H-163 paragraph ended the base history at `a674356` | a new paragraph names `4dacf07`, its module sha256 and §16 |
| §0, two rules | ancestor test against `a674356` (H-163, §15) | ancestor test against `4dacf07` (H-209, §16), with the `a674356` run kept as history |
| §4, §5, §6, §7, §8 headers and column heads | "ancestor / merged state at `a674356`" | "ancestor / merged state at `4dacf07`", re-run and unchanged |
| §4 P0-7 evidence cell | ended "nothing was approved or taught (§15)" | same, plus a pointer to §16's newer live material and why it does not close the row |
| §6 D-04 note | "Re-derived OPEN at `a674356` (§15)" | "… and again at `4dacf07` (§16)" |
| §10 | no bullet about the `a674356`→`4dacf07` fixes | a bullet saying the merged fixes are not re-audits, pointing at §16 |
| this section | did not exist | the census, the ten-row table, the open rows, the module pin and the commands above |

No status cell in §4–§7 moved from FIXED to OPEN or the reverse; the ten fixes in this section were
never rows in this index, so there was no earlier cell to flip. §11–§15 are left exactly as their
own revisions wrote them.

