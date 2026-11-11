# HARNESS-STATUS — what is build-complete, what is proven, what is fixture-only

Owner: quill (H-11, board card `t_6f41e0b0`). Branch `wt/harness-docs`.

**Current `master` (measured 2026-11-10, supervisor CP-052 merge `b1913af7`):**
`b1913af77c3f50319af1dbd85555f9adc4271a20`. On it `cb.rpc` is v26
(`coursebook/contracts.py`) with 93 declared methods and 93 handlers, `cb.db` is v14
(`contracts/db.v14.json`, `DB_SCHEMA_VERSION = 14` in `coursebook/db.py`, migrations
`0001`-`0014`), `desktop/plugin.js` is sha256
`4087908c1881df93bf0f7e71bbac65c2511aee3f115271f6b3f846091c9d03b7` (the module this tree ships; the record's
M4 pin is the older `b9f4a19` `cd862140` measurement, whose numbers the head audit reproduces), and the suite is
`Ran 3523 tests in 951.634s … OK (skipped=11)`.

The suite and contract values are the record in `docs/release-evidence.json`, measured at that
commit (the `tests`, `rpc` and `db` blocks each name `b1913af7`). The record's top-level
`measured_commit`, module pin and M4 block remain the `b9f4a19` release-tree
measurement (`cb.rpc` v20, `cb.db` v13, module `cd862140…`, suite `Ran 2747 tests … OK (skipped=1)`).

**Historical snapshot label — not current.** The row-by-row body (§1-§7) is a snapshot written
against `master` at `498b1daeae946d988072bb7852c07b4cfbddeb8e` (2026-11-07 01:54 -0700), where the
suite was `Ran 1177 tests … OK` and `desktop/plugin.js` was sha256
`5beed34797ef18fa328c748e6d82fcbd0fef84997e9cc640fab46363b2879b25` (last changed by H-02,
`5b7423374a5b8d10a2fe94ce520a2613b5c8f02e`). Every "on `master`" / "not on `master`" statement in
those rows describes `498b1da` unless §5.1 or §8 re-derives it. Do not quote a row as current
without re-running `git merge-base --is-ancestor <commit> origin/master`; §8 records the H-171
re-derivation for the harness cards.

This document exists because the harness slice produced a great deal of evidence, and most of it
lives on **unmerged branches** or in commits that reached `master` only through successor merges.
Prose that says "the harness works" without saying which commit it works on, and whether a model or
a recording produced the output, is the failure this pass repairs. Nothing here is new capability;
every row points at a file or a command.

> **Superseded evidence (H-102, 2026-11-07):** §4 and §5 quote `SUMMARY total=22 fail=0 pass=22`
> from their own commits. That is **not** the current matrix. `S08` and `S09` were written against
> the pre-skill hook shape and the current tree adds `S17`; the live expected shape is **23
> scenarios, `fail=0`, `S13` still `BLOCKED`**, with `S08` asserting reference *values* are absent
> (not the word "reference") and `S09` allowing a skill instruction but no grading continuation.
> Re-derived command and details are in §7.

## 1. Status table

Five classes that are routinely confused. They are not a ladder — a later class does not imply an
earlier one, and an earlier one does not imply a later one.

Vocabulary, used strictly below:

- **MERGED** — the code is an ancestor of `master` and is covered by the suite.
- **BRANCH** — the code or evidence exists only on a named branch; it is not on `master`.
- **FIXTURE** — deterministic fixture, stub, fake model or **recorded transcript**. It proves the
  pipeline's behaviour around the model, not the model's output.
- **LIVE** — a command or capture taken against a running process on a named commit.
- **UNPROVEN** — no evidence exists and none is claimed.

