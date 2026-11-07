# HARNESS-E2E — an arbitrary-topic course on the shipped blueprint-v2 path

This document records what was actually executed for **H-40** (base `c588e4a`) and how to
reproduce it. It is evidence, not a product claim: it does not assert mastery, efficacy or a live
provider run.

The executable packet lives in `audit/adversarial/harness-e2e/` (`STATUS.md` carries the verdicts
and the H-30b finding re-checks; `evidence/` carries the raw records).

## The claim it can support

A free-form, non-Japanese goal entered through the product surface reaches the current generation
pipeline and produces a course — a unit/objective blueprint, independent validation, a digest
approval, per-unit owner sections, validated lessons, a served lesson page and real graded
attempts — without the prepared Japanese pack and without Japanese content:

* `single` (`one_off`, bicycle repair): exactly one unit, one objective, one `verification` check,
  no quiz, approval only after validation, tick-list graded `pass` / `self_reported`.
* `short` (committed, music theory): 2 units, 4 objectives, `exact`-lane text quizzes, correct →
  `pass`, wrong → `not_yet`, every unit user-enqueued.
* `full` (committed, through-hole soldering): 6 units, 12 objectives with backward prerequisite
  edges, graded checks, and a full-scope plan accepted at the declared 12-unit / 40-objective
  bound while 41 objectives is rejected.

## The claim it cannot support

- It does not show a live model produced these responses. The model half is a recorded transcript
  (two distinct recorded identities, so H-36 independence is exercised, not asserted).
- It does not show research over the live web. The fetched page is a recording; the budget and
  ledger code around it are real.
- It does not re-establish H-09's course-export row. Export moved to the authored-export surface
  (H-08b) and is covered by its own tests and packet; this run stops at grading.
- It does not cover a language goal's audio/pronunciation path.
- It does not show a 40-objective course authored end to end; only plan acceptance at the bound.
- It does not cover the Desktop renderer, accessibility or responsive layout.

## Run it

From the repository root, with the branch checked out:

```bash
# 1. (optional) regenerate the recorded transcripts from their authored content tables
python3 audit/adversarial/harness-e2e/build_transcripts.py

# 2. drive all three scenarios through the product path (also runs the ceiling and
#    partial-unit-batch probes)
PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py

# 3. the same runner as a unit test, including a guard that the committed packet is current
PYTHONPATH=. python3 -m unittest tests.test_harness_e2e -v
```

Expected output of step 2:

```text
bicycle_single: PASS  scope=single units=1 objectives=1 checks=1 lessons=1 validation=independently_validated
music_short: PASS  scope=short units=2 objectives=4 checks=4 lessons=4 validation=independently_validated
soldering_full: PASS  scope=full units=6 objectives=12 checks=12 lessons=12 validation=independently_validated
partial_unit_batch (H-30b D1): unit state=needs_review persisted_sections=1 lesson_refusal=GenerationRejected page_state=not_started check_id=None
overall: PASS  (3/3 scenarios)
```

Each run creates a throwaway `HERMES_HOME`, runs the real migrations there, and deletes it
afterwards. It never touches the operator's profile.

## What each scenario does, in order

1. `course.create` with the exact capability inputs: goal, recipe, locale, level,
   `subject_domain`, `scope`, and the four dials.
2. `enrollment.create`.
3. `jobs.create(kind=plan)` with the closed plan brief, then `generation.run_plan_job`:
   research through the seam, blueprint rules, independent validation, cost preflight and the
   stored plan + units.
4. Two refused approvals (wrong revision, stale digest), then `parent.blueprint.read` for the
   kernel digest and `plan.approve` with it.
5. Per unit: `jobs.create` + `generation.run_unit_sections_job` (the stage must not create the
   next unit's job), then `jobs.create` + `generation.run_lesson_job`.
6. `course.outline`, then `lesson.page` for the first objective — the served document a learner
   reads, checked for the absence of any answer key.
7. `check.open` + `attempt.submit`: one correct answer, and for committed courses one wrong answer,
   through the real grading lanes.

The `full` run additionally executes the plan-ceiling probe (12 units/40 objectives accepted,
12/41 rejected) and the packet runs H-30b's D1 probe (a unit batch missing one owner section).

## Where the evidence is

| file | what it holds |
|---|---|
| `evidence/bicycle_single.json` | single-shape plan, units, lessons, check lanes, grading, assertions |
| `evidence/music_short.json` | short-shape run with both grading verdicts |
| `evidence/soldering_full.json` | full-shape run plus `ceiling_probe` |
| `evidence/partial_unit_batch.json` | H-30b D1: partial unit batch, lesson refusal, empty page |
| `evidence/summary.json` | per-scenario verdicts |
| `evidence/run-output.txt` | the runner's own output for this run |
| `evidence/full-suite.txt` | `python3 -m unittest discover -s tests -t .` on this branch |
| `evidence/focused-tests.txt` | `tests.test_harness_e2e` on this branch |

The JSON contains run-specific ids (`plan_id`, `job_id`, attempt nonces), so re-running the same
commit changes the ids while the observed verdicts must stay the same; the unit test in step 3
enforces the verdicts and assertions, not the ids.

## Labels on this run

- model: `RECORDED TRANSCRIPT (recorded-transcript-h40)`, replayed through the real pipeline;
- validator: `RECORDED TRANSCRIPT (recorded-validator-h40)`, a distinct recorded identity so H-36's
  independence comparison is real;
- research: `RECORDED PAGE` through the real search seam;
- provider calls: 0; provider spend: $0.00; network: none; credentials: none.
