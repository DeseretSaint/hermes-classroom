# HARNESS-STATUS — what is build-complete, what is proven, what is fixture-only

Owner: quill (H-11, board card `t_6f41e0b0`). Branch `wt/harness-docs`.
Base: `master` at `498b1daeae946d988072bb7852c07b4cfbddeb8e` (2026-11-07 01:54 -0700).
`desktop/plugin.js` on that tree: sha256 `5beed34797ef18fa328c748e6d82fcbd0fef84997e9cc640fab46363b2879b25`
(last changed by H-02, `5b7423374a5b8d10a2fe94ce520a2613b5c8f02e`).

This document exists because the harness slice produced a great deal of evidence, and almost all of
it lives on **unmerged branches**. Prose that says "the harness works" without saying which commit
it works on, and whether a model or a recording produced the output, is the failure this pass
repairs. Nothing here is new capability; every row points at a file or a command.

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
| 1 | **Harness code complete** | **PARTIAL** — pipeline MERGED; P0-5, P0-6 and P0-7 only on branches | On `master`: cb.rpc v10 with `level`/`subject_domain`/`scope` on `course.create` (H-01), learner create → plan job → approve → lessons (H-02, `5b74233`), runtime threading (H-13), bounded research depth (H-04), plan-time `media_need` (H-05), parent brief fidelity (H-07), fail-closed plan approval with a durable validation binding (H-12), plan-sized cost ceilings (H-17). Not on `master`: procedure authoring (H-06 `00b502f`), general authored export (H-08 `c9c6cec`), locale-aware scaffolds (H-18 `2aca201`), validator independence (H-15 `833e335`), rubric extensibility (H-24 `491443a`). | `contracts/rpc.v10.json:532-556` (the three new inputs); `coursebook/domain.py:678`; `coursebook/research.py:67-97`; `coursebook/generation.py:147`; branch commits as named. Merge check: `git merge-base --is-ancestor <branch> master; echo $?` | Does not mean the review's P0 list is closed. P0-5 (export) and P0-6 (procedure) are fixed only on branches, P0-7 (arbitrary-topic generation) is proved only on a branch, and P0-2's scope cell contradicts its own design doc (§2). |
| 2 | **Authored course generated end to end** | **BRANCH + FIXTURE** — 3/3 scenarios PASS, recorded transcripts | Three non-Japanese goals (`single`/`one_off` bicycle repair, `short`/`committed` music analysis, `full`/`committed` soldering) each ran `course.create` → plan job → kernel-digest approval → lessons job → `lesson.page` → `course.export.read` → `course.export` against a throwaway `HERMES_HOME` on branch `wt/harness-e2e-proof`. The model and the research pages are **recorded transcripts**: 0 provider calls, $0 spend. | `docs/HARNESS-E2E.md` and `audit/adversarial/harness-e2e/STATUS.md` at `111c7e9` (content commit `4dd0f18`); `audit/adversarial/harness-e2e/evidence/{bicycle_single,music_short,soldering_full}.json`; `tests/test_harness_e2e.py` (9 tests). Reach them with `git show 111c7e9:docs/HARNESS-E2E.md`. | Does not mean a live model produced those lessons, that the web was searched live, that a check attempt was submitted on a generated objective, or that the branch is merged. The `single` scenario has 4 objectives where `docs/COURSE-BLUEPRINT.md` says 1 (§2). |
| 3 | **Live UI proof** (the harness loop driven in a real Desktop window) | **UNPROVEN** | The UI half of H-02 exists on `master` but is covered by jsdom/unit tests (`tests/test_desktop_create_flow.py`, `tests/test_learner_plan_flow.py`), not by a mounted Desktop window reaching a real backend on this tree. The M4 frames are a headless render against a stub transport. | `tests/test_desktop_create_flow.py` at `master`; the M4 frames and their stated limits in `docs/M4-VISUAL-MEDIA-AUDIT.md` and `docs/DEMO.md` §"Product-line measurement". | Does not mean "attempted and failed" — it means nobody has mounted the new create flow in a live window and driven it. Recording is still gated (§3). |
| 4 | **Prepared-pack demo** | **FIXTURE**, gate NOT MET | `bundled/packs/japanese-affection-context-l0` imported by `scripts/seed-demo-course.py`. It proves a governed loop over **one** prepared pack. No video exists and the demo gate is NOT MET. | `docs/DEMO.md` (gate status, per-shot verdicts, `audit/demo-gate-5b0f124/`); `docs/REVIEW_CB017-demo-gate.md`. | Not proof of arbitrary-topic generation. This pack is a fixture in every claim in this repository; H-09 is the only card that speaks to arbitrary goals, and only on a branch, only for its three goals. |
| 5 | **Product 1.0** | **UNTAGGED / UNPROVEN** | No release tag, no catalog pull request, no publication, no license. `docs/SUBMISSION.md` §0 remains closed. | `docs/SUBMISSION.md` §0 and §1 gate table; `README.md` §Status. | Nothing above moves this row. Evidence on branches is not a release candidate, and a green suite is not a gate (§5). |

## 2. Claim-by-claim corrections (procedure / media / language / export / scope)

Each row is the claim a reader should take away, held to H-06/H-08/H-09 evidence. Where a doc
disagreed with the code, the disagreement is recorded rather than resolved by silence.