| # | Claim class | Verdict | What that means here | Evidence | What it does not mean |
|---|---|---|---|---|---|
| 1 | **Harness code complete** | **PARTIAL** — pipeline and the harness cards are MERGED on `38ecc22`; the P0-7 live claim is not | On `master` `38ecc22`: cb.rpc v17 with `level`/`subject_domain`/`scope` on `course.create` (H-01), learner create → plan job → approve → lessons (H-02, `5b74233`), runtime threading (H-13), bounded research depth (H-04), plan-time `media_need` (H-05), procedure authoring (H-06 `00b502f`), parent brief fidelity (H-07), fail-closed plan approval with a durable validation binding (H-12), validator independence (H-15 `833e335`), plan-sized cost ceilings (H-17), the rubric-extensibility decision (H-24 `491443a`, docs/registry — not a new runtime seam), authored export through its successor commit (H-08b `18638be`: `course.export.read`/`course.export` in cb.rpc v17, `coursebook/pack_flow.py:1618,1649`), and locale scaffolds through their successor commit (H-18b `9e6c5e4`: `coursebook/localization.py:139`). Not on `master`: the H-08 original `c9c6cec`, the H-18 original `2aca201` (an M4 frame refresh, not the locale code), and the H-09 evidence packet `4dd0f18`/`111c7e9` (superseded by the merged H-40 packet `9f2de53`). `git merge-base --is-ancestor` for `00b502f`, `833e335`, `491443a`, `18638be`, `9e6c5e4` returns `0`; for `c9c6cec`, `2aca201`, `111c7e9` it returns `1` (§8). | `coursebook/contracts.py:51`; `contracts/rpc.v17.json`; `coursebook/research.py:67-97`; `coursebook/generation.py:157-174`; `coursebook/localization.py:139`; `coursebook/pack_flow.py:1618-1758`; commit graph as named. Merge check: `git merge-base --is-ancestor <commit> origin/master; echo $?` | Does not mean the review's P0 list is closed. P0-5 (export) and P0-6 (procedure) now have code on `master`, but P0-7 (arbitrary-topic generation) is proved only by a recorded-transcript packet plus one off-tree live run with no validation record (`docs/AUDIT-INDEX.md` §4, §15). The P0-2 scope cell is not a live contradiction: §2 separates the v1 fixture band from the enforced v2 band. |
| 2 | **Authored course generated end to end** | **BRANCH + FIXTURE** — 3/3 scenarios PASS, recorded transcripts | Three non-Japanese goals (`single`/`one_off` bicycle repair, `short`/`committed` music analysis, `full`/`committed` soldering) each ran `course.create` → plan job → kernel-digest approval → lessons job → `lesson.page` → `course.export.read` → `course.export` against a throwaway `HERMES_HOME` on branch `wt/harness-e2e-proof`. The model and the research pages are **recorded transcripts**: 0 provider calls, $0 spend. | `docs/HARNESS-E2E.md` and `audit/adversarial/harness-e2e/STATUS.md` at `111c7e9` (content commit `4dd0f18`); `audit/adversarial/harness-e2e/evidence/{bicycle_single,music_short,soldering_full}.json`; `tests/test_harness_e2e.py` (9 tests). Reach them with `git show 111c7e9:docs/HARNESS-E2E.md`. | Does not mean a live model produced those lessons, that the web was searched live, that a check attempt was submitted on a generated objective, or that the branch is merged. The `single` scenario has 4 objectives because its plan is a **v1** fixture; the enforced v2 band is 1 unit / 1 objective (§2). |
| 3 | **Live UI proof** (the harness loop driven in a real Desktop window) | **UNPROVEN** | The UI half of H-02 exists on `master` but is covered by jsdom/unit tests (`tests/test_desktop_create_flow.py`, `tests/test_learner_plan_flow.py`), not by a mounted Desktop window reaching a real backend on this tree. The M4 frames are a headless render against a stub transport. | `tests/test_desktop_create_flow.py` at `master`; the M4 frames and their stated limits in `docs/M4-VISUAL-MEDIA-AUDIT.md` and `docs/DEMO.md` §"Product-line measurement". | Does not mean "attempted and failed" — it means nobody has mounted the new create flow in a live window and driven it. Recording is still gated (§3). |
| 4 | **Prepared-pack demo** | **FIXTURE**, gate NOT MET | `bundled/packs/japanese-affection-context-l0` imported by `scripts/seed-demo-course.py`. It proves a governed loop over **one** prepared pack. No video exists and the demo gate is NOT MET. | `docs/DEMO.md` (gate status, per-shot verdicts, `audit/demo-gate-5b0f124/`); `docs/REVIEW_CB017-demo-gate.md`. | Not proof of arbitrary-topic generation. This pack is a fixture in every claim in this repository; H-09's own packet is on a branch (`111c7e9`, superseded by the merged H-40 packet `9f2de53`), and the live half is H-68's off-tree run with no validation record. |
| 5 | **Product 1.0** | **UNTAGGED / UNPROVEN** | No release tag, no merged catalog entry (a draft pull request is open and unmerged), no publication. MIT license since 2026-11-10. `docs/SUBMISSION.md` §0 remains closed. | `docs/SUBMISSION.md` §0 and §1 gate table; `README.md` §Status. | Nothing above moves this row. Evidence on branches is not a release candidate, and a green suite is not a gate (§5). |

