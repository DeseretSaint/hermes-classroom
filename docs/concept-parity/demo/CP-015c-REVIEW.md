# CP-015c-ja — Japanese Cafe Basics: review packet

Status at this commit: **the plan is approved; the course is not authorable to export.** One
authorized further lessons pass (CP-015g/h/j merged) was run. All three owner pages were
re-authored once and were parked `needs_review` again on real rules, so the card's stop rule fired.
No pack, no Workshop entry, no install proof and no lesson visual exist, because
`course.export.read` refuses with `lessons_not_validated` and `lesson.page` serves an empty document
for a parked page.

This is a red result. Nothing here may be described as high quality, and no surface was captured.

## 1. Commit and branch

| | |
|---|---|
| Branch | `wt/cp-015c-ja` |
| Run commit | `33f44287` (driver, evidence, packet, tests, regenerated record) |
| Head at review | `33f44287` plus the packet-only revision that first carries this line |
| Lineage | CP-015b `ddf32b52` + master `c054f977` + CP-015e `3dd1665a` + CP-015f `8ba13d52`/`39450d2e` + CP-015g `650bc605` + CP-015h `24897ed3` + **CP-015j merged** (`f70591dd` → merge commit below) |
| Pushed | no |
| Published | no |

`coursebook/*.py` changes only by merging cinder's fixes (CP-015g, CP-015h, CP-015j); nothing in the
kernel was authored here. CP-015j was merged at `b8d4ad21`.

## 2. The plan — approved

| | |
|---|---|
| Plan | `pln_5dde08c973f94cc0a444caa77a09d53c` |
| Validation | `b0c0c6d0c01e97e1`, verdict **pass**, 11/11 criteria, `validation-prompt.v7` |
| Independence | `independent` — validator `z-ai/glm-5.3-flash` (nous) judging `deepseek/deepseek-v4.1-flash-1017` |
| Course | `crs_44880979e34f45a9926512c0bf24c098` — `ja-JP`, `L0`, `language`, presentation `game` |
| Shape | 2 units, 5 objectives, 10 stored sources |

## 3. Unit 1 sections — approved

`unit-sections-prompt.v2` / `validation-prompt.v8`, verdict **pass**, `independent`. Four sections
stored (three owner + one review), validation `6a7090de7e223e3d`.

## 4. The one further lessons pass (2026-11-11 11:33–11:42 UTC)

Driver: `scripts/cp015c-resume.py` (new, committed). It uses the product's own routes only:
`lesson.regenerate` for each parked owner section, then one unit `jobs.create` lessons job for the
review section. No prompt was edited, no page was approved by hand, nothing was written to the
database.

| Section | Job | Result | Verbatim stored reason |
|---|---|---|---|
| 1 Party Size: 二人です | `job_bd19c3ea4a3d44e7a305da763dd892d9` | `needs_review` v2 | `learner-facing narrative contains the check reference answer or a keyed answer` |
| 2 Table Request: テーブル席でお願いします | `job_7825c0e5ce5a428e808bcab750a62fe0` | `needs_review` v2 | `lesson.learner_explanation: The pre-check learner explanation states the correct choice ('choose the line that names テーブル席 and ends with お願いします'), leaking the quiz answer to the learner before the graded check.` |
| 3 Seating-Order Question: 先に席を取ったほうがいいですか | `job_23f201329b5e4b30bed72fa18edc944a` | `needs_review` v2 | `criteria could not be verified: source_support` |
| 4 Review: Matching Entrance Phrases to Their Jobs | `job_436041eae3b74afb97c2ac7dce337c53` | `needs_review` v1 | `review section 4 presents a closed owner check: objective 1 is served by 75630acdb704f7c2 (closed) from owner lesson 436bc19c28010e01 (needs_review); objective 2 is served by f0c14474b5534478 (closed) …; objective 3 is served by bd79dc5c98364cb0 (closed) … The review page is authored and parked; approve or regenerate the owner lessons, then regenerate this section so the review binds to an open check.` **and** `lesson.check.reference_answer: Learner-facing check ships the reference answer and accepted answers with full justifications, letting the learner copy the graded response verbatim.` |

**CP-015j is verified in the product.** The review job **completed** (`4 lessons authored`) instead
of ending `VALIDATION_FAILED`, and the parked review page names each closed owner check, its owner
lesson id and that lesson's state. The earlier blocking defect is gone.

**Stop rule.** Sections 1 and 2 each failed the same criterion class a second time after the pass
(the answer-leak family: deterministic rule for section 1, validator for section 2). Section 3 was
`source_support` in both versions. The card says stop after two rejections on the same class and
report the defect; the pass stopped there and no third authoring attempt was made on this branch.