| Claim | Correct statement on `master` `498b1da` | Correct statement including branches | Evidence |
|---|---|---|---|
| **Procedure lens authoring** | The renderer, contract and validator are real; `master`'s `lesson-prompt` does **not** emit a `procedure` header. Before this pass the README said "no authoring path" — that is true of `master`, not of the slice. | H-06 (`00b502f`) adds the authoring path: `LESSON_SCHEMA` accepts the typed `procedure` object, `lesson-prompt.v7` requests it for a technical procedure, `_build_learner_page` projects it as segment references, and `tests/test_procedure_authoring.py` drives the real lesson job with a **fake model**. No live course has been authored through it. | `docs/M4-PROCEDURE-LAYOUT.md` at `00b502f`; `tests/test_procedure_authoring.py` |
| **Media** | Plan-time media is real on `master`: every plan section declares a typed `media_need` and the capability policy adopts it (H-05). Host image/TTS generation is real (M0) but no live lesson-pane generation has run on this tree. | H-09 asserts `every_section_declares_media_need` for all three scenarios and a technical procedure with schematic rows — over recorded transcripts. | `docs/CAPABILITY-POLICY.md`, `docs/GENERATION.md`; `audit/adversarial/harness-e2e/evidence/*.json` at `111c7e9` |
| **Language** | The L0 scaffold fields are still Japanese-named and required on **every** lesson: `check.scaffolds.romaji/furigana/english_meaning`. All 15 H-09 lessons had to set them `false`. This is review finding P1-4, still open on `master`. | H-18 (`2aca201`) is the locale-scaffold branch and is **unmerged**. Do not describe the language path as general until it merges. A language goal's audio/pronunciation path is **not covered** by H-09 at all — none of its three goals is a language goal. | `coursebook/generation.py` `LESSON_SCHEMA`; `docs/HARNESS-E2E.md` §Findings F1; `audit/adversarial/harness-e2e/STATUS.md` §"Not exercised" |
| **Export** | On `master`, `pack.export` still refuses a course with no `pack_id` (`course_not_pack_backed`); the only authored export is Parent Studio's `parent.export`. A learner-created course cannot package itself on this tree. | H-08 (`c9c6cec`) adds `course.export.read` / `course.export` (cb.rpc **v11**, not on `master`) with a four-step gate: not pack-backed, plan approved, every page `validated`, stored final-approval hash unchanged. | `docs/PACK-AUTHORING.md` §5 at `c9c6cec`; `tests/test_course_export.py`; H-09 asserts `export_ready` and `export_produced_an_archive` per scenario |
| **Plan scope** | **Contradiction, unresolved.** `SCOPE_EXPECTATIONS["single"]` is `objectives: (4, 5)` in `coursebook/generation.py:147-152`. `docs/COURSE-BLUEPRINT.md:42` says `single` = exactly 1 objective / 1 section. H-09's `bicycle_single` produced 4 objectives and asserted the *code's* cell. | The blueprint implementer must reconcile the two; this docs pass does not choose. Until then, any "one-off course is one session" claim is unproven at the contract level. | `coursebook/generation.py:147`; `docs/COURSE-BLUEPRINT.md:42`; H-09 F2 in `docs/HARNESS-E2E.md` |
| **Research depth** | Real on `master`: `survey`/`working`/`deep` are the only accepted values, aliases map `overview`→`survey` and `thorough`→`deep`, and the budget scales with scope (a `full` course at `working` gets at least 9 queries / 14 pages). No live web was used by H-09 — its pages are a recording. | — | `coursebook/research.py:67-97`; `docs/GENERATION.md` |
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
| Base of this docs branch | `498b1daeae946d988072bb7852c07b4cfbddeb8e` | `master`; suite `1177 tests OK` (§5) |
| H-06 procedure authoring | `00b502f` | branch `wt/harness-procedure-author`, unmerged |
| H-08 authored export | `c9c6cec` | branch `wt/harness-authored-export`, unmerged; brings cb.rpc v11 |
| H-09 end-to-end proof | `4dd0f18` content, `111c7e9` tip | branch `wt/harness-e2e-proof`, unmerged |
| H-18 locale scaffolds | `2aca201` | branch `wt/harness-locale-scaffolds`, unmerged |
| H-15 validator independence | `833e335` | branch `wt/harness-validator-independence`, unmerged |
| H-24 rubric extensibility | `491443a` | branch `wt/harness-rubric-extensibility`, unmerged |

A branch commit is not a merge. `git merge-base --is-ancestor <commit> master; echo $?` answers
whether any of the above is on the merged tree; at this base the answer is `1` for all but `498b1da`.

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
commit, not on the working tree. Each later docs-only commit on this branch was re-gated the same
way, with the same 3/3 and the same file count.

The 1177-test run is the merged tree at this base. It contains no H-06/H-08/H-09 tests, because
those modules live on their branches; the 1230-test count in the H-09 handoff is a count on
`wt/harness-e2e-proof`, not on `master`, and the two numbers are not comparable.

**A green suite is not the harness gate.** It runs with the model and the researcher replaced by
doubles in the generation tests; that is exactly why H-09 exists as a separate, product-path run.

## 6. What a reader may conclude

- A course can be generated, approved, validated and exported end to end **on
  `wt/harness-e2e-proof`, with recorded transcripts**, for three non-Japanese goals.
- The merged tree carries the contract, create flow, approval gate, plan-time media declaration and
  bounded research, and none of the export/procedure/locale work.
- No live UI run of the harness loop has happened, no demo is recorded, no pack but the Japanese
  fixture has been demonstrated by the demo path, and nothing is published.

A reader may **not** conclude that Coursebook is installable from a catalog, that a live model has
produced an arbitrary course, that a video exists, that the prepared Japanese pack is evidence for
other subjects, or that the five P0 findings of `docs/ADVERSARIAL-HARNESS-REVIEW.md` are closed.