## 2. Claim-by-claim corrections (procedure / media / language / export / scope)

Each row is the claim a reader should take away, held to H-06/H-08/H-09 evidence. Where a doc
disagreed with the code, the disagreement is recorded rather than resolved by silence.

| Claim | Correct statement on this tree (rows re-derived by H-171 at `38ecc22`; research depth updated by H-175 once H-168 landed; the `498b1da` snapshot is named where it differs) | Correct statement including branches | Evidence |
|---|---|---|---|
| **Procedure lens authoring** | The renderer, contract and validator are real, and the authoring path is on `master`: `LESSON_SCHEMA` accepts the typed `procedure` object, `lesson-prompt.v9` requests it for a technical procedure, and `_build_learner_page` projects it as segment references (H-06 `00b502f`, merged — §8). Before the H-47 docs merge the README said "no authoring path"; that was true of `498b1da`, not of `38ecc22`. | No live course has been authored through the procedure path; the evidence is `tests/test_procedure_authoring.py` driving the real lesson job with a **fake model**. | `docs/M4-PROCEDURE-LAYOUT.md`; `coursebook/generation.py` `LESSON_SCHEMA`; `tests/test_procedure_authoring.py`; ancestry `00b502f` → `0` |
| **Media** | Plan-time media is real on `master`: every plan section declares a typed `media_need` and the capability policy adopts it (H-05). Host image/TTS generation is real (M0) but no live lesson-pane generation has run on this tree. | H-09 asserts `every_section_declares_media_need` for all three scenarios and a technical procedure with schematic rows — over recorded transcripts. | `docs/CAPABILITY-POLICY.md`, `docs/GENERATION.md`; `audit/adversarial/harness-e2e/evidence/*.json` at `111c7e9` |
| **Language** | The locale-aware scaffold vocabulary is on `master` through H-18b (`9e6c5e4`): `LESSON_SCHEMA.check.scaffolds` accepts either the legacy `{romaji, furigana, english_meaning}` object (so pages authored before the change read unchanged) or an array of only the kinds the locale/level mandates (`[{kind, script?, gloss?, direction?}]`, `coursebook/localization.py:139`). A French course is not forced to declare a Japanese scaffold. | The H-18 tip `2aca201` is an M4 frame refresh and is **unmerged**; the locale code landed via `9e6c5e4`, not through it. A language goal's audio/pronunciation path is still **not covered** by H-09 — none of its three goals is a language goal. | `coursebook/generation.py` `LESSON_SCHEMA`; `coursebook/localization.py:139-160`; `docs/HARNESS-E2E.md` §Findings F1; ancestry `2aca201` → `1`, `9e6c5e4` → `0` |
| **Export** | The general authored export is on `master` through H-08b (`18638be`, cb.rpc v13; the method is in v17): `course.export.read` / `course.export` are declared in `contracts/rpc.v17.json` and handled in `coursebook/pack_flow.py:1618,1649`, behind the four-step gate (not pack-backed, plan approved, every page `validated`, stored final-approval hash unchanged). `pack.export` still refuses a course with no `pack_id` (`course_not_pack_backed`). | The H-08 tip `c9c6cec` is **unmerged**; `18638be` is the successor that landed. No live model has produced an exported course through this path. | `contracts/rpc.v17.json`; `coursebook/pack_flow.py:1618-1758`; `tests/test_course_export.py`; H-09's branch packet asserts `export_ready` and `export_produced_an_archive` per scenario (recorded transcripts) |
| **Plan scope** | **Not ambiguous on the current contract.** `SCOPE_EXPECTATIONS` (`coursebook/generation.py:202-235`) carries two bands per scope, each named for the contract it serves: `v1_objectives` is the pre-blueprint v1 range (single `(4, 5)`), while `blueprint_objectives` / `blueprint_units` are the v2 band (single `(1, 1)`), and only those are enforced — by the v2 plan rule at `generation.py:2790-2791`, the unit stage at `3746-3747`, and the v2 prompt at `4755-4756`. `docs/COURSE-BLUEPRINT.md:222` states single = 1 unit / 1 objective, and `tests/test_harness_e2e.py:183` asserts `(1, 1)`. | The H-09 `bicycle_single` fixture plan has 4 objectives because it is a **v1** fixture (`plan_one_off.json`); 4 is the v1 band, not a contradiction with the enforced v2 contract. Under the v2 blueprint a one-off course is exactly one unit and one objective. | `coursebook/generation.py:202-235,2790-2791,3746-3747,4755-4756`; `docs/COURSE-BLUEPRINT.md:222`; `tests/test_harness_e2e.py:183`; `tests/test_scope_copy.py` asserts the two bands are kept distinct |
| **Research depth** | Real on `master`: `survey`/`working`/`deep` are the only accepted values, aliases map `overview`→`survey` and `thorough`→`deep`, and the budget scales with scope. Since H-168 (`3d378a1`) the scope is also a floor: `single`/`short` run at least `working` and `full` at least `deep`, so a `full` course derives 10 queries whatever depth the dial declares; an explicit `budget` is still the hard ceiling, and `effective_depth` is recorded beside, never written into, the four dials. No live web was used by H-09 — its pages are a recording. | H-175 re-recorded the H-40 packet's `soldering_full` research against that floor: six really fetched pages (ST, Purdue, CU Boulder, iFixit ×2, Instructables), replayed offline at `provider_calls: 0`. The recording is a fixed result set, not authored page bytes, and a fetch for an unrecorded URL raises rather than inventing a page. | `coursebook/research.py` (`SCOPE_MIN_DEPTH`, `effective_depth`); `docs/GENERATION.md`; `audit/adversarial/harness-e2e/STATUS.md` §"H-175" |
| **Plan approval** | Fail-closed on `master` since H-12 (`plan_approve`, `coursebook/domain.py:678`): empty plans refused, generated plans need a durable pass bound to the exact content hash, refusals write no transition or revision. | — | `coursebook/domain.py:678-747`; `tests/test_adversarial_round2.py` asserts the refusal |