Evidence: `docs/concept-parity/demo/cp015c-lessons-pass.json` (the driver's own record of the pass),
pinned by `tests/test_cp015c_ja_pass.py`.

## 5. Why there is no export, pack, Workshop entry or visual

`course.export.read` (wire 26, same backend):

```json
{"ready": false, "blocked_reason": "lessons_not_validated",
 "sections": {"total": 4, "validated": 0}}
```

- `lesson.page` for objective 1 answers `document.state = "empty"` with
  *"A generated lesson page exists for this section but is awaiting review, so it is not served
  until it is approved. Its check stays closed until then."* There is therefore **no rendered lesson
  page**.
- `world.read` answers `world: null`. The world stage was **not started**: the card's item 2 pairs
  an approved world with a rendered lesson page, `scripts/cp015-demo-courses.py` builds the world only
  after a servable page, and spending image calls on a course that cannot export would buy evidence
  the card does not accept. This is not a provider-unavailable claim: the isolated home's managed
  tool gateway token was present when checked (`probe_gateway.py`: `token present: True`).
- With no export there is no pack for `packs.validate_manifest`, no content hash for
  `catalog/workshop.v1.json`, nothing to install, and no Home/Discover card or lesson capture.
  `scripts/cp015c-workshop-install-proof.py` remains unrun for want of a pack.
- No licence was invented or stamped, because `course.export` never ran. The probe did not create a
  grant.

## 6. Acceptance, item by item

| Acceptance item | Result |
|---|---|
| One validator-approved plan with stored sources | **pass** — `b0c0c6d0c01e97e1`, 11/11, 10 stored sources |
| One approved world and one rendered lesson page | **absent** — page parked, `lesson.page` empty; world not started |
| Pack manifest valid; Workshop entry with real hash and licence | **absent** — export refuses (`lessons_not_validated`, 0 of 4 validated) |
| Fresh library empty of the course, then installed | **not exercised** — no pack exists |
| No fixture words in user-visible surfaces | **not applicable** — no user-visible surface was produced; section titles scanned clean |
| Run record regenerates byte-identically | **pass** — `scripts/cp015_record.py`, two runs, sha256 stable; `tests.test_cp015_run_record` 10 OK |
| Visual review; real plate, not a flat panel | **absent** — nothing rendered |
| Tests green | **pass for this branch's scope** — 10 run-record + 59 CP-015h/j/policy/blueprint + 6 new pass tests |

## 7. Cost

| Pass | Provider calls | Output tokens |
|---|---|---|
| r1–r3 (plan, unit sections, first lessons) | 21 | ≈95,286 |
| r4 (this pass) | 13 | 77,065 |
| **total on this backend home** | **34** | **≈172,351** |

No image spend. `usage_events.cost_usd` is `null` on this backend, so no dollar figure is claimed.

## 8. Defects and follow-ups

Filed to cinder from this card as **`t_a0bcacdd`**: the lesson author prompt never states the
answer-leak surfaces (`learner_explanation`, `worked_example`, recap) — analogous to CP-015h — and
the learner-facing check for the review section ships its reference answer and accepted answers with
justifications (`lesson.check.reference_answer`). Both are recorded there with the verbatim
rejections and the live reproduction ids.

Open, not diagnosed here: `source_support` for sections 2 (v1) and 3 (v1 and v2). The plan's
stored ledger marks most sources `unassessed` with `claim_count 0`, so the lesson validator cannot
verify the pages' claims. That is a research/ledger quality question, not a pack-format defect.

## 9. Tests

```text
tests.test_cp015_run_record                 10 OK
tests.test_cp015j_closed_owner_check         8 OK
tests.test_cp015h_media_construct_shape      8 OK
tests.test_capability_policy / test_blueprint_units   43 OK  (59 total in that batch)
tests.test_cp015c_ja_pass                    6 OK
```

## 10. Reproduction

```bash
export HERMES_HOME=$HOME/.hermes/coursebook-test-cp015c/home
hermes serve --isolated --port 44601 &
CB013_BASE=http://127.0.0.1:44601 CB013_TOKEN=… CP015_HOME=$HERMES_HOME \
  python3 scripts/cp015c-resume.py --record <scratch>/cp015c-resume.json
python3 scripts/cp015_record.py \
  --db $HERMES_HOME/plugin-data/coursebook/data.db   # byte-identical to docs/concept-parity/demo/*.json
```