## 3. The operator-only gate, and the exact builds

**Operator-only, not an agent action:** `t_6a32ffe9` (assignee sentinel, status `blocked`). The host
runs one gateway, owned by profile `default`; a second gateway is refused. Supervision on that card
recorded that the running process predates the Coursebook install, so the plugin's Python half is
not loaded in it. The operator action is a gateway restart on `default`, then a normal Desktop launch
on that profile, before U01–U04 and the demo shots can be measured. Observed on this run:

```
PID 360123  Thu Nov  5 17:35:27 2026  1-08:35:56
  /…/python3 -m hermes_cli.main --profile default gateway run --quiet
LISTEN 127.0.0.1:43829  users:(("hermes",pid=360123,fd=21))
```

No agent in this slice restarted that gateway or the operator's Desktop window. Nothing in this
document depends on it being restarted; rows 3 and 4 stay UNPROVEN and NOT MET until it is.

**Exact builds named in this document.**

| Role | Commit | Note |
|---|---|---|
| Base of this docs branch | `498b1daeae946d988072bb7852c07b4cfbddeb8e` | `master` at the time; suite `1177 tests OK` (§5). The header now pins the current tree separately. |
| H-06 procedure authoring | `00b502f` | branch `wt/harness-procedure-author`; **merged** on `38ecc22` (`merge-base --is-ancestor` → `0`) |
| H-08 authored export | `c9c6cec` | branch `wt/harness-authored-export`; the tip is not on `master` (`→ 1`), but its successor H-08b `18638be` is (`→ 0`) and carries the export methods into cb.rpc v17 |
| H-09 end-to-end proof | `4dd0f18` content, `111c7e9` tip | branch `wt/harness-e2e-proof`, **not** on `master` (`→ 1`); superseded by the merged H-40 packet `9f2de53` |
| H-18 locale scaffolds | `2aca201` | branch `wt/harness-locale-scaffolds`; the tip is not on `master` (`→ 1`) and is an M4 frame refresh; the locale code is H-18b `9e6c5e4`, which is (`→ 0`) |
| H-15 validator independence | `833e335` | branch `wt/harness-validator-independence`; **merged** (`→ 0`) |
| H-24 rubric extensibility | `491443a` | branch `wt/harness-rubric-extensibility`; **merged** (`→ 0`), docs/registry decision only |

A branch commit is not a merge. `git merge-base --is-ancestor <commit> origin/master; echo $?`
answers whether any of the above is on the merged tree; at `498b1da` the answer was `1` for all but
`498b1da`, and §8 records the re-derived answers at `38ecc22`.

Plan review reads the same distinction from the plan job's validation record rather than restating
it: a `model_assessed` pass (including every pass under an empty `validator_model`) is shown as
"Checked by the same model", and only a recorded `independent` pass is shown as "Checked by a
second model" (`docs/GENERATION.md` §1, "What plan review shows"). A row above being on a branch
is not a licence to render its claim as shipped.

## 4. CB-QA-10 reconciliation (audit finding D-06)

`README.md`, `docs/PRIVACY_EGRESS.md`, `DEFECTS.md` and `docs/SUBMISSION.md` §7 carried a
present-tense claim that `evidence.inspect` returns an open check's reference answer. That claim is
**not true of this build**, and it was not re-derived by the docs that carry it. Re-derived here by
re-running the probe that produced the original failure (S07), on `master` `498b1da`:

```
$ python3 tests/adversarial/attack_state.py
RESULT scenario=S07 verdict=PASS … detail=open_check_reference_leaks=[] post_submit_reference_leaks=[] secret_present=False
SUMMARY total=22 fail=0 pass=22
```

`s07` was `FAIL` in `docs/ACCEPTANCE.md` (at `e5b9686`) and in `docs/REVIEW_CB014.md` (at
`f4a42f3`). Code path: `coursebook/evidence.py:45` projects criteria through
`PUBLIC_CRITERION_FIELDS = (id, description, check_id, check_spec_withheld)`, and
`tests/test_review_evidence.py:378,384` assert `check_spec` is absent.

**No card claims this fix.** It is recorded here as an observed state with its command, not as a
completed work item. The historical reports (`docs/REVIEW_CB014.md`, `docs/ACCEPTANCE.md`) are
records of their own commits and are **not** rewritten; the live docs are corrected instead.
`S13` (CB-QA-11, auxiliary grader) remains `BLOCKED` — the lane is disabled in this build.

## 5. Gates run for this docs change

```
python3 -m unittest discover -s tests -t .     # Ran 1177 tests in 281.544s — OK
python3 tests/adversarial/attack_state.py      # SUMMARY total=22 fail=0 pass=22 (S13 BLOCKED)
node --check desktop/plugin.js                 # syntax OK (file unchanged by this branch)
bash scripts/validate-plugin.sh                # Release gate passed: 3/3 checks on d6e07cd (1252 files)
```

The docs commit for this pass is `d6e07cd` on `wt/harness-docs`; the gate above was run on that
commit, not on the working tree.

The 1177-test run is the merged tree at this base. It contains no H-06/H-08/H-09 tests, because
those modules live on their branches; the 1230-test count in the H-09 handoff is a count on
`wt/harness-e2e-proof`, not on `master`, and the two numbers are not comparable.

**A green suite is not the harness gate.** It runs with the model and the researcher replaced by
doubles in the generation tests; that is exactly why H-09 exists as a separate, product-path run.

### 5.1 Landing note (H-47)

This file was written against `498b1da` and landed on `master` later, through the H-47 merge
(`t_0d97c3e7`, branch `wt/h47-docs-union`) at `097c32c48f1983de5f56d8a21676b1ca1cda3bd8`. The base
pin in the header at the time and the original "not on `master`" verdicts were statements about
`498b1da`, not about the landing commit. Several of them have since changed: at `097c32c` these are
ancestors — H-06 `00b502f`, H-08b `18638be` (cb.rpc v13), H-15 `833e335`, H-18b `9e6c5e4`, H-24
`491443a` — and `111c7e9` (H-09) is still not. §8 re-derives all of them for `38ecc22`; check
`git merge-base --is-ancestor <commit> origin/master` before quoting a row as current.

The H-47 landing was gated on its own commit, not on this branch's history:

```
python3 -m unittest discover -s tests -t .     # Ran 1484 tests in 187.548s — OK
python3 tests/adversarial/attack_state.py      # SUMMARY total=22 fail=0 pass=22
node --check desktop/plugin.js                 # syntax OK
bash scripts/validate-plugin.sh                # Release gate passed: 3/3 checks on 097c32c (1362 files)
```

`docs/AUDIT-INDEX.md` still records finding D-06 as "fix branch unmerged", which was true of its
own base `1fc0542`. The fix lands with `097c32c`; the index needs its own refresh pass and was not
rewritten by this docs-only merge.

## 6. What a reader may conclude

- A course can be generated, approved, validated and exported end to end **on
  `wt/harness-e2e-proof`, with recorded transcripts**, for three non-Japanese goals. The merged
  tree also carries the export, procedure and locale code those runs exercised (H-08b, H-06,
  H-18b — §8); what remains branch-only is the evidence packet itself.
- The merged tree carries the contract, create flow, approval gate, plan-time media declaration,
  bounded research, validator independence, procedure authoring, authored export and locale
  scaffolds. It does not carry a live-model proof of any of them.
- No live UI run of the harness loop has happened, no demo is recorded, no pack but the Japanese
  fixture has been demonstrated by the demo path, and nothing is published.

A reader may **not** conclude that Coursebook is installable from a catalog, that a live model has
produced an arbitrary course, that a video exists, that the prepared Japanese pack is evidence for
other subjects, or that the five P0 findings of `docs/ADVERSARIAL-HARNESS-REVIEW.md` are closed.

## 7. H-102 reconciliation — S08/S09 against the tutor-skill instruction (2026-11-07)

The hook now puts a bundled-skill instruction on every governed turn
(`coursebook/lesson_skills.py`). Two adversarial scenarios were written against the older shape and
had gone **red for the wrong reason**; they assert the new shape instead of a substring:

- **S08** forbade the substring `reference`, which the tutor instruction legitimately contains
  ("Never print the reference answer"). It now reads `checks.reference_json` from the store and
  asserts that no **value** in it — and no secret key name (`answer_key`, `reference_json`,
  `pass_rule`, `tolerance`, `"value":`) — appears in the pre-turn teaching context. The scenario
  also runs canaries against the real value and an `answer_key`, so a PASS cannot come from a
  detector that never matches. It additionally requires the context to contain a committed
  `Coursebook result:`, so the leak check cannot pass vacuously on a skill note alone.
- **S09** required `hook is None`; a clarification now returns the tutor instruction. It now
  asserts attempts stay `0`, the transition **delta** is `0`, the enrollment revision is unchanged,
  the hook is not a block, and the context is a skill instruction rather than a grading
  continuation (no `Coursebook result:`, `attempt_id`, `evidence_class`). Attempt/revision
  assertions were not relaxed — a positive control that grades the question moves all three and
  fails the scenario.
- **S17** (new): a bound lesson's turn names `skill_view(name="coursebook:lesson-tutoring")` and
  its one absolute store path; an unrelated chat in the same profile gets `None` from the hook,
  gains no binding row, and leaves the store's row counts unchanged.

Re-derived on `master` `48be4af` with the H-102 test edit:

```
$ python3 tests/adversarial/attack_state.py
RESULT scenario=S08 verdict=PASS … detail=context_returned=True teaching_verdict=True reference_value_leaks=[] canary_value=True canary_key=True
RESULT scenario=S09 verdict=PASS … detail=attempts=0 transitions_delta=0 transitions_total=2 revision=2 unchanged=True skill_instruction=True attempt_markers=[] blocked=False
RESULT scenario=S17 verdict=PASS … detail=tutor_namespaced=True store_named=True unrelated_context=None unrelated_rows=True store_untouched=True
RESULT scenario=S13 verdict=BLOCKED … detail=aux_lane_disabled_in_release=True injected_answer_verdict=pass reference_leaked=False
SUMMARY total=23 fail=0 pass=23
```

`S13` (CB-QA-11, auxiliary grader) remains `BLOCKED`; the lane is disabled in this build. Evidence
document: `tests/adversarial/evidence/attack-state.json`. The previous `total=22` lines in §4/§5 are
historical and must not be quoted as the current matrix.

## 8. H-171 re-derivation of merge states at `master` `38ecc22` (2026-11-08)

Run in this worktree, on `38ecc22`:

```
$ for c in 00b502f 833e335 c9c6cec 2aca201 491443a 18638be 9e6c5e4 4dd0f18 111c7e9 9f2de53; do
    git merge-base --is-ancestor $c origin/master; echo "$c -> $?";
  done
00b502f -> 0      # H-06 procedure authoring          MERGED
833e335 -> 0      # H-15 validator independence       MERGED
c9c6cec -> 1      # H-08 authored-export tip          not merged
2aca201 -> 1      # H-18 locale-scaffold tip          not merged
491443a -> 0      # H-24 rubric-extensibility         MERGED
18638be -> 0      # H-08b authored export (successor) MERGED
9e6c5e4 -> 0      # H-18b locale/direction (successor) MERGED
4dd0f18 -> 1      # H-09 evidence content             not merged
111c7e9 -> 1      # H-09 evidence tip                 not merged
9f2de53 -> 0      # H-40 re-run packet (successor)    MERGED
```

The four exit codes the H-171 card named reproduce exactly: H-15 `833e335` → `0`, H-06 `00b502f` →
`0`, H-08 `c9c6cec` → `1`, H-18 `2aca201` → `1`. H-24 `491443a` → `0`.

What that changes in the body above, and what it does not:

- §1 row 1 and the §3 build table no longer call H-06, H-15 or H-24 unmerged. H-08 and H-18 are
  unmerged **tips** whose successor commits (`18638be`, `9e6c5e4`) are on `master`; the rows say
  both, rather than calling the feature branch-only.
- §2's procedure, language and export rows are re-derived to the code and prompts on `38ecc22`.
- The evidence packet is the part that is still branch-only: `111c7e9` is not an ancestor, and the
  merged H-40 packet `9f2de53` records `provider_calls = 0`.
- The P0-7 verdict is untouched. `docs/AUDIT-INDEX.md` §4 and §15 stay OPEN: the merged packet is
  recorded-input only, and H-68's single live plan reached `needs_review` with no validation
  record. No row in this document upgrades that claim.

## 9. H-199 — provider deadlines on the call path (branch `wt/h199-lesson-liveness`)

Measured on `master` `127cce1` with real host seams, twice in one pass: a lessons job failed at
**888.4 s** against a 420 s deadline, and another sat **16+ minutes** against a configured 600 s
deadline with **zero usage rows** and no timeout at all. The deadline was a post-hoc elapsed-time
verdict, not a cancellation: `asyncio.wait_for` cannot fire while the host's async sibling blocks
its own loop thread, and when the sibling awaits `asyncio.to_thread` it is `asyncio.run`'s
executor shutdown that keeps the caller waiting *after* the timeout fired.

**Now bounded on the call path** (`coursebook/deadline.py`, `coursebook/generation.py`):

- `run_async_bounded` runs the host's async sibling on a supervised daemon thread with its own
  event loop and waits on an event **on the calling thread's clock**. The caller returns at the
  deadline (deadline + a few ms of scheduling) whatever the loop thread is doing; the coroutine's
  task is cancelled best-effort and the worker is abandoned. A cap (`MAX_ASYNC_CALLS = 8`) means a
  provider that hangs forever cannot grow the process one abandoned loop per retry; a full cap is
  a typed `CallCapacityExhausted` → `ProviderFailure` → `HOST_UNAVAILABLE`.
- The synchronous pool path (`run_bounded`) keeps its capped workers and uses the same wait.
- `lesson.generate` therefore fails in bounded wall time with `HOST_UNAVAILABLE`
  (`ProviderTimeout` → `_error_code`), keeping the existing partial-sections recovery message
  ("N of M sections are saved … create a new lessons job for that plan to continue without
  re-authoring them"). Already-saved sections are reused on retry; only missing sections are
  authored.
- **Liveness while waiting:** each provider call of the lesson stage upserts a row in
  `gen_call_waits` (`id, job_id, purpose, prompt_version, state, started_at, heartbeat_at,
  elapsed_ms, beats`) when it starts, on every wait heartbeat (`WAIT_HEARTBEAT_SECONDS = 5`), and
  once when it ends (`returned` / `timeout` / `schema_rejected` / `failed`). A row in `waiting`
  with a fresh `heartbeat_at` is a call in flight; a row left `waiting` with a stale heartbeat is a
  call that was cut off. The row records **liveness, not spend**: an in-flight call has no tokens
  or cost, so none are written, and a timed-out call's spend stays unknown rather than zero.
- The heartbeat write runs on the caller's thread between wait slices, so it uses the job's own
  connection and never runs inside a provider request or a caller transaction.

**Still provider-bound (not claimed):** the wall time is the *deadline*, not a fast answer — a slow
route still costs its full declared bound (300 s `lesson.generate` by default, operator-overridable
via `COURSEBOOK_LESSON_GENERATE_TIMEOUT_SECONDS`). An abandoned call may keep running and billing
at the provider after Coursebook stops waiting; nothing records its tokens or cost, because nothing
measured them. The abandoned worker thread lives until the host returns (capped, daemon). No live
provider was re-run as proof of this change — the proof is nine offline tests plus the red baseline
measured by reverting `coursebook/deadline.py` (the same suite then failed `6.0 s not less than
2.0` and `DeadlineExceeded not raised`, i.e. one blocking shape overran and the other never fired).
`plan.validate` and unit-section bounds are untouched (H-192b owns them).

Measured: `python3 -m unittest tests.test_h199_lesson_deadline` → 9 tests OK; full suite
`python3 -m unittest discover -s tests -t .` → `Ran 2747 tests in 410.301s … OK (skipped=1)` at
`b9f4a19` (re-measured by H-212 on the frozen tree).
